package com.animus.smartroom.core.brain.router

/**
 * Standardized result returned by the Deterministic Execution Engine.
 */
data class ExecutionResult(
    val status: Status,
    val correlationId: String,
    val intent: String,
    val target: String? = null,
    val requested: Any? = null,
    val verified: Any? = null,
    val message: String,
    val reason: String? = null,
    val latencyTraceMs: Map<String, Long> = emptyMap()
) {
    enum class Status {
        SUCCESS,
        FAILED,
        ALREADY_IN_STATE,
        CLARIFICATION_REQUIRED,
        REJECTED
    }
}
