package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.DailyActivityEvent
import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.MemoryCategory
import com.animus.smartroom.core.memory.model.PreferenceEvent
import com.animus.smartroom.core.memory.model.ProjectProgressEvent
import com.animus.smartroom.core.memory.model.ProjectStatus
import com.animus.smartroom.core.memory.model.SystemMilestoneEvent
import com.animus.smartroom.core.memory.query.MemoryQuery
import com.animus.smartroom.core.memory.query.MemoryQueryEngine
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MemoryQueryEngineTest {

    private val sampleEvents = listOf(
        LearningEvent(timestamp = 1000L, topic = "SQL", action = "Window functions", source = "USER"),
        LearningEvent(timestamp = 2000L, topic = "Power BI", action = "DAX measures", source = "USER"),
        ProjectProgressEvent(
            timestamp = 3000L,
            projectName = "Steam Games Analysis",
            milestone = "Data Cleaning",
            action = "Merged datasets",
            status = ProjectStatus.COMPLETED,
            source = "USER"
        ),
        ProjectProgressEvent(
            timestamp = 4000L,
            projectName = "Amazon Review Analysis",
            milestone = "Dashboard",
            action = "Created charts",
            status = ProjectStatus.IN_PROGRESS,
            source = "USER"
        ),
        PreferenceEvent(timestamp = 5000L, prefCategory = "AC", key = "target_temp", value = "24", source = "USER"),
        SystemMilestoneEvent(
            timestamp = 6000L,
            milestoneName = "Phase 5B.1 Hardening",
            description = "199 unit tests passing",
            versionOrPhase = "Phase 5B.1",
            source = "SYSTEM"
        ),
        DailyActivityEvent(timestamp = 7000L, title = "Exercise", description = "Morning run", source = "SYSTEM")
    )

    @Test
    fun `Filter by category returns only matching items`() {
        val query = MemoryQuery(category = MemoryCategory.LEARNING)
        val result = MemoryQueryEngine.execute(sampleEvents, query)

        assertEquals(2, result.size)
        assertTrue(result.all { it.category == MemoryCategory.LEARNING })
    }

    @Test
    fun `Filter by timestamp range`() {
        val query = MemoryQuery(startTimestamp = 2000L, endTimestamp = 4000L)
        val result = MemoryQueryEngine.execute(sampleEvents, query)

        assertEquals(3, result.size)
        assertEquals(4000L, result[0].timestamp)
        assertEquals(3000L, result[1].timestamp)
        assertEquals(2000L, result[2].timestamp)
    }

    @Test
    fun `Filter by topic query`() {
        val query = MemoryQuery(topic = "SQL")
        val result = MemoryQueryEngine.execute(sampleEvents, query)

        assertEquals(1, result.size)
        val event = result[0] as LearningEvent
        assertEquals("SQL", event.topic)
    }

    @Test
    fun `Filter by project query`() {
        val query = MemoryQuery(project = "Steam Games")
        val result = MemoryQueryEngine.execute(sampleEvents, query)

        assertEquals(1, result.size)
        val event = result[0] as ProjectProgressEvent
        assertEquals("Steam Games Analysis", event.projectName)
    }

    @Test
    fun `Filter by source`() {
        val query = MemoryQuery(source = "SYSTEM")
        val result = MemoryQueryEngine.execute(sampleEvents, query)

        assertEquals(2, result.size)
        assertTrue(result.all { it.source == "SYSTEM" })
    }

    @Test
    fun `Limit constraint truncates results`() {
        val query = MemoryQuery(limit = 3)
        val result = MemoryQueryEngine.execute(sampleEvents, query)

        assertEquals(3, result.size)
        assertEquals(7000L, result[0].timestamp)
        assertEquals(6000L, result[1].timestamp)
        assertEquals(5000L, result[2].timestamp)
    }
}
