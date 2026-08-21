package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.factory.AnimusActionEventFactory
import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.query.ActionEventQuery
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class EventCorrelationTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `composite multi-command request correlates distinct actions under same correlationId`() {
        val corrId = "cmd-xyz-123"

        // 1. Initial Request Event
        DiagnosticBus.publish {
            received(
                correlationId = corrId,
                action = "MULTI_COMMAND",
                message = "Set AC to 24 degrees, set volume to 25%, and play Zara Zara"
            )
        }

        // 2. Sub-command 1: AC Temperature
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                metadata = mapOf("temperature" to "24")
            )
        }
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                message = "Bedroom AC temperature set to 24°C."
            )
        }

        // 3. Sub-command 2: Volume
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "SET_VOLUME",
                metadata = mapOf("volume" to "25")
            )
        }
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "SET_VOLUME",
                message = "Volume set to 25%"
            )
        }

        // 4. Sub-command 3: Music
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "PLAY_MUSIC",
                metadata = mapOf("track" to "Zara Zara", "outputDevice" to "LG SNC4R")
            )
        }
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "PLAY_MUSIC",
                message = "Playing Zara Zara"
            )
        }

        // Query events by correlationId
        val correlatedEvents = ActionEventQuery.byCorrelationId(DiagnosticBus.getRecentActionEvents(), corrId)
        assertEquals(7, correlatedEvents.size)

        // Verify unique event IDs with identical correlationId
        val eventIds = correlatedEvents.map { it.id }.toSet()
        assertEquals(7, eventIds.size)

        // Reconstruct individual actions from the correlation stream
        val actions = correlatedEvents.map { it.action }.toSet()
        assertTrue(actions.contains("MULTI_COMMAND"))
        assertTrue(actions.contains("SET_TEMPERATURE"))
        assertTrue(actions.contains("SET_VOLUME"))
        assertTrue(actions.contains("PLAY_MUSIC"))
    }
}
