package com.animus.smartroom.core.port

import org.junit.Assert.assertEquals
import org.junit.Test

class ClockTest {

    @Test
    fun `AndroidClock returns system time and default Asia Kolkata timezone`() {
        val clock = AndroidClock()
        val before = System.currentTimeMillis()
        val clockTime = clock.currentTimeMillis()
        val after = System.currentTimeMillis()

        assert(clockTime in before..after)
        assertEquals("Asia/Kolkata", clock.timeZoneId())
    }

    @Test
    fun `FakeClock allows deterministic time progression`() {
        val fakeClock = FakeClock(currentTime = 1000L, timeZone = "Asia/Kolkata")
        assertEquals(1000L, fakeClock.currentTimeMillis())
        assertEquals("Asia/Kolkata", fakeClock.timeZoneId())

        fakeClock.advanceTime(5000L)
        assertEquals(6000L, fakeClock.currentTimeMillis())

        fakeClock.setTime(20000L)
        assertEquals(20000L, fakeClock.currentTimeMillis())

        fakeClock.setTimeZone("UTC")
        assertEquals("UTC", fakeClock.timeZoneId())
    }
}
