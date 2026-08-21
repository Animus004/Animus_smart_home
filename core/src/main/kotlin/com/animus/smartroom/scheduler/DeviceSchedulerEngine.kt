package com.animus.smartroom.scheduler

import com.animus.smartroom.context.HomeLocationContext
import com.animus.smartroom.core.port.Clock
import com.animus.smartroom.core.port.PlatformScheduler
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.RecurrenceRule
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
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
    val storage: ScheduledActionStorage,
    val clock: Clock,
    private val platformScheduler: PlatformScheduler? = null
) {
    companion object {
        const val ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION = "com.animus.smartroom.ACTION_EXECUTE_SCHEDULED_DEVICE_ACTION"
        const val EXTRA_ACTION_ID = "extra_action_id"

        fun getRequestCode(actionId: String): Int {
            return (actionId.hashCode() and 0x7FFFFFFF)
        }

        fun parseExecutionTime(
            delayMinutes: Int?,
            scheduledTimeStr: String?,
            currentTimeMillis: Long,
            timeZoneId: String = HomeLocationContext.getLocation().timeZone
        ): Long? {
            if (delayMinutes != null && delayMinutes > 0) {
                return currentTimeMillis + (delayMinutes * 60 * 1000L)
            }

            if (!scheduledTimeStr.isNullOrBlank()) {
                return parseClockTimeString(scheduledTimeStr, currentTimeMillis, timeZoneId)
            }

            return null
        }

        fun parseClockTimeString(timeStr: String, currentTimeMillis: Long, timeZoneId: String): Long? {
            val normalized = timeStr.trim().lowercase(Locale.ROOT)
            val tz = TimeZone.getTimeZone(timeZoneId)
            val cal = Calendar.getInstance(tz).apply {
                timeInMillis = currentTimeMillis
            }

            val regex12 = Regex("""^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$""")
            val match12 = regex12.find(normalized)

            if (match12 != null) {
                var hour = match12.groupValues[1].toInt()
                val minute = match12.groupValues[2].takeIf { it.isNotEmpty() }?.toInt() ?: 0
                val ampm = match12.groupValues[3]

                if (ampm == "pm" && hour < 12) hour += 12
                if (ampm == "am" && hour == 12) hour = 0

                val targetCal = Calendar.getInstance(tz).apply {
                    timeInMillis = currentTimeMillis
                    set(Calendar.HOUR_OF_DAY, hour)
                    set(Calendar.MINUTE, minute)
                    set(Calendar.SECOND, 0)
                    set(Calendar.MILLISECOND, 0)
                }

                if (targetCal.timeInMillis <= currentTimeMillis) {
                    targetCal.add(Calendar.DAY_OF_YEAR, 1)
                }

                return targetCal.timeInMillis
            }

            val regex24 = Regex("""^(\d{1,2}):(\d{2})$""")
            val match24 = regex24.find(normalized)
            if (match24 != null) {
                val hour = match24.groupValues[1].toInt()
                val minute = match24.groupValues[2].toInt()

                val targetCal = Calendar.getInstance(tz).apply {
                    timeInMillis = currentTimeMillis
                    set(Calendar.HOUR_OF_DAY, hour)
                    set(Calendar.MINUTE, minute)
                    set(Calendar.SECOND, 0)
                    set(Calendar.MILLISECOND, 0)
                }

                if (targetCal.timeInMillis <= currentTimeMillis) {
                    targetCal.add(Calendar.DAY_OF_YEAR, 1)
                }

                return targetCal.timeInMillis
            }

            return null
        }
    }

    open fun scheduleAction(
        targetDeviceType: DeviceType,
        actionType: DeviceActionType,
        delayMinutes: Int? = null,
        scheduledTimeStr: String? = null,
        parameters: Map<String, Any> = emptyMap(),
        recurrence: RecurrenceRule? = null
    ): ActionScheduleResult {
        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.REQUESTED,
            message = "target=$targetDeviceType, action=$actionType, delay=$delayMinutes, time=$scheduledTimeStr"
        )

        val currentTime = clock.currentTimeMillis()
        val tzId = clock.timeZoneId()
        val executionTime = parseExecutionTime(
            delayMinutes = delayMinutes,
            scheduledTimeStr = scheduledTimeStr,
            currentTimeMillis = currentTime,
            timeZoneId = tzId
        ) ?: return ActionScheduleResult.Error("Could not determine execution time for $delayMinutes min / '$scheduledTimeStr'.")

        // Cancel superseded pending timer for the same device
        val existingPending = storage.getPendingActionForDevice(targetDeviceType)
        if (existingPending != null) {
            cancelExistingAction(existingPending.id)
        }

        val actionId = UUID.randomUUID().toString()
        val action = ScheduledDeviceAction(
            id = actionId,
            targetDeviceType = targetDeviceType,
            actionType = actionType,
            scheduledExecutionTimeMillis = executionTime,
            status = ScheduledActionStatus.SCHEDULED,
            parameters = parameters,
            recurrenceRule = recurrence
        )

        storage.saveAction(action)
        armPlatformAlarm(action)

        val timeFmt = SimpleDateFormat("HH:mm:ss dd-MMM", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone(tzId)
        }
        val formattedDate = timeFmt.format(Date(executionTime))

        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.SCHEDULED,
            message = "target=$targetDeviceType, action=$actionType, executeAt=$formattedDate"
        )

        return ActionScheduleResult.Success(action)
    }

    private fun cancelExistingAction(actionId: String) {
        platformScheduler?.disarm(actionId)
        storage.cancelAction(actionId)
    }

    open fun cancelAction(actionId: String): Boolean {
        val action = storage.getAction(actionId) ?: return false
        if (action.status != ScheduledActionStatus.SCHEDULED) return false
        cancelExistingAction(actionId)
        return true
    }

    open fun cancelActionsForDevice(deviceType: DeviceType): Int {
        val pending = storage.getPendingActions().filter { it.targetDeviceType == deviceType }
        pending.forEach { cancelExistingAction(it.id) }
        return pending.size
    }

    open fun queryRemainingTime(deviceType: DeviceType): String {
        val pending = storage.getPendingActionForDevice(deviceType)
            ?: return "You have no active timer set for ${deviceType.name.replace('_', ' ').lowercase()}."

        val now = clock.currentTimeMillis()
        val remainingMillis = pending.scheduledExecutionTimeMillis - now

        if (remainingMillis <= 0) {
            return "The scheduled action for ${pending.targetDeviceType.name.replace('_', ' ').lowercase()} is executing right now."
        }

        val remainingMinutes = (remainingMillis + 59_999L) / 60_000L
        val hours = remainingMinutes / 60
        val mins = remainingMinutes % 60

        val deviceName = if (deviceType == DeviceType.AIR_CONDITIONER) "AC" else deviceType.name.replace('_', ' ').lowercase()
        val actionName = when (pending.actionType) {
            DeviceActionType.POWER_OFF -> "turn off"
            DeviceActionType.POWER_ON -> "turn on"
            DeviceActionType.SET_TEMPERATURE -> "set temperature"
            DeviceActionType.SET_MODE -> "change mode"
            DeviceActionType.SET_FAN_SPEED -> "change fan speed"
            DeviceActionType.CONNECT -> "connect"
            DeviceActionType.DISCONNECT -> "disconnect"
            DeviceActionType.PAUSE_MUSIC -> "pause music"
        }

        return if (hours > 0) {
            if (mins > 0) {
                "Your $deviceName is scheduled to $actionName in $hours hour${if (hours > 1) "s" else ""} and $mins minute${if (mins > 1) "s" else ""}."
            } else {
                "Your $deviceName is scheduled to $actionName in $hours hour${if (hours > 1) "s" else ""}."
            }
        } else {
            "Your $deviceName is scheduled to $actionName in $mins minute${if (mins > 1) "s" else ""}."
        }
    }

    open fun restorePersistedActions() {
        val pending = storage.getPendingActions()
        val now = clock.currentTimeMillis()
        pending.forEach { action ->
            if (action.scheduledExecutionTimeMillis > now) {
                armPlatformAlarm(action)
            } else {
                // If action passed while dead, mark FAILED
                storage.updateStatus(action.id, ScheduledActionStatus.FAILED, "Expired while app process was stopped.")
            }
        }
    }

    private fun armPlatformAlarm(action: ScheduledDeviceAction) {
        platformScheduler?.armExact(
            actionId = action.id,
            triggerAtMillis = action.scheduledExecutionTimeMillis,
            metadataJson = action.toJson()
        )
    }
}
