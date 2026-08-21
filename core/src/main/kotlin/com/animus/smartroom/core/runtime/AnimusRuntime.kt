package com.animus.smartroom.core.runtime

import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import kotlinx.coroutines.flow.StateFlow

/**
 * Pure JVM runtime interface. No Android dependencies.
 * The Android implementation lives in :app as AnimusRuntimeImpl.
 * Future PC/Web hosts may provide alternative implementations.
 */
interface AnimusRuntime {
    /** Current runtime state snapshot. */
    val state: StateFlow<RuntimeState>

    /** Structured action event stream from DiagnosticBus 2.0. */
    val actionEvents: StateFlow<List<AnimusActionEvent>>

    /** Apply a state transformation. Thread-safe. */
    fun updateState(transform: (RuntimeState) -> RuntimeState)

    /** Mark runtime as started and notify observers. */
    fun onStarted()

    /** Mark runtime as stopped and notify observers. */
    fun onStopped()
}
