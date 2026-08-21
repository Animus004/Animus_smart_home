package com.animus.smartroom.core.memory.store

import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.query.MemoryQuery

/**
 * Pure platform-independent contract for Animus memory storage.
 */
interface MemoryStore {

    /**
     * Records a new memory event, applying retention bounds if necessary.
     */
    suspend fun record(event: MemoryEvent)

    /**
     * Queries stored memory events matching filter/order criteria.
     */
    suspend fun query(query: MemoryQuery): List<MemoryEvent>

    /**
     * Retrieves the most recent memory events up to [limit].
     */
    suspend fun getRecent(limit: Int): List<MemoryEvent>

    /**
     * Retrieves all memory events recorded since [timestamp] (inclusive).
     */
    suspend fun getSince(timestamp: Long): List<MemoryEvent>

    /**
     * Deletes a specific memory event by its ID.
     */
    suspend fun delete(eventId: String): Boolean

    /**
     * Clears all stored memory events.
     */
    suspend fun clear()
}
