package com.animus.smartroom.core.port

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.animus.smartroom.MainActivity
import com.animus.smartroom.routine.receiver.SleepWakeReceiver

/**
 * Android implementation of [NotificationPort] managing notification channels, high-priority alarm banners, and stop actions.
 */
class AndroidNotificationPort(
    private val context: Context
) : NotificationPort {

    companion object {
        private const val CHANNEL_ID = "animus_routine_wake_channel"
        private const val CHANNEL_NAME = "Sleep Mode Wake-up"
    }

    private val notificationManager: NotificationManager? =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager

    init {
        createChannel()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Wakes user up when Sleep Mode timer completes"
                enableVibration(true)
                setSound(null, null) // Audio is handled via AlarmSoundPlayer
            }
            notificationManager?.createNotificationChannel(channel)
        }
    }

    override fun postAlarmNotification(
        notificationId: Int,
        title: String,
        message: String,
        stopActionTitle: String
    ) {
        val tapIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val tapPendingIntent = PendingIntent.getActivity(
            context,
            0,
            tapIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = Intent(context, SleepWakeReceiver::class.java).apply {
            action = SleepWakeReceiver.ACTION_STOP_ALARM
        }
        val stopPendingIntent = PendingIntent.getBroadcast(
            context,
            1,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(title)
            .setContentText(message)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(tapPendingIntent)
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                stopActionTitle,
                stopPendingIntent
            )
            .build()

        notificationManager?.notify(notificationId, notification)
    }

    override fun cancelNotification(notificationId: Int) {
        notificationManager?.cancel(notificationId)
    }
}
