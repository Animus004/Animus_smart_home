package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningProgress
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.LearningTopicStatus
import org.junit.Assert.assertEquals
import org.junit.Test

class LearningProgressTest {

    @Test
    fun `Empty events return NOT_STARTED status`() {
        val progress = LearningProgress.deriveFromEvents("Python", emptyList())
        assertEquals("Python", progress.topic)
        assertEquals(0L, progress.firstSeen)
        assertEquals(0L, progress.lastActivity)
        assertEquals(0, progress.activityCount)
        assertEquals(0, progress.completedCount)
        assertEquals(LearningTopicStatus.NOT_STARTED, progress.status)
    }

    @Test
    fun `Single studied event derives LEARNING status and correct timestamps`() {
        val events = listOf(
            LearningEvent(timestamp = 1000L, topic = "SQL", action = "Intro", status = LearningStatus.STUDIED)
        )
        val progress = LearningProgress.deriveFromEvents("SQL", events)
        assertEquals(1000L, progress.firstSeen)
        assertEquals(1000L, progress.lastActivity)
        assertEquals(1, progress.activityCount)
        assertEquals(0, progress.completedCount)
        assertEquals(LearningTopicStatus.LEARNING, progress.status)
    }

    @Test
    fun `Practiced event derives PRACTICING status`() {
        val events = listOf(
            LearningEvent(timestamp = 1000L, topic = "Power BI", action = "Intro", status = LearningStatus.STUDIED),
            LearningEvent(timestamp = 2000L, topic = "Power BI", action = "DAX Measures", status = LearningStatus.PRACTICED)
        )
        val progress = LearningProgress.deriveFromEvents("Power BI", events)
        assertEquals(1000L, progress.firstSeen)
        assertEquals(2000L, progress.lastActivity)
        assertEquals(2, progress.activityCount)
        assertEquals(LearningTopicStatus.PRACTICING, progress.status)
    }

    @Test
    fun `Completed events derive COMPLETED status`() {
        val events = listOf(
            LearningEvent(timestamp = 1000L, topic = "Excel", action = "Pivot Tables", status = LearningStatus.PRACTICED),
            LearningEvent(timestamp = 2000L, topic = "Excel", action = "Advanced Formulas", status = LearningStatus.COMPLETED)
        )
        val progress = LearningProgress.deriveFromEvents("Excel", events)
        assertEquals(2, progress.activityCount)
        assertEquals(1, progress.completedCount)
        assertEquals(LearningTopicStatus.COMPLETED, progress.status)
    }
}
