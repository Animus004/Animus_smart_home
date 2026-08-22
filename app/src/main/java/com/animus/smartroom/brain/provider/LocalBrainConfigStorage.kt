package com.animus.smartroom.brain.provider

import android.content.Context
import android.content.SharedPreferences
import com.animus.smartroom.core.brain.model.LocalBrainConfig

class LocalBrainConfigStorage(context: Context) {

    companion object {
        private const val PREFS_NAME = "animus_local_brain_prefs"
        private const val KEY_ENABLED = "local_brain_enabled"
        private const val KEY_HOST = "local_brain_host"
        private const val KEY_PORT = "local_brain_port"
        private const val KEY_MODEL = "local_brain_model"
        private const val KEY_TIMEOUT_MS = "local_brain_timeout_ms"
        private const val KEY_WARMUP_TIMEOUT_MS = "local_brain_warmup_timeout_ms"
        private const val KEY_MAX_TOKENS = "local_brain_max_tokens"
        private const val KEY_TEMPERATURE = "local_brain_temperature"
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getConfig(): LocalBrainConfig {
        val storedWarmup = prefs.getInt(KEY_WARMUP_TIMEOUT_MS, 300_000)
        val effectiveWarmup = if (storedWarmup < 180_000) 300_000 else storedWarmup
        return LocalBrainConfig(
            enabled = prefs.getBoolean(KEY_ENABLED, true),
            host = prefs.getString(KEY_HOST, "192.168.1.9") ?: "192.168.1.9",
            port = prefs.getInt(KEY_PORT, 11434),
            model = prefs.getString(KEY_MODEL, "qwen3:4b-instruct") ?: "qwen3:4b-instruct",
            timeoutMs = prefs.getInt(KEY_TIMEOUT_MS, 30_000),
            warmupTimeoutMs = effectiveWarmup,
            maxTokens = prefs.getInt(KEY_MAX_TOKENS, 512),
            temperature = prefs.getFloat(KEY_TEMPERATURE, 0.2f)
        )
    }

    fun saveConfig(config: LocalBrainConfig) {
        prefs.edit()
            .putBoolean(KEY_ENABLED, config.enabled)
            .putString(KEY_HOST, config.host.trim())
            .putInt(KEY_PORT, config.port)
            .putString(KEY_MODEL, config.model.trim())
            .putInt(KEY_TIMEOUT_MS, config.timeoutMs)
            .putInt(KEY_WARMUP_TIMEOUT_MS, config.warmupTimeoutMs)
            .putInt(KEY_MAX_TOKENS, config.maxTokens)
            .putFloat(KEY_TEMPERATURE, config.temperature)
            .apply()
    }

    fun setHost(host: String) {
        prefs.edit().putString(KEY_HOST, host.trim()).apply()
    }

    fun setModel(model: String) {
        prefs.edit().putString(KEY_MODEL, model.trim()).apply()
    }
}
