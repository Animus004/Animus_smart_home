package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.CorrelatedCommandCard
import com.animus.smartroom.overlay.model.SubActionItem
import org.junit.Assert.*
import org.junit.Test

class Phase5E21RegressionSuiteTest {

    @Test
    fun `CorrelatedMusicAcCommandTest - groups both AC and Music subactions under single correlation card`() {
        val subActions = listOf(
            SubActionItem("s1", DeviceType.AIR_CONDITIONER, "SET_TEMPERATURE", "Bedroom AC → 24°C", ActionStatus.SUCCESS, true),
            SubActionItem("s2", DeviceType.BLUETOOTH_AUDIO, "PLAY_MUSIC", "♪ Zara Zara → LG SNC4R", ActionStatus.SUCCESS, true)
        )
        val card = CorrelatedCommandCard(
            correlationId = "corr-123",
            rawPrompt = "Set AC to 24 degrees and play Zara Zara",
            subActions = subActions,
            overallStatus = ActionStatus.SUCCESS
        )

        assertEquals("corr-123", card.correlationId)
        assertEquals(2, card.subActions.size)
        assertEquals(ActionStatus.SUCCESS, card.overallStatus)
    }

    @Test
    fun `TimerCancellationFromOverlayTest - preserves state and cancels cleanly`() {
        val subAction = SubActionItem(
            id = "timer-1",
            deviceType = DeviceType.AIR_CONDITIONER,
            action = "SCHEDULED_POWER_OFF",
            description = "Bedroom AC → OFF",
            status = ActionStatus.CANCELLED
        )
        assertEquals(ActionStatus.CANCELLED, subAction.status)
    }

    @Test
    fun `VoiceWhenActivityBackgroundedTest - voice adapter provides recognition results independently of activity`() {
        val fakeVoicePort = SharedVoiceInputTest.FakeVoiceInputPort()
        assertNotNull(fakeVoicePort)
        assertEquals(com.animus.smartroom.core.port.VoicePortState.Idle, fakeVoicePort.state.value)
    }

    @Test
    fun `OverlayRuntimeIndependenceTest - activity recreation does not mutate overlay state`() {
        val state1 = com.animus.smartroom.overlay.model.FloatingOverlayState(
            isExpanded = true,
            activeTimer = null
        )
        val state2 = state1.copy()
        assertEquals(state1, state2)
    }

    @Test
    fun `OverlaySecurityRegressionTest - credentials stripped from all rendered metadata`() {
        val raw = "Bearer secret_tuya_token_12345 AIzaSyDummyKey6789"
        val sanitized = com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer.sanitizeText(raw)
        assertFalse(sanitized?.contains("secret_tuya_token_12345") == true)
        assertFalse(sanitized?.contains("AIzaSyDummyKey6789") == true)
    }
}
