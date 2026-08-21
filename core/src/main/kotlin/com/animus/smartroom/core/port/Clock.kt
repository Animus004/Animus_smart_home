package com.animus.smartroom.core.port

import java.util.TimeZone

/**
 * Platform-independent time and clock interface.
 */
interface Clock {
    fun currentTimeMillis(): Long
    fun timeZoneId(): String
}

class SystemClock(
    private val tzId: String = TimeZone.getDefault().id
) : Clock {
    override fun currentTimeMillis(): Long = System.currentTimeMillis()
    override fun timeZoneId(): String = tzId
}
