package com.animus.smartroom.core.port

import android.annotation.SuppressLint
import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.util.Log
import com.animus.smartroom.MainActivity
import com.animus.smartroom.scheduler.receiver.ScheduledDeviceActionReceiver

/**
 * Android AlarmManager implementation of [PlatformScheduler].
 * Preserves deterministic exact alarm arming, unique request codes, and background wakeups.
 */
class AndroidAlarmManagerScheduler(
    private val context: Context
) : PlatformScheduler {

    companion object {
        private const val TAG = "AlarmManagerScheduler"
        const val ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION = "com.animus.smartroom.ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION"
        const val EXTRA_ACTION_ID = "extra_action_id"

        fun getRequestCode(actionId: String): Int {
            return actionId.hashCode() and 0x7FFFFFFF
        }
    }

    private val alarmManager: AlarmManager? =
        context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager

    @SuppressLint("ScheduleExactAlarm")
    override fun armExact(actionId: String, triggerAtMillis: Long, metadataJson: String) {
        if (alarmManager == null) {
            Log.e(TAG, "[scheduler] AlarmManager is null")
            return
        }

        val intent = Intent(context, ScheduledDeviceActionReceiver::class.java).apply {
            action = ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION
            putExtra(EXTRA_ACTION_ID, actionId)
        }

        val reqCode = getRequestCode(actionId)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            reqCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val showIntent = Intent(context, MainActivity::class.java)
        val showPendingIntent = PendingIntent.getActivity(
            context,
            reqCode,
            showIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        try {
            val alarmClockInfo = AlarmManager.AlarmClockInfo(triggerAtMillis, showPendingIntent)
            alarmManager.setAlarmClock(alarmClockInfo, pendingIntent)
            Log.i(TAG, "[scheduler] Armed AlarmManager for action $actionId (reqCode=$reqCode) at $triggerAtMillis")
        } catch (e: Exception) {
            Log.w(TAG, "[scheduler] setAlarmClock failed, falling back to setExactAndAllowWhileIdle", e)
            alarmManager.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                triggerAtMillis,
                pendingIntent
            )
        }
    }

    override fun disarm(actionId: String) {
        if (alarmManager == null) return

        val intent = Intent(context, ScheduledDeviceActionReceiver::class.java).apply {
            action = ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION
            putExtra(EXTRA_ACTION_ID, actionId)
        }

        val reqCode = getRequestCode(actionId)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            reqCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        alarmManager.cancel(pendingIntent)
        Log.i(TAG, "[scheduler] Disarmed alarm for action $actionId (reqCode=$reqCode)")
    }
}
