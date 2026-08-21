package com.animus.smartroom.diagnostics

import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class DiagnosticBusTest {

    @Before
    fun setUp() {
        DiagnosticBus.clear()
    }

    @Test
    fun testEventLoggingAndRetrieval() {
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.REQUESTED,
            message = "Set temperature = 24°C"
        )

        val events = DiagnosticBus.getRecentEvents()
        assertEquals(1, events.size)
        assertEquals("ac", events[0].tag)
        assertEquals(DiagnosticStage.REQUESTED, events[0].stage)
        assertEquals("Set temperature = 24°C", events[0].message)
    }

    @Test
    fun testRingBufferCapacityLimit() {
        for (i in 1..120) {
            DiagnosticBus.log(
                tag = "test",
                stage = DiagnosticStage.EXECUTING,
                message = "Event $i"
            )
        }

        val events = DiagnosticBus.getRecentEvents()
        assertEquals(100, events.size)
        assertEquals("Event 21", events[0].message)
        assertEquals("Event 120", events[99].message)
    }

    @Test
    fun testClearBuffer() {
        DiagnosticBus.log("test", DiagnosticStage.REQUESTED, "Test")
        assertEquals(1, DiagnosticBus.getRecentEvents().size)
        DiagnosticBus.clear()
        assertTrue(DiagnosticBus.getRecentEvents().isEmpty())
    }
}
