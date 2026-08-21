package com.animus.smartroom.brain.model

import com.animus.smartroom.core.memory.model.MemoryEvent

/**
 * Bounded runtime context provided to the brain (LLM or parser).
 * Encapsulates limited relevant recent memory, device states, and active schedules.
 */
data class BrainContext(
    val recentMemoryEvents: List<MemoryEvent> = emptyList(),
    val learningSummary: String? = null,
    val projectSummary: String? = null,
    val activeSchedulesSummary: String? = null,
    val deviceStatusSummary: String? = null
) {
    companion object {
        const val MAX_CONTEXT_MEMORY_EVENTS = 20

        fun createBounded(
            allEvents: List<MemoryEvent>,
            learningSummary: String? = null,
            projectSummary: String? = null,
            activeSchedulesSummary: String? = null,
            deviceStatusSummary: String? = null
        ): BrainContext {
            return BrainContext(
                recentMemoryEvents = allEvents.take(MAX_CONTEXT_MEMORY_EVENTS),
                learningSummary = learningSummary,
                projectSummary = projectSummary,
                activeSchedulesSummary = activeSchedulesSummary,
                deviceStatusSummary = deviceStatusSummary
            )
        }
    }
}
