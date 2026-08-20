package com.animus.smartroom.brain.validator

import android.util.Log
import java.net.URI
import java.util.Locale
import java.util.regex.Pattern

object YouTubeVideoIdExtractor {

    private const val TAG = "YouTubeVideoIdExtractor"
    private val VIDEO_ID_REGEX = Pattern.compile("^[a-zA-Z0-9_-]{11}$")

    /**
     * Deterministically extracts an 11-character YouTube video ID from supported URL structures.
     * Returns null if URL is malformed, not a YouTube URL, or does not contain a valid 11-char video ID.
     */
    fun extractVideoId(rawUrl: String?): String? {
        if (rawUrl.isNullOrBlank()) return null

        val trimmed = rawUrl.trim()

        return try {
            val uri = URI(trimmed)
            val host = uri.host?.lowercase(Locale.ROOT) ?: return null

            val isYouTubeDomain = host == "youtube.com" || host.endsWith(".youtube.com")

            val candidateId = when {
                host == "youtu.be" -> {
                    // https://youtu.be/<videoId>
                    val path = uri.path?.removePrefix("/") ?: ""
                    path.takeWhile { it != '?' && it != '&' && it != '/' }
                }
                isYouTubeDomain -> {
                    val path = uri.path ?: ""
                    when {
                        path.startsWith("/shorts/") -> {
                            // https://www.youtube.com/shorts/<videoId>
                            path.removePrefix("/shorts/").takeWhile { it != '?' && it != '&' && it != '/' }
                        }
                        path.startsWith("/embed/") -> {
                            // https://www.youtube.com/embed/<videoId>
                            path.removePrefix("/embed/").takeWhile { it != '?' && it != '&' && it != '/' }
                        }
                        path.startsWith("/v/") -> {
                            // https://www.youtube.com/v/<videoId>
                            path.removePrefix("/v/").takeWhile { it != '?' && it != '&' && it != '/' }
                        }
                        else -> {
                            // Standard query param: ?v=<videoId>
                            val query = uri.query ?: ""
                            extractQueryParam(query, "v")
                        }
                    }
                }
                else -> null
            }

            if (candidateId != null && isValidVideoId(candidateId)) {
                Log.d(TAG, "[youtube-url] Deterministically extracted valid video ID: $candidateId from '$trimmed'")
                candidateId
            } else {
                Log.w(TAG, "[youtube-url] Failed to extract valid 11-character video ID from '$trimmed' (candidate='$candidateId')")
                null
            }
        } catch (e: Exception) {
            Log.e(TAG, "[youtube-url] Error parsing URL syntax for: '$trimmed'", e)
            null
        }
    }

    fun isValidVideoId(videoId: String?): Boolean {
        if (videoId.isNullOrBlank() || videoId.length != 11) return false
        return VIDEO_ID_REGEX.matcher(videoId).matches()
    }

    private fun extractQueryParam(query: String, paramName: String): String? {
        if (query.isBlank()) return null
        val pairs = query.split("&")
        for (pair in pairs) {
            val parts = pair.split("=", limit = 2)
            if (parts.size == 2 && parts[0].equals(paramName, ignoreCase = true)) {
                return parts[1]
            }
        }
        return null
    }
}
