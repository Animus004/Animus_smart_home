package com.animus.smartroom.core.memory.summary

import com.animus.smartroom.core.memory.model.DailyActivityEvent
import com.animus.smartroom.core.memory.model.DevicePreferenceEvent
import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.model.PreferenceEvent
import com.animus.smartroom.core.memory.model.ProjectProgressEvent
import com.animus.smartroom.core.memory.model.ProjectStatus
import com.animus.smartroom.core.memory.model.RoutineHistoryEvent
import com.animus.smartroom.core.memory.model.SystemMilestoneEvent

/**
 * Structured, deterministic summary of a single day's meaningful memory events.
 */
data class DailySummary(
    val date: String,
    val learningHighlights: List<String> = emptyList(),
    val projectHighlights: List<String> = emptyList(),
    val completedRoutines: List<String> = emptyList(),
    val systemMilestones: List<String> = emptyList(),
    val unfinishedItems: List<String> = emptyList(),
    val preferencesChanged: List<String> = emptyList(),
    val totalMeaningfulEvents: Int = 0
)

object DailySummaryBuilder {

    fun build(dateStr: String, events: List<MemoryEvent>): DailySummary {
        val learning = mutableListOf<String>()
        val projects = mutableListOf<String>()
        val routines = mutableListOf<String>()
        val milestones = mutableListOf<String>()
        val unfinished = mutableListOf<String>()
        val preferences = mutableListOf<String>()

        events.forEach { event ->
            when (event) {
                is LearningEvent -> {
                    val highlight = "${event.topic}: ${event.action}"
                    learning.add(highlight)
                    if (event.status == LearningStatus.STRUGGLED_WITH) {
                        unfinished.add("Needs review: ${event.topic} (${event.action})")
                    }
                }
                is ProjectProgressEvent -> {
                    val highlight = "${event.projectName} — ${event.milestone} (${event.status.name.lowercase()})"
                    projects.add(highlight)
                    if (event.status == ProjectStatus.BLOCKED || event.status == ProjectStatus.IN_PROGRESS) {
                        unfinished.add("In Progress: ${event.projectName} (${event.milestone})")
                    }
                }
                is RoutineHistoryEvent -> {
                    if (event.outcome.contains("COMPLETED", ignoreCase = true) || event.outcome.contains("SUCCESS", ignoreCase = true)) {
                        routines.add("${event.routineName} (${event.outcome})")
                    }
                }
                is SystemMilestoneEvent -> {
                    milestones.add("[${event.versionOrPhase}] ${event.milestoneName}")
                }
                is PreferenceEvent -> {
                    preferences.add("${event.key} = ${event.value}")
                }
                is DevicePreferenceEvent -> {
                    preferences.add("${event.targetDevice} preferred state updated")
                }
                is DailyActivityEvent -> {
                    // Optional extra activity
                }
            }
        }

        return DailySummary(
            date = dateStr,
            learningHighlights = learning.distinct(),
            projectHighlights = projects.distinct(),
            completedRoutines = routines.distinct(),
            systemMilestones = milestones.distinct(),
            unfinishedItems = unfinished.distinct(),
            preferencesChanged = preferences.distinct(),
            totalMeaningfulEvents = events.size
        )
    }
}
