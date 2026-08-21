package com.animus.smartroom.core.port

import org.junit.Assert.assertEquals
import org.junit.Test

class ClockTest {

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
