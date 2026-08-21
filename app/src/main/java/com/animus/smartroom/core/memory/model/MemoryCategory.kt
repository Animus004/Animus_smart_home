package com.animus.smartroom.core.memory.model

/**
 * High-level classification for personal memory records.
 */
enum class MemoryCategory {
    LEARNING,
    PROJECT,
    PREFERENCE,
    DEVICE_PREFERENCE,
    ROUTINE,
    DAILY_ACTIVITY,
    SYSTEM_MILESTONE;

    companion object {
        fun fromString(name: String): MemoryCategory? {
            return entries.firstOrNull { it.name.equals(name.trim(), ignoreCase = true) }
        }
    }
}
