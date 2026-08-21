package com.animus.smartroom.core.overlay

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import org.junit.Assert.assertEquals
import org.junit.Test

class OverlayEventPolicyTest {

    @Test
    fun `music completed event surfaces as music persistent`() {
        val event = AnimusActionEvent(
            id = "m1",
            timestamp = System.currentTimeMillis(),
            source = ActionSource.MUSIC,
            targetDevice = DeviceType.BLUETOOTH_AUDIO,
            action = "PLAY_MUSIC",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "Playing Zara Zara"
        )
        val action = OverlayEventPolicy.evaluate(event, isMusicActive = false)
        assertEquals(OverlayEventAction.SURFACE_MUSIC_PERSISTENT, action)
    }

    @Test
    fun `music resolving event surfaces immediately`() {
        val event = AnimusActionEvent(
            id = "m2",
            timestamp = System.currentTimeMillis(),
            source = ActionSource.MUSIC,
            targetDevice = DeviceType.BLUETOOTH_AUDIO,
            action = "PLAY_MUSIC",
            stage = ActionStage.RESOLVING,
            status = ActionStatus.IN_PROGRESS,
            message = "Resolving track"
        )
        val action = OverlayEventPolicy.evaluate(event, isMusicActive = false)
        assertEquals(OverlayEventAction.SURFACE_IMMEDIATELY, action)
    }

    @Test
    fun `scheduled timer triggered or completed surfaces timer completion`() {
        val event = AnimusActionEvent(
            id = "t1",
            timestamp = System.currentTimeMillis(),
            source = ActionSource.SCHEDULER,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SCHEDULED_POWER_OFF",
            stage = ActionStage.TRIGGERED,
            status = ActionStatus.IN_PROGRESS,
            message = "AC timer triggered"
        )
        val action = OverlayEventPolicy.evaluate(event, isMusicActive = false)
        assertEquals(OverlayEventAction.SURFACE_TIMER_COMPLETION, action)
    }

    @Test
    fun `ac completed event surfaces immediately`() {
        val event = AnimusActionEvent(
            id = "ac1",
            timestamp = System.currentTimeMillis(),
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "AC temp set"
        )
        val action = OverlayEventPolicy.evaluate(event, isMusicActive = false)
        assertEquals(OverlayEventAction.SURFACE_IMMEDIATELY, action)
    }

    @Test
    fun `low level precondition stage shows only if visible`() {
        val event = AnimusActionEvent(
            id = "ac2",
            timestamp = System.currentTimeMillis(),
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            stage = ActionStage.PRECONDITION,
            status = ActionStatus.IN_PROGRESS,
            message = "Precondition power on"
        )
        val action = OverlayEventPolicy.evaluate(event, isMusicActive = false)
        assertEquals(OverlayEventAction.SHOW_ONLY_IF_VISIBLE, action)
    }
}
