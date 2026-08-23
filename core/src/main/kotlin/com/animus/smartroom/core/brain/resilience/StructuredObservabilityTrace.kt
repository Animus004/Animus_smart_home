package com.animus.smartroom.core.brain.resilience

import java.util.UUID

/**
 * Authoritative Structured Observability Trace for Phase 8.
 * Encapsulates the complete diagnostic timeline across all brain pipeline stages.
 */
data class StructuredObservabilityTrace(
    val requestId: String = UUID.randomUUID().toString(),
    val intent: String,
    var currentState: String = "IDLE",
    var healthState: String = "UNKNOWN",
    var arbitrationState: Map<String, String> = emptyMap(),
    var executionState: String = "PLANNED",
    val recoveryEvents: MutableList<String> = mutableListOf(),
    var hardwareVerification: Map<String, Any?> = emptyMap(),
    var finalResult: String = "PENDING",
    val milestoneTimestamps: MutableMap<String, Long> = mutableMapOf(),
    var totalLatencyMs: Long = 0L
) {
    private val t0 = System.currentTimeMillis()

    init {
        mark("REQUEST_INITIALIZED")
    }

    fun mark(milestone: String) {
        val now = System.currentTimeMillis()
        milestoneTimestamps[milestone] = now
        totalLatencyMs = now - t0
    }

    fun addRecoveryEvent(event: String) {
        recoveryEvents.add("[${System.currentTimeMillis() - t0}ms] $event")
    }

    fun toSummaryMap(): Map<String, Any?> {
        return mapOf(
            "request_id" to requestId,
            "intent" to intent,
            "current_state" to currentState,
            "health_state" to healthState,
            "arbitration_state" to arbitrationState,
            "execution_state" to executionState,
            "recovery_events" to recoveryEvents,
            "hardware_verification" to hardwareVerification,
            "final_result" to finalResult,
            "total_latency_ms" to totalLatencyMs
        )
    }
}
