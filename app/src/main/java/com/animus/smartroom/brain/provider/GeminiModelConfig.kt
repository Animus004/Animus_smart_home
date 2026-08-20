package com.animus.smartroom.brain.provider

object GeminiModelConfig {
    /**
     * Currently active supported Flash model for standard REST generateContent.
     * 'gemini-3.5-flash-lite' is optimized for high-volume, low-latency structured JSON parsing (500 RPD quota).
     */
    const val DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
    private const val BASE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

    fun getGenerateContentUrl(modelId: String = DEFAULT_GEMINI_MODEL): String {
        return "$BASE_ENDPOINT/$modelId:generateContent"
    }
}
