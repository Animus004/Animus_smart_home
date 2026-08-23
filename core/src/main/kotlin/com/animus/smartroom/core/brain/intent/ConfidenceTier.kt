package com.animus.smartroom.core.brain.intent

/**
 * Deterministic confidence tiers for intent classification.
 */
enum class ConfidenceTier {
    HIGH,
    MEDIUM,
    LOW;

    companion object {
        const val HIGH_THRESHOLD = 0.85
        const val MEDIUM_THRESHOLD = 0.60

        fun fromScore(score: Double): ConfidenceTier {
            return when {
                score >= HIGH_THRESHOLD -> HIGH
                score >= MEDIUM_THRESHOLD -> MEDIUM
                else -> LOW
            }
        }
    }
}
