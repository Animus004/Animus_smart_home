package com.animus.smartroom.brain.repository

import android.content.Context
import android.content.SharedPreferences
import com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine
import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory
import com.animus.smartroom.core.brain.repository.MemoryRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject

class AndroidMemoryRepository(
    private val context: Context? = null,
    private val sharedPreferences: SharedPreferences? = context?.getSharedPreferences("animus_memories", Context.MODE_PRIVATE)
) : MemoryRepository {

    private val mutex = Mutex()
    private val memoriesMap = mutableMapOf<String, Memory>()
    private val _memoriesFlow = MutableStateFlow<List<Memory>>(emptyList())

    init {
        loadPersistedMemories()
    }

    override fun getMemoriesFlow(): Flow<List<Memory>> = _memoriesFlow.asStateFlow()

    override suspend fun getRelevantMemories(
        query: String,
        category: MemoryCategory?,
        limit: Int
    ): List<Memory> = mutex.withLock {
        MemoryRelevanceEngine.rankMemories(query, memoriesMap.values.toList(), category, limit)
    }

    override suspend fun saveMemory(memory: Memory): Unit = mutex.withLock {
        memoriesMap[memory.id] = memory
        persistMemoriesLocked()
        updateFlowLocked()
    }

    override suspend fun deleteMemory(memoryId: String): Boolean = mutex.withLock {
        val removed = memoriesMap.remove(memoryId) != null
        if (removed) {
            persistMemoriesLocked()
            updateFlowLocked()
        }
        removed
    }

    private fun updateFlowLocked() {
        _memoriesFlow.value = memoriesMap.values.toList()
    }

    private fun persistMemoriesLocked() {
        val prefs = sharedPreferences ?: return
        val jsonArray = JSONArray()
        memoriesMap.values.forEach { mem ->
            val obj = JSONObject().apply {
                put("id", mem.id)
                put("content", mem.content)
                put("category", mem.category.name)
                put("createdAt", mem.createdAt)
                put("source", mem.source)
                put("relevance", mem.relevance.toDouble())
            }
            jsonArray.put(obj)
        }
        prefs.edit().putString("memories_json", jsonArray.toString()).apply()
    }

    private fun loadPersistedMemories() {
        val prefs = sharedPreferences ?: return
        val rawJson = prefs.getString("memories_json", null) ?: return
        try {
            val jsonArray = JSONArray(rawJson)
            for (i in 0 until jsonArray.length()) {
                val obj = jsonArray.getJSONObject(i)
                val memory = Memory(
                    id = obj.getString("id"),
                    content = obj.getString("content"),
                    category = MemoryCategory.valueOf(obj.optString("category", MemoryCategory.GENERAL.name)),
                    createdAt = obj.optLong("createdAt", System.currentTimeMillis()),
                    source = obj.optString("source", "USER"),
                    relevance = obj.optDouble("relevance", 1.0).toFloat()
                )
                memoriesMap[memory.id] = memory
            }
            updateFlowLocked()
        } catch (e: Exception) {
            // Log or ignore corrupted storage
        }
    }
}
