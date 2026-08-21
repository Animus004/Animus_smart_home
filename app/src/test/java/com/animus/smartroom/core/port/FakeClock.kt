package com.animus.smartroom.core.port

/**
 * Deterministic test implementation of [Clock].
 */
class FakeClock(
    private var currentTime: Long = 0L,
    private var timeZone: String = "Asia/Kolkata"
) : Clock {

    override fun currentTimeMillis(): Long = currentTime
    override fun timeZoneId(): String = timeZone

    fun setTime(millis: Long) {
        currentTime = millis
    }

    fun advanceTime(millis: Long) {
        currentTime += millis
    }

    fun setTimeZone(tz: String) {
        timeZone = tz
    }
}
