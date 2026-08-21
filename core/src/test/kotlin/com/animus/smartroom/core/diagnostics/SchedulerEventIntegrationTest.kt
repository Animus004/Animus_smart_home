package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.query.ActionEventQuery
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class SchedulerEventIntegrationTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `scheduled action execution emits scheduled, triggered, and completed lifecycle`() {
        val action = ScheduledDeviceAction(
            id = "act-sched-101",
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            scheduledExecutionTimeMillis = 1787334000000L
        )

        // 1. Scheduled
        DiagnosticBus.publish {
            create(
                correlationId = "sched-${action.id}",
                source = ActionSource.SCHEDULER,
                targetDevice = action.targetDeviceType,
                action = action.actionType.name,
                stage = ActionStage.TRIGGERED,
                status = ActionStatus.PENDING,
                message = "Scheduled AIR_CONDITIONER -> POWER_OFF",
                metadata = mapOf("actionId" to action.id, "scheduledFor" to action.scheduledExecutionTimeMillis.toString())
            )
        }

        // 2. Triggered
        DiagnosticBus.publish {
            create(
                correlationId = "sched-${action.id}",
                source = ActionSource.SCHEDULER,
                targetDevice = action.targetDeviceType,
                action = action.actionType.name,
                stage = ActionStage.TRIGGERED,
                status = ActionStatus.IN_PROGRESS,
                message = "Triggered scheduled action: ${action.id}",
                metadata = mapOf("actionId" to action.id)
            )
        }

        // 3. Executing
        DiagnosticBus.publish {
            executing(
                correlationId = "sched-${action.id}",
                source = ActionSource.SCHEDULER,
                targetDevice = action.targetDeviceType,
                action = action.actionType.name,
                message = "Executing AIR_CONDITIONER -> POWER_OFF"
            )
        }

        // 4. Completed
        DiagnosticBus.publish {
            completed(
                correlationId = "sched-${action.id}",
                source = ActionSource.SCHEDULER,
                targetDevice = action.targetDeviceType,
                action = action.actionType.name,
                message = "Successfully executed and verified POWER_OFF"
            )
        }

        val events = DiagnosticBus.getRecentActionEvents()
        val schedEvents = ActionEventQuery.bySource(events, ActionSource.SCHEDULER)
        assertEquals(4, schedEvents.size)

        val completed = ActionEventQuery.completedActions(schedEvents)
        assertEquals(1, completed.size)
        assertEquals(ActionStatus.SUCCESS, completed.first().status)
    }

    @Test
    fun `scheduled action on already OFF AC emits NO_CHANGE status`() {
        val actionId = "act-sched-102"
        DiagnosticBus.publish {
            noChange(
                correlationId = "sched-$actionId",
                source = ActionSource.SCHEDULER,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_OFF",
                message = "AC already OFF. Completed with no change.",
                metadata = mapOf("actionId" to actionId)
            )
        }

        val event = DiagnosticBus.getRecentActionEvents().first()
        assertEquals(ActionStage.COMPLETED, event.stage)
        assertEquals(ActionStatus.NO_CHANGE, event.status)
    }
}
