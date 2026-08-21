package com.animus.smartroom.core.runtime

import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.diagnostics.DiagnosticBus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Tests for AnimusRuntime lifecycle contract using a pure-JVM stub.
 * Does not depend on AnimusRuntimeImpl (Android), only the interface contract.
 */
class RuntimeLifecycleTest {

    /** Pure JVM test double for AnimusRuntime. */
    private class TestRuntime : AnimusRuntime {
        private val _state = MutableStateFlow(RuntimeState.IDLE)
        override val state: StateFlow<RuntimeState> = _state
        override val actionEvents: StateFlow<List<AnimusActionEvent>> = DiagnosticBus.actionEvents

        var startCount = 0
        var stopCount = 0

        override fun updateState(transform: (RuntimeState) -> RuntimeState) {
            _state.value = transform(_state.value)
        }

        override fun onStarted() {
            startCount++
            updateState { it.copy(isRunning = true, lastUpdatedAt = 1000L) }
        }

        override fun onStopped() {
            stopCount++
            updateState { it.copy(isRunning = false, lastUpdatedAt = 2000L) }
        }
    }

    private lateinit var runtime: TestRuntime

    @Before
    fun setup() {
        DiagnosticBus.clear()
        runtime = TestRuntime()
    }

    @Test
    fun `initial runtime state is IDLE`() {
        assertEquals(RuntimeState.IDLE, runtime.state.value)
        assertFalse(runtime.state.value.isRunning)
    }

    @Test
    fun `onStarted transitions state to running`() {
        runtime.onStarted()
        assertTrue(runtime.state.value.isRunning)
        assertEquals(1000L, runtime.state.value.lastUpdatedAt)
    }

    @Test
    fun `onStopped transitions state to not running`() {
        runtime.onStarted()
        runtime.onStopped()
        assertFalse(runtime.state.value.isRunning)
        assertEquals(2000L, runtime.state.value.lastUpdatedAt)
    }

    @Test
    fun `repeated onStarted calls are handled gracefully`() {
        runtime.onStarted()
        runtime.onStarted()
        runtime.onStarted()
        // State should still be running
        assertTrue(runtime.state.value.isRunning)
    }

    @Test
    fun `repeated onStopped calls are handled gracefully`() {
        runtime.onStarted()
        runtime.onStopped()
        runtime.onStopped()
        runtime.onStopped()
        assertFalse(runtime.state.value.isRunning)
    }

    @Test
    fun `start-stop-start cycle works correctly`() {
        runtime.onStarted()
        assertTrue(runtime.state.value.isRunning)

        runtime.onStopped()
        assertFalse(runtime.state.value.isRunning)

        runtime.onStarted()
        assertTrue(runtime.state.value.isRunning)
    }

    @Test
    fun `updateState applies transformation correctly`() {
        runtime.updateState { it.copy(activeActionCount = 5, connectedDeviceCount = 2) }
        assertEquals(5, runtime.state.value.activeActionCount)
        assertEquals(2, runtime.state.value.connectedDeviceCount)
        assertFalse(runtime.state.value.isRunning)
    }

    @Test
    fun `actionEvents backed by DiagnosticBus 2_0`() {
        // Verify the contract — actionEvents must be the DiagnosticBus.actionEvents StateFlow
        assertEquals(DiagnosticBus.actionEvents, runtime.actionEvents)
    }
}
