package com.animus.smartroom.core.brain.port

interface LocalInferencePort {
    suspend fun generate(
        prompt: String,
        context: List<String> = emptyList()
    ): String

    fun isAvailable(): Boolean
}
