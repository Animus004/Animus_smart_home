package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.diagnostics.query.ActionEventQuery
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors

class DiagnosticBusTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `publish updates StateFlow and preserves bounded ring buffer`() {
        // Publish 550 events (buffer limit is 500)
        for (i in 1..550) {
            DiagnosticBus.publish {
                create(
                    id = "evt-$i",
                    source = ActionSource.SYSTEM,
                    action = "TEST_ACTION",
                    stage = ActionStage.EXECUTING,
                    status = ActionStatus.IN_PROGRESS,
                    message = "Event number $i"
                )
            }
        }

        val actionEvents = DiagnosticBus.getRecentActionEvents()
        assertEquals(500, actionEvents.size)
        // First event in buffer should now be evt-51 (first 50 evicted)
        assertEquals("evt-51", actionEvents.first().id)
        assertEquals("evt-550", actionEvents.last().id)
        assertEquals(500, DiagnosticBus.actionEvents.value.size)
    }

    @Test
    fun `legacy log seamlessly updates both legacy flow and structured action events`() {
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.PRECONDITION,
            message = "AC is OFF, turning on first",
            details = mapOf("temp" to 24)
        )

        val legacyEvents = DiagnosticBus.getRecentEvents()
        assertEquals(1, legacyEvents.size)
        assertEquals("ac", legacyEvents.first().tag)
        assertEquals(DiagnosticStage.PRECONDITION, legacyEvents.first().stage)

        val actionEvents = DiagnosticBus.getRecentActionEvents()
        assertEquals(1, actionEvents.size)
        val action = actionEvents.first()
        assertEquals(ActionSource.DEVICE, action.source)
        assertEquals(DeviceType.AIR_CONDITIONER, action.targetDevice)
        assertEquals(ActionStage.PRECONDITION, action.stage)
        assertEquals(ActionStatus.IN_PROGRESS, action.status)
        assertEquals("AC is OFF, turning on first", action.message)
    }

    @Test
    fun `concurrent publishers do not corrupt buffer or drop events within capacity`() {
        val threads = 10
        val eventsPerThread = 30
        val executor = Executors.newFixedThreadPool(threads)
        val latch = CountDownLatch(threads)

        for (t in 0 until threads) {
            executor.submit {
                try {
                    for (i in 0 until eventsPerThread) {
                        DiagnosticBus.publish {
                            create(
                                id = "th-$t-ev-$i",
                                source = ActionSource.SYSTEM,
                                action = "CONCURRENT_ACTION",
                                stage = ActionStage.EXECUTING,
                                status = ActionStatus.IN_PROGRESS
                            )
                        }
                    }
                } finally {
                    latch.countDown()
                }
            }
        }

        latch.await()
        executor.shutdown()

        val recent = DiagnosticBus.getRecentActionEvents()
        assertEquals(threads * eventsPerThread, recent.size)
    }

    @Test
    fun `ActionEventQuery filters events accurately`() {
        DiagnosticBus.publish {
            create(
                correlationId = "corr-100",
                source = ActionSource.USER_COMMAND,
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMP",
                stage = ActionStage.COMPLETED,
                status = ActionStatus.SUCCESS
            )
        }
        DiagnosticBus.publish {
            create(
                correlationId = "corr-100",
                source = ActionSource.USER_COMMAND,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "PLAY",
                stage = ActionStage.FAILED,
                status = ActionStatus.FAILED
            )
        }

        val all = DiagnosticBus.getRecentActionEvents()
        val corrEvents = ActionEventQuery.byCorrelationId(all, "corr-100")
        assertEquals(2, corrEvents.size)

        val completed = ActionEventQuery.completedActions(all)
        assertEquals(1, completed.size)
        assertEquals(DeviceType.AIR_CONDITIONER, completed.first().targetDevice)

        val failed = ActionEventQuery.failedActions(all)
        assertEquals(1, failed.size)
        assertEquals(DeviceType.BLUETOOTH_AUDIO, failed.first().targetDevice)
    }
}
