package com.animus.smartroom.core.brain.intent

import org.json.JSONArray
import org.json.JSONObject

object IntentClassifier {

    fun parse(raw: String): IntentPayload {
        val cleaned = cleanJsonString(raw)
        return try {
            val json = JSONObject(cleaned)
            parseJsonObject(json)
        } catch (e: Exception) {
            // Fallback for non-JSON conversational text
            IntentPayload(
                schemaVersion = "1.0",
                type = "conversation",
                intent = UserIntent.CONVERSATION,
                confidence = 0.5,
                spokenResponse = raw.trim()
            )
        }
    }

    private fun parseJsonObject(json: JSONObject): IntentPayload {
        val schemaVersion = json.optString("schema_version", "1.0")
        val rawType = json.optString("type", "intent")
        val rawIntent = json.optString("intent", "UNKNOWN")
        var intentEnum = UserIntent.fromString(rawIntent)
        var confidence = json.optDouble("confidence", 1.0)
        if (confidence.isNaN() || confidence < 0.0) confidence = 0.0
        if (confidence > 1.0) confidence = 1.0

        val parameters = json.optJSONObject("parameters")?.toMap() ?: emptyMap()
        val context = parseContext(json.optJSONObject("context"))
        
        var requiresClarification = json.optBoolean("requires_clarification", false)
        var clarificationReason = json.optString("clarification_reason").takeIf { it.isNotBlank() }
        val spokenResponse = json.optString("spoken_response").takeIf { it.isNotBlank() }

        // Parse sub-intents if present
        val subIntentsArray = json.optJSONArray("sub_intents")
        val subIntents = if (subIntentsArray != null && subIntentsArray.length() > 0) {
            val list = mutableListOf<IntentPayload>()
            for (i in 0 until subIntentsArray.length()) {
                val subObj = subIntentsArray.optJSONObject(i)
                if (subObj != null) {
                    list.add(parseJsonObject(subObj))
                }
            }
            list
        } else null

        // Apply Deterministic Confidence Policy:
        val tier = ConfidenceTier.fromScore(confidence)
        if (tier == ConfidenceTier.LOW && intentEnum != UserIntent.CONVERSATION && intentEnum != UserIntent.CLARIFICATION_REQUIRED) {
            intentEnum = UserIntent.CLARIFICATION_REQUIRED
            requiresClarification = true
            if (clarificationReason == null) {
                clarificationReason = "Confidence is low ($confidence). Could you please clarify your request?"
            }
        }

        if (intentEnum == UserIntent.CLARIFICATION_REQUIRED) {
            requiresClarification = true
        }

        val finalType = when {
            subIntents != null && subIntents.isNotEmpty() -> "multi_intent"
            requiresClarification -> "clarification"
            intentEnum == UserIntent.CONVERSATION -> "conversation"
            else -> rawType
        }

        return IntentPayload(
            schemaVersion = schemaVersion,
            type = finalType,
            intent = if (subIntents != null && subIntents.isNotEmpty()) UserIntent.MULTI_INTENT else intentEnum,
            confidence = confidence,
            confidenceTier = tier,
            parameters = parameters,
            context = context,
            subIntents = subIntents,
            requiresClarification = requiresClarification,
            clarificationReason = clarificationReason,
            spokenResponse = spokenResponse
        )
    }

    private fun parseContext(json: JSONObject?): IntentContext? {
        if (json == null) return null
        return IntentContext(
            mood = json.optString("mood").takeIf { it.isNotBlank() },
            energy = json.optString("energy").takeIf { it.isNotBlank() },
            urgency = json.optString("urgency").takeIf { it.isNotBlank() },
            timeReference = (json.optString("time_reference").takeIf { it.isNotBlank() }
                ?: json.optString("timeReference").takeIf { it.isNotBlank() }),
            desiredAtmosphere = (json.optString("desired_atmosphere").takeIf { it.isNotBlank() }
                ?: json.optString("desiredAtmosphere").takeIf { it.isNotBlank() }),
            activity = json.optString("activity").takeIf { it.isNotBlank() },
            contentReference = (json.optString("content_reference").takeIf { it.isNotBlank() }
                ?: json.optString("contentReference").takeIf { it.isNotBlank() }),
            rawSignals = json.jsonToMap()
        )
    }

    private fun cleanJsonString(raw: String): String {
        var trimmed = raw.trim()
        if (trimmed.startsWith("```json")) {
            trimmed = trimmed.removePrefix("```json")
        } else if (trimmed.startsWith("```")) {
            trimmed = trimmed.removePrefix("```")
        }
        if (trimmed.endsWith("```")) {
            trimmed = trimmed.removeSuffix("```")
        }
        return trimmed.trim()
    }

    private fun JSONObject.jsonToMap(): Map<String, Any?> {
        val map = mutableMapOf<String, Any?>()
        val keys = this.keys()
        while (keys.hasNext()) {
            val key = keys.next()
            val value = this.get(key)
            map[key] = when (value) {
                is JSONObject -> value.jsonToMap()
                is JSONArray -> value.jsonToList()
                JSONObject.NULL -> null
                else -> value
            }
        }
        return map
    }

    private fun JSONArray.jsonToList(): List<Any?> {
        val list = mutableListOf<Any?>()
        for (i in 0 until this.length()) {
            val item = this.get(i)
            list.add(
                when (item) {
                    is JSONObject -> item.jsonToMap()
                    is JSONArray -> item.jsonToList()
                    JSONObject.NULL -> null
                    else -> item
                }
            )
        }
        return list
    }
}
