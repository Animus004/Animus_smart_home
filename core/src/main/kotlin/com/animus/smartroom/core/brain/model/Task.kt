package com.animus.smartroom.core.brain.model

import java.util.UUID

enum class TaskPriority {
    LOW,
    NORMAL,
    HIGH,
    CRITICAL
}

enum class TaskStatus {
    PENDING,
    IN_PROGRESS,
    COMPLETED,
    CANCELLED
}

data class Task(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val description: String? = null,
    val dueAt: Long? = null,
    val priority: TaskPriority = TaskPriority.NORMAL,
    val status: TaskStatus = TaskStatus.PENDING,
    val createdAt: Long = System.currentTimeMillis(),
    val source: String = "USER"
)
