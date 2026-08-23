package com.animus.smartroom.core.brain.intent

/**
 * Contextual signals extracted during intent understanding.
 * Context is informational only; it does not autonomously trigger actions.
 */
data class IntentContext(
    val mood: String? = null,
    val energy: String? = null,
    val urgency: String? = null,
    val timeReference: String? = null,
    val desiredAtmosphere: String? = null,
    val activity: String? = null,
    val contentReference: String? = null,
    val rawSignals: Map<String, Any?> = emptyMap()
)
