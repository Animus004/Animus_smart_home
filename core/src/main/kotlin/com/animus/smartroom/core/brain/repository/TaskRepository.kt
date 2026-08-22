package com.animus.smartroom.core.brain.repository

import com.animus.smartroom.core.brain.model.Task
import com.animus.smartroom.core.brain.model.TaskStatus
import kotlinx.coroutines.flow.Flow

interface TaskRepository {
    fun getTasksFlow(): Flow<List<Task>>
    suspend fun getActiveTasks(): List<Task>
    suspend fun addTask(task: Task)
    suspend fun updateTaskStatus(taskId: String, status: TaskStatus)
    suspend fun deleteTask(taskId: String): Boolean
}
