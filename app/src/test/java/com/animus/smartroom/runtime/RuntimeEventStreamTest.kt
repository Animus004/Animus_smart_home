package com.animus.smartroom.runtime

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.query.ActionEventQuery
import com.animus.smartroom.core.runtime.RuntimeState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Verifies that DiagnosticBus 2.0 actionEvents correctly drives RuntimeState
 * via the runtime interface contract. Tests ordering, correlation preservation,
 * and multi-source event coexistence.
 */
class RuntimeEventStreamTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `action events flow is the single source of truth`() {
        val runtime = AnimusRuntimeImpl()
        // The runtime's actionEvents must be the exact same reference as DiagnosticBus
        assertTrue(runtime.actionEvents === DiagnosticBus.actionEvents)
    }

    @Test
    fun `events are ordered chronologically by arrival`() {
        val corrId = "stream-test-1"

        DiagnosticBus.publish { received(correlationId = corrId, action = "SET_TEMPERATURE") }
        DiagnosticBus.publish { executing(correlationId = corrId, action = "SET_TEMPERATURE") }
        DiagnosticBus.publish { completed(correlationId = corrId, action = "SET_TEMPERATURE") }

        val events = DiagnosticBus.getRecentActionEvents()
        assertEquals(3, events.size)
        assertEquals(ActionStage.RECEIVED, events[0].stage)
        assertEquals(ActionStage.EXECUTING, events[1].stage)
        assertEquals(ActionStage.COMPLETED, events[2].stage)
    }

    @Test
    fun `correlation is preserved across multi-source event stream`() {
        val corrId = "multi-source-1"

        DiagnosticBus.publish {
            received(
                correlationId = corrId,
                source = ActionSource.USER_COMMAND,
                action = "MULTI_COMMAND"
            )
        }
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                source = ActionSource.SYSTEM,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE"
            )
        }
        DiagnosticBus.publish {
            executing(
                correlationId = corrId,
                source = ActionSource.MUSIC,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "PLAY_MUSIC"
            )
        }

        val correlated = ActionEventQuery.byCorrelationId(
            DiagnosticBus.getRecentActionEvents(), corrId
        )
        assertEquals(3, correlated.size)
        assertTrue(correlated.map { it.source }.containsAll(
            listOf(ActionSource.USER_COMMAND, ActionSource.SYSTEM, ActionSource.MUSIC)
        ))
    }

    @Test
    fun `RuntimeState updates after onStarted reflect in state flow`() {
        val runtime = AnimusRuntimeImpl()
        assertEquals(RuntimeState.IDLE, runtime.state.value)

        runtime.onStarted()
        assertTrue(runtime.state.value.isRunning)
        assertTrue(runtime.state.value.lastUpdatedAt > 0L)
    }

    @Test
    fun `syncActiveActionCount updates RuntimeState without touching isRunning`() {
        val runtime = AnimusRuntimeImpl()
        runtime.onStarted()
        runtime.syncActiveActionCount(3)

        assertEquals(3, runtime.state.value.activeActionCount)
        assertTrue(runtime.state.value.isRunning) // unchanged
    }

    @Test
    fun `onActionEvent updates lastActionEventId in RuntimeState`() {
        val runtime = AnimusRuntimeImpl()

        DiagnosticBus.publish {
            completed(
                correlationId = "corr-xyz",
                action = "POWER_OFF",
                source = ActionSource.SCHEDULER,
                targetDevice = DeviceType.AIR_CONDITIONER,
                message = "AC turned off"
            )
        }

        val latestEvent = DiagnosticBus.getRecentActionEvents().lastOrNull()
        assertNotNull(latestEvent)
        runtime.onActionEvent(latestEvent!!)

        assertEquals(latestEvent.id, runtime.state.value.lastActionEventId)
    }
}
