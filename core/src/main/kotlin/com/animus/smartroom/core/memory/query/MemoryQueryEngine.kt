package com.animus.smartroom.core.memory.query

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.model.ProjectProgressEvent

/**
 * Pure JVM engine that filters, sorts, and limits MemoryEvents.
 */
object MemoryQueryEngine {

    fun execute(events: List<MemoryEvent>, query: MemoryQuery): List<MemoryEvent> {
        var filtered = events.asSequence()

        if (query.category != null) {
            filtered = filtered.filter { it.category == query.category }
        }

        if (query.startTimestamp != null) {
            filtered = filtered.filter { it.timestamp >= query.startTimestamp }
        }

        if (query.endTimestamp != null) {
            filtered = filtered.filter { it.timestamp <= query.endTimestamp }
        }

        if (query.source != null) {
            filtered = filtered.filter { it.source.equals(query.source.trim(), ignoreCase = true) }
        }

        if (query.topic != null) {
            filtered = filtered.filter { event ->
                event is LearningEvent && event.topic.contains(query.topic.trim(), ignoreCase = true)
            }
        }

        if (query.project != null) {
            filtered = filtered.filter { event ->
                event is ProjectProgressEvent && event.projectName.contains(query.project.trim(), ignoreCase = true)
            }
        }

        val sorted = if (query.ascending) {
            filtered.sortedBy { it.timestamp }
        } else {
            filtered.sortedByDescending { it.timestamp }
        }

        return if (query.limit != null && query.limit > 0) {
            sorted.take(query.limit).toList()
        } else {
            sorted.toList()
        }
    }
}
