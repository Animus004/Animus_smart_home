package com.animus.smartroom.brain.validator

import java.net.URI
import java.util.Locale
import java.util.regex.Pattern

object YouTubeVideoIdExtractor {

    private val VIDEO_ID_REGEX = Pattern.compile("^[a-zA-Z0-9_-]{11}$")

    fun extractVideoId(rawUrl: String?): String? {
        if (rawUrl.isNullOrBlank()) return null

        val trimmed = rawUrl.trim()

        return try {
            val uri = URI(trimmed)
            val host = uri.host?.lowercase(Locale.ROOT) ?: return null

            val isYouTubeDomain = host == "youtube.com" || host.endsWith(".youtube.com")

            val candidateId = when {
                host == "youtu.be" -> {
                    val path = uri.path?.removePrefix("/") ?: ""
                    path.takeWhile { it != '?' && it != '&' && it != '/' }
                }
                isYouTubeDomain -> {
                    val path = uri.path ?: ""
                    when {
                        path.startsWith("/shorts/") -> {
                            path.removePrefix("/shorts/").takeWhile { it != '?' && it != '&' && it != '/' }
                        }
                        path.startsWith("/embed/") -> {
                            path.removePrefix("/embed/").takeWhile { it != '?' && it != '&' && it != '/' }
                        }
                        path.startsWith("/v/") -> {
                            path.removePrefix("/v/").takeWhile { it != '?' && it != '&' && it != '/' }
                        }
                        else -> {
                            val query = uri.query ?: ""
                            extractQueryParam(query, "v")
                        }
                    }
                }
                else -> null
            }

            if (candidateId != null && isValidVideoId(candidateId)) {
                candidateId
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    fun isValidVideoId(videoId: String?): Boolean {
        if (videoId.isNullOrBlank()) return false
        return VIDEO_ID_REGEX.matcher(videoId.trim()).matches()
    }

    private fun extractQueryParam(query: String, paramName: String): String? {
        if (query.isBlank()) return null
        val pairs = query.split("&")
        for (pair in pairs) {
            val parts = pair.split("=", limit = 2)
            if (parts.size == 2 && parts[0].trim().equals(paramName, ignoreCase = true)) {
                val candidate = parts[1].trim()
                if (candidate.isNotEmpty()) return candidate
            }
        }
        return null
    }
}
