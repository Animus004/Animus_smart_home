package com.animus.smartroom.event.model

import org.json.JSONObject

/**
 * Data Transfer Object corresponding to backend AgentEvent schema.
 */
data class AgentEventDto(
    val eventId: String,
    val eventType: String,
    val timestamp: Double,
    val priority: String,
    val message: String,
    val payload: JSONObject
) {
    companion object {
        fun fromJson(json: JSONObject): AgentEventDto {
            return AgentEventDto(
                eventId = json.optString("event_id", ""),
                eventType = json.optString("event_type", "SYSTEM_NOTIFICATION"),
                timestamp = json.optDouble("timestamp", System.currentTimeMillis() / 1000.0),
                priority = json.optString("priority", "NORMAL"),
                message = json.optString("message", ""),
                payload = json.optJSONObject("payload") ?: JSONObject()
            )
        }
    }
}
