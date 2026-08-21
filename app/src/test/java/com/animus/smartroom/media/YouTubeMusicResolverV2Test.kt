package com.animus.smartroom.media

import com.animus.smartroom.media.resolver.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class YouTubeMusicResolverV2Test {

    private lateinit var cache: MusicResolutionCache

    @Before
    fun setUp() {
        cache = MusicResolutionCache(null, maxEntries = 5)
    }

    // 1. Query Construction Tests
    @Test
    fun testQueryConstruction_standard() {
        val query = YouTubeMusicResolver.buildSearchQuery("Zara Zara", "Bombay Jayashri")
        assertEquals("Zara Zara Bombay Jayashri official audio", query)
    }

    @Test
    fun testQueryConstruction_titleOnly() {
        val query = YouTubeMusicResolver.buildSearchQuery("Kesariya", null)
        assertEquals("Kesariya official audio", query)
    }

    @Test
    fun testQueryConstruction_userModifiersPreserved() {
        assertEquals("Zara Zara acoustic", YouTubeMusicResolver.buildSearchQuery("Zara Zara acoustic", null))
        assertEquals("Zara Zara live", YouTubeMusicResolver.buildSearchQuery("Zara Zara live", null))
        assertEquals("Zara Zara remix", YouTubeMusicResolver.buildSearchQuery("Zara Zara remix", null))
        assertEquals("Zara Zara cover", YouTubeMusicResolver.buildSearchQuery("Zara Zara cover", null))
        assertEquals("Zara Zara unplugged", YouTubeMusicResolver.buildSearchQuery("Zara Zara unplugged", null))
    }

    // 2. Candidate Scoring Engine Tests
    @Test
    fun testScoring_topicChannelPreference() {
        val topicCandidate = YouTubeSearchCandidate(
            videoId = "IWjbBSMsQJg",
            title = "Zara Zara",
            channelTitle = "Bombay Jayashri - Topic",
            duration = "PT4M58S",
            licensedContent = true
        )
        val score = MusicCandidateScorer.score("Zara Zara", topicCandidate)
        // Base 50 + Topic 35 + Licensed 15 = 100
        assertEquals(100, score)
    }

    @Test
    fun testScoring_officialLabelPreference() {
        val labelCandidate = YouTubeSearchCandidate(
            videoId = "BddP6PYo2gs",
            title = "Kesariya - Official Audio | Brahmāstra",
            channelTitle = "Sony Music India",
            duration = "PT2M52S",
            licensedContent = true
        )
        val score = MusicCandidateScorer.score("Kesariya", labelCandidate)
        // Base 50 + Label 25 + Licensed 15 + "official audio" 20 = 110
        assertEquals(110, score)
    }

    @Test
    fun testScoring_shortsPenalized() {
        val shortCandidate = YouTubeSearchCandidate(
            videoId = "short123456",
            title = "Zara Zara WhatsApp status #shorts",
            channelTitle = "Status Channel",
            duration = "PT30S",
            licensedContent = false
        )
        val score = MusicCandidateScorer.score("Zara Zara", shortCandidate)
        // Base 50 - status/shorts 50 - shorts duration 50 = -50
        assertTrue(score < 0)
    }

    @Test
    fun testScoring_coverPenalizedWhenNotRequested() {
        val coverCandidate = YouTubeSearchCandidate(
            videoId = "cover123456",
            title = "Zara Zara (Cover Song) by Someone",
            channelTitle = "Singer Girl",
            duration = "PT3M30S"
        )
        val score = MusicCandidateScorer.score("Zara Zara", coverCandidate)
        // Base 50 - cover 30 = 20
        assertEquals(20, score)
    }

    @Test
    fun testScoring_coverBoostedWhenRequested() {
        val coverCandidate = YouTubeSearchCandidate(
            videoId = "cover123456",
            title = "Zara Zara (Cover Song) by Someone",
            channelTitle = "Singer Girl",
            duration = "PT3M30S"
        )
        val score = MusicCandidateScorer.score("Zara Zara cover", coverCandidate)
        // Base 50 + coverBonus 20 = 70 (no cover penalty)
        assertEquals(70, score)
    }

    @Test
    fun testScoring_remixBoostedWhenRequested() {
        val remixCandidate = YouTubeSearchCandidate(
            videoId = "remix123456",
            title = "Zara Zara Club Remix",
            channelTitle = "DJ Mixes",
            duration = "PT4M00S"
        )
        val score = MusicCandidateScorer.score("Zara Zara remix", remixCandidate)
        // Base 50 + remixBonus 30 = 80
        assertEquals(80, score)
    }

    @Test
    fun testScoring_reactionPenalized() {
        val reactionCandidate = YouTubeSearchCandidate(
            videoId = "react123456",
            title = "Foreigners REACTION to Zara Zara song!",
            channelTitle = "Reactions Hub",
            duration = "PT8M20S"
        )
        val score = MusicCandidateScorer.score("Zara Zara", reactionCandidate)
        // Base 50 - reaction 40 = 10
        assertEquals(10, score)
    }

    // 3. Batch Metadata & Candidate Selection
    @Test
    fun testCandidateRanking_selectsBestOverDefaultFirst() = runBlocking {
        val mockApiClient = object : YouTubeDataApiClient {
            override suspend fun searchCandidates(
                apiKey: String,
                query: String,
                maxResults: Int
            ): Result<List<YouTubeSearchCandidate>> {
                return Result.success(
                    listOf(
                        YouTubeSearchCandidate(
                            videoId = "bad12345678",
                            title = "Zara Zara WhatsApp Status #shorts",
                            channelTitle = "Fan Edit",
                            duration = "PT45S"
                        ),
                        YouTubeSearchCandidate(
                            videoId = "best1234567",
                            title = "Zara Zara (Official Audio)",
                            channelTitle = "Sony Music India",
                            duration = "PT4M58S",
                            licensedContent = true
                        )
                    )
                )
            }

            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                throw NotImplementedError()
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy_key" },
            cache = cache,
            apiClient = mockApiClient
        )

        val result = resolver.resolveTrack("Zara Zara", "Bombay Jayashri")
        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("best1234567", resolved.videoId)
        assertEquals("Sony Music India", resolved.channelTitle)
    }

    // 4. Cache & Invalidation Behavior
    @Test
    fun testCacheHit_bypassesApi() = runBlocking {
        cache.put("Tum Hi Ho", "Arijit Singh", "BjL7AuPsmEk", "Arijit Singh - Topic")

        var apiCalled = false
        val mockApiClient = object : YouTubeDataApiClient {
            override suspend fun searchCandidates(apiKey: String, query: String, maxResults: Int): Result<List<YouTubeSearchCandidate>> {
                apiCalled = true
                return Result.failure(IllegalStateException("Should not be called"))
            }

            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                apiCalled = true
                return Result.failure(IllegalStateException("Should not be called"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy_key" },
            cache = cache,
            apiClient = mockApiClient
        )

        val result = resolver.resolveTrack("Tum Hi Ho", "Arijit Singh")
        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("BjL7AuPsmEk", resolved.videoId)
        assertEquals(ResolutionSource.Cache, resolved.source)
        assertFalse(apiCalled)
    }

    @Test
    fun testReResolveOnPlaybackFailure_invalidatesAndFetchesFresh() = runBlocking {
        cache.put("Raataan Lambiyan", "Tanishk Bagchi", "old_dead_id", "Old Channel")

        val mockApiClient = object : YouTubeDataApiClient {
            override suspend fun searchCandidates(apiKey: String, query: String, maxResults: Int): Result<List<YouTubeSearchCandidate>> {
                return Result.success(
                    listOf(
                        YouTubeSearchCandidate(
                            videoId = "new_live_id",
                            title = "Raataan Lambiyan Official Video",
                            channelTitle = "Sony Music India",
                            duration = "PT3M50S",
                            licensedContent = true
                        )
                    )
                )
            }

            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                throw NotImplementedError()
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy_key" },
            cache = cache,
            apiClient = mockApiClient
        )

        val result = resolver.reResolveOnPlaybackFailure("Raataan Lambiyan", "Tanishk Bagchi")
        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("new_live_id", resolved.videoId)
        assertEquals("new_live_id", cache.get("Raataan Lambiyan", "Tanishk Bagchi")?.videoId)
    }

    // 5. Direct Video ID Bypass
    @Test
    fun testExplicitDirectId_bypassesCacheAndApi() = runBlocking {
        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy_key" },
            cache = cache
        )

        val result = resolver.resolveTrack("Any Track", null, explicitDirectId = "IWjbBSMsQJg")
        assertTrue(result is MusicResolutionResult.Resolved)
        val resolved = result as MusicResolutionResult.Resolved
        assertEquals("IWjbBSMsQJg", resolved.videoId)
        assertEquals(ResolutionSource.DirectCommand, resolved.source)
    }
}
