package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.SubActionItem
import com.animus.smartroom.voice.VoiceInputState
import org.junit.Assert.*
import org.junit.Test

class FloatingOverlayStateTest {

    @Test
    fun `default state is collapsed and idle`() {
        val state = FloatingOverlayState()
        assertFalse(state.isExpanded)
        assertEquals(VoiceInputState.Idle, state.voiceState)
        assertNull(state.activeCommandCard)
        assertTrue(state.recentCompletedActions.isEmpty())
        assertNull(state.activeTimer)
        assertFalse(state.musicSummary.isPlaying)
    }

    @Test
    fun `expand and collapse state transitions`() {
        val state = FloatingOverlayState()
        val expanded = state.copy(isExpanded = true)
        assertTrue(expanded.isExpanded)

        val collapsed = expanded.copy(isExpanded = false)
        assertFalse(collapsed.isExpanded)
    }

    @Test
    fun `voice state transitions reflect in overlay state`() {
        val state = FloatingOverlayState()
        val listening = state.copy(voiceState = VoiceInputState.Listening(12.5f))
        assertTrue(listening.voiceState is VoiceInputState.Listening)

        val recognizing = state.copy(voiceState = VoiceInputState.Recognizing("Set AC to 24"))
        assertTrue(recognizing.voiceState is VoiceInputState.Recognizing)

        val error = state.copy(voiceState = VoiceInputState.Error("Mic timeout"))
        assertTrue(error.voiceState is VoiceInputState.Error)
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
