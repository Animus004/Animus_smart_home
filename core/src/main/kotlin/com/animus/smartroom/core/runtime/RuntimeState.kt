package com.animus.smartroom.core.runtime

/**
 * Pure JVM immutable runtime state snapshot.
 * No Android dependencies. Safe to use in :core tests.
 */
data class RuntimeState(
    val isRunning: Boolean = false,
    val activeActionCount: Int = 0,
    val activeRoutineCount: Int = 0,
    val connectedDeviceCount: Int = 0,
    val lastActionEventId: String? = null,
    val lastUpdatedAt: Long = 0L
) {
    companion object {
        val IDLE = RuntimeState()
    }
}
