package com.animus.smartroom.voice

import android.content.Context
import android.content.SharedPreferences

/**
 * Storage for wake-word configuration and rollout/rollback flag.
 * Default is FALSE to ensure strict backward compatibility and manual safety until explicitly enabled.
 */
class VoiceWakeWordConfigStorage(context: Context) {

    companion object {
        private const val PREFS_NAME = "animus_voice_config"
        private const val KEY_WAKE_WORD_ENABLED = "voice_wake_word_enabled"
        private const val DEFAULT_ENABLED = false
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun isWakeWordEnabled(): Boolean {
        return prefs.getBoolean(KEY_WAKE_WORD_ENABLED, DEFAULT_ENABLED)
    }

    fun setWakeWordEnabled(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_WAKE_WORD_ENABLED, enabled).apply()
    }
}
