package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.store.AndroidMemoryStore
import com.animus.smartroom.core.memory.store.InMemoryMemoryStore
import com.animus.smartroom.core.port.FakePersistentStore
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MemoryRetentionTest {

    @Test
    fun `InMemoryMemoryStore evicts oldest events when maxCapacity is exceeded`() = runBlocking {
        val store = InMemoryMemoryStore(maxCapacity = 5)

        for (i in 1..8) {
            store.record(LearningEvent(id = "event_$i", timestamp = i * 1000L, topic = "Topic $i", action = "Action $i"))
        }

        assertEquals(5, store.size())
        val recent = store.getRecent(10)
        assertEquals(5, recent.size)

        // Events 1, 2, 3 should have been evicted; 4, 5, 6, 7, 8 should remain
        val ids = recent.map { it.id }.toSet()
        assertFalse(ids.contains("event_1"))
        assertFalse(ids.contains("event_2"))
        assertFalse(ids.contains("event_3"))
        assertTrue(ids.contains("event_4"))
        assertTrue(ids.contains("event_8"))
    }

    @Test
    fun `AndroidMemoryStore evicts oldest events when maxCapacity is exceeded`() = runBlocking {
        val fakePersistentStore = FakePersistentStore()
        val store = AndroidMemoryStore(persistentStore = fakePersistentStore, maxCapacity = 5)

        for (i in 1..8) {
            store.record(LearningEvent(id = "event_$i", timestamp = i * 1000L, topic = "Topic $i", action = "Action $i"))
        }

        val recent = store.getRecent(10)
        assertEquals(5, recent.size)

        val ids = recent.map { it.id }.toSet()
        assertFalse(ids.contains("event_1"))
        assertFalse(ids.contains("event_2"))
        assertFalse(ids.contains("event_3"))
        assertTrue(ids.contains("event_4"))
        assertTrue(ids.contains("event_8"))
    }
}
