package com.animus.smartroom.core.runtime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RuntimeStateTest {

    @Test
    fun `IDLE state has expected defaults`() {
        val state = RuntimeState.IDLE
        assertFalse(state.isRunning)
        assertEquals(0, state.activeActionCount)
        assertEquals(0, state.activeRoutineCount)
        assertEquals(0, state.connectedDeviceCount)
        assertNull(state.lastActionEventId)
        assertEquals(0L, state.lastUpdatedAt)
    }

    @Test
    fun `state transitions preserve other fields`() {
        val state = RuntimeState(
            isRunning = true,
            activeActionCount = 2,
            activeRoutineCount = 1,
            connectedDeviceCount = 3,
            lastActionEventId = "evt-001",
            lastUpdatedAt = 1000L
        )

        val updated = state.copy(activeActionCount = 0, lastUpdatedAt = 2000L)

        assertTrue(updated.isRunning)
        assertEquals(0, updated.activeActionCount)
        assertEquals(1, updated.activeRoutineCount)
        assertEquals(3, updated.connectedDeviceCount)
        assertEquals("evt-001", updated.lastActionEventId)
        assertEquals(2000L, updated.lastUpdatedAt)
    }

    @Test
    fun `timestamp updates produce distinct states`() {
        val t1 = RuntimeState(isRunning = true, lastUpdatedAt = 1000L)
        val t2 = t1.copy(lastUpdatedAt = 2000L)

        assertTrue(t1 != t2)
        assertEquals(1000L, t1.lastUpdatedAt)
        assertEquals(2000L, t2.lastUpdatedAt)
    }

    @Test
    fun `lastActionEventId can be set and cleared`() {
        val state = RuntimeState.IDLE.copy(lastActionEventId = "evt-abc")
        assertEquals("evt-abc", state.lastActionEventId)

        val cleared = state.copy(lastActionEventId = null)
        assertNull(cleared.lastActionEventId)
    }

    @Test
    fun `RuntimeState is a value type — structural equality`() {
        val a = RuntimeState(isRunning = true, activeActionCount = 1, lastUpdatedAt = 1000L)
        val b = RuntimeState(isRunning = true, activeActionCount = 1, lastUpdatedAt = 1000L)
        assertEquals(a, b)
        assertEquals(a.hashCode(), b.hashCode())
    }
}
