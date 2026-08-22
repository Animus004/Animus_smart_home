package com.animus.smartroom.core.brain.repository

import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory
import kotlinx.coroutines.flow.Flow

interface MemoryRepository {
    fun getMemoriesFlow(): Flow<List<Memory>>
    suspend fun getRelevantMemories(query: String, category: MemoryCategory? = null, limit: Int = 5): List<Memory>
    suspend fun saveMemory(memory: Memory)
    suspend fun deleteMemory(memoryId: String): Boolean
}
