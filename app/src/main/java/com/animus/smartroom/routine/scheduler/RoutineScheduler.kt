package com.animus.smartroom.routine.scheduler

import android.annotation.SuppressLint
import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.animus.smartroom.MainActivity
import com.animus.smartroom.routine.receiver.SleepWakeReceiver

sealed interface ScheduleResult {
    data class Success(val triggerAtMillis: Long) : ScheduleResult
    data class PermissionRequired(val message: String) : ScheduleResult
    data class Error(val message: String) : ScheduleResult
}

open class RoutineScheduler(
    private val context: Context? = null
) {
    companion object {
        private const val TAG = "RoutineScheduler"
        const val ACTION_SLEEP_WAKE = "com.animus.smartroom.ACTION_SLEEP_WAKE"
        const val EXTRA_ROUTINE_ID = "extra_routine_id"
        private const val WAKE_ALARM_REQUEST_CODE = 9001
    }

    private val alarmManager: AlarmManager? =
        context?.getSystemService(Context.ALARM_SERVICE) as? AlarmManager

    open fun canScheduleExactAlarms(): Boolean {
        if (alarmManager == null) return false
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            alarmManager.canScheduleExactAlarms()
        } else {
            true
        }
    }

    @SuppressLint("ScheduleExactAlarm")
    open fun scheduleWake(routineId: String, triggerAtMillis: Long): ScheduleResult {
        val ctx = context ?: return ScheduleResult.Error("Context is unavailable.")
        if (alarmManager == null) {
            Log.e(TAG, "[scheduler] AlarmManager is not available on this device")
            return ScheduleResult.Error("AlarmManager service is unavailable.")
        }

        if (!canScheduleExactAlarms()) {
            Log.w(TAG, "[scheduler] Exact alarm permission is not granted on this device")
            return ScheduleResult.PermissionRequired("Exact alarm permission is required to schedule a precise wake-up time.")
        }

        return try {
            val intent = Intent(context, SleepWakeReceiver::class.java).apply {
                action = ACTION_SLEEP_WAKE
                putExtra(EXTRA_ROUTINE_ID, routineId)
            }

            val pendingIntent = PendingIntent.getBroadcast(
                context,
                WAKE_ALARM_REQUEST_CODE,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            // Use setAlarmClock or setExactAndAllowWhileIdle for exact delivery across Doze
            val showIntent = Intent(context, MainActivity::class.java)
            val showPendingIntent = PendingIntent.getActivity(
                context,
                0,
                showIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )

            val alarmClockInfo = AlarmManager.AlarmClockInfo(triggerAtMillis, showPendingIntent)
            alarmManager.setAlarmClock(alarmClockInfo, pendingIntent)

            Log.i(TAG, "[scheduler] Successfully scheduled exact wake alarm for routine '$routineId' at $triggerAtMillis (${java.util.Date(triggerAtMillis)})")
            ScheduleResult.Success(triggerAtMillis)
        } catch (e: Exception) {
            Log.e(TAG, "[scheduler] Failed to schedule exact alarm", e)
            ScheduleResult.Error("Failed to schedule alarm: ${e.message}")
        }
    }

    open fun cancelWake(routineId: String) {
        if (alarmManager == null) return

        try {
            val intent = Intent(context, SleepWakeReceiver::class.java).apply {
                action = ACTION_SLEEP_WAKE
                putExtra(EXTRA_ROUTINE_ID, routineId)
            }

            val pendingIntent = PendingIntent.getBroadcast(
                context,
                WAKE_ALARM_REQUEST_CODE,
                intent,
                PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
            )

            if (pendingIntent != null) {
                alarmManager.cancel(pendingIntent)
                pendingIntent.cancel()
                Log.i(TAG, "[scheduler] Cancelled wake alarm for routine '$routineId'")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[scheduler] Error cancelling wake alarm", e)
        }
    }
}
