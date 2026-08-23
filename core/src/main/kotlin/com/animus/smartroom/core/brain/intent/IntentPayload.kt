package com.animus.smartroom.core.brain.intent

/**
 * Versioned, strict schema for intent classification results.
 */
data class IntentPayload(
    val schemaVersion: String = "1.0",
    val type: String = "intent", // "intent", "multi_intent", "conversation", "clarification"
    val intent: UserIntent = UserIntent.UNKNOWN,
    val confidence: Double = 1.0,
    val confidenceTier: ConfidenceTier = ConfidenceTier.fromScore(confidence),
    val parameters: Map<String, Any?> = emptyMap(),
    val context: IntentContext? = null,
    val subIntents: List<IntentPayload>? = null,
    val requiresClarification: Boolean = false,
    val clarificationReason: String? = null,
    val spokenResponse: String? = null
)
