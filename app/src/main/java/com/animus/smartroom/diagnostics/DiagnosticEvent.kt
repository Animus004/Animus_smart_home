package com.animus.smartroom.diagnostics

import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.ArrayDeque
import java.util.Date
import java.util.Locale

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
            val sdf = SimpleDateFormat("HH:mm:ss.SSS", Locale.getDefault())
            return sdf.format(Date(timestamp))
        }

    val displayString: String
        get() = "$formattedTime [$tag] [${stage.name}] $message"
}

object DiagnosticBus {
    private const val MAX_CAPACITY = 100
    private val buffer = ArrayDeque<DiagnosticEvent>(MAX_CAPACITY)
    private val _eventsFlow = MutableStateFlow<List<DiagnosticEvent>>(emptyList())
    val eventsFlow: StateFlow<List<DiagnosticEvent>> = _eventsFlow.asStateFlow()

    @Synchronized
    fun log(
        tag: String,
        stage: DiagnosticStage,
        message: String,
        details: Map<String, Any?> = emptyMap()
    ): DiagnosticEvent {
        val event = DiagnosticEvent(
            timestamp = System.currentTimeMillis(),
            tag = tag,
            stage = stage,
            message = message,
            details = details
        )

        // Log to Android Logcat
        when (stage) {
            DiagnosticStage.FAILED -> Log.e(tag, "[${stage.name}] $message")
            else -> Log.i(tag, "[${stage.name}] $message")
        }

        // Store in bounded ring buffer
        if (buffer.size >= MAX_CAPACITY) {
            buffer.pollFirst()
        }
        buffer.offerLast(event)
        _eventsFlow.value = buffer.toList()

        return event
    }

    @Synchronized
    fun getRecentEvents(): List<DiagnosticEvent> {
        return buffer.toList()
    }

    @Synchronized
    fun clear() {
        buffer.clear()
        _eventsFlow.value = emptyList()
    }
}
