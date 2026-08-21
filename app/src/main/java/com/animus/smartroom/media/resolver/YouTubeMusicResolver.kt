package com.animus.smartroom.media.resolver

import android.util.Log
import com.animus.smartroom.brain.validator.YouTubeVideoIdExtractor
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import java.util.Locale

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
        val channelTitle: String? = null,
        val score: Int = 0
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
            val tLower = cleanTitle.lowercase(Locale.ROOT)

            val hasExplicitModifier = tLower.contains("cover") ||
                    tLower.contains("remix") ||
                    tLower.contains("acoustic") ||
                    tLower.contains("unplugged") ||
                    tLower.contains("live") ||
                    tLower.contains("karaoke") ||
                    tLower.contains("instrumental") ||
                    tLower.contains("soundtrack") ||
                    tLower.contains("official")

            val base = when {
                cleanArtist.isNullOrBlank() -> cleanTitle
                else -> "$cleanTitle $cleanArtist"
            }

            return if (hasExplicitModifier) {
                base
            } else {
                "$base official audio"
            }
        }
    }

    /**
     * Resolves a natural-language track request to a verified, scored YouTube Music video ID.
     * Order of resolution:
     * 1. Existing directVideoId (if valid)
     * 2. Persistent Bounded Cache hit
     * 3. YouTube Data API v3 (search.list maxResults=5 + videos.list batch metadata + Candidate Scoring)
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

        DiagnosticBus.log(
            tag = "youtube-resolver",
            stage = DiagnosticStage.RESOLVING,
            message = "title='$trimmedTitle', artist='${artist ?: ""}'"
        )

        // 1. Check explicit directVideoId
        if (!explicitDirectId.isNullOrBlank()) {
            if (YouTubeVideoIdExtractor.isValidVideoId(explicitDirectId)) {
                Log.i(TAG, "[music-resolver] Using explicit valid direct video ID '$explicitDirectId' for '$trimmedTitle'")
                DiagnosticBus.log(
                    tag = "youtube-resolver",
                    stage = DiagnosticStage.SELECTED,
                    message = "explicit videoId='$explicitDirectId'"
                )
                return MusicResolutionResult.Resolved(
                    videoId = explicitDirectId,
                    title = trimmedTitle,
                    artist = artist,
                    source = ResolutionSource.DirectCommand,
                    score = 100
                )
            } else {
                Log.w(TAG, "[music-resolver] Explicit video ID '$explicitDirectId' is invalid. Proceeding to cache/API resolution.")
            }
        }

        // 2. Check persistent bounded cache
        val cached = cache.get(trimmedTitle, artist)
        if (cached != null && YouTubeVideoIdExtractor.isValidVideoId(cached.videoId)) {
            Log.i(TAG, "[music-resolver] Cache hit for '$trimmedTitle' by '$artist' -> videoId='${cached.videoId}' (${cached.channelTitle})")
            DiagnosticBus.log(
                tag = "youtube-resolver",
                stage = DiagnosticStage.SELECTED,
                message = "cache hit videoId='${cached.videoId}'"
            )
            return MusicResolutionResult.Resolved(
                videoId = cached.videoId,
                title = trimmedTitle,
                artist = artist ?: cached.artist,
                source = ResolutionSource.Cache,
                channelTitle = cached.channelTitle,
                score = 100
            )
        }

        // 3. Query YouTube Data API v3 with Batch Metadata & Scoring
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

        val searchResult = apiClient.searchCandidates(apiKey, searchQuery, maxResults = 5)
        return searchResult.fold(
            onSuccess = { candidates ->
                if (candidates.isEmpty()) {
                    Log.w(TAG, "[music-resolver] No candidates returned for '$searchQuery'")
                    return@fold MusicResolutionResult.FallbackSearch(
                        title = trimmedTitle,
                        artist = artist,
                        reason = "No candidates found from YouTube search."
                    )
                }

                // Score candidates using user-intent aware MusicCandidateScorer
                val scoredCandidates = candidates.map { candidate ->
                    val score = MusicCandidateScorer.score(trimmedTitle, candidate)
                    candidate.copy(score = score)
                }.sortedByDescending { it.score }

                val bestCandidate = scoredCandidates.first()

                DiagnosticBus.log(
                    tag = "youtube-resolver",
                    stage = DiagnosticStage.SCORING,
                    message = "Evaluated ${scoredCandidates.size} candidates. Best: '${bestCandidate.title}' (Score: ${bestCandidate.score}, Channel: '${bestCandidate.channelTitle}')"
                )

                if (YouTubeVideoIdExtractor.isValidVideoId(bestCandidate.videoId)) {
                    Log.i(TAG, "[music-resolver] Selected candidate: videoId='${bestCandidate.videoId}', title='${bestCandidate.title}', score=${bestCandidate.score}")

                    // Cache verified candidate
                    cache.put(
                        title = trimmedTitle,
                        artist = artist,
                        videoId = bestCandidate.videoId,
                        channelTitle = bestCandidate.channelTitle
                    )

                    DiagnosticBus.log(
                        tag = "youtube-resolver",
                        stage = DiagnosticStage.CACHED,
                        message = "Cached videoId='${bestCandidate.videoId}' for '$trimmedTitle'"
                    )

                    MusicResolutionResult.Resolved(
                        videoId = bestCandidate.videoId,
                        title = trimmedTitle,
                        artist = artist,
                        source = ResolutionSource.YouTubeDataApi,
                        channelTitle = bestCandidate.channelTitle,
                        score = bestCandidate.score
                    )
                } else {
                    Log.w(TAG, "[music-resolver] Top candidate contained invalid video ID: '${bestCandidate.videoId}'")
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
     * Invalidate cache entry and re-query the YouTube API if a video ID is found to fail playback.
     */
    suspend fun reResolveOnPlaybackFailure(title: String, artist: String?): MusicResolutionResult {
        Log.i(TAG, "[music-resolver] Invalidating cache and re-resolving for '$title' by '$artist'")
        DiagnosticBus.log(
            tag = "youtube-resolver",
            stage = DiagnosticStage.FAILED,
            message = "Playback failed for '$title'. Invalidating cache and re-resolving."
        )
        cache.invalidate(title, artist)
        return resolveTrack(title, artist, explicitDirectId = null)
    }

    fun invalidate(title: String, artist: String?) {
        cache.invalidate(title, artist)
    }
}
