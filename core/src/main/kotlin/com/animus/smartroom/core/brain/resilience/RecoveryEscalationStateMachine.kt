package com.animus.smartroom.core.brain.resilience

/**
 * 6-state Bounded Recovery Escalation Lifecycle.
 * HEALTHY -> DEGRADED -> REPAIRING -> RECOVERING -> VERIFIED -> FAILED_REQUIRES_USER
 * Enforces strict bounds: no infinite loops, explicit retry budgets, backoff, and structured telemetry.
 */
enum class ResilienceState {
    HEALTHY,
    DEGRADED,
    REPAIRING,
    RECOVERING,
    VERIFIED,
    FAILED_REQUIRES_USER
}

data class EscalationEvent(
    val fromState: ResilienceState,
    val toState: ResilienceState,
    val reason: String,
    val attemptNumber: Int,
    val timestamp: Long = System.currentTimeMillis()
)

data class RecoveryBudget(
    val maxRetries: Int = 2,
    val initialBackoffMs: Long = 50L,
    val backoffMultiplier: Double = 1.5,
    val timeoutMs: Long = 10_000L
)

class RecoveryEscalationStateMachine(
    val budget: RecoveryBudget = RecoveryBudget()
) {
    var currentState: ResilienceState = ResilienceState.HEALTHY
        private set

    private var currentAttempts: Int = 0
    private val history = mutableListOf<EscalationEvent>()

    fun getHistory(): List<EscalationEvent> = history.toList()

    fun transitionTo(nextState: ResilienceState, reason: String): Boolean {
        // Enforce valid state transitions
        val isValid = when (currentState) {
            ResilienceState.HEALTHY -> nextState in listOf(
                ResilienceState.HEALTHY,
                ResilienceState.DEGRADED,
                ResilienceState.REPAIRING,
                ResilienceState.VERIFIED,
                ResilienceState.FAILED_REQUIRES_USER
            )
            ResilienceState.DEGRADED -> nextState in listOf(
                ResilienceState.HEALTHY,
                ResilienceState.REPAIRING,
                ResilienceState.VERIFIED,
                ResilienceState.FAILED_REQUIRES_USER
            )
            ResilienceState.REPAIRING -> nextState in listOf(
                ResilienceState.RECOVERING,
                ResilienceState.VERIFIED,
                ResilienceState.FAILED_REQUIRES_USER
            )
            ResilienceState.RECOVERING -> nextState in listOf(
                ResilienceState.VERIFIED,
                ResilienceState.REPAIRING,
                ResilienceState.FAILED_REQUIRES_USER
            )
            ResilienceState.VERIFIED -> nextState in listOf(
                ResilienceState.HEALTHY,
                ResilienceState.DEGRADED,
                ResilienceState.VERIFIED,
                ResilienceState.REPAIRING
            )
            ResilienceState.FAILED_REQUIRES_USER -> nextState in listOf(
                ResilienceState.REPAIRING,
                ResilienceState.HEALTHY,
                ResilienceState.VERIFIED
            )
        }

        if (!isValid) return false

        if (nextState == ResilienceState.REPAIRING || nextState == ResilienceState.RECOVERING) {
            currentAttempts++
            if (currentAttempts > budget.maxRetries) {
                // Escalate to terminal failure: budget exhausted
                val failEvent = EscalationEvent(
                    fromState = currentState,
                    toState = ResilienceState.FAILED_REQUIRES_USER,
                    reason = "Retry budget exhausted ($currentAttempts > ${budget.maxRetries}). Cause: $reason",
                    attemptNumber = currentAttempts
                )
                currentState = ResilienceState.FAILED_REQUIRES_USER
                history.add(failEvent)
                return false
            }
        } else if (nextState == ResilienceState.HEALTHY || nextState == ResilienceState.VERIFIED) {
            currentAttempts = 0 // Reset attempt counter upon successful recovery
        }

        val event = EscalationEvent(
            fromState = currentState,
            toState = nextState,
            reason = reason,
            attemptNumber = currentAttempts
        )
        currentState = nextState
        history.add(event)
        return true
    }

    fun computeBackoffMs(attempt: Int): Long {
        var delay = budget.initialBackoffMs
        for (i in 1 until attempt) {
            delay = (delay * budget.backoffMultiplier).toLong()
        }
        return delay.coerceAtMost(2000L)
    }

    fun reset() {
        currentState = ResilienceState.HEALTHY
        currentAttempts = 0
        history.clear()
    }
}
