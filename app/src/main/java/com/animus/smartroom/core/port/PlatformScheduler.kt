package com.animus.smartroom.core.port

/**
 * Platform-independent exact timer & scheduling interface.
 */
interface PlatformScheduler {
    fun armExact(
        actionId: String,
        triggerAtMillis: Long,
        metadataJson: String = ""
    )

    fun disarm(actionId: String)
}
