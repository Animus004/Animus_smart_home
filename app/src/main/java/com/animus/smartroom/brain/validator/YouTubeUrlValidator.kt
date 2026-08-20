package com.animus.smartroom.brain.validator

import android.util.Log
import java.net.URI
import java.util.Locale

sealed interface UrlValidationResult {
    data class Valid(val videoId: String, val canonicalUri: String) : UrlValidationResult
    data class Invalid(val reason: String) : UrlValidationResult
}

object YouTubeUrlValidator {

    private const val TAG = "YouTubeUrlValidator"

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
            Log.w(TAG, "[youtube-url] URL validation invoked with null/blank URL from: ${Throwable().stackTrace.take(5).joinToString(" -> ") { "${it.fileName}:${it.lineNumber}" }}")
            return UrlValidationResult.Invalid("URL is empty or blank.")
        }

        val trimmed = rawUrl.trim()

        return try {
            val uri = URI(trimmed)
            val scheme = uri.scheme?.lowercase(Locale.ROOT)
            if (scheme in REJECTED_SCHEMES || (scheme != "http" && scheme != "https")) {
                Log.w(TAG, "[youtube-url] Rejected dangerous or unsupported URL scheme '$scheme': $trimmed")
                return UrlValidationResult.Invalid("Invalid or dangerous URL scheme '$scheme'.")
            }

            val host = uri.host?.lowercase(Locale.ROOT)
            if (host == null || host !in ALLOWED_HOSTS) {
                Log.w(TAG, "[youtube-url] Rejected untrusted or spoofed domain '$host': $trimmed")
                return UrlValidationResult.Invalid("Unauthorized domain '$host'. Only authentic YouTube domains allowed.")
            }

            val videoId = YouTubeVideoIdExtractor.extractVideoId(trimmed)
            if (videoId == null) {
                Log.w(TAG, "[youtube-url] No valid 11-character video ID extractable from '$trimmed'")
                return UrlValidationResult.Invalid("Could not extract valid 11-character YouTube video ID from URL: '$trimmed'.")
            }

            val canonicalUri = "https://music.youtube.com/watch?v=$videoId"
            Log.i(TAG, "[youtube-url] Validated authentic candidate track: videoId='$videoId', canonical='$canonicalUri'")
            UrlValidationResult.Valid(videoId = videoId, canonicalUri = canonicalUri)
        } catch (e: Exception) {
            Log.e(TAG, "[youtube-url] Malformed URL syntax: $trimmed", e)
            UrlValidationResult.Invalid("Malformed URL syntax: ${e.message}")
        }
    }
}
