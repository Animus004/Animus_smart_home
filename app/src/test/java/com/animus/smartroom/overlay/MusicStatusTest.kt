package com.animus.smartroom.overlay

import com.animus.smartroom.overlay.model.OverlayMusicSummary
import org.junit.Assert.*
import org.junit.Test

class MusicStatusTest {

    @Test
    fun `music summary represents playing state correctly`() {
        val summary = OverlayMusicSummary(
            trackTitle = "Zara Zara",
            outputDeviceName = "LG SNC4R",
            isConnected = true,
            isPlaying = true
        )

        assertEquals("Zara Zara", summary.trackTitle)
        assertEquals("LG SNC4R", summary.outputDeviceName)
        assertTrue(summary.isConnected)
        assertTrue(summary.isPlaying)
    }

    @Test
    fun `music summary represents disconnected speaker correctly`() {
        val summary = OverlayMusicSummary(
            trackTitle = "Zara Zara",
            outputDeviceName = "LG SNC4R",
            isConnected = false,
            isPlaying = false
        )

        assertFalse(summary.isConnected)
        assertFalse(summary.isPlaying)
    }
}
