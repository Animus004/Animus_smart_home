package com.animus.smartroom.core.diagnostics.model

/**
 * Categorizes the initiating entity or subsystem of an action event.
 */
enum class ActionSource {
    USER_COMMAND,
    SCHEDULER,
    ROUTINE,
    SYSTEM,
    BRAIN,
    DEVICE,
    MUSIC;

    companion object {
        fun fromString(value: String): ActionSource? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}
