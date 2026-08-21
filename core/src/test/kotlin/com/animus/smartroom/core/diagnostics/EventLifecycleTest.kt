package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class EventLifecycleTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `standard action progresses through complete lifecycle successfully`() {
        val corrId = "corr-lifecycle-1"

        // 1. RECEIVED
        DiagnosticBus.publish {
            received(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                message = "User requested AC to 24°C"
            )
        }

        // 2. PRECONDITION
        DiagnosticBus.publish {
            precondition(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_ON",
                message = "AC is OFF. Automatic power-on required."
            )
        }

        // 3. EXECUTING
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                message = "Writing temp_set=24 to device"
            )
        }

        // 4. VERIFYING
        DiagnosticBus.publish {
            verifying(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                message = "Verifying live readback"
            )
        }

        // 5. COMPLETED
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                message = "AC was off, so I turned it on and set the temperature to 24°C."
            )
        }

        val stages = DiagnosticBus.getRecentActionEvents().map { it.stage }
        assertEquals(
            listOf(
                ActionStage.RECEIVED,
                ActionStage.PRECONDITION,
                ActionStage.EXECUTING,
                ActionStage.VERIFYING,
                ActionStage.COMPLETED
            ),
            stages
        )
    }

    @Test
    fun `cancelled action records CANCELLED stage and status`() {
        DiagnosticBus.publish {
            cancelled(
                correlationId = "corr-cancel",
                action = "SCHEDULED_ACTION",
                message = "Scheduled action was cancelled by user"
            )
        }

        val event = DiagnosticBus.getRecentActionEvents().first()
        assertEquals(ActionStage.CANCELLED, event.stage)
        assertEquals(ActionStatus.CANCELLED, event.status)
    }
}
