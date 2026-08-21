package com.animus.smartroom.core.diagnostics.model

/**
 * Represents the lifecycle stages of an action execution.
 */
enum class ActionStage {
    RECEIVED,
    PARSING,
    RESOLVING,
    PRECONDITION,
    TRIGGERED,
    EXECUTING,
    VERIFYING,
    COMPLETED,
    FAILED,
    CANCELLED;

    companion object {
        fun fromString(value: String): ActionStage? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}
