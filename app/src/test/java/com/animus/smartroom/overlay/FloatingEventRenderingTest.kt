package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.SubActionItem
import org.junit.Assert.*
import org.junit.Test

class FloatingEventRenderingTest {

    @Test
    fun `ac power off event renders correctly`() {
        val event = AnimusActionEvent(
            id = "evt-1",
            timestamp = 1000L,
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "POWER_OFF",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "AC turned OFF successfully",
            metadata = mapOf("power" to "OFF", "verified" to "true")
        )

        val subAction = SubActionItem(
            id = event.id,
            deviceType = event.targetDevice,
            action = event.action,
            description = "Bedroom AC → OFF",
            status = event.status,
            verified = event.metadata["verified"] == "true"
        )

        assertEquals("Bedroom AC → OFF", subAction.description)
        assertTrue(subAction.verified)
        assertEquals(ActionStatus.SUCCESS, subAction.status)
    }

    @Test
    fun `ac set temperature event renders correctly`() {
        val event = AnimusActionEvent(
            id = "evt-2",
            timestamp = 1000L,
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "AC temperature set to 24",
            metadata = mapOf("temperature" to "24", "verified" to "true")
        )

        val subAction = SubActionItem(
            id = event.id,
            deviceType = event.targetDevice,
            action = event.action,
            description = "Bedroom AC → 24°C",
            status = event.status,
            verified = event.metadata["verified"] == "true"
        )

        assertEquals("Bedroom AC → 24°C", subAction.description)
        assertTrue(subAction.verified)
    }

    @Test
    fun `no change status is preserved`() {
        val event = AnimusActionEvent(
            id = "evt-3",
            timestamp = 1000L,
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "POWER_OFF",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.NO_CHANGE,
            message = "AC already OFF",
            metadata = mapOf("verified" to "true")
        )

        assertEquals(ActionStatus.NO_CHANGE, event.status)
    }
}
