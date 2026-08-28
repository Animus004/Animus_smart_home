package com.animus.smartroom.core.memory.store

import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.query.MemoryQuery
import com.animus.smartroom.core.memory.query.MemoryQueryEngine
import com.animus.smartroom.core.port.PersistentStore
import org.json.JSONArray
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Android persistent implementation of [MemoryStore] backed by [PersistentStore].
 */
class AndroidMemoryStore(
    private val persistentStore: PersistentStore,
    private val maxCapacity: Int = 1000
) : MemoryStore {

    companion object {
        private const val KEY_EVENTS = "animus_memory_events"
    }

    private val events = CopyOnWriteArrayList<MemoryEvent>()

    init {
        loadEvents()
    }

    private fun loadEvents() {
        val raw = persistentStore.getString(KEY_EVENTS) ?: return
        try {
            val arr = JSONArray(raw)
            for (i in 0 until arr.length()) {
                val str = arr.getString(i)
                val evt = MemoryEvent.fromJson(str)
                if (evt != null) {
                    events.add(evt)
                }
            }
        } catch (_: Exception) {}
    }

    private fun persistEvents() {
        try {
            val arr = JSONArray()
            events.takeLast(maxCapacity).forEach { evt ->
                arr.put(evt.toJson())
            }
            persistentStore.putString(KEY_EVENTS, arr.toString())
        } catch (_: Exception) {}
    }

    override suspend fun record(event: MemoryEvent) {
        events.removeIf { it.id == event.id }
        while (events.size >= maxCapacity) {
            events.removeAt(0)
        }
        events.add(event)
        persistEvents()
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
        val removed = events.removeIf { it.id == eventId }
        if (removed) persistEvents()
        return removed
    }

    override suspend fun clear() {
        events.clear()
        persistentStore.remove(KEY_EVENTS)
    }
}
