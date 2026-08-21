package com.animus.smartroom.core.diagnostics.model

/**
 * Machine-readable state of an action event.
 */
enum class ActionStatus {
    PENDING,
    IN_PROGRESS,
    SUCCESS,
    NO_CHANGE,
    FAILED,
    CANCELLED;

    companion object {
        fun fromString(value: String): ActionStatus? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}
