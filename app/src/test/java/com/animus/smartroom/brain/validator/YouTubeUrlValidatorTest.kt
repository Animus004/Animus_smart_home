package com.animus.smartroom.brain.validator

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class YouTubeUrlValidatorTest {

    @Test
    fun testValidYouTubeMusicWatchUrl() {
        val url = "https://music.youtube.com/watch?v=IWjbBSMsQJg"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Valid)
        val valid = result as UrlValidationResult.Valid
        assertEquals("IWjbBSMsQJg", valid.videoId)
        assertEquals("https://music.youtube.com/watch?v=IWjbBSMsQJg", valid.canonicalUri)
    }

    @Test
    fun testValidStandardYouTubeWatchUrl() {
        val url = "https://www.youtube.com/watch?v=abc123XYZ_9&feature=share"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Valid)
        val valid = result as UrlValidationResult.Valid
        assertEquals("abc123XYZ_9", valid.videoId)
    }

    @Test
    fun testValidShortYoutuBeUrl() {
        val url = "https://youtu.be/abc123XYZ_9"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Valid)
        val valid = result as UrlValidationResult.Valid
        assertEquals("abc123XYZ_9", valid.videoId)
    }

    @Test
    fun testRejectUntrustedDomain() {
        val url = "https://spotify.com/track/IWjbBSMsQJg"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Invalid)
    }

    @Test
    fun testRejectPhishingDomain() {
        val url = "https://music.youtube.com.evil.com/watch?v=IWjbBSMsQJg"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Invalid)
    }

    @Test
    fun testRejectJavascriptInjection() {
        val url = "javascript:alert('attack')"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Invalid)
    }

    @Test
    fun testRejectInvalidVideoIdLength() {
        val url = "https://music.youtube.com/watch?v=tooShort"
        val result = YouTubeUrlValidator.validateAndExtractVideoId(url)
        assertTrue(result is UrlValidationResult.Invalid)
    }

    @Test
    fun testRejectNullOrBlank() {
        assertTrue(YouTubeUrlValidator.validateAndExtractVideoId(null) is UrlValidationResult.Invalid)
        assertTrue(YouTubeUrlValidator.validateAndExtractVideoId("") is UrlValidationResult.Invalid)
        assertTrue(YouTubeUrlValidator.validateAndExtractVideoId("   ") is UrlValidationResult.Invalid)
    }
}
