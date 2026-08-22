package com.animus.smartroom.brain.repository

import android.content.Context
import android.content.SharedPreferences
import com.animus.smartroom.core.brain.model.Task
import com.animus.smartroom.core.brain.model.TaskPriority
import com.animus.smartroom.core.brain.model.TaskStatus
import com.animus.smartroom.core.brain.repository.TaskRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject

class AndroidTaskRepository(
    private val context: Context? = null,
    private val sharedPreferences: SharedPreferences? = context?.getSharedPreferences("animus_tasks", Context.MODE_PRIVATE)
) : TaskRepository {

    private val mutex = Mutex()
    private val tasksMap = mutableMapOf<String, Task>()
    private val _tasksFlow = MutableStateFlow<List<Task>>(emptyList())

    init {
        loadPersistedTasks()
    }

    override fun getTasksFlow(): Flow<List<Task>> = _tasksFlow.asStateFlow()

    override suspend fun getActiveTasks(): List<Task> = mutex.withLock {
        tasksMap.values.filter { it.status == TaskStatus.PENDING || it.status == TaskStatus.IN_PROGRESS }
            .sortedBy { it.dueAt ?: Long.MAX_VALUE }
    }

    suspend fun getTodayTasks(): List<Task> = mutex.withLock {
        val now = System.currentTimeMillis()
        val startOfDay = now - (now % 86400000L)
        val endOfDay = startOfDay + 86400000L
        tasksMap.values.filter {
            val due = it.dueAt
            due != null && due in startOfDay until endOfDay
        }
    }

    suspend fun getOverdueTasks(): List<Task> = mutex.withLock {
        val now = System.currentTimeMillis()
        tasksMap.values.filter {
            val due = it.dueAt
            due != null && due < now && it.status == TaskStatus.PENDING
        }
    }

    suspend fun getUpcomingTasks(): List<Task> = mutex.withLock {
        val now = System.currentTimeMillis()
        tasksMap.values.filter {
            val due = it.dueAt
            due != null && due >= now && it.status == TaskStatus.PENDING
        }
    }

    override suspend fun addTask(task: Task): Unit = mutex.withLock {
        tasksMap[task.id] = task
        persistTasksLocked()
        updateFlowLocked()
    }

    override suspend fun updateTaskStatus(taskId: String, status: TaskStatus): Unit = mutex.withLock {
        val existing = tasksMap[taskId]
        if (existing != null) {
            tasksMap[taskId] = existing.copy(status = status)
            persistTasksLocked()
            updateFlowLocked()
        }
    }

    override suspend fun deleteTask(taskId: String): Boolean = mutex.withLock {
        val removed = tasksMap.remove(taskId) != null
        if (removed) {
            persistTasksLocked()
            updateFlowLocked()
        }
        removed
    }

    private fun updateFlowLocked() {
        _tasksFlow.value = tasksMap.values.toList()
    }

    private fun persistTasksLocked() {
        val prefs = sharedPreferences ?: return
        val jsonArray = JSONArray()
        tasksMap.values.forEach { task ->
            val obj = JSONObject().apply {
                put("id", task.id)
                put("title", task.title)
                put("description", task.description ?: "")
                if (task.dueAt != null) put("dueAt", task.dueAt)
                put("priority", task.priority.name)
                put("status", task.status.name)
                put("createdAt", task.createdAt)
                put("source", task.source)
            }
            jsonArray.put(obj)
        }
        prefs.edit().putString("tasks_json", jsonArray.toString()).apply()
    }

    private fun loadPersistedTasks() {
        val prefs = sharedPreferences ?: return
        val rawJson = prefs.getString("tasks_json", null) ?: return
        try {
            val jsonArray = JSONArray(rawJson)
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                val task = Task(
                    id = obj.getString("id"),
                    title = obj.getString("title"),
                    description = obj.optString("description").takeIf { it.isNotBlank() },
                    dueAt = if (obj.has("dueAt")) obj.getLong("dueAt") else null,
                    priority = TaskPriority.valueOf(obj.optString("priority", TaskPriority.NORMAL.name)),
                    status = TaskStatus.valueOf(obj.optString("status", TaskStatus.PENDING.name)),
                    createdAt = obj.optLong("createdAt", System.currentTimeMillis()),
                    source = obj.optString("source", "USER")
                )
                tasksMap[task.id] = task
            }
            updateFlowLocked()
        } catch (e: Exception) {
            // Log or ignore corrupted storage
        }
    }
}
