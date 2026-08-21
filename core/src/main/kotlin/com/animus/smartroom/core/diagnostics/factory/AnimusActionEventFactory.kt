package com.animus.smartroom.core.diagnostics.factory

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.core.port.Clock
import com.animus.smartroom.core.port.SystemClock
import com.animus.smartroom.device.model.DeviceType
import java.util.UUID

class AnimusActionEventFactory(
    private val clock: Clock = SystemClock()
) {

    fun create(
        id: String = UUID.randomUUID().toString(),
        correlationId: String? = null,
        source: ActionSource,
        targetDevice: DeviceType? = null,
        action: String,
        stage: ActionStage,
        status: ActionStatus,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent {
        return AnimusActionEvent(
            id = id,
            correlationId = correlationId,
            timestamp = clock.currentTimeMillis(),
            source = source,
            targetDevice = targetDevice,
            action = action,
            stage = stage,
            status = status,
            message = EventSanitizer.sanitizeText(message),
            metadata = EventSanitizer.sanitizeMetadata(metadata)
        )
    }

    fun received(
        correlationId: String? = null,
        source: ActionSource = ActionSource.USER_COMMAND,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.RECEIVED,
        status = ActionStatus.PENDING,
        message = message,
        metadata = metadata
    )

    fun precondition(
        correlationId: String? = null,
        source: ActionSource = ActionSource.DEVICE,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.PRECONDITION,
        status = ActionStatus.IN_PROGRESS,
        message = message,
        metadata = metadata
    )

    fun executing(
        correlationId: String? = null,
        source: ActionSource = ActionSource.SYSTEM,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.EXECUTING,
        status = ActionStatus.IN_PROGRESS,
        message = message,
        metadata = metadata
    )

    fun verifying(
        correlationId: String? = null,
        source: ActionSource = ActionSource.DEVICE,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.VERIFYING,
        status = ActionStatus.IN_PROGRESS,
        message = message,
        metadata = metadata
    )

    fun completed(
        correlationId: String? = null,
        source: ActionSource = ActionSource.SYSTEM,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.COMPLETED,
        status = ActionStatus.SUCCESS,
        message = message,
        metadata = metadata
    )

    fun noChange(
        correlationId: String? = null,
        source: ActionSource = ActionSource.DEVICE,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.COMPLETED,
        status = ActionStatus.NO_CHANGE,
        message = message,
        metadata = metadata
    )

    fun failed(
        correlationId: String? = null,
        source: ActionSource = ActionSource.SYSTEM,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.FAILED,
        status = ActionStatus.FAILED,
        message = message,
        metadata = metadata
    )

    fun cancelled(
        correlationId: String? = null,
        source: ActionSource = ActionSource.SYSTEM,
        targetDevice: DeviceType? = null,
        action: String,
        message: String? = null,
        metadata: Map<String, String> = emptyMap()
    ): AnimusActionEvent = create(
        correlationId = correlationId,
        source = source,
        targetDevice = targetDevice,
        action = action,
        stage = ActionStage.CANCELLED,
        status = ActionStatus.CANCELLED,
        message = message,
        metadata = metadata
    )
}
