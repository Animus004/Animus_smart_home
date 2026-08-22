package com.animus.smartroom.core.brain.port

interface KnowledgeCapturePort {
    suspend fun capture(
        source: String,
        content: String,
        relevance: Float = 1.0f
    ): Boolean
}
