package com.animus.smartroom.core.memory.store

import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.query.MemoryQuery
import com.animus.smartroom.core.memory.query.MemoryQueryEngine
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Thread-safe in-memory reference implementation of [MemoryStore].
 * Enforces a bounded retention limit (default 1000 items) by evicting oldest events first.
 */
class InMemoryMemoryStore(
    private val maxCapacity: Int = 1000
) : MemoryStore {

    private val events = CopyOnWriteArrayList<MemoryEvent>()
    private val eventIndex = ConcurrentHashMap<String, MemoryEvent>()

    override suspend fun record(event: MemoryEvent) {
        synchronized(this) {
            // If already exists, replace
            val existing = eventIndex[event.id]
            if (existing != null) {
                events.remove(existing)
            }

            // Evict oldest if capacity reached
            while (events.size >= maxCapacity) {
                val oldest = events.minByOrNull { it.timestamp }
                if (oldest != null) {
                    events.remove(oldest)
                    eventIndex.remove(oldest.id)
                } else {
                    break
                }
            }

            events.add(event)
            eventIndex[event.id] = event
        }
    }

    override suspend fun query(query: MemoryQuery): List<MemoryEvent> {
        return MemoryQueryEngine.execute(events.toList(), query)
    }

    override suspend fun getRecent(limit: Int): List<MemoryEvent> {
        return query(MemoryQuery(limit = limit, ascending = false))
    }

    override suspend fun getSince(timestamp: Long): List<MemoryEvent> {
        return query(MemoryQuery(startTimestamp = timestamp, ascending = true))
    }

    override suspend fun delete(eventId: String): Boolean {
        synchronized(this) {
            val removed = eventIndex.remove(eventId)
            return if (removed != null) {
                events.remove(removed)
                true
            } else {
                false
            }
        }
    }

    override suspend fun clear() {
        synchronized(this) {
            events.clear()
            eventIndex.clear()
        }
    }

    fun size(): Int = events.size
}
