package com.animus.smartroom.core.brain.router

import java.util.Locale

/**
 * Detects underspecified or ambiguous commands and produces clarification questions.
 */
object AmbiguityDetector {

    data class AmbiguityCheckResult(
        val isAmbiguous: Boolean,
        val reason: String? = null,
        val question: String? = null,
        val candidates: List<String> = emptyList()
    )

    fun checkAmbiguity(rawInput: String, contextTarget: CapabilityRegistry.DeviceTarget?): AmbiguityCheckResult {
        val normalized = rawInput.trim().lowercase(Locale.ROOT)

        // 1. Generic "Turn it on / power on" without explicit target or context
        if (normalized in setOf("turn it on", "power it on", "start it", "turn on", "switch it on", "power on")) {
            if (contextTarget == null) {
                return AmbiguityCheckResult(
                    isAmbiguous = true,
                    reason = "AMBIGUOUS_TARGET",
                    question = "Which device would you like to turn on: AC, Projector, or Fire TV?",
                    candidates = listOf("AC", "PROJECTOR", "FIRE_TV")
                )
            }
        }

        // 2. Generic "Turn it off / power off" without explicit target or context
        if (normalized in setOf("turn it off", "power it off", "stop it", "turn off", "switch it off", "power off")) {
            if (contextTarget == null) {
                return AmbiguityCheckResult(
                    isAmbiguous = true,
                    reason = "AMBIGUOUS_TARGET",
                    question = "Which device would you like to turn off: AC, Projector, or all devices?",
                    candidates = listOf("AC", "PROJECTOR", "ALL")
                )
            }
        }

        // 3. Generic "Put something on / play something"
        if (normalized in setOf("put something on", "play something", "play video", "watch something")) {
            return AmbiguityCheckResult(
                isAmbiguous = true,
                reason = "AMBIGUOUS_ACTION",
                question = "Do you want music, a movie, or YouTube?",
                candidates = listOf("MUSIC", "MOVIE", "YOUTUBE")
            )
        }

        // 4. Underspecified temperature relative adjustments without context
        if (normalized in setOf("make it cooler", "make it warmer", "it's too cold", "it's too hot")) {
            // If AC is obvious target, can be routed to AC with default step or clarification
            return AmbiguityCheckResult(
                isAmbiguous = false
            )
        }

        return AmbiguityCheckResult(isAmbiguous = false)
    }
}
