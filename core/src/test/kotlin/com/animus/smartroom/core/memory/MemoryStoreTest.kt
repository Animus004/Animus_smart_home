package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.MemoryCategory
import com.animus.smartroom.core.memory.model.PreferenceEvent
import com.animus.smartroom.core.memory.query.MemoryQuery
import com.animus.smartroom.core.memory.store.InMemoryMemoryStore
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class MemoryStoreTest {

    private lateinit var store: InMemoryMemoryStore

    @Before
    fun setup() {
        store = InMemoryMemoryStore(maxCapacity = 100)
    }

    @Test
    fun `Record and retrieve single learning event`() = runBlocking {
        val event = LearningEvent(
            topic = "SQL",
            subtopic = "Window Functions",
            action = "Practiced ROW_NUMBER() and RANK()",
            status = LearningStatus.PRACTICED
        )

        store.record(event)
        val recent = store.getRecent(10)

        assertEquals(1, recent.size)
        assertEquals(event.id, recent[0].id)
        assertEquals(MemoryCategory.LEARNING, recent[0].category)
        val retrieved = recent[0] as LearningEvent
        assertEquals("SQL", retrieved.topic)
        assertEquals("Window Functions", retrieved.subtopic)
        assertEquals(LearningStatus.PRACTICED, retrieved.status)
    }

    @Test
    fun `Query respects descending timestamp ordering by default`() = runBlocking {
        val event1 = LearningEvent(timestamp = 1000L, topic = "Kotlin", action = "Basics")
        val event2 = LearningEvent(timestamp = 3000L, topic = "Kotlin", action = "Coroutines")
        val event3 = LearningEvent(timestamp = 2000L, topic = "Kotlin", action = "Flows")

        store.record(event1)
        store.record(event2)
        store.record(event3)

        val results = store.query(MemoryQuery(ascending = false))
        assertEquals(3, results.size)
        assertEquals(3000L, results[0].timestamp)
        assertEquals(2000L, results[1].timestamp)
        assertEquals(1000L, results[2].timestamp)
    }

    @Test
    fun `Delete event by id removes only target event`() = runBlocking {
        val event1 = LearningEvent(topic = "Python", action = "Pandas")
        val event2 = PreferenceEvent(prefCategory = "AC", key = "sleep_temp", value = "24")

        store.record(event1)
        store.record(event2)
        assertEquals(2, store.size())

        val deleted = store.delete(event1.id)
        assertTrue(deleted)
        assertEquals(1, store.size())

        val recent = store.getRecent(10)
        assertEquals(event2.id, recent[0].id)

        val deletedAgain = store.delete(event1.id)
        assertFalse(deletedAgain)
    }

    @Test
    fun `Clear store removes all items`() = runBlocking {
        store.record(LearningEvent(topic = "Math", action = "Calculus"))
        store.record(LearningEvent(topic = "Math", action = "Linear Algebra"))
        assertEquals(2, store.size())

        store.clear()
        assertEquals(0, store.size())
        assertTrue(store.getRecent(10).isEmpty())
    }

    @Test
    fun `Concurrent recording is thread-safe`() = runBlocking {
        val jobs = (1..50).map { i ->
            async {
                store.record(
                    LearningEvent(
                        topic = "Topic $i",
                        action = "Action $i",
                        timestamp = 1000L + i
                    )
                )
            }
        }
        jobs.awaitAll()

        assertEquals(50, store.size())
        val recent = store.getRecent(100)
        assertEquals(50, recent.size)
    }
}
