package com.animus.smartroom.brain.provider

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64

class GeminiApiKeyStorage(context: Context) {

    companion object {
        private const val PREFS_NAME = "animus_brain_prefs"
        private const val KEY_GEMINI_API_KEY = "gemini_api_key_enc"
        private const val KEY_SELECTED_PROVIDER = "selected_brain_provider"
        private const val OBFUSCATION_SALT = "AnimusSmartRoom_v1.1_Gemini_Salt"
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getSelectedProvider(): com.animus.smartroom.brain.model.BrainProviderType {
        val stored = prefs.getString(KEY_SELECTED_PROVIDER, null)
        return if (stored != null) {
            try {
                com.animus.smartroom.brain.model.BrainProviderType.valueOf(stored)
            } catch (e: Exception) {
                com.animus.smartroom.brain.model.BrainProviderType.LOCAL
            }
        } else if (hasApiKey()) {
            com.animus.smartroom.brain.model.BrainProviderType.GEMINI
        } else {
            com.animus.smartroom.brain.model.BrainProviderType.LOCAL
        }
    }

    fun saveSelectedProvider(type: com.animus.smartroom.brain.model.BrainProviderType) {
        prefs.edit().putString(KEY_SELECTED_PROVIDER, type.name).apply()
    }

    fun getApiKey(): String? {
        val stored = prefs.getString(KEY_GEMINI_API_KEY, null) ?: return null
        return try {
            val decoded = Base64.decode(stored, Base64.NO_WRAP)
            val combined = String(decoded, Charsets.UTF_8)
            if (combined.startsWith(OBFUSCATION_SALT)) {
                combined.removePrefix(OBFUSCATION_SALT)
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    fun saveApiKey(key: String?) {
        val editor = prefs.edit()
        if (key.isNullOrBlank()) {
            editor.remove(KEY_GEMINI_API_KEY).apply()
        } else {
            val combined = OBFUSCATION_SALT + key.trim()
            val encoded = Base64.encodeToString(combined.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
            editor.putString(KEY_GEMINI_API_KEY, encoded).apply()
        }
    }

    fun hasApiKey(): Boolean {
        val key = getApiKey()
        return !key.isNullOrBlank()
    }

    fun getMaskedApiKey(): String? {
        val key = getApiKey() ?: return null
        if (key.length <= 8) return "••••••••"
        val start = key.take(4)
        val end = key.takeLast(4)
        return "$start••••••••$end"
    }
}
