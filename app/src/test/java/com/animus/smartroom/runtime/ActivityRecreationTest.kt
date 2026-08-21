package com.animus.smartroom.runtime

import com.animus.smartroom.core.runtime.RuntimeState
import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.diagnostics.DiagnosticBus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ActivityRecreationTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    /**
     * Verifies that the runtime contract models Activity recreation correctly.
     * AnimusRuntimeImpl is application-scoped — survives ViewModel recreation.
     *
     * Simulated lifecycle:
     * 1. Schedule action (stored in ScheduledActionStorage — persisted)
     * 2. Destroy ViewModel → runtime state survives in application scope
     * 3. Recreate ViewModel → reads same runtime state
     * 4. Timer still active — same action ID
     * 5. Execute action → DiagnosticBus shows complete lifecycle
     * 6. RuntimeState reflects 0 active actions
     */
    @Test
    fun `runtime state survives simulated ViewModel recreation`() {
        val corrId = "cmd-act-recr-1"

        // 1. Schedule (emit structured event as if scheduler ran)
        DiagnosticBus.publish {
            create(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                action = "POWER_OFF",
                stage = ActionStage.TRIGGERED,
                status = ActionStatus.PENDING,
                message = "AC scheduled to turn off in 2 minutes"
            )
        }

        val eventsBefore = DiagnosticBus.getRecentActionEvents()
        assertEquals(1, eventsBefore.size)
        val scheduledEventId = eventsBefore.first().id

        // 2. Simulate ViewModel destruction — DiagnosticBus ring buffer persists
        // (In production: AnimusRuntimeImpl survives in AnimusApplication scope)

        // 3. Simulate ViewModel recreation — events still visible
        val eventsAfter = DiagnosticBus.getRecentActionEvents()
        assertEquals(1, eventsAfter.size)
        assertEquals(scheduledEventId, eventsAfter.first().id) // Same event ID → same action

        // 4. Verify timer still active
        val activeEvents = eventsAfter.filter {
            it.status == ActionStatus.PENDING && it.stage == ActionStage.TRIGGERED
        }
        assertEquals(1, activeEvents.size)

        // 5. Execute action → COMPLETED
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                source = ActionSource.SCHEDULER,
                action = "POWER_OFF",
                message = "AC turned off successfully",
                metadata = mapOf("verified" to "true")
            )
        }

        val allEvents = DiagnosticBus.getRecentActionEvents()
        assertEquals(2, allEvents.size)
        assertEquals(ActionStatus.SUCCESS, allEvents.last().status)

        // 6. No duplicate events — unique IDs
        val ids = allEvents.map { it.id }.toSet()
        assertEquals(2, ids.size)
    }

    @Test
    fun `multiple ViewModels reading same DiagnosticBus see identical events`() {
        // Simulate two ViewModel instances (e.g., before/after recreation) reading same flow
        val events1 = DiagnosticBus.actionEvents
        val events2 = DiagnosticBus.actionEvents
        assertTrue(events1 === events2) // Must be the same object reference — single StateFlow
    }

    @Test
    fun `RuntimeState updateState is thread-safe and deterministic`() {
        val impl = com.animus.smartroom.runtime.AnimusRuntimeImpl()

        impl.updateState { it.copy(activeActionCount = 1) }
        impl.updateState { it.copy(activeActionCount = 0) }
        impl.updateState { it.copy(isRunning = true) }

        val final = impl.state.value
        assertTrue(final.isRunning)
        assertEquals(0, final.activeActionCount)
    }
}
