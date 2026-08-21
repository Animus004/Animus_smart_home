package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.ProjectProgressEvent
import com.animus.smartroom.core.memory.model.ProjectStatus
import com.animus.smartroom.core.memory.summary.DailySummary
import com.animus.smartroom.core.memory.summary.MorningBriefingBuilder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MorningBriefingBuilderTest {

    @Test
    fun `Empty inputs produce clean deterministic briefing`() {
        val briefing = MorningBriefingBuilder.build(
            dateStr = "2026-08-22",
            yesterdaySummary = null
        )

        assertEquals("2026-08-22", briefing.date)
        assertTrue(briefing.yesterdayHighlights.isEmpty())
        assertTrue(briefing.activeLearningTopics.isEmpty())
        assertTrue(briefing.projectStatusSummaries.isEmpty())
        assertEquals("Morning Briefing for 2026-08-22", briefing.formatPlainText())
    }

    @Test
    fun `Synthesize yesterday highlights, active learning, and project status`() {
        val yesterdaySummary = DailySummary(
            date = "2026-08-21",
            learningHighlights = listOf("SQL: Window functions practiced"),
            projectHighlights = listOf("Animus — Phase 5B.1 (completed)"),
            completedRoutines = listOf("Sleep Mode (COMPLETED)"),
            systemMilestones = listOf("[Phase 5B.1] 199 unit tests passing")
        )

        val learningEvents = listOf(
            LearningEvent(topic = "SQL", action = "Intro", status = LearningStatus.STUDIED),
            LearningEvent(topic = "SQL", action = "Window functions", status = LearningStatus.PRACTICED),
            LearningEvent(topic = "Power BI", action = "DAX", status = LearningStatus.STUDIED)
        )

        val projectEvents = listOf(
            ProjectProgressEvent(
                projectName = "Steam Games Analysis",
                milestone = "ETL Parser",
                action = "Writing transform",
                status = ProjectStatus.IN_PROGRESS
            ),
            ProjectProgressEvent(
                projectName = "Animus",
                milestone = "Phase 5C",
                action = "Implementing Memory",
                status = ProjectStatus.IN_PROGRESS
            )
        )

        val briefing = MorningBriefingBuilder.build(
            dateStr = "2026-08-22",
            yesterdaySummary = yesterdaySummary,
            allLearningEvents = learningEvents,
            recentProjectEvents = projectEvents,
            activeScheduledSummary = "AC scheduled to turn off at 11 PM",
            deviceContextSummary = "Bedroom AC is OFF • LG Soundbar Connected"
        )

        assertEquals(4, briefing.yesterdayHighlights.size)
        assertEquals(2, briefing.activeLearningTopics.size)
        assertEquals(2, briefing.projectStatusSummaries.size)
        assertEquals("AC scheduled to turn off at 11 PM", briefing.activeScheduledActionsSummary)

        val plainText = briefing.formatPlainText()
        assertTrue(plainText.contains("Morning Briefing for 2026-08-22"))
        assertTrue(plainText.contains("SQL: Window functions practiced"))
        assertTrue(plainText.contains("Steam Games Analysis: ETL Parser"))
        assertTrue(plainText.contains("AC scheduled to turn off at 11 PM"))
    }
}
