package com.animus.smartroom.runtime

import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.runtime.AnimusRuntime
import com.animus.smartroom.core.runtime.RuntimeState
import com.animus.smartroom.diagnostics.DiagnosticBus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Android-layer implementation of [AnimusRuntime].
 * Bridges DiagnosticBus 2.0 action events into RuntimeState.
 *
 * Lifecycle:
 *  - Created once in AnimusApplication.
 *  - onStarted() called when AnimusRuntimeService starts.
 *  - onStopped() called when AnimusRuntimeService stops.
 *  - State survives Activity recreation — lives in Application scope.
 */
class AnimusRuntimeImpl : AnimusRuntime {

    private val _state = MutableStateFlow(RuntimeState.IDLE)
    override val state: StateFlow<RuntimeState> = _state.asStateFlow()

    /** Directly backed by DiagnosticBus 2.0 — single source of truth. */
    override val actionEvents: StateFlow<List<AnimusActionEvent>> = DiagnosticBus.actionEvents

    private val _running = AtomicBoolean(false)

    override fun updateState(transform: (RuntimeState) -> RuntimeState) {
        _state.value = transform(_state.value)
    }

    override fun onStarted() {
        if (_running.compareAndSet(false, true)) {
            updateState { it.copy(isRunning = true, lastUpdatedAt = System.currentTimeMillis()) }
            DiagnosticBus.publish {
                create(
                    action = "RUNTIME_STARTED",
                    stage = com.animus.smartroom.core.diagnostics.model.ActionStage.COMPLETED,
                    status = com.animus.smartroom.core.diagnostics.model.ActionStatus.SUCCESS,
                    source = com.animus.smartroom.core.diagnostics.model.ActionSource.SYSTEM,
                    message = "Animus runtime started"
                )
            }
        }
    }

    override fun onStopped() {
        if (_running.compareAndSet(true, false)) {
            updateState { it.copy(isRunning = false, lastUpdatedAt = System.currentTimeMillis()) }
            DiagnosticBus.publish {
                create(
                    action = "RUNTIME_STOPPED",
                    stage = com.animus.smartroom.core.diagnostics.model.ActionStage.COMPLETED,
                    status = com.animus.smartroom.core.diagnostics.model.ActionStatus.SUCCESS,
                    source = com.animus.smartroom.core.diagnostics.model.ActionSource.SYSTEM,
                    message = "Animus runtime stopped"
                )
            }
        }
    }

    /** Sync active action count from scheduler storage into RuntimeState. */
    fun syncActiveActionCount(count: Int) {
        updateState { it.copy(activeActionCount = count, lastUpdatedAt = System.currentTimeMillis()) }
    }

    /** Sync connected device count into RuntimeState. */
    fun syncConnectedDeviceCount(count: Int) {
        updateState { it.copy(connectedDeviceCount = count, lastUpdatedAt = System.currentTimeMillis()) }
    }

    /** Sync active routine count into RuntimeState. */
    fun syncActiveRoutineCount(count: Int) {
        updateState { it.copy(activeRoutineCount = count, lastUpdatedAt = System.currentTimeMillis()) }
    }

    /** Called when a new AnimusActionEvent is published, to update lastActionEventId. */
    fun onActionEvent(event: AnimusActionEvent) {
        updateState { it.copy(lastActionEventId = event.id, lastUpdatedAt = System.currentTimeMillis()) }
    }
}
