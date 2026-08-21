package com.animus.smartroom.notification

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import com.animus.smartroom.MainActivity
import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.device.model.DeviceType
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Produces and updates Android notifications from structured [AnimusActionEvent] data.
 * Never receives raw API keys, tokens, or network responses — only sanitized events.
 */
object AndroidNotificationAdapter {

    const val CHANNEL_ID = "animus_runtime"
    const val CHANNEL_NAME = "Animus"
    const val NOTIFICATION_ID_RUNTIME = 1001

    private val timeFormat = SimpleDateFormat("HH:mm", Locale.getDefault())

    fun createNotificationChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Animus smart-room runtime status"
                setShowBadge(false)
            }
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    /** Build the baseline persistent runtime notification. */
    fun buildRuntimeNotification(context: Context): Notification {
        val tapIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_SINGLE_TOP },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Animus")
            .setContentText("Runtime ready")
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(tapIntent)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build()
    }

    /**
     * Build an updated notification from a structured [AnimusActionEvent].
     * Applies [EventSanitizer] defensively before any string is placed into the notification.
     */
    fun buildEventNotification(context: Context, event: AnimusActionEvent): Notification {
        val tapIntent = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_SINGLE_TOP },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val (title, body) = resolveNotificationContent(event)
        val safeTitle = EventSanitizer.sanitizeText(title) ?: "Animus"
        val safeBody = EventSanitizer.sanitizeText(body) ?: ""

        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(resolveIcon(event))
            .setContentTitle(safeTitle)
            .setContentText(safeBody)
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(tapIntent)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .build()
    }

    private fun resolveNotificationContent(event: AnimusActionEvent): Pair<String, String> {
        val timeStr = timeFormat.format(Date(event.timestamp))

        return when {
            // AC commands
            event.targetDevice == DeviceType.AIR_CONDITIONER && event.status == ActionStatus.SUCCESS -> {
                val action = when {
                    event.action.contains("POWER_OFF", ignoreCase = true) -> "Turned OFF"
                    event.action.contains("POWER_ON", ignoreCase = true) -> "Turned ON"
                    event.action.contains("TEMPERATURE", ignoreCase = true) ->
                        "Temperature set to ${event.metadata["temperature"] ?: ""}°C"
                    else -> event.action.replace("_", " ").lowercase(Locale.ROOT)
                        .replaceFirstChar { it.uppercase() }
                }
                "✓ Bedroom AC" to "$action · $timeStr"
            }

            event.targetDevice == DeviceType.AIR_CONDITIONER && event.status == ActionStatus.FAILED -> {
                "⚠ AC command failed" to (EventSanitizer.sanitizeText(event.message) ?: "Command failed")
            }

            event.targetDevice == DeviceType.AIR_CONDITIONER && event.status == ActionStatus.NO_CHANGE -> {
                "✓ Bedroom AC" to "Already in desired state · $timeStr"
            }

            // Scheduled timer (active)
            event.source == ActionSource.SCHEDULER && event.stage == ActionStage.TRIGGERED -> {
                "⏱ AC timer" to (EventSanitizer.sanitizeText(event.message) ?: "Scheduled action")
            }

            // Music playback
            event.targetDevice == DeviceType.BLUETOOTH_AUDIO && event.status == ActionStatus.SUCCESS &&
                    event.action.contains("PLAY", ignoreCase = true) -> {
                val track = event.metadata["track"] ?: "Music"
                val output = event.metadata["outputDevice"] ?: ""
                "♪ $track" to if (output.isNotBlank()) "Playing on $output" else "Playing"
            }

            // Runtime lifecycle
            event.action == "RUNTIME_STARTED" -> "Animus" to "Runtime ready"
            event.action == "RUNTIME_STOPPED" -> "Animus" to "Runtime stopped"

            // Generic fallback
            event.status == ActionStatus.SUCCESS ->
                "✓ Animus" to (EventSanitizer.sanitizeText(event.message) ?: "Done · $timeStr")

            event.status == ActionStatus.FAILED ->
                "⚠ Animus" to (EventSanitizer.sanitizeText(event.message) ?: "Action failed")

            else -> "Animus" to "Runtime ready"
        }
    }

    private fun resolveIcon(event: AnimusActionEvent): Int {
        return when (event.status) {
            ActionStatus.FAILED -> android.R.drawable.ic_dialog_alert
            ActionStatus.SUCCESS, ActionStatus.NO_CHANGE -> android.R.drawable.ic_dialog_info
            else -> android.R.drawable.ic_dialog_info
        }
    }

    /** Push an updated notification to the system tray. */
    fun updateNotification(context: Context, event: AnimusActionEvent) {
        val notification = buildEventNotification(context, event)
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID_RUNTIME, notification)
    }
}
