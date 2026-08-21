package com.animus.smartroom.core.memory.summary

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningProgress
import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.model.ProjectProgressEvent
import com.animus.smartroom.core.memory.model.ProjectStatus

/**
 * Structured Morning Briefing synthesizing yesterday's progress and active context.
 */
data class MorningBriefing(
    val date: String,
    val yesterdayHighlights: List<String> = emptyList(),
    val activeLearningTopics: List<String> = emptyList(),
    val projectStatusSummaries: List<String> = emptyList(),
    val activeScheduledActionsSummary: String? = null,
    val deviceStatusSummary: String? = null
) {
    fun formatPlainText(): String {
        val sb = StringBuilder()
        sb.append("Morning Briefing for $date\n")

        if (yesterdayHighlights.isNotEmpty()) {
            sb.append("\nYesterday's Highlights:\n")
            yesterdayHighlights.forEach { sb.append("• $it\n") }
        }

        if (activeLearningTopics.isNotEmpty()) {
            sb.append("\nActive Learning Topics:\n")
            activeLearningTopics.forEach { sb.append("• $it\n") }
        }

        if (projectStatusSummaries.isNotEmpty()) {
            sb.append("\nProjects In Progress:\n")
            projectStatusSummaries.forEach { sb.append("• $it\n") }
        }

        if (!activeScheduledActionsSummary.isNullOrBlank()) {
            sb.append("\nActive Timers / Schedules:\n")
            sb.append("• $activeScheduledActionsSummary\n")
        }

        if (!deviceStatusSummary.isNullOrBlank()) {
            sb.append("\nDevice Status:\n")
            sb.append("• $deviceStatusSummary\n")
        }

        return sb.toString().trim()
    }
}

object MorningBriefingBuilder {

    fun build(
        dateStr: String,
        yesterdaySummary: DailySummary?,
        allLearningEvents: List<LearningEvent> = emptyList(),
        recentProjectEvents: List<ProjectProgressEvent> = emptyList(),
        activeScheduledSummary: String? = null,
        deviceContextSummary: String? = null
    ): MorningBriefing {
        val yHighlights = mutableListOf<String>()
        if (yesterdaySummary != null) {
            yHighlights.addAll(yesterdaySummary.learningHighlights)
            yHighlights.addAll(yesterdaySummary.projectHighlights)
            yHighlights.addAll(yesterdaySummary.completedRoutines)
            yHighlights.addAll(yesterdaySummary.systemMilestones)
        }

        // Active learning topics
        val distinctTopics = allLearningEvents.map { it.topic.trim() }.distinct()
        val learningSummaries = distinctTopics.map { topic ->
            val prog = LearningProgress.deriveFromEvents(topic, allLearningEvents)
            "${prog.topic} (${prog.status.name.lowercase()}, ${prog.activityCount} sessions)"
        }

        // Active projects
        val activeProjects = recentProjectEvents
            .filter { it.status == ProjectStatus.IN_PROGRESS || it.status == ProjectStatus.STARTED || it.status == ProjectStatus.RESUMED }
            .groupBy { it.projectName }
            .map { (name, events) ->
                val latest = events.maxByOrNull { it.timestamp }
                "$name: ${latest?.milestone ?: "In Progress"}"
            }

        return MorningBriefing(
            date = dateStr,
            yesterdayHighlights = yHighlights.distinct(),
            activeLearningTopics = learningSummaries,
            projectStatusSummaries = activeProjects,
            activeScheduledActionsSummary = activeScheduledSummary,
            deviceStatusSummary = deviceContextSummary
        )
    }
}
