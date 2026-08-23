package com.animus.smartroom.core.brain.intent

/**
 * Centralized registry of all supported and extensible user intents for Animus Smart Room.
 */
enum class UserIntent {
    // Core Phase 1 Intents
    GENERAL_COMMAND,
    MOVIE,
    VIDEO,
    MUSIC,
    WORK_MODE,
    SLEEP_ROUTINE,
    WEATHER,
    NEWS,
    INFORMATION_QUERY,
    DEVICE_STATUS,
    FOLLOW_UP,
    CONVERSATION,
    UNKNOWN,
    CLARIFICATION_REQUIRED,
    MULTI_INTENT,

    // Extensible Domain-Specific Intents (registered for future phases)
    AC_CONTROL,
    PROJECTOR_CONTROL,
    FIRE_TV_CONTROL,
    BLUETOOTH_ROUTING,
    AUDIO_ROUTING,
    MOVIE_NIGHT,
    GOODNIGHT,
    MORNING_ROUTINE,
    ALARM,
    NETFLIX,
    YOUTUBE;

    companion object {
        fun fromString(raw: String?): UserIntent {
            if (raw.isNullOrBlank()) return UNKNOWN
            val sanitized = raw.trim().uppercase()
            return entries.firstOrNull { it.name == sanitized } ?: UNKNOWN
        }
    }
}
