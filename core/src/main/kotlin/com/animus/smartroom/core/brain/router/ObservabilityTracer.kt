package com.animus.smartroom.core.brain.router

/**
 * Observability tracer recording structured milestone timestamps and latency metrics.
 */
class ObservabilityTracer(val correlationId: String) {

    private val timestamps = mutableMapOf<String, Long>()
    private val events = mutableListOf<String>()

    init {
        mark("REQUEST_RECEIVED")
    }

    fun mark(eventName: String) {
        val now = System.currentTimeMillis()
        timestamps[eventName] = now
        events.add(eventName)
    }

    fun getTraceLatencies(): Map<String, Long> {
        val t0 = timestamps["REQUEST_RECEIVED"] ?: return emptyMap()
        val latencies = mutableMapOf<String, Long>()

        val tLlm = timestamps["INTENT_CLASSIFICATION"]
        if (tLlm != null) latencies["llm_latency_ms"] = tLlm - t0

        val tVal = timestamps["INTENT_VALIDATED"]
        if (tVal != null && tLlm != null) latencies["validation_latency_ms"] = tVal - tLlm

        val tPlan = timestamps["EXECUTION_PLANNED"]
        if (tPlan != null && tVal != null) latencies["planning_latency_ms"] = tPlan - tVal

        val tActionDone = timestamps["ACTION_COMPLETED"]
        val tActionStart = timestamps["ACTION_STARTED"]
        if (tActionDone != null && tActionStart != null) latencies["hardware_exec_latency_ms"] = tActionDone - tActionStart

        val tVerified = timestamps["HARDWARE_VERIFIED"]
        if (tVerified != null && tActionDone != null) latencies["verification_latency_ms"] = tVerified - tActionDone

        val tFinal = timestamps["FINAL_RESULT"] ?: System.currentTimeMillis()
        latencies["total_latency_ms"] = tFinal - t0

        return latencies
    }

    fun getEvents(): List<String> = events.toList()
}
