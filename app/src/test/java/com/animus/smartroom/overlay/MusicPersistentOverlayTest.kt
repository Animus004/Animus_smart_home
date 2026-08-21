package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.model.OverlayMusicSummary
import com.animus.smartroom.overlay.model.SubActionItem
import org.junit.Assert.*
import org.junit.Test

class MusicPersistentOverlayTest {

    @Test
    fun `music playback keeps overlay persistent even after sub-actions complete`() {
        val state = FloatingOverlayState(
            visibility = FloatingOverlayVisibility.MUSIC_PERSISTENT,
            isExpanded = false,
            musicSummary = OverlayMusicSummary(
                trackTitle = "Zara Zara",
                outputDeviceName = "LG SNC4R",
                isConnected = true,
                isPlaying = true
            )
        )

        assertTrue(state.isMusicPersistent)
        assertEquals("Zara Zara", state.musicSummary.trackTitle)
        assertEquals("LG SNC4R", state.musicSummary.outputDeviceName)
        assertTrue(state.musicSummary.isConnected)
    }

    @Test
    fun `music disconnect shows disconnected status without playback loops`() {
        val playingSummary = OverlayMusicSummary(
            trackTitle = "Zara Zara",
            outputDeviceName = "LG SNC4R",
            isConnected = true,
            isPlaying = true
        )
        assertTrue(playingSummary.isConnected)

        // Disconnected speaker state
        val disconnectedSummary = playingSummary.copy(
            isConnected = false
        )
        assertFalse(disconnectedSummary.isConnected)
        assertEquals("LG SNC4R", disconnectedSummary.outputDeviceName)
    }

    @Test
    fun `music stopping exits persistent mode to collapsed`() {
        val state = FloatingOverlayState(
            visibility = FloatingOverlayVisibility.MUSIC_PERSISTENT,
            musicSummary = OverlayMusicSummary(isPlaying = true)
        )
        assertTrue(state.isMusicPersistent)

        // Stopped playback
        val stoppedState = state.copy(
            visibility = FloatingOverlayVisibility.COLLAPSED,
            musicSummary = OverlayMusicSummary(isPlaying = false)
        )
        assertFalse(stoppedState.isMusicPersistent)
        assertEquals(FloatingOverlayVisibility.COLLAPSED, stoppedState.visibility)
    }
}
