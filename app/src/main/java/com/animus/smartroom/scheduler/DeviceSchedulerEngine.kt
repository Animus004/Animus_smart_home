package com.animus.smartroom.scheduler

import android.annotation.SuppressLint
import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import com.animus.smartroom.MainActivity
import com.animus.smartroom.context.HomeLocationContext
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.RecurrenceRule
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import com.animus.smartroom.scheduler.receiver.ScheduledDeviceActionReceiver
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID

sealed interface ActionScheduleResult {
    data class Success(val action: ScheduledDeviceAction) : ActionScheduleResult
    data class Error(val message: String) : ActionScheduleResult
}

open class DeviceSchedulerEngine(
    private val context: Context? = null,
    val storage: ScheduledActionStorage = ScheduledActionStorage(context)
) {

    companion object {
        private const val TAG = "DeviceSchedulerEngine"
        const val ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION = "com.animus.smartroom.ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION"
        const val EXTRA_ACTION_ID = "extra_action_id"

        fun getRequestCode(actionId: String): Int {
            return (actionId.hashCode() and 0x7FFFFFFF)
        }

        fun parseExecutionTime(
            delayMinutes: Int?,
            scheduledTimeStr: String?,
            currentTimeMillis: Long = System.currentTimeMillis(),
            timeZoneId: String = HomeLocationContext.getLocation().timeZone
        ): Long? {
            if (delayMinutes != null && delayMinutes > 0) {
                return currentTimeMillis + (delayMinutes * 60 * 1000L)
            }

            if (scheduledTimeStr.isNullOrBlank()) {
                return null
            }

            val tz = TimeZone.getTimeZone(timeZoneId)
            val cal = Calendar.getInstance(tz).apply {
                timeInMillis = currentTimeMillis
            }

            val cleanTime = scheduledTimeStr.trim().lowercase(Locale.ROOT)
            val isTomorrowExplicit = cleanTime.contains("tomorrow")

            val timeOnly = cleanTime
                .replace("tomorrow", "")
                .replace("at", "")
                .trim()

            // Try formats: "23:00", "11:00 pm", "11 pm", "6:30 am", "6 am"
            var parsedHour = -1
            var parsedMinute = 0

            val hourMinuteRegex = Regex("""(\d{1,2}):(\d{2})\s*(am|pm)?""")
            val hourOnlyRegex = Regex("""(\d{1,2})\s*(am|pm)""")
            val simple24Regex = Regex("""^(\d{1,2}):(\d{2})$""")

            val matchHM = hourMinuteRegex.find(timeOnly)
            val matchH = hourOnlyRegex.find(timeOnly)
            val match24 = simple24Regex.find(timeOnly)

            if (matchHM != null) {
                var h = matchHM.groupValues[1].toInt()
                val m = matchHM.groupValues[2].toInt()
                val ampm = matchHM.groupValues[3]
                if (ampm.equals("pm", ignoreCase = true) && h < 12) h += 12
                if (ampm.equals("am", ignoreCase = true) && h == 12) h = 0
                parsedHour = h
                parsedMinute = m
            } else if (matchH != null) {
                var h = matchH.groupValues[1].toInt()
                val ampm = matchH.groupValues[2]
                if (ampm.equals("pm", ignoreCase = true) && h < 12) h += 12
                if (ampm.equals("am", ignoreCase = true) && h == 12) h = 0
                parsedHour = h
                parsedMinute = 0
            } else if (match24 != null) {
                parsedHour = match24.groupValues[1].toInt()
                parsedMinute = match24.groupValues[2].toInt()
            }

            if (parsedHour in 0..23 && parsedMinute in 0..59) {
                val targetCal = Calendar.getInstance(tz).apply {
                    timeInMillis = currentTimeMillis
                    set(Calendar.HOUR_OF_DAY, parsedHour)
                    set(Calendar.MINUTE, parsedMinute)
                    set(Calendar.SECOND, 0)
                    set(Calendar.MILLISECOND, 0)
                }

                if (isTomorrowExplicit || targetCal.timeInMillis <= currentTimeMillis) {
                    targetCal.add(Calendar.DAY_OF_YEAR, 1)
                }

                return targetCal.timeInMillis
            }

            return null
        }
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
    open fun scheduleAction(
        targetDeviceType: DeviceType,
        actionType: DeviceActionType,
        delayMinutes: Int? = null,
        scheduledTime: String? = null,
        recurrence: String? = null,
        parameters: Map<String, Any> = emptyMap(),
        explicitTimeMillis: Long? = null
    ): ActionScheduleResult {
        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.REQUESTED,
            message = "target=$targetDeviceType, action=$actionType, delay=$delayMinutes, time=$scheduledTime"
        )

        val triggerAtMillis = explicitTimeMillis ?: parseExecutionTime(delayMinutes, scheduledTime)
        if (triggerAtMillis == null || triggerAtMillis <= System.currentTimeMillis()) {
            val err = "Invalid execution time specified: delay='$delayMinutes', scheduledTime='$scheduledTime'"
            Log.w(TAG, "[scheduler] $err")
            DiagnosticBus.log(
                tag = "scheduler",
                stage = DiagnosticStage.FAILED,
                message = err
            )
            return ActionScheduleResult.Error(err)
        }

        // Cancel existing pending action of same device & type to maintain deterministic one-active-timer semantics
        val existing = storage.getActiveActionForDevice(targetDeviceType)
        if (existing != null) {
            Log.i(TAG, "[scheduler] Cancelling superseded pending action ${existing.id} for $targetDeviceType")
            cancelAction(existing.id)
        }

        val actionId = UUID.randomUUID().toString()
        val recurrenceRule = if (!recurrence.isNullOrBlank()) {
            RecurrenceRule(frequency = recurrence.uppercase(Locale.ROOT), timeOfDay = scheduledTime)
        } else null

        val action = ScheduledDeviceAction(
            id = actionId,
            targetDeviceType = targetDeviceType,
            actionType = actionType,
            parameters = parameters,
            scheduledExecutionTimeMillis = triggerAtMillis,
            status = ScheduledActionStatus.SCHEDULED,
            recurrenceRule = recurrenceRule
        )

        // Persist to storage
        storage.saveAction(action)

        // Schedule AlarmManager
        armAlarm(action)

        val sdf = SimpleDateFormat("HH:mm:ss dd-MMM", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone(HomeLocationContext.getLocation().timeZone)
        }

        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.SCHEDULED,
            message = "target=$targetDeviceType, action=$actionType, executeAt=${sdf.format(Date(triggerAtMillis))}"
        )

        Log.i(TAG, "[scheduler] Successfully scheduled action $actionId at $triggerAtMillis (${sdf.format(Date(triggerAtMillis))})")
        return ActionScheduleResult.Success(action)
    }

    @SuppressLint("ScheduleExactAlarm")
    open fun armAlarm(action: ScheduledDeviceAction) {
        val ctx = context ?: return
        if (alarmManager == null) {
            Log.e(TAG, "[scheduler] AlarmManager service is null")
            return
        }

        val intent = Intent(ctx, ScheduledDeviceActionReceiver::class.java).apply {
            this.action = ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION
            putExtra(EXTRA_ACTION_ID, action.id)
        }

        val reqCode = getRequestCode(action.id)
        val pendingIntent = PendingIntent.getBroadcast(
            ctx,
            reqCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val showIntent = Intent(ctx, MainActivity::class.java)
        val showPendingIntent = PendingIntent.getActivity(
            ctx,
            reqCode,
            showIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        try {
            val alarmClockInfo = AlarmManager.AlarmClockInfo(action.scheduledExecutionTimeMillis, showPendingIntent)
            alarmManager.setAlarmClock(alarmClockInfo, pendingIntent)
            Log.i(TAG, "[scheduler] Armed AlarmManager for action ${action.id} (reqCode=$reqCode) at ${action.scheduledExecutionTimeMillis}")
        } catch (e: Exception) {
            Log.w(TAG, "[scheduler] setAlarmClock failed, falling back to setExactAndAllowWhileIdle", e)
            alarmManager.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                action.scheduledExecutionTimeMillis,
                pendingIntent
            )
        }
    }

    open fun cancelAction(actionId: String): Boolean {
        val action = storage.getAction(actionId) ?: return false
        disarmAlarm(action.id)
        storage.cancelAction(actionId)

        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.STOP_REQUESTED,
            message = "Cancelled action $actionId for ${action.targetDeviceType}"
        )
        return true
    }

    open fun cancelActionsForDevice(deviceType: DeviceType): Int {
        val active = storage.getActiveActions().filter { it.targetDeviceType == deviceType }
        active.forEach { action ->
            disarmAlarm(action.id)
            storage.cancelAction(action.id)
        }

        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.STOP_REQUESTED,
            message = "Cancelled ${active.size} active timer(s) for $deviceType"
        )
        return active.size
    }

    open fun disarmAlarm(actionId: String) {
        val ctx = context ?: return
        if (alarmManager == null) return

        val intent = Intent(ctx, ScheduledDeviceActionReceiver::class.java).apply {
            this.action = ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION
            putExtra(EXTRA_ACTION_ID, actionId)
        }

        val reqCode = getRequestCode(actionId)
        val pendingIntent = PendingIntent.getBroadcast(
            ctx,
            reqCode,
            intent,
            PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
        )

        if (pendingIntent != null) {
            alarmManager.cancel(pendingIntent)
            pendingIntent.cancel()
            Log.i(TAG, "[scheduler] Disarmed alarm for action $actionId (reqCode=$reqCode)")
        }
    }

    open fun queryRemainingTime(deviceType: DeviceType): String {
        val action = storage.getActiveActionForDevice(deviceType)
        if (action == null) {
            return when (deviceType) {
                DeviceType.AIR_CONDITIONER -> "You don't have an active AC timer."
                else -> "No active timer found for $deviceType."
            }
        }

        val remainingMillis = action.remainingMillis()
        if (remainingMillis <= 0) {
            return "The ${action.targetDeviceType} timer is triggering now."
        }

        val totalMinutes = ((remainingMillis + 59999L) / 60000L).toInt()
        val hours = totalMinutes / 60
        val minutes = totalMinutes % 60

        val durationStr = when {
            hours > 0 && minutes > 0 -> "$hours hour${if (hours > 1) "s" else ""} $minutes minute${if (minutes > 1) "s" else ""}"
            hours > 0 -> "$hours hour${if (hours > 1) "s" else ""}"
            minutes > 0 -> "$minutes minute${if (minutes > 1) "s" else ""}"
            else -> "less than a minute"
        }

        val actionDesc = when (action.actionType) {
            DeviceActionType.POWER_OFF -> "turn off"
            DeviceActionType.POWER_ON -> "turn on"
            DeviceActionType.SET_TEMPERATURE -> "change temperature"
            else -> action.actionType.name.lowercase(Locale.ROOT)
        }

        return "Your AC is scheduled to $actionDesc in $durationStr."
    }

    open fun restorePersistedActions() {
        val pending = storage.getActiveActions()
        Log.i(TAG, "[scheduler] Restoring ${pending.size} pending scheduled action(s)")
        val now = System.currentTimeMillis()

        pending.forEach { action ->
            if (action.scheduledExecutionTimeMillis > now) {
                armAlarm(action)
            } else {
                // Action expired while app was dead - trigger immediately or mark failed
                Log.w(TAG, "[scheduler] Action ${action.id} expired while offline. Triggering execution.")
                val intent = Intent(context, ScheduledDeviceActionReceiver::class.java).apply {
                    this.action = ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION
                    putExtra(EXTRA_ACTION_ID, action.id)
                }
                context?.sendBroadcast(intent)
            }
        }
    }
}
