package com.animus.smartroom.core.diagnostics.query

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType

/**
 * Pure JVM query and filtering utilities over streams of AnimusActionEvent.
 */
object ActionEventQuery {

    fun byCorrelationId(events: List<AnimusActionEvent>, correlationId: String): List<AnimusActionEvent> {
        return events.filter { it.correlationId == correlationId }
    }

    fun byStatus(events: List<AnimusActionEvent>, status: ActionStatus): List<AnimusActionEvent> {
        return events.filter { it.status == status }
    }

    fun byStage(events: List<AnimusActionEvent>, stage: ActionStage): List<AnimusActionEvent> {
        return events.filter { it.stage == stage }
    }

    fun bySource(events: List<AnimusActionEvent>, source: ActionSource): List<AnimusActionEvent> {
        return events.filter { it.source == source }
    }

    fun byDevice(events: List<AnimusActionEvent>, deviceType: DeviceType): List<AnimusActionEvent> {
        return events.filter { it.targetDevice == deviceType }
    }

    fun activeActions(events: List<AnimusActionEvent>): List<AnimusActionEvent> {
        return events.filter { it.status == ActionStatus.IN_PROGRESS || it.status == ActionStatus.PENDING }
    }

    fun completedActions(events: List<AnimusActionEvent>): List<AnimusActionEvent> {
        return events.filter { it.status == ActionStatus.SUCCESS || it.status == ActionStatus.NO_CHANGE }
    }

    fun failedActions(events: List<AnimusActionEvent>): List<AnimusActionEvent> {
        return events.filter { it.status == ActionStatus.FAILED }
    }

    fun currentAction(events: List<AnimusActionEvent>): AnimusActionEvent? {
        return events.lastOrNull { it.status == ActionStatus.IN_PROGRESS }
            ?: events.lastOrNull()
    }
}
