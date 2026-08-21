package com.animus.smartroom.core.memory.query

import com.animus.smartroom.core.memory.model.MemoryCategory

/**
 * Filter and ordering criteria for memory retrieval.
 */
data class MemoryQuery(
    val category: MemoryCategory? = null,
    val startTimestamp: Long? = null,
    val endTimestamp: Long? = null,
    val topic: String? = null,
    val project: String? = null,
    val source: String? = null,
    val limit: Int? = null,
    val ascending: Boolean = false
)
