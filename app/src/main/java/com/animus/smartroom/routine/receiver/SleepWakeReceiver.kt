package com.animus.smartroom.routine.receiver

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.animus.smartroom.MainActivity
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.routine.alarm.AlarmSoundPlayer
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.scheduler.RoutineScheduler
import com.animus.smartroom.routine.storage.RoutineStorage

class SleepWakeReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "SleepWakeReceiver"
        const val ACTION_STOP_ALARM = "com.animus.smartroom.ACTION_STOP_ALARM"
        private const val CHANNEL_ID = "animus_routine_wake_channel"
        private const val CHANNEL_NAME = "Sleep Mode Wake-up"
        const val NOTIFICATION_ID = 9002
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        Log.i(TAG, "[wake] Broadcast received with action: $action")

        when (action) {
            RoutineScheduler.ACTION_SLEEP_WAKE -> {
                handleWakeTrigger(context, intent)
            }
            ACTION_STOP_ALARM -> {
                handleStopAlarm(context)
            }
        }
    }

    private fun handleWakeTrigger(context: Context, intent: Intent) {
        val routineId = intent.getStringExtra(RoutineScheduler.EXTRA_ROUTINE_ID) ?: "default_sleep"
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.TRIGGERED,
            message = "Wake-up alarm triggered"
        )
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.STATE,
            message = "routine=$routineId"
        )

        // Acquire temporary wake lock to ensure execution across Doze
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
        val wakeLock = powerManager?.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "animus:SleepWakeReceiverWakeLock"
        )
        wakeLock?.acquire(20000L) // 20 seconds max

        try {
            // 1. Pause sleep music
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.MUSIC,
                message = "pause requested"
            )
            val musicController = MusicController(context.applicationContext)
            musicController.pause()
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.MUSIC,
                message = "paused"
            )

            // 2. Transition persistent state to ALARMING
            DiagnosticBus.log(
                tag = "routine",
                stage = DiagnosticStage.STATE,
                message = "ACTIVE -> ALARMING"
            )
            val storage = RoutineStorage(context.applicationContext)
            val current = storage.getActiveRoutine()
            if (current != null) {
                storage.saveActiveRoutine(
                    current.copy(status = RoutineStatus.ALARMING)
                )
            }
            DiagnosticBus.log(
                tag = "engine",
                stage = DiagnosticStage.STATE,
                message = "ALARMING"
            )
            DiagnosticBus.log(
                tag = "viewmodel",
                stage = DiagnosticStage.STATE,
                message = "ALARMING"
            )
            DiagnosticBus.log(
                tag = "ui",
                stage = DiagnosticStage.STATE,
                message = "ALARMING"
            )

            // 3. Start local alarm chime sound
            AlarmSoundPlayer.startAlarm(context.applicationContext)

            // 4. Post persistent wake-up notification with STOP action
            postPersistentAlarmNotification(context, routineId)
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.NOTIFICATION,
                message = "posted"
            )
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.COMPLETED,
                message = "alarm displayed"
            )

        } catch (e: Exception) {
            Log.e(TAG, "[wake] Error executing wake-up sequence", e)
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.FAILED,
                message = "Wake sequence error: ${e.message}"
            )
        } finally {
            try {
                if (wakeLock?.isHeld == true) {
                    wakeLock.release()
                }
            } catch (ignored: Exception) {}
        }
    }

    private fun handleStopAlarm(context: Context) {
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.STOP_REQUESTED,
            message = "User requested STOP alarm"
        )
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.ALARM,
            message = "stop requested"
        )

        // 1. Stop alarm sound
        AlarmSoundPlayer.stopAlarm()
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.ALARM,
            message = "audio stopped"
        )

        // 2. Dismiss notification
        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        notificationManager?.cancel(NOTIFICATION_ID)
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.NOTIFICATION,
            message = "dismissed"
        )

        // 3. Update persistent state to COMPLETED
        DiagnosticBus.log(
            tag = "routine",
            stage = DiagnosticStage.STATE,
            message = "ALARMING -> COMPLETED"
        )
        val storage = RoutineStorage(context.applicationContext)
        val current = storage.getActiveRoutine()
        if (current != null) {
            storage.saveActiveRoutine(
                current.copy(status = RoutineStatus.COMPLETED)
            )
        }
        DiagnosticBus.log(
            tag = "viewmodel",
            stage = DiagnosticStage.STATE,
            message = "COMPLETED"
        )
        DiagnosticBus.log(
            tag = "ui",
            stage = DiagnosticStage.STATE,
            message = "COMPLETED"
        )
    }

    private fun postPersistentAlarmNotification(context: Context, routineId: String) {
        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifies when your scheduled sleep timer is complete"
                enableVibration(true)
            }
            notificationManager.createNotificationChannel(channel)
        }

        val openIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingOpenIntent = PendingIntent.getActivity(
            context,
            0,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Stop Action Intent
        val stopIntent = Intent(context, SleepWakeReceiver::class.java).apply {
            action = ACTION_STOP_ALARM
        }
        val pendingStopIntent = PendingIntent.getBroadcast(
            context,
            1,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle("Sleep Mode Complete ☀️")
            .setContentText("Wake up! Tap STOP to silence the alarm.")
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(pendingOpenIntent)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "STOP", pendingStopIntent)
            .build()

        notificationManager.notify(NOTIFICATION_ID, notification)
        Log.i(TAG, "[wake] Posted persistent alarm notification to user")
    }
}
