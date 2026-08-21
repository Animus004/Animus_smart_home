package com.animus.smartroom.core.port

/**
 * Platform-independent time and clock interface.
 */
interface Clock {
    fun currentTimeMillis(): Long
    fun timeZoneId(): String
}
