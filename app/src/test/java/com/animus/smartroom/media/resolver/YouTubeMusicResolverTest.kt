package com.animus.smartroom.media.resolver

import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.model.MusicUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.lang.reflect.Field
import java.util.concurrent.atomic.AtomicInteger

class YouTubeMusicResolverTest {

    private lateinit var cache: MusicResolutionCache

    @Before
    fun setUp() {
        cache = MusicResolutionCache(prefs = null, maxEntries = 5)
    }

    // --- Cache Unit Tests ---

    @Test
    fun testCachePutAndGetHitWithNormalization() {
        cache.put("Ramta Jogi", "Alka Yagnik", "QxwmIXIWO7I", "90's Gaane")

        // Exact match
        val exact = cache.get("Ramta Jogi", "Alka Yagnik")
        assertNotNull(exact)
        assertEquals("QxwmIXIWO7I", exact?.videoId)

        // Case-insensitive, extra whitespace, punctuation normalization
        val normalized = cache.get("  ramta jogi! ", "ALKA   YAGNIK ")
        assertNotNull(normalized)
        assertEquals("QxwmIXIWO7I", normalized?.videoId)
        assertEquals("90's Gaane", normalized?.channelTitle)
    }

    @Test
    fun testCacheMiss() {
        val missed = cache.get("Unknown Track", "Unknown Artist")
        assertNull(missed)
    }

    @Test
    fun testCacheInvalidation() {
        cache.put("Zara Zara", "Bombay Jayashri", "IWjbBSMsQJg", "Saregama")
        assertNotNull(cache.get("Zara Zara", "Bombay Jayashri"))

        cache.invalidate("Zara Zara", "Bombay Jayashri")
        assertNull(cache.get("Zara Zara", "Bombay Jayashri"))
    }

    @Test
    fun testCacheRejectsInvalidVideoIdOnPut() {
        cache.put("Invalid Track", "Artist", "too_short", "Channel")
        assertNull(cache.get("Invalid Track", "Artist"))
    }

    @Test
    fun testCacheBoundedCapacityAndLRUEviction() {
        // Cache maxEntries is 5
        cache.put("Song 1", "Artist", "11111111111", "Channel")
        cache.put("Song 2", "Artist", "22222222222", "Channel")
        cache.put("Song 3", "Artist", "33333333333", "Channel")
        cache.put("Song 4", "Artist", "44444444444", "Channel")
        cache.put("Song 5", "Artist", "55555555555", "Channel")

        assertEquals(5, cache.size())

        // Add 6th song -> Song 1 (oldest) should be evicted
        cache.put("Song 6", "Artist", "66666666666", "Channel")
        assertEquals(5, cache.size())
        assertNull(cache.get("Song 1", "Artist"))
        assertNotNull(cache.get("Song 6", "Artist"))
    }

    // --- Resolver Flow Unit Tests ---

    @Test
    fun testResolverUsesValidExplicitDirectIdWithoutCallingApi() = runBlocking {
        val apiCallCount = AtomicInteger(0)
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                apiCallCount.incrementAndGet()
                return Result.success(YouTubeSearchCandidate("99999999999", "Title", "Channel"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val result = resolver.resolveTrack(
            title = "Ramta Jogi",
            artist = "Alka Yagnik",
            explicitDirectId = "QxwmIXIWO7I"
        )

        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("QxwmIXIWO7I", resolved.videoId)
        assertEquals(ResolutionSource.DirectCommand, resolved.source)
        assertEquals(0, apiCallCount.get())
    }

    @Test
    fun testResolverReturnsCacheHitWithoutCallingApi() = runBlocking {
        cache.put("Kal Ho Naa Ho", "Sonu Nigam", "g0eO74UmRBs", "Sony Music India")

        val apiCallCount = AtomicInteger(0)
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                apiCallCount.incrementAndGet()
                return Result.success(YouTubeSearchCandidate("99999999999", "Title", "Channel"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val result = resolver.resolveTrack("Kal Ho Naa Ho", "Sonu Nigam")

        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("g0eO74UmRBs", resolved.videoId)
        assertEquals(ResolutionSource.Cache, resolved.source)
        assertEquals(0, apiCallCount.get())
    }

    @Test
    fun testResolverQueriesApiOnCacheMissAndCachesResult() = runBlocking {
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                return Result.success(
                    YouTubeSearchCandidate(
                        videoId = "1BWdglekty0",
                        title = "Maahi Ve",
                        channelTitle = "Sony Music India"
                    )
                )
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val result = resolver.resolveTrack("Maahi Ve", "Kal Ho Naa Ho")

        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("1BWdglekty0", resolved.videoId)
        assertEquals(ResolutionSource.YouTubeDataApi, resolved.source)

        // Verify stored in cache for next query
        val cached = cache.get("Maahi Ve", "Kal Ho Naa Ho")
        assertNotNull(cached)
        assertEquals("1BWdglekty0", cached?.videoId)
    }

    @Test
    fun testResolverFallsBackGracefullyWhenApiKeyMissing() = runBlocking {
        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { null },
            cache = cache
        )

        val result = resolver.resolveTrack("Pretty Woman", "Kal Ho Naa Ho")

        assertTrue(result is MusicResolutionResult.FallbackSearch)
        val fallback = result as MusicResolutionResult.FallbackSearch
        assertEquals("Pretty Woman", fallback.title)
        assertTrue(fallback.reason.contains("API key not configured"))
    }

    @Test
    fun testResolverFallsBackGracefullyOnApiErrorOrQuotaExhausted() = runBlocking {
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                return Result.failure(RuntimeException("HTTP 429: Quota exceeded"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val result = resolver.resolveTrack("Any Song", "Any Artist")

        assertTrue(result is MusicResolutionResult.FallbackSearch)
        val fallback = result as MusicResolutionResult.FallbackSearch
        assertTrue(fallback.reason.contains("429"))
    }

    @Test
    fun testResolverRejectsInvalidVideoIdFromApi() = runBlocking {
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                return Result.success(YouTubeSearchCandidate("invalid_id", "Bad Song", "Channel"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val result = resolver.resolveTrack("Bad Song", "Artist")

        assertTrue(result is MusicResolutionResult.FallbackSearch)
        assertNull(cache.get("Bad Song", "Artist"))
    }

    @Test
    fun testReResolveOnPlaybackFailureInvalidatesCache() = runBlocking {
        cache.put("Stale Track", "Artist", "11111111111", "Old Channel")

        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                return Result.success(YouTubeSearchCandidate("22222222222", "Fresh Track", "New Channel"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val freshResult = resolver.reResolveOnPlaybackFailure("Stale Track", "Artist")

        assertTrue(freshResult is MusicResolutionResult.Resolved)
        val resolved = freshResult as MusicResolutionResult.Resolved
        assertEquals("22222222222", resolved.videoId)
        assertEquals(ResolutionSource.YouTubeDataApi, resolved.source)
        assertEquals("22222222222", cache.get("Stale Track", "Artist")?.videoId)
    }
}
