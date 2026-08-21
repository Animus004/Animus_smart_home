package com.animus.smartroom.core.memory

import com.animus.smartroom.brain.model.BrainContext
import com.animus.smartroom.core.memory.model.LearningEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BrainContextMemoryTest {

    @Test
    fun `BrainContext bounds memory events to maximum limit`() {
        val events = (1..50).map { i ->
            LearningEvent(topic = "Topic $i", action = "Action $i")
        }

        val context = BrainContext.createBounded(
            allEvents = events,
            learningSummary = "Active in SQL and Python",
            projectSummary = "Phase 5C underway"
        )

        assertEquals(BrainContext.MAX_CONTEXT_MEMORY_EVENTS, context.recentMemoryEvents.size)
        assertEquals(20, context.recentMemoryEvents.size)
        assertEquals("Active in SQL and Python", context.learningSummary)
        assertEquals("Phase 5C underway", context.projectSummary)
    }

    @Test
    fun `BrainContext handles empty memory gracefully`() {
        val context = BrainContext.createBounded(emptyList())
        assertTrue(context.recentMemoryEvents.isEmpty())
    }
}
