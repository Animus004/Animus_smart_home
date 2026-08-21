package com.animus.smartroom.core.port

/**
 * Platform-independent user notification port interface.
 */
interface NotificationPort {
    fun postAlarmNotification(
        notificationId: Int,
        title: String,
        message: String,
        stopActionTitle: String = "Stop Alarm"
    )

    fun cancelNotification(notificationId: Int)
}
