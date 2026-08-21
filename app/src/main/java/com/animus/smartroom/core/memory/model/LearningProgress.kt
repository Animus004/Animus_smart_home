package com.animus.smartroom.core.memory.model

enum class LearningTopicStatus {
    NOT_STARTED,
    LEARNING,
    PRACTICING,
    REVIEWING,
    COMPLETED
}

/**
 * Derived learning tracker progress summary for a given topic.
 */
data class LearningProgress(
    val topic: String,
    val firstSeen: Long,
    val lastActivity: Long,
    val activityCount: Int,
    val completedCount: Int,
    val status: LearningTopicStatus
) {
    companion object {
        fun deriveFromEvents(topic: String, events: List<LearningEvent>): LearningProgress {
            val topicEvents = events.filter { it.topic.equals(topic.trim(), ignoreCase = true) }
                .sortedBy { it.timestamp }

            if (topicEvents.isEmpty()) {
                return LearningProgress(
                    topic = topic,
                    firstSeen = 0L,
                    lastActivity = 0L,
                    activityCount = 0,
                    completedCount = 0,
                    status = LearningTopicStatus.NOT_STARTED
                )
            }

            val firstSeen = topicEvents.first().timestamp
            val lastActivity = topicEvents.last().timestamp
            val activityCount = topicEvents.size
            val completedCount = topicEvents.count { it.status == LearningStatus.COMPLETED || it.status == LearningStatus.MASTERED }

            val status = when {
                completedCount >= 3 || topicEvents.last().status == LearningStatus.COMPLETED -> LearningTopicStatus.COMPLETED
                topicEvents.any { it.status == LearningStatus.REVIEWED } -> LearningTopicStatus.REVIEWING
                topicEvents.any { it.status == LearningStatus.PRACTICED } -> LearningTopicStatus.PRACTICING
                else -> LearningTopicStatus.LEARNING
            }

            return LearningProgress(
                topic = topic,
                firstSeen = firstSeen,
                lastActivity = lastActivity,
                activityCount = activityCount,
                completedCount = completedCount,
                status = status
            )
        }
    }
}
