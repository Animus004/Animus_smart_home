package com.animus.smartroom.core.memory.store

import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.query.MemoryQuery
import com.animus.smartroom.core.memory.query.MemoryQueryEngine
import com.animus.smartroom.core.port.PersistentStore
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray

/**
 * Persistent adapter for [MemoryStore] backed by the platform [PersistentStore] port.
 * Preserves memory events across process termination and system reboots.
 */
class AndroidMemoryStore(
    private val persistentStore: PersistentStore,
    private val maxCapacity: Int = 1000
) : MemoryStore {

    companion object {
        const val KEY_MEMORY_EVENTS = "animus_memory_events"
    }

    private val mutex = Mutex()

    private fun loadEvents(): MutableList<MemoryEvent> {
        val rawJson = persistentStore.getString(KEY_MEMORY_EVENTS, "[]")
        val result = mutableListOf<MemoryEvent>()
        try {
            val array = JSONArray(rawJson)
            for (i in 0 until array.length()) {
                val itemStr = array.getString(i)
                val event = MemoryEvent.fromJson(itemStr)
                if (event != null) {
                    result.add(event)
                }
            }
        } catch (e: Exception) {
            // Graceful handling of corrupted cache
        }
        return result
    }

    private fun persistEvents(events: List<MemoryEvent>) {
        val array = JSONArray()
        events.forEach { array.put(it.toJson()) }
        persistentStore.putString(KEY_MEMORY_EVENTS, array.toString())
    }

    override suspend fun record(event: MemoryEvent) = mutex.withLock {
        val current = loadEvents()
        current.removeAll { it.id == event.id }

        while (current.size >= maxCapacity) {
            val oldest = current.minByOrNull { it.timestamp }
            if (oldest != null) {
                current.remove(oldest)
            } else {
                break
            }
        }

        current.add(event)
        persistEvents(current)
    }

    override suspend fun query(query: MemoryQuery): List<MemoryEvent> = mutex.withLock {
        val current = loadEvents()
        return MemoryQueryEngine.execute(current, query)
    }

    override suspend fun getRecent(limit: Int): List<MemoryEvent> {
        return query(MemoryQuery(limit = limit, ascending = false))
    }

    override suspend fun getSince(timestamp: Long): List<MemoryEvent> {
        return query(MemoryQuery(startTimestamp = timestamp, ascending = true))
    }

    override suspend fun delete(eventId: String): Boolean = mutex.withLock {
        val current = loadEvents()
        val removed = current.removeAll { it.id == eventId }
        if (removed) {
            persistEvents(current)
        }
        return removed
    }

    override suspend fun clear() = mutex.withLock {
        persistEvents(emptyList())
    }
}
