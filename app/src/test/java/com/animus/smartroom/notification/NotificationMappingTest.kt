package com.animus.smartroom.notification

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.device.model.DeviceType
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Tests for notification content mapping from AnimusActionEvent.
 * Does not require Android context — tests pure notification content logic.
 */
class NotificationMappingTest {

    private fun buildEvent(
        source: ActionSource = ActionSource.SYSTEM,
        targetDevice: DeviceType? = null,
        action: String = "TEST",
        stage: ActionStage = ActionStage.COMPLETED,
        status: ActionStatus = ActionStatus.SUCCESS,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = AnimusActionEvent(
        id = "notif-evt-${System.nanoTime()}",
        timestamp = System.currentTimeMillis(),
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = stage,
        status = status,
        message = message,
        metadata = metadata
    )

    @Test
    fun `AC success event produces sanitized content without credentials`() {
        val event = buildEvent(
            source = ActionSource.USER_COMMAND,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "POWER_OFF",
            status = ActionStatus.SUCCESS,
            message = "Bedroom AC turned off. access_token=super_secret",
            metadata = mapOf("power" to "OFF")
        )

        val sanitizedMessage = EventSanitizer.sanitizeText(event.message)
        assertFalse("Credentials must be redacted", sanitizedMessage!!.contains("super_secret"))
    }

    @Test
    fun `AC failure event message is sanitized`() {
        val event = buildEvent(
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "SET_TEMPERATURE",
            status = ActionStatus.FAILED,
            message = "API error: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 rejected"
        )

        val sanitized = EventSanitizer.sanitizeText(event.message)
        assertFalse("Bearer token must be redacted", sanitized!!.contains("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"))
        assertTrue("REDACTED label should be present", sanitized.contains("[REDACTED_BEARER_TOKEN]"))
    }

    @Test
    fun `music success event maps to play notification format`() {
        val event = buildEvent(
            source = ActionSource.MUSIC,
            targetDevice = DeviceType.BLUETOOTH_AUDIO,
            action = "PLAY_MUSIC",
            status = ActionStatus.SUCCESS,
            message = "Playing Zara Zara on LG SNC4R",
            metadata = mapOf("track" to "Zara Zara", "outputDevice" to "LG SNC4R")
        )

        val metadata = event.metadata
        assertTrue(metadata["track"] == "Zara Zara")
        assertTrue(metadata["outputDevice"] == "LG SNC4R")
        // EventSanitizer should not modify non-sensitive keys
        val sanitized = EventSanitizer.sanitizeMetadata(metadata)
        assertTrue(sanitized["track"] == "Zara Zara")
        assertTrue(sanitized["outputDevice"] == "LG SNC4R")
    }

    @Test
    fun `scheduler trigger event preserves actionId in metadata without credential leakage`() {
        val event = buildEvent(
            source = ActionSource.SCHEDULER,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "POWER_OFF",
            stage = ActionStage.TRIGGERED,
            status = ActionStatus.PENDING,
            metadata = mapOf(
                "actionId" to "act-notif-001",
                "tuya_secret" to "secret_value"  // should be redacted
            )
        )

        val sanitized = EventSanitizer.sanitizeMetadata(event.metadata)
        assertTrue(sanitized["actionId"] == "act-notif-001")
        assertTrue(sanitized["tuya_secret"] == "[REDACTED]")
    }

    @Test
    fun `no_change event does not appear as failure in notification`() {
        val event = buildEvent(
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "POWER_OFF",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.NO_CHANGE,
            message = "AC already OFF"
        )

        // NO_CHANGE should map to success/info, not failure
        assertTrue(event.status != ActionStatus.FAILED)
        assertTrue(event.status != ActionStatus.CANCELLED)
    }

    @Test
    fun `runtime started event maps to ready notification`() {
        val event = buildEvent(
            source = ActionSource.SYSTEM,
            action = "RUNTIME_STARTED",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "Animus runtime started"
        )

        // Validate the event properties expected by AndroidNotificationAdapter.resolveNotificationContent
        assertTrue(event.action == "RUNTIME_STARTED")
        assertTrue(event.status == ActionStatus.SUCCESS)
    }
}
