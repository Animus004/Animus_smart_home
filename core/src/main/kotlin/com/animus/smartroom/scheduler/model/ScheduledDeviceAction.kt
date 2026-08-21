package com.animus.smartroom.scheduler.model

import com.animus.smartroom.device.model.DeviceType
import org.json.JSONObject

enum class DeviceActionType {
    POWER_ON,
    POWER_OFF,
    SET_TEMPERATURE,
    SET_MODE,
    SET_FAN_SPEED,
    CONNECT,
    DISCONNECT,
    PAUSE_MUSIC;

    companion object {
        fun fromString(value: String): DeviceActionType? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}

enum class ScheduledActionStatus {
    SCHEDULED,
    TRIGGERED,
    EXECUTING,
    VERIFYING,
    COMPLETED,
    COMPLETED_WITH_NO_CHANGE,
    CANCELLED,
    FAILED
}

data class RecurrenceRule(
    val frequency: String, // "DAILY"
    val timeOfDay: String? = null // "23:00"
) {
    fun toJson(): JSONObject {
        return JSONObject().apply {
            put("frequency", frequency)
            if (timeOfDay != null) put("timeOfDay", timeOfDay)
        }
    }

    companion object {
        fun fromJson(json: JSONObject): RecurrenceRule {
            return RecurrenceRule(
                frequency = json.optString("frequency", "DAILY"),
                timeOfDay = json.optString("timeOfDay", "").ifBlank { null }
            )
        }
    }
}

data class ScheduledDeviceAction(
    val id: String,
    val targetDeviceType: DeviceType,
    val actionType: DeviceActionType,
    val parameters: Map<String, Any> = emptyMap(),
    val scheduledExecutionTimeMillis: Long,
    val createdAt: Long = System.currentTimeMillis(),
    val status: ScheduledActionStatus = ScheduledActionStatus.SCHEDULED,
    val recurrenceRule: RecurrenceRule? = null,
    val failureReason: String? = null
) {
    val isPending: Boolean
        get() = status == ScheduledActionStatus.SCHEDULED || status == ScheduledActionStatus.TRIGGERED

    fun remainingMillis(currentTimeMillis: Long = System.currentTimeMillis()): Long {
        return (scheduledExecutionTimeMillis - currentTimeMillis).coerceAtLeast(0L)
    }

    fun toJson(): String {
        return JSONObject().apply {
            put("id", id)
            put("targetDeviceType", targetDeviceType.name)
            put("actionType", actionType.name)
            put("scheduledExecutionTimeMillis", scheduledExecutionTimeMillis)
            put("createdAt", createdAt)
            put("status", status.name)
            if (failureReason != null) put("failureReason", failureReason)
            recurrenceRule?.let { put("recurrenceRule", it.toJson()) }

            val paramObj = JSONObject()
            parameters.forEach { (k, v) -> paramObj.put(k, v) }
            put("parameters", paramObj)
        }.toString()
    }

    companion object {
        fun fromJson(jsonStr: String): ScheduledDeviceAction? {
            return try {
                val obj = JSONObject(jsonStr)
                val id = obj.getString("id")
                val target = DeviceType.valueOf(obj.getString("targetDeviceType"))
                val action = DeviceActionType.valueOf(obj.getString("actionType"))
                val scheduledTime = obj.getLong("scheduledExecutionTimeMillis")
                val created = obj.optLong("createdAt", System.currentTimeMillis())
                val status = ScheduledActionStatus.valueOf(obj.getString("status"))
                val reason = obj.optString("failureReason", "").ifBlank { null }
                val recurrence = obj.optJSONObject("recurrenceRule")?.let { RecurrenceRule.fromJson(it) }

                val params = mutableMapOf<String, Any>()
                val paramObj = obj.optJSONObject("parameters")
                paramObj?.keys()?.forEach { k ->
                    params[k] = paramObj.get(k)
                }

                ScheduledDeviceAction(
                    id = id,
                    targetDeviceType = target,
                    actionType = action,
                    parameters = params,
                    scheduledExecutionTimeMillis = scheduledTime,
                    createdAt = created,
                    status = status,
                    recurrenceRule = recurrence,
                    failureReason = reason
                )
            } catch (e: Exception) {
                null
            }
        }
    }
}
