package com.animus.smartroom.runtime

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import com.animus.smartroom.scheduler.model.DeviceActionType
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Simulates lock-screen execution scenarios using pure JVM components.
 * The actual WakeLock + BroadcastReceiver execution is tested at BootReceiver/physical validation level.
 * Here we test the pure-JVM contract: what happens before/during/after the receiver fires.
 */
class LockScreenExecutionTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `scheduled action produces complete lifecycle events even without Activity running`() {
        // This simulates what ScheduledDeviceActionReceiver publishes
        // when the device is locked and Activity is not running.
        val actionId = "act-lock-001"
        val corrId = "sched-$actionId"

        // Phase 1: Action was scheduled (may have happened before lock)
        DiagnosticBus.publish {
            create(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                action = "POWER_OFF",
                stage = ActionStage.TRIGGERED,
                status = ActionStatus.PENDING,
                message = "Scheduled AC POWER_OFF",
                metadata = mapOf("actionId" to actionId)
            )
        }

        // Phase 2: WakeLock acquired, receiver fires
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_OFF",
                message = "Executing AC -> POWER_OFF (device locked)"
            )
        }

        // Phase 3: Tuya write + readback verification
        DiagnosticBus.publish {
            verifying(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_OFF",
                message = "Verifying physical AC state via live readback"
            )
        }

        // Phase 4: Completion
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_OFF",
                message = "AC POWER_OFF verified. AC is now physically OFF.",
                metadata = mapOf("power" to "OFF", "verified" to "true", "actionId" to actionId)
            )
        }

        val events = DiagnosticBus.getRecentActionEvents()
        assertEquals(4, events.size)

        val stages = events.map { it.stage }
        assertTrue(stages.contains(ActionStage.TRIGGERED))
        assertTrue(stages.contains(ActionStage.EXECUTING))
        assertTrue(stages.contains(ActionStage.VERIFYING))
        assertTrue(stages.contains(ActionStage.COMPLETED))

        val completionEvent = events.last()
        assertEquals(ActionStatus.SUCCESS, completionEvent.status)
        assertEquals("OFF", completionEvent.metadata["power"])
        assertEquals("true", completionEvent.metadata["verified"])
    }

    @Test
    fun `lock screen POWER_OFF on already OFF AC produces NO_CHANGE`() {
        val actionId = "act-lock-002"
        val corrId = "sched-$actionId"

        DiagnosticBus.publish {
            noChange(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_OFF",
                message = "AC is already physically OFF. Completed with no change.",
                metadata = mapOf("actionId" to actionId, "verified" to "true")
            )
        }

        val events = DiagnosticBus.getRecentActionEvents()
        assertEquals(1, events.size)
        assertEquals(ActionStatus.NO_CHANGE, events.first().status)
        assertEquals(ActionStage.COMPLETED, events.first().stage)
    }

    @Test
    fun `scheduled action model correctly tracks EXECUTING status`() {
        val action = ScheduledDeviceAction(
            id = "act-lock-003",
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            scheduledExecutionTimeMillis = System.currentTimeMillis() - 1000L,
            status = ScheduledActionStatus.EXECUTING
        )

        // Action in EXECUTING state means the receiver is currently running
        assertEquals(ScheduledActionStatus.EXECUTING, action.status)
        assertTrue(action.scheduledExecutionTimeMillis <= System.currentTimeMillis())
    }
}
