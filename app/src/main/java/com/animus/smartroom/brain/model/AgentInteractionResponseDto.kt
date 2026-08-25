package com.animus.smartroom.brain.model

import org.json.JSONObject

/**
 * Data Transfer Object corresponding to backend AgentInteractionResponse schema.
 */
data class AgentInteractionResponseDto(
    val understoodIntent: String,
    val agentMessage: String,
    val actionTaken: Boolean,
    val deterministicPreparationDone: Boolean,
    val followupRequired: Boolean,
    val followupQuestion: String?,
    val timestamp: Double
) {
    companion object {
        fun fromJson(json: JSONObject): AgentInteractionResponseDto {
            return AgentInteractionResponseDto(
                understoodIntent = json.optString("understood_intent", "UNKNOWN"),
                agentMessage = json.optString("agent_message", ""),
                actionTaken = json.optBoolean("action_taken", false),
                deterministicPreparationDone = json.optBoolean("deterministic_preparation_done", false),
                followupRequired = json.optBoolean("followup_required", false),
                followupQuestion = if (json.has("followup_question") && !json.isNull("followup_question")) json.getString("followup_question") else null,
                timestamp = json.optDouble("timestamp", System.currentTimeMillis() / 1000.0)
            )
        }
    }
}
