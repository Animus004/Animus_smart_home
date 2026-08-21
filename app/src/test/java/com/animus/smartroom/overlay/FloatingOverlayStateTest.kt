package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.model.SubActionItem
import org.junit.Assert.*
import org.junit.Test

class FloatingOverlayStateTest {

    @Test
    fun `default state is collapsed and idle`() {
        val state = FloatingOverlayState()
        assertFalse(state.isExpanded)
        assertEquals(FloatingOverlayVisibility.COLLAPSED, state.visibility)
        assertEquals(VoicePortState.Idle, state.voiceState)
        assertNull(state.activeCommandCard)
        assertTrue(state.recentCompletedActions.isEmpty())
        assertNull(state.activeTimer)
        assertFalse(state.musicSummary.isPlaying)
    }

    @Test
    fun `expand and collapse state transitions`() {
        val state = FloatingOverlayState()
        val expanded = state.copy(isExpanded = true, visibility = FloatingOverlayVisibility.EXPANDED)
        assertTrue(expanded.isExpanded)
        assertEquals(FloatingOverlayVisibility.EXPANDED, expanded.visibility)

        val collapsed = expanded.copy(isExpanded = false, visibility = FloatingOverlayVisibility.COLLAPSED)
        assertFalse(collapsed.isExpanded)
        assertEquals(FloatingOverlayVisibility.COLLAPSED, collapsed.visibility)
    }

    @Test
    fun `voice state transitions reflect in overlay state`() {
        val state = FloatingOverlayState()
        val listening = state.copy(voiceState = VoicePortState.Listening(12.5f))
        assertTrue(listening.voiceState is VoicePortState.Listening)

        val recognizing = state.copy(voiceState = VoicePortState.Recognizing("Set AC to 24"))
        assertTrue(recognizing.voiceState is VoicePortState.Recognizing)

        val error = state.copy(voiceState = VoicePortState.Error("Mic timeout"))
        assertTrue(error.voiceState is VoicePortState.Error)
    }

    @Test
    fun `subAction status transitions reflect in card state`() {
        val item = SubActionItem(
            id = "sub-1",
            deviceType = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            description = "Bedroom AC → 24°C",
            status = ActionStatus.IN_PROGRESS,
            verified = false
        )
        assertFalse(item.verified)
        assertEquals(ActionStatus.IN_PROGRESS, item.status)

        val completedItem = item.copy(status = ActionStatus.SUCCESS, verified = true)
        assertTrue(completedItem.verified)
        assertEquals(ActionStatus.SUCCESS, completedItem.status)
    }
}
