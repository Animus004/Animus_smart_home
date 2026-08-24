package com.animus.smartroom.core.brain.policy

/**
 * Deterministic energy-aware climate comfort policy for Movie Mode.
 * Evaluates current room temperature or active AC state and selects an optimal,
 * energy-efficient temperature according to deterministic comfort rules.
 *
 * Invariant: LLM cannot directly choose or override this temperature decision.
 */
object AdaptiveMovieClimatePolicy {

    const val MIN_TEMPERATURE = 16
    const val MAX_TEMPERATURE = 30

    data class ClimateDecision(
        val targetTemperature: Int?,
        val shouldPowerOn: Boolean,
        val reason: String,
        val isAlreadyOptimal: Boolean = false
    )

    data class ClimateThresholds(
        val veryWarmThreshold: Double = 28.0, // >= 28°C -> target 24°C
        val warmThreshold: Double = 26.0,     // >= 26°C -> target 25°C
        val comfortableThreshold: Double = 24.0, // >= 24°C -> target 26°C
        val veryWarmTarget: Int = 24,
        val warmTarget: Int = 25,
        val comfortableTarget: Int = 26
    )

    /**
     * Deterministically calculates the target temperature and power decision
     * given current ambient temperature and AC state.
     */
    fun evaluate(
        currentAmbientTemp: Double?,
        currentAcTemp: Int? = null,
        isAcPoweredOn: Boolean = false,
        thresholds: ClimateThresholds = ClimateThresholds()
    ): ClimateDecision {
        // If no ambient temp is provided, use current AC set temp or standard comfortable target
        val temp = currentAmbientTemp ?: currentAcTemp?.toDouble() ?: 26.0

        val rawTarget = when {
            temp >= thresholds.veryWarmThreshold -> thresholds.veryWarmTarget
            temp >= thresholds.warmThreshold -> thresholds.warmTarget
            temp >= thresholds.comfortableThreshold -> thresholds.comfortableTarget
            else -> null // Already cool (< 24°C) -> avoid unnecessary cooling
        }

        if (rawTarget == null) {
            return ClimateDecision(
                targetTemperature = null,
                shouldPowerOn = false,
                reason = "Room is already cool (${temp}°C). Avoiding unnecessary cooling for energy efficiency.",
                isAlreadyOptimal = true
            )
        }

        // Clamp to physical bounds
        val clampedTarget = rawTarget.coerceIn(MIN_TEMPERATURE, MAX_TEMPERATURE)

        // Check if AC is already powered on and at this exact target
        if (isAcPoweredOn && currentAcTemp == clampedTarget) {
            return ClimateDecision(
                targetTemperature = clampedTarget,
                shouldPowerOn = true,
                reason = "AC is already running at optimal temperature ${clampedTarget}°C.",
                isAlreadyOptimal = true
            )
        }

        val reason = when {
            temp >= thresholds.veryWarmThreshold -> "Room is very warm (${temp}°C) -> setting energy-aware cooling to ${clampedTarget}°C."
            temp >= thresholds.warmThreshold -> "Room is warm (${temp}°C) -> setting energy-aware cooling to ${clampedTarget}°C."
            else -> "Room is comfortable (${temp}°C) -> maintaining gentle comfort at ${clampedTarget}°C."
        }

        return ClimateDecision(
            targetTemperature = clampedTarget,
            shouldPowerOn = true,
            reason = reason,
            isAlreadyOptimal = false
        )
    }
}
