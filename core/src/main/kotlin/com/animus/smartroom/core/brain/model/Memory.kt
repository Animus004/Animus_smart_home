package com.animus.smartroom.core.brain.model

import java.util.UUID

enum class MemoryCategory {
    PREFERENCE,
    DEVICE_USAGE,
    FACT,
    ROUTINE_SCHEDULE,
    PROJECT,
    GOAL,
    EXPLICIT_MEMORY,
    GENERAL
}

data class Memory(
    val id: String = UUID.randomUUID().toString(),
    val content: String,
    val category: MemoryCategory = MemoryCategory.GENERAL,
    val createdAt: Long = System.currentTimeMillis(),
    val source: String = "USER",
    val relevance: Float = 1.0f
)
