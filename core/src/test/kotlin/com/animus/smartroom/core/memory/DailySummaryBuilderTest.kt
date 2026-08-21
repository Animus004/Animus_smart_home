package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.PreferenceEvent
import com.animus.smartroom.core.memory.model.ProjectProgressEvent
import com.animus.smartroom.core.memory.model.ProjectStatus
import com.animus.smartroom.core.memory.model.RoutineHistoryEvent
import com.animus.smartroom.core.memory.model.SystemMilestoneEvent
import com.animus.smartroom.core.memory.summary.DailySummaryBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DailySummaryBuilderTest {

    @Test
    fun `Empty day produces zero metrics`() {
        val summary = DailySummaryBuilder.build("2026-08-21", emptyList())
        assertEquals("2026-08-21", summary.date)
        assertEquals(0, summary.totalMeaningfulEvents)
        assertTrue(summary.learningHighlights.isEmpty())
        assertTrue(summary.projectHighlights.isEmpty())
        assertTrue(summary.completedRoutines.isEmpty())
    }

    @Test
    fun `Mixed events populate corresponding highlights and unfinished items`() {
        val events = listOf(
            LearningEvent(topic = "SQL", action = "Window functions practiced", status = LearningStatus.PRACTICED),
            LearningEvent(topic = "Power BI", action = "DAX optimization", status = LearningStatus.STRUGGLED_WITH),
            ProjectProgressEvent(
                projectName = "Animus",
                milestone = "Phase 5B.1",
                action = "Hardened contracts",
                status = ProjectStatus.COMPLETED
            ),
            ProjectProgressEvent(
                projectName = "Steam Games",
                milestone = "ETL Pipeline",
                action = "Writing pandas transform",
                status = ProjectStatus.IN_PROGRESS
            ),
            RoutineHistoryEvent(
                routineName = "Sleep Mode",
                startedAt = 1000L,
                completedAt = 2000L,
                outcome = "COMPLETED"
            ),
            SystemMilestoneEvent(
                milestoneName = "199 unit tests passing",
                description = "All tests green",
                versionOrPhase = "v5.2"
            ),
            PreferenceEvent(
                prefCategory = "Soundbar",
                key = "default_volume",
                value = "25%"
            )
        )

        val summary = DailySummaryBuilder.build("2026-08-21", events)

        assertEquals(7, summary.totalMeaningfulEvents)
        assertEquals(2, summary.learningHighlights.size)
        assertEquals(2, summary.projectHighlights.size)
        assertEquals(1, summary.completedRoutines.size)
        assertEquals("Sleep Mode (COMPLETED)", summary.completedRoutines[0])
        assertEquals(1, summary.systemMilestones.size)
        assertEquals("[v5.2] 199 unit tests passing", summary.systemMilestones[0])
        assertEquals(1, summary.preferencesChanged.size)

        // Verify unfinished items captured the struggling topic & in-progress project
        assertEquals(2, summary.unfinishedItems.size)
        assertTrue(summary.unfinishedItems.any { it.contains("Needs review: Power BI") })
        assertTrue(summary.unfinishedItems.any { it.contains("In Progress: Steam Games") })
    }
}
