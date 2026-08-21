package com.animus.smartroom.diagnostics

import com.animus.smartroom.core.diagnostics.factory.AnimusActionEventFactory
import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.device.model.DeviceType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.ArrayDeque
import java.util.Date
import java.util.Locale
import java.util.UUID

enum class DiagnosticStage {
    REQUESTED,
    VALIDATING,
    RESOLVING,
    SEARCH,
    SCORING,
    SELECTED,
    CACHED,
    INTENT,
    PLAYBACK,
    INVALIDATED,
    SCHEDULED,
    PRECONDITION,
    EXECUTING,
    DEVICE_RESPONSE,
    VERIFYING,
    STATE,
    SNAPSHOT,
    SPEAKER,
    MUSIC,
    VOLUME,
    AC,
    SCHEDULER,
    PERSISTED,
    TRIGGERED,
    ALARM,
    NOTIFICATION,
    STOP_REQUESTED,
    COMPLETED,
    FAILED
}

data class DiagnosticEvent(
    val timestamp: Long = System.currentTimeMillis(),
    val tag: String,
    val stage: DiagnosticStage,
    val message: String,
    val details: Map<String, Any?> = emptyMap()
) {
    val formattedTime: String
        get() {
            val sdf = SimpleDateFormat("HH:mm:ss.SSS", Locale.ROOT)
            return sdf.format(Date(timestamp))
        }

    val displayString: String
        get() = "$formattedTime [$tag] [${stage.name}] $message"
}

/**
 * DiagnosticBus 2.0: Thread-safe, reactive event bus for both structured AnimusActionEvent
 * and legacy DiagnosticEvent, with bounded memory and zero-credential guarantees.
 */
object DiagnosticBus {
    private const val MAX_ACTION_CAPACITY = 500
    private const val MAX_LEGACY_CAPACITY = 100

    private val actionBuffer = ArrayDeque<AnimusActionEvent>(MAX_ACTION_CAPACITY)
    private val _actionEvents = MutableStateFlow<List<AnimusActionEvent>>(emptyList())
    val actionEvents: StateFlow<List<AnimusActionEvent>> = _actionEvents.asStateFlow()

    private val legacyBuffer = ArrayDeque<DiagnosticEvent>(MAX_LEGACY_CAPACITY)
    private val _eventsFlow = MutableStateFlow<List<DiagnosticEvent>>(emptyList())
    val eventsFlow: StateFlow<List<DiagnosticEvent>> = _eventsFlow.asStateFlow()

    val factory = AnimusActionEventFactory()

    var logSink: ((tag: String, stage: DiagnosticStage, message: String) -> Unit)? = null

    @Synchronized
    fun publish(event: AnimusActionEvent): AnimusActionEvent {
        val sanitizedEvent = if (event.message != null || event.metadata.isNotEmpty()) {
            event.copy(
                message = EventSanitizer.sanitizeText(event.message),
                metadata = EventSanitizer.sanitizeMetadata(event.metadata)
            )
        } else {
            event
        }

        if (actionBuffer.size >= MAX_ACTION_CAPACITY) {
            actionBuffer.pollFirst()
        }
        actionBuffer.offerLast(sanitizedEvent)
        _actionEvents.value = actionBuffer.toList()

        return sanitizedEvent
    }

    fun publish(builder: AnimusActionEventFactory.() -> AnimusActionEvent): AnimusActionEvent {
        val event = factory.builder()
        return publish(event)
    }

    @Synchronized
    fun log(
        tag: String,
        stage: DiagnosticStage,
        message: String,
        details: Map<String, Any?> = emptyMap()
    ): DiagnosticEvent {
        val sanitizedMsg = EventSanitizer.sanitizeText(message) ?: message
        val event = DiagnosticEvent(
            timestamp = System.currentTimeMillis(),
            tag = tag,
            stage = stage,
            message = sanitizedMsg,
            details = details
        )

        logSink?.invoke(tag, stage, sanitizedMsg)

        if (legacyBuffer.size >= MAX_LEGACY_CAPACITY) {
            legacyBuffer.pollFirst()
        }
        legacyBuffer.offerLast(event)
        _eventsFlow.value = legacyBuffer.toList()

        // Bridge to structured action event
        val (actionStage, actionStatus) = mapLegacyStage(stage)
        val source = when (tag.lowercase()) {
            "scheduler" -> ActionSource.SCHEDULER
            "routine" -> ActionSource.ROUTINE
            "brain" -> ActionSource.BRAIN
            "music", "audio", "bt" -> ActionSource.MUSIC
            "ac" -> ActionSource.DEVICE
            else -> ActionSource.SYSTEM
        }
        val targetDevice = when (tag.lowercase()) {
            "ac" -> DeviceType.AIR_CONDITIONER
            "music", "audio", "bt", "speaker" -> DeviceType.BLUETOOTH_AUDIO
            else -> null
        }

        val metadata = mutableMapOf<String, String>()
        details.forEach { (k, v) ->
            if (v != null) metadata[k] = v.toString()
        }

        val actionEvent = AnimusActionEvent(
            id = UUID.randomUUID().toString(),
            timestamp = event.timestamp,
            source = source,
            targetDevice = targetDevice,
            action = tag.uppercase(),
            stage = actionStage,
            status = actionStatus,
            message = sanitizedMsg,
            metadata = EventSanitizer.sanitizeMetadata(metadata)
        )

        if (actionBuffer.size >= MAX_ACTION_CAPACITY) {
            actionBuffer.pollFirst()
        }
        actionBuffer.offerLast(actionEvent)
        _actionEvents.value = actionBuffer.toList()

        return event
    }

    private fun mapLegacyStage(stage: DiagnosticStage): Pair<ActionStage, ActionStatus> {
        return when (stage) {
            DiagnosticStage.REQUESTED -> ActionStage.RECEIVED to ActionStatus.PENDING
            DiagnosticStage.VALIDATING -> ActionStage.PARSING to ActionStatus.IN_PROGRESS
            DiagnosticStage.RESOLVING, DiagnosticStage.SEARCH, DiagnosticStage.SCORING,
            DiagnosticStage.SELECTED, DiagnosticStage.CACHED, DiagnosticStage.INTENT ->
                ActionStage.RESOLVING to ActionStatus.IN_PROGRESS
            DiagnosticStage.PRECONDITION -> ActionStage.PRECONDITION to ActionStatus.IN_PROGRESS
            DiagnosticStage.SCHEDULED -> ActionStage.TRIGGERED to ActionStatus.PENDING
            DiagnosticStage.TRIGGERED -> ActionStage.TRIGGERED to ActionStatus.IN_PROGRESS
            DiagnosticStage.EXECUTING, DiagnosticStage.PLAYBACK, DiagnosticStage.DEVICE_RESPONSE,
            DiagnosticStage.STATE, DiagnosticStage.SNAPSHOT, DiagnosticStage.SPEAKER,
            DiagnosticStage.MUSIC, DiagnosticStage.VOLUME, DiagnosticStage.AC,
            DiagnosticStage.SCHEDULER, DiagnosticStage.PERSISTED, DiagnosticStage.ALARM,
            DiagnosticStage.NOTIFICATION ->
                ActionStage.EXECUTING to ActionStatus.IN_PROGRESS
            DiagnosticStage.VERIFYING -> ActionStage.VERIFYING to ActionStatus.IN_PROGRESS
            DiagnosticStage.COMPLETED -> ActionStage.COMPLETED to ActionStatus.SUCCESS
            DiagnosticStage.FAILED, DiagnosticStage.INVALIDATED -> ActionStage.FAILED to ActionStatus.FAILED
            DiagnosticStage.STOP_REQUESTED -> ActionStage.CANCELLED to ActionStatus.CANCELLED
        }
    }

    @Synchronized
    fun getRecentActionEvents(): List<AnimusActionEvent> {
        return actionBuffer.toList()
    }

    @Synchronized
    fun getRecentEvents(): List<DiagnosticEvent> {
        return legacyBuffer.toList()
    }

    @Synchronized
    fun clear() {
        actionBuffer.clear()
        legacyBuffer.clear()
        _actionEvents.value = emptyList()
        _eventsFlow.value = emptyList()
    }
}
