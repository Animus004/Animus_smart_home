package com.animus.smartroom.media.resolver

import android.util.Log
import com.animus.smartroom.brain.validator.YouTubeVideoIdExtractor

sealed interface ResolutionSource {
    data object DirectCommand : ResolutionSource
    data object Cache : ResolutionSource
    data object YouTubeDataApi : ResolutionSource
}

sealed interface MusicResolutionResult {
    data class Resolved(
        val videoId: String,
        val title: String,
        val artist: String?,
        val source: ResolutionSource,
        val channelTitle: String? = null
    ) : MusicResolutionResult

    data class FallbackSearch(
        val title: String,
        val artist: String?,
        val reason: String
    ) : MusicResolutionResult
}

class YouTubeMusicResolver(
    private val apiKeyProvider: () -> String?,
    val cache: MusicResolutionCache,
    private val apiClient: YouTubeDataApiClient = DefaultYouTubeDataApiClient()
) {

    companion object {
        private const val TAG = "YouTubeMusicResolver"

        fun buildSearchQuery(title: String, artist: String?): String {
            val cleanTitle = title.trim()
            val cleanArtist = artist?.trim()
            return when {
                cleanArtist.isNullOrBlank() -> "$cleanTitle official"
                else -> "$cleanTitle $cleanArtist official"
            }
        }
    }

    /**
     * Resolves a natural-language track request to a verified YouTube video ID.
     * Order of resolution:
     * 1. Existing directVideoId (if valid)
     * 2. Persistent Bounded Cache hit
     * 3. YouTube Data API v3 search.list
     * 4. Graceful Fallback (Search and play)
     */
    suspend fun resolveTrack(
        title: String,
        artist: String?,
        explicitDirectId: String? = null
    ): MusicResolutionResult {
        val trimmedTitle = title.trim()
        if (trimmedTitle.isBlank()) {
            return MusicResolutionResult.FallbackSearch(title, artist, "Title is empty.")
        }

        // 1. Check explicit directVideoId
        if (!explicitDirectId.isNullOrBlank()) {
            if (YouTubeVideoIdExtractor.isValidVideoId(explicitDirectId)) {
                Log.i(TAG, "[music-resolver] Using explicit valid direct video ID '$explicitDirectId' for '$trimmedTitle'")
                return MusicResolutionResult.Resolved(
                    videoId = explicitDirectId,
                    title = trimmedTitle,
                    artist = artist,
                    source = ResolutionSource.DirectCommand
                )
            } else {
                Log.w(TAG, "[music-resolver] Explicit video ID '$explicitDirectId' is invalid. Proceeding to cache/API resolution.")
            }
        }

        // 2. Check persistent bounded cache
        val cached = cache.get(trimmedTitle, artist)
        if (cached != null && YouTubeVideoIdExtractor.isValidVideoId(cached.videoId)) {
            Log.i(TAG, "[music-resolver] Cache hit for '$trimmedTitle' by '$artist' -> videoId='${cached.videoId}' (${cached.channelTitle})")
            return MusicResolutionResult.Resolved(
                videoId = cached.videoId,
                title = trimmedTitle,
                artist = artist ?: cached.artist,
                source = ResolutionSource.Cache,
                channelTitle = cached.channelTitle
            )
        }

        // 3. Query YouTube Data API v3
        val apiKey = apiKeyProvider()?.trim()
        if (apiKey.isNullOrBlank()) {
            Log.w(TAG, "[music-resolver] YouTube API key is missing. Using graceful search fallback.")
            return MusicResolutionResult.FallbackSearch(
                title = trimmedTitle,
                artist = artist,
                reason = "YouTube API key not configured."
            )
        }

        val searchQuery = buildSearchQuery(trimmedTitle, artist)
        Log.i(TAG, "[music-resolver] Querying YouTube Data API for query: '$searchQuery'")

        val searchResult = apiClient.searchVideo(apiKey, searchQuery)
        return searchResult.fold(
            onSuccess = { candidate ->
                if (YouTubeVideoIdExtractor.isValidVideoId(candidate.videoId)) {
                    Log.i(TAG, "[music-resolver] YouTube API resolved '$trimmedTitle' -> videoId='${candidate.videoId}', channel='${candidate.channelTitle}'")
                    cache.put(
                        title = trimmedTitle,
                        artist = artist,
                        videoId = candidate.videoId,
                        channelTitle = candidate.channelTitle
                    )
                    MusicResolutionResult.Resolved(
                        videoId = candidate.videoId,
                        title = trimmedTitle,
                        artist = artist,
                        source = ResolutionSource.YouTubeDataApi,
                        channelTitle = candidate.channelTitle
                    )
                } else {
                    Log.w(TAG, "[music-resolver] YouTube API returned invalid video ID: '${candidate.videoId}'")
                    MusicResolutionResult.FallbackSearch(
                        title = trimmedTitle,
                        artist = artist,
                        reason = "Invalid video ID returned from API."
                    )
                }
            },
            onFailure = { error ->
                Log.w(TAG, "[music-resolver] YouTube API query failed: ${error.message}. Falling back to search.", error)
                MusicResolutionResult.FallbackSearch(
                    title = trimmedTitle,
                    artist = artist,
                    reason = error.message ?: "YouTube API search failed."
                )
            }
        )
    }

    /**
     * Invalidate cache entry and re-query the YouTube API if a cached video ID is found to be dead/unavailable at playback time.
     */
    suspend fun reResolveOnPlaybackFailure(title: String, artist: String?): MusicResolutionResult {
        Log.i(TAG, "[music-resolver] Invalidating cache and re-resolving for '$title' by '$artist'")
        cache.invalidate(title, artist)
        return resolveTrack(title, artist, explicitDirectId = null)
    }

    fun invalidate(title: String, artist: String?) {
        cache.invalidate(title, artist)
    }
}
