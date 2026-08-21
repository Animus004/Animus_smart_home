package com.animus.smartroom.core.diagnostics.model

import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.device.model.DeviceType
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Immutable structured action event contract for DiagnosticBus 2.0.
 */
data class AnimusActionEvent(
    val id: String,
    val correlationId: String? = null,
    val timestamp: Long,
    val source: ActionSource,
    val targetDevice: DeviceType?,
    val action: String,
    val stage: ActionStage,
    val status: ActionStatus,
    val message: String?,
    val metadata: Map<String, String> = emptyMap()
) {
    init {
        require(id.isNotBlank()) { "AnimusActionEvent id cannot be blank" }
        require(action.isNotBlank()) { "AnimusActionEvent action cannot be blank" }
    }

    val formattedTime: String
        get() {
            val sdf = SimpleDateFormat("HH:mm:ss.SSS", Locale.ROOT)
            return sdf.format(Date(timestamp))
        }

    val displayString: String
        get() {
            val corr = if (correlationId != null) " [corr:$correlationId]" else ""
            val target = if (targetDevice != null) " [${targetDevice.name}]" else ""
            val msg = if (message != null) " - $message" else ""
            return "$formattedTime [${source.name}]$corr$target [$action] [${stage.name}] [${status.name}]$msg"
        }

    /**
     * Serializes this event to a clean JSON string for transport/persistence.
     */
    fun toJson(): String {
        val json = JSONObject()
        json.put("id", id)
        if (correlationId != null) json.put("correlationId", correlationId)
        json.put("timestamp", timestamp)
        json.put("source", source.name)
        if (targetDevice != null) json.put("targetDevice", targetDevice.name)
        json.put("action", action)
        json.put("stage", stage.name)
        json.put("status", status.name)
        if (message != null) json.put("message", EventSanitizer.sanitizeText(message))
        if (metadata.isNotEmpty()) {
            val metaJson = JSONObject()
            EventSanitizer.sanitizeMetadata(metadata).forEach { (k, v) ->
                metaJson.put(k, v)
            }
            json.put("metadata", metaJson)
        }
        return json.toString()
    }

    companion object {
        fun fromJson(jsonStr: String): AnimusActionEvent {
            val json = JSONObject(jsonStr)
            val id = json.getString("id")
            val correlationId = if (json.has("correlationId")) json.getString("correlationId") else null
            val timestamp = json.getLong("timestamp")
            val source = ActionSource.fromString(json.getString("source")) ?: ActionSource.SYSTEM
            val targetDevice = if (json.has("targetDevice") && !json.isNull("targetDevice")) {
                DeviceType.fromString(json.getString("targetDevice"))
            } else null
            val action = json.getString("action")
            val stage = ActionStage.fromString(json.getString("stage")) ?: ActionStage.EXECUTING
            val status = ActionStatus.fromString(json.getString("status")) ?: ActionStatus.IN_PROGRESS
            val message = if (json.has("message") && !json.isNull("message")) json.getString("message") else null

            val metadata = mutableMapOf<String, String>()
            if (json.has("metadata") && !json.isNull("metadata")) {
                val metaJson = json.getJSONObject("metadata")
                for (key in metaJson.keys()) {
                    metadata[key] = metaJson.getString(key)
                }
            }

            return AnimusActionEvent(
                id = id,
                correlationId = correlationId,
                timestamp = timestamp,
                source = source,
                targetDevice = targetDevice,
                action = action,
                stage = stage,
                status = status,
                message = message,
                metadata = metadata
            )
        }
    }
}
