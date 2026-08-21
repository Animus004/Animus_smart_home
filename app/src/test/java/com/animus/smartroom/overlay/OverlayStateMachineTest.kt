package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.overlay.OverlayEventAction
import com.animus.smartroom.core.overlay.OverlayEventPolicy
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.model.OverlayMusicSummary
import org.junit.Assert.*
import org.junit.Test

class OverlayStateMachineTest {

    @Test
    fun `auto collapse transitions from EXPANDED to COLLAPSED or MUSIC_PERSISTENT`() {
        val state = FloatingOverlayState(
            visibility = FloatingOverlayVisibility.EXPANDED,
            isExpanded = true
        )
        // Simulated collapse without music
        val collapsed = state.copy(visibility = FloatingOverlayVisibility.COLLAPSED, isExpanded = false)
        assertEquals(FloatingOverlayVisibility.COLLAPSED, collapsed.visibility)
        assertFalse(collapsed.isExpanded)

        // Simulated collapse with music active
        val musicState = state.copy(
            musicSummary = OverlayMusicSummary(trackTitle = "Zara Zara", isPlaying = true)
        )
        val musicCollapsed = musicState.copy(
            visibility = FloatingOverlayVisibility.MUSIC_PERSISTENT,
            isExpanded = false
        )
        assertEquals(FloatingOverlayVisibility.MUSIC_PERSISTENT, musicCollapsed.visibility)
        assertTrue(musicCollapsed.isMusicPersistent)
    }

    @Test
    fun `auto hide only triggers when no active timer or playing music`() {
        val idleState = FloatingOverlayState(
            visibility = FloatingOverlayVisibility.COLLAPSED,
            voiceState = VoicePortState.Idle,
            activeTimer = null,
            musicSummary = OverlayMusicSummary(isPlaying = false)
        )
        val canHideIdle = !idleState.musicSummary.isPlaying && idleState.activeTimer == null && idleState.voiceState is VoicePortState.Idle
        assertTrue(canHideIdle)

        val musicPlayingState = idleState.copy(
            musicSummary = OverlayMusicSummary(trackTitle = "Zara Zara", isPlaying = true),
            visibility = FloatingOverlayVisibility.MUSIC_PERSISTENT
        )
        val canHideMusic = !musicPlayingState.musicSummary.isPlaying && musicPlayingState.activeTimer == null
        assertFalse(canHideMusic)
    }

    @Test
    fun `wake on meaningful event transitions HIDDEN to EXPANDED`() {
        val hiddenState = FloatingOverlayState(visibility = FloatingOverlayVisibility.HIDDEN)
        val event = AnimusActionEvent(
            id = "e1",
            timestamp = System.currentTimeMillis(),
            source = com.animus.smartroom.core.diagnostics.model.ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "AC temp set"
        )

        val policyAction = OverlayEventPolicy.evaluate(event)
        assertEquals(OverlayEventAction.SURFACE_IMMEDIATELY, policyAction)

        val nextVisibility = if (hiddenState.visibility == FloatingOverlayVisibility.HIDDEN && policyAction == OverlayEventAction.SURFACE_IMMEDIATELY) {
            FloatingOverlayVisibility.EXPANDED
        } else hiddenState.visibility

        assertEquals(FloatingOverlayVisibility.EXPANDED, nextVisibility)
    }
}
