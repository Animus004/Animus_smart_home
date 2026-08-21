package com.animus.smartroom.overlay

import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.OverlayTimerCard
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TimerCountdownTest {

    @Test
    fun `formattedRemaining produces MM SS when under one hour`() {
        val now = 1000000L
        val target = now + 42 * 60 * 1000L + 18 * 1000L // 42 mins 18 secs

        val timer = OverlayTimerCard(
            actionId = "act-timer-1",
            deviceType = DeviceType.AIR_CONDITIONER,
            actionType = "POWER_OFF",
            targetTimestamp = target
        )

        assertEquals("42:18", timer.formattedRemaining(now))
    }

    @Test
    fun `formattedRemaining produces HH MM SS when over one hour`() {
        val now = 1000000L
        val target = now + 1 * 3600 * 1000L + 42 * 60 * 1000L + 18 * 1000L // 1 hour 42 mins 18 secs

        val timer = OverlayTimerCard(
            actionId = "act-timer-2",
            deviceType = DeviceType.AIR_CONDITIONER,
            actionType = "POWER_OFF",
            targetTimestamp = target
        )

        assertEquals("01:42:18", timer.formattedRemaining(now))
    }

    @Test
    fun `remainingMillis clamps to zero when expired`() {
        val now = 2000000L
        val target = 1000000L // in the past

        val timer = OverlayTimerCard(
            actionId = "act-timer-3",
            deviceType = DeviceType.AIR_CONDITIONER,
            actionType = "POWER_OFF",
            targetTimestamp = target
        )

        assertEquals(0L, timer.remainingMillis(now))
        assertEquals("00:00", timer.formattedRemaining(now))
    }
}
