package com.animus.smartroom.core.brain.model

data class LocalBrainConfig(
    val enabled: Boolean = true,
    val host: String = "127.0.0.1",
    val port: Int = 11434,
    val model: String = "qwen3:4b-instruct",
    val timeoutMs: Int = 30_000,
    val warmupTimeoutMs: Int = 300_000,
    val maxTokens: Int = 512,
    val temperature: Float = 0.2f
) {
    fun isValid(): Boolean {
        if (host.isBlank()) return false
        if (port !in 1..65535) return false
        if (model.isBlank()) return false
        if (timeoutMs !in 500..300_000) return false
        if (warmupTimeoutMs !in 5000..600_000) return false
        if (maxTokens !in 16..4096) return false
        if (temperature !in 0.0f..2.0f) return false
        return true
    }

    val endpointUrl: String
        get() = "http://$host:$port/v1/chat/completions"

    val baseUrl: String
        get() = "http://$host:$port/v1"
}
