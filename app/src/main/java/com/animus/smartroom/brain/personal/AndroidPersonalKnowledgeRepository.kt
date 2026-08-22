package com.animus.smartroom.brain.personal

import android.content.Context
import android.content.SharedPreferences
import com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine
import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory
import com.animus.smartroom.core.brain.personal.PersonalContextSummary
import com.animus.smartroom.core.brain.personal.PersonalProfile
import com.animus.smartroom.core.brain.personal.PersonalProfileBootstrap
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject

class AndroidPersonalKnowledgeRepository(
    private val context: Context? = null,
    private val sharedPreferences: SharedPreferences? = context?.getSharedPreferences("animus_personal_knowledge", Context.MODE_PRIVATE)
) {
    private val mutex = Mutex()
    private val profile = PersonalProfile()
    private val knowledgeMap = mutableMapOf<String, Memory>()
    private val _knowledgeFlow = MutableStateFlow<List<Memory>>(emptyList())

    init {
        loadPersistedKnowledge()
    }

    fun getKnowledgeFlow(): Flow<List<Memory>> = _knowledgeFlow.asStateFlow()

    suspend fun getRelevantPersonalContext(query: String): PersonalContextSummary = mutex.withLock {
        val ranked = MemoryRelevanceEngine.rankMemories(query, knowledgeMap.values.toList(), null, limit = 5)
        PersonalContextSummary(
            preferredName = profile.preferredName,
            primarySpeaker = profile.primarySpeaker,
            preferredAcTemp = profile.preferredAcTemperatureCelsius,
            activeProjects = profile.activeProjects,
            primaryGoals = profile.primaryGoals,
            relevantPersonalKnowledge = ranked.map { it.content }
        )
    }

    suspend fun saveKnowledge(memory: Memory): Unit = mutex.withLock {
        knowledgeMap[memory.id] = memory
        persistKnowledgeLocked()
        updateFlowLocked()
    }

    suspend fun deleteKnowledge(memoryId: String): Boolean = mutex.withLock {
        val removed = knowledgeMap.remove(memoryId) != null
        if (removed) {
            persistKnowledgeLocked()
            updateFlowLocked()
        }
        removed
    }

    suspend fun deleteKnowledgeMatching(keyword: String): Int = mutex.withLock {
        val toRemove = knowledgeMap.values.filter { it.content.contains(keyword, ignoreCase = true) }
        toRemove.forEach { knowledgeMap.remove(it.id) }
        if (toRemove.isNotEmpty()) {
            persistKnowledgeLocked()
            updateFlowLocked()
        }
        toRemove.size
    }

    suspend fun listAllKnowledge(): List<Memory> = mutex.withLock {
        knowledgeMap.values.toList()
    }

    private fun updateFlowLocked() {
        _knowledgeFlow.value = knowledgeMap.values.toList()
    }

    private fun persistKnowledgeLocked() {
        val prefs = sharedPreferences ?: return
        val array = JSONArray()
        for (k in knowledgeMap.values) {
            val obj = JSONObject()
            obj.put("id", k.id)
            obj.put("content", k.content)
            obj.put("category", k.category.name)
            obj.put("createdAt", k.createdAt)
            obj.put("source", k.source)
            obj.put("relevance", k.relevance.toDouble())
            array.put(obj)
        }
        prefs.edit().putString("personal_knowledge_json", array.toString()).apply()
    }

    private fun loadPersistedKnowledge() {
        val prefs = sharedPreferences
        if (prefs == null) {
            // Seed default bootstrap memories in-memory
            PersonalProfileBootstrap.createInitialMemories().forEach { knowledgeMap[it.id] = it }
            _knowledgeFlow.value = knowledgeMap.values.toList()
            return
        }

        val jsonStr = prefs.getString("personal_knowledge_json", null)
        if (jsonStr.isNullOrBlank()) {
            // First time load -> seed bootstrap memories
            PersonalProfileBootstrap.createInitialMemories().forEach { knowledgeMap[it.id] = it }
            persistKnowledgeLocked()
            _knowledgeFlow.value = knowledgeMap.values.toList()
            return
        }

        try {
            val array = JSONArray(jsonStr)
            for (i in 0 until array.length()) {
                val obj = array.getJSONObject(i)
                val cat = try { MemoryCategory.valueOf(obj.getString("category")) } catch (e: Exception) { MemoryCategory.GENERAL }
                val mem = Memory(
                    id = obj.getString("id"),
                    content = obj.getString("content"),
                    category = cat,
                    createdAt = obj.optLong("createdAt", System.currentTimeMillis()),
                    source = obj.optString("source", "USER"),
                    relevance = obj.optDouble("relevance", 1.0).toFloat()
                )
                knowledgeMap[mem.id] = mem
            }
            _knowledgeFlow.value = knowledgeMap.values.toList()
        } catch (e: Exception) {
            PersonalProfileBootstrap.createInitialMemories().forEach { knowledgeMap[it.id] = it }
            _knowledgeFlow.value = knowledgeMap.values.toList()
        }
    }
}
