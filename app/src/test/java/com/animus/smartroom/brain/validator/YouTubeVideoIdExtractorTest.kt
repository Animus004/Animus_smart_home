package com.animus.smartroom.brain.validator

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class YouTubeVideoIdExtractorTest {

    @Test
    fun testExtractFromStandardWatchUrl() {
        val url = "https://www.youtube.com/watch?v=PhWhGt28wNY"
        val id = YouTubeVideoIdExtractor.extractVideoId(url)
        assertEquals("PhWhGt28wNY", id)
    }

    @Test
    fun testExtractFromYouTubeMusicWatchUrl() {
        val url = "https://music.youtube.com/watch?v=k1bEaBcDeFg"
        val id = YouTubeVideoIdExtractor.extractVideoId(url)
        assertEquals("k1bEaBcDeFg", id)
    }

    @Test
    fun testExtractFromShortYoutuBeUrl() {
        val url = "https://youtu.be/PhWhGt28wNY"
        val id = YouTubeVideoIdExtractor.extractVideoId(url)
        assertEquals("PhWhGt28wNY", id)
    }

    @Test
    fun testExtractFromShortsUrl() {
        val url = "https://www.youtube.com/shorts/PhWhGt28wNY"
        val id = YouTubeVideoIdExtractor.extractVideoId(url)
        assertEquals("PhWhGt28wNY", id)
    }

    @Test
    fun testExtractFromEmbedUrl() {
        val url = "https://www.youtube.com/embed/PhWhGt28wNY"
        val id = YouTubeVideoIdExtractor.extractVideoId(url)
        assertEquals("PhWhGt28wNY", id)
    }

    @Test
    fun testExtractWithExtraQueryParams() {
        val url = "https://m.youtube.com/watch?v=PhWhGt28wNY&feature=share&t=10s"
        val id = YouTubeVideoIdExtractor.extractVideoId(url)
        assertEquals("PhWhGt28wNY", id)
    }

    @Test
    fun testTestSongUrls() {
        // Ramta Jogi
        assertEquals(
            "PhWhGt28wNY",
            YouTubeVideoIdExtractor.extractVideoId("https://www.youtube.com/watch?v=PhWhGt28wNY")
        )

        // Tera Mera Rishta
        assertEquals(
            "aBcDeFgHiJk",
            YouTubeVideoIdExtractor.extractVideoId("https://music.youtube.com/watch?v=aBcDeFgHiJk")
        )

        // Tum Se Hi
        assertEquals(
            "lMnOpQrStUv",
            YouTubeVideoIdExtractor.extractVideoId("https://youtu.be/lMnOpQrStUv")
        )

        // Zara Zara
        assertEquals(
            "IWjbBSMsQJg",
            YouTubeVideoIdExtractor.extractVideoId("https://music.youtube.com/watch?v=IWjbBSMsQJg")
        )
    }

    @Test
    fun testRejectUntrustedOrSpoofedDomains() {
        assertNull(YouTubeVideoIdExtractor.extractVideoId("https://evil.com/watch?v=PhWhGt28wNY"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("https://music.youtube.com.attacker.com/watch?v=PhWhGt28wNY"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("https://spotify.com/track/PhWhGt28wNY"))
    }

    @Test
    fun testRejectDangerousSchemes() {
        assertNull(YouTubeVideoIdExtractor.extractVideoId("javascript:alert('attack')"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("file:///sdcard/music.mp3"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("content://media/external/audio/123"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("intent://#Intent;action=play;end"))
    }

    @Test
    fun testRejectInvalidLengthOrCharacters() {
        assertNull(YouTubeVideoIdExtractor.extractVideoId("https://youtu.be/short"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("https://youtu.be/toolongvideoid12345"))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("https://music.youtube.com/watch?v=abc!@#$$%^^"))
    }

    @Test
    fun testRejectNullOrBlank() {
        assertNull(YouTubeVideoIdExtractor.extractVideoId(null))
        assertNull(YouTubeVideoIdExtractor.extractVideoId(""))
        assertNull(YouTubeVideoIdExtractor.extractVideoId("   "))
    }

    @Test
    fun testIsValidVideoId() {
        assertTrue(YouTubeVideoIdExtractor.isValidVideoId("PhWhGt28wNY"))
        assertTrue(YouTubeVideoIdExtractor.isValidVideoId("IWjbBSMsQJg"))
        assertTrue(YouTubeVideoIdExtractor.isValidVideoId("k1bEaBcDeFg"))
        assertFalse(YouTubeVideoIdExtractor.isValidVideoId("short"))
        assertFalse(YouTubeVideoIdExtractor.isValidVideoId("tooLongVideoId123"))
        assertFalse(YouTubeVideoIdExtractor.isValidVideoId(null))
    }
}
