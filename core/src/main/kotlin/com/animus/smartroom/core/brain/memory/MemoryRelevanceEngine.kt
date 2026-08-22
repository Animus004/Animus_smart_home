package com.animus.smartroom.core.brain.memory

import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory
import java.util.Locale

/**
 * Pure-JVM deterministic relevance engine for memory retrieval.
 * Computes a weighted score based on token overlap, category weight, and memory importance.
 * Zero external or vector database dependencies.
 */
object MemoryRelevanceEngine {

    fun rankMemories(
        query: String,
        memories: List<Memory>,
        categoryFilter: MemoryCategory? = null,
        limit: Int = 5
    ): List<Memory> {
        val queryTokens = tokenize(query)
        if (queryTokens.isEmpty() && categoryFilter == null) {
            return memories.sortedByDescending { it.relevance }.take(limit)
        }

        return memories
            .filter { categoryFilter == null || it.category == categoryFilter }
            .map { mem ->
                val score = computeScore(queryTokens, mem)
                Pair(mem, score)
            }
            .filter { it.second > 0f }
            .sortedByDescending { it.second }
            .map { it.first }
            .take(limit)
    }

    private fun computeScore(queryTokens: Set<String>, memory: Memory): Float {
        val memoryTokens = tokenize(memory.content)
        if (queryTokens.isEmpty() || memoryTokens.isEmpty()) {
            return memory.relevance * 0.5f
        }

        val overlapCount = queryTokens.count { memoryTokens.contains(it) }
        if (overlapCount == 0) return 0f

        val overlapRatio = overlapCount.toFloat() / queryTokens.size.toFloat()

        val categoryBonus = when (memory.category) {
            MemoryCategory.PREFERENCE -> 1.3f
            MemoryCategory.ROUTINE_SCHEDULE -> 1.2f
            MemoryCategory.FACT -> 1.1f
            else -> 1.0f
        }

        return (overlapRatio * 0.7f + memory.relevance * 0.3f) * categoryBonus
    }

    private fun tokenize(text: String): Set<String> {
        val stopWords = setOf(
            "the", "a", "an", "is", "in", "at", "to", "for", "of", "and", "or", "on", "my", "me", "i", "you"
        )
        return text.lowercase(Locale.ROOT)
            .split(Regex("[^a-zA-Z0-9_-]+"))
            .filter { it.isNotBlank() && it !in stopWords }
            .toSet()
    }
}
