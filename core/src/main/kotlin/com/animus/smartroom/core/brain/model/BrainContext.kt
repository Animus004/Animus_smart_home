package com.animus.smartroom.core.brain.model

data class TaskSummary(
    val id: String,
    val title: String,
    val priority: String,
    val status: String,
    val dueAt: Long?
)

data class ScheduledActionSummary(
    val id: String,
    val target: String,
    val actionType: String,
    val scheduledTimeMillis: Long,
    val status: String
)

data class DeviceSummary(
    val name: String,
    val type: String,
    val isOnline: Boolean,
    val state: Map<String, Any> = emptyMap()
)

data class MusicSummary(
    val trackTitle: String?,
    val isPlaying: Boolean,
    val activeOutputDeviceName: String?,
    val isOutputConnected: Boolean
)

data class RecentActionSummary(
    val id: String,
    val action: String,
    val targetDevice: String?,
    val status: String,
    val timestamp: Long
)

/**
 * Curated, bounded, immutable context provided to the Brain for interpretation.
 * Contains only safe domain summaries. Never exposes credentials, API keys, or raw system descriptors.
 */
data class BrainContext(
    val currentTimeMillis: Long = System.currentTimeMillis(),
    val timezone: String = "UTC",
    val brainMode: String = "LOCAL",
    val todayTasks: List<TaskSummary> = emptyList(),
    val overdueTasks: List<TaskSummary> = emptyList(),
    val upcomingTasks: List<TaskSummary> = emptyList(),
    val scheduledActions: List<ScheduledActionSummary> = emptyList(),
    val deviceSummaries: List<DeviceSummary> = emptyList(),
    val currentMusicSummary: MusicSummary? = null,
    val recentActionSummaries: List<RecentActionSummary> = emptyList(),
    val userPreferences: UserPreferences = UserPreferences(),
    val relevantMemories: List<Memory> = emptyList(),
    val sessionSummary: com.animus.smartroom.core.brain.session.AssistantSessionSummary? = null,
    val personalContext: com.animus.smartroom.core.brain.personal.PersonalContextSummary? = null
) {
    companion object {
        const val MAX_TASKS_PER_SECTION = 10
        const val MAX_MEMORIES = 10
        const val MAX_MEMORY_CONTENT_LENGTH = 250
        const val MAX_SCHEDULED_ACTIONS = 10
        const val MAX_RECENT_ACTIONS = 5

        /**
         * Builder helper ensuring context never exceeds size and safety boundaries.
         */
        fun bounded(
            currentTimeMillis: Long = System.currentTimeMillis(),
            timezone: String = "UTC",
            brainMode: String = "LOCAL",
            todayTasks: List<TaskSummary> = emptyList(),
            overdueTasks: List<TaskSummary> = emptyList(),
            upcomingTasks: List<TaskSummary> = emptyList(),
            scheduledActions: List<ScheduledActionSummary> = emptyList(),
            deviceSummaries: List<DeviceSummary> = emptyList(),
            currentMusicSummary: MusicSummary? = null,
            recentActionSummaries: List<RecentActionSummary> = emptyList(),
            userPreferences: UserPreferences = UserPreferences(),
            relevantMemories: List<Memory> = emptyList(),
            sessionSummary: com.animus.smartroom.core.brain.session.AssistantSessionSummary? = null,
            personalContext: com.animus.smartroom.core.brain.personal.PersonalContextSummary? = null
        ): BrainContext {
            val sanitizedMemories = relevantMemories
                .take(MAX_MEMORIES)
                .map { mem ->
                    if (mem.content.length > MAX_MEMORY_CONTENT_LENGTH) {
                        mem.copy(content = mem.content.take(MAX_MEMORY_CONTENT_LENGTH) + "...")
                    } else {
                        mem
                    }
                }

            return BrainContext(
                currentTimeMillis = currentTimeMillis,
                timezone = timezone,
                brainMode = brainMode,
                todayTasks = todayTasks.take(MAX_TASKS_PER_SECTION),
                overdueTasks = overdueTasks.take(MAX_TASKS_PER_SECTION),
                upcomingTasks = upcomingTasks.take(MAX_TASKS_PER_SECTION),
                scheduledActions = scheduledActions.take(MAX_SCHEDULED_ACTIONS),
                deviceSummaries = deviceSummaries,
                currentMusicSummary = currentMusicSummary,
                recentActionSummaries = recentActionSummaries.take(MAX_RECENT_ACTIONS),
                userPreferences = userPreferences,
                relevantMemories = sanitizedMemories,
                sessionSummary = sessionSummary,
                personalContext = personalContext
            )
        }
    }
}
