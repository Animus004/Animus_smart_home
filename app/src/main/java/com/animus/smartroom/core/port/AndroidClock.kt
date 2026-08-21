package com.animus.smartroom.core.port

import com.animus.smartroom.context.HomeLocationContext

/**
 * Android system clock implementation of [Clock].
 * Default timezone is set to HomeLocationContext (Asia/Kolkata).
 */
class AndroidClock(
    private val timeZone: String = HomeLocationContext.getLocation().timeZone
) : Clock {
    override fun currentTimeMillis(): Long = System.currentTimeMillis()
    override fun timeZoneId(): String = timeZone
}
