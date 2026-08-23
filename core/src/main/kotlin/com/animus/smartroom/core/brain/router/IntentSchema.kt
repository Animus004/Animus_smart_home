package com.animus.smartroom.core.brain.router

/**
 * Strict Machine-Readable Intent Contract for Phase 2.
 */
sealed interface BrainIntent {
    val schemaVersion: String get() = "2.0"
    val correlationId: String

    data class DirectCommand(
        val target: CapabilityRegistry.DeviceTarget,
        val capability: CapabilityRegistry.ActionCapability,
        val parameters: Map<String, Any?> = emptyMap(),
        override val correlationId: String = java.util.UUID.randomUUID().toString()
    ) : BrainIntent

    data class RoutineCommand(
        val routineName: String,
        val parameters: Map<String, Any?> = emptyMap(),
        override val correlationId: String = java.util.UUID.randomUUID().toString()
    ) : BrainIntent

    data class MultiActionCommand(
        val actions: List<DirectCommand>,
        override val correlationId: String = java.util.UUID.randomUUID().toString()
    ) : BrainIntent

    data class ClarificationRequired(
        val reason: String, // "AMBIGUOUS_TARGET", "AMBIGUOUS_ACTION", "MISSING_PARAMETER"
        val question: String,
        val candidates: List<String> = emptyList(),
        override val correlationId: String = java.util.UUID.randomUUID().toString()
    ) : BrainIntent

    data class Rejection(
        val reason: String, // "UNKNOWN_DEVICE", "UNKNOWN_CAPABILITY", "INVALID_PARAMETER", "SECURITY_VIOLATION"
        val message: String,
        override val correlationId: String = java.util.UUID.randomUUID().toString()
    ) : BrainIntent

    data class ConversationalOnly(
        val spokenResponse: String,
        override val correlationId: String = java.util.UUID.randomUUID().toString()
    ) : BrainIntent
}
