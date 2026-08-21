package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AnimusActionEventTest {

    @Test
    fun `AnimusActionEvent constructs with all fields and formats displayString`() {
        val event = AnimusActionEvent(
            id = "evt-123",
            correlationId = "corr-456",
            timestamp = 1787333400000L,
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            stage = ActionStage.EXECUTING,
            status = ActionStatus.IN_PROGRESS,
            message = "Setting target temperature to 24°C",
            metadata = mapOf("temperature" to "24", "mode" to "COOL")
        )

        assertEquals("evt-123", event.id)
        assertEquals("corr-456", event.correlationId)
        assertEquals(ActionSource.USER_COMMAND, event.source)
        assertEquals(DeviceType.AIR_CONDITIONER, event.targetDevice)
        assertEquals("SET_TEMPERATURE", event.action)
        assertEquals(ActionStage.EXECUTING, event.stage)
        assertEquals(ActionStatus.IN_PROGRESS, event.status)
        assertEquals(2, event.metadata.size)

        val display = event.displayString
        assertTrue(display.contains("[USER_COMMAND]"))
        assertTrue(display.contains("[corr:corr-456]"))
        assertTrue(display.contains("[AIR_CONDITIONER]"))
        assertTrue(display.contains("[SET_TEMPERATURE]"))
        assertTrue(display.contains("[EXECUTING]"))
        assertTrue(display.contains("[IN_PROGRESS]"))
    }

    @Test
    fun `AnimusActionEvent serializes to and deserializes from JSON deterministically`() {
        val original = AnimusActionEvent(
            id = "evt-789",
            correlationId = "corr-001",
            timestamp = 1787333400000L,
            source = ActionSource.MUSIC,
            targetDevice = DeviceType.BLUETOOTH_AUDIO,
            action = "PLAY_MUSIC",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "Playing Zara Zara",
            metadata = mapOf("track" to "Zara Zara", "provider" to "YouTube Music", "outputDevice" to "LG SNC4R")
        )

        val json = original.toJson()
        val deserialized = AnimusActionEvent.fromJson(json)

        assertEquals(original.id, deserialized.id)
        assertEquals(original.correlationId, deserialized.correlationId)
        assertEquals(original.timestamp, deserialized.timestamp)
        assertEquals(original.source, deserialized.source)
        assertEquals(original.targetDevice, deserialized.targetDevice)
        assertEquals(original.action, deserialized.action)
        assertEquals(original.stage, deserialized.stage)
        assertEquals(original.status, deserialized.status)
        assertEquals(original.message, deserialized.message)
        assertEquals(original.metadata, deserialized.metadata)
    }

    @Test(expected = IllegalArgumentException::class)
    fun `AnimusActionEvent rejects blank id`() {
        AnimusActionEvent(
            id = "",
            timestamp = 1000L,
            source = ActionSource.SYSTEM,
            targetDevice = null,
            action = "PING",
            stage = ActionStage.EXECUTING,
            status = ActionStatus.IN_PROGRESS,
            message = null
        )
    }
}
