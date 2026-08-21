package com.animus.smartroom.brain.validator

import java.net.URI
import java.util.Locale

sealed interface UrlValidationResult {
    data class Valid(val videoId: String, val canonicalUri: String) : UrlValidationResult
    data class Invalid(val reason: String) : UrlValidationResult
}

object YouTubeUrlValidator {

    private val ALLOWED_HOSTS = setOf(
        "music.youtube.com",
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be"
    )

    private val REJECTED_SCHEMES = setOf(
        "javascript", "file", "content", "intent", "data", "about"
    )

    fun validateAndExtractVideoId(rawUrl: String?): UrlValidationResult {
        if (rawUrl.isNullOrBlank() || rawUrl.trim().equals("null", ignoreCase = true)) {
            return UrlValidationResult.Invalid("URL is empty or blank.")
        }

        val trimmed = rawUrl.trim()

        return try {
            val uri = URI(trimmed)
            val scheme = uri.scheme?.lowercase(Locale.ROOT)
            if (scheme in REJECTED_SCHEMES || (scheme != "http" && scheme != "https")) {
                return UrlValidationResult.Invalid("Invalid or dangerous URL scheme '$scheme'.")
            }

            val host = uri.host?.lowercase(Locale.ROOT)
            if (host == null || host !in ALLOWED_HOSTS) {
                return UrlValidationResult.Invalid("Unauthorized domain '$host'. Only authentic YouTube domains allowed.")
            }

            val videoId = YouTubeVideoIdExtractor.extractVideoId(trimmed)
                ?: return UrlValidationResult.Invalid("Could not extract valid 11-character YouTube video ID from URL: '$trimmed'.")

            val canonicalUri = "https://music.youtube.com/watch?v=$videoId"
            UrlValidationResult.Valid(videoId = videoId, canonicalUri = canonicalUri)
        } catch (e: Exception) {
            UrlValidationResult.Invalid("Malformed URL syntax: ${e.message}")
        }
    }
}
