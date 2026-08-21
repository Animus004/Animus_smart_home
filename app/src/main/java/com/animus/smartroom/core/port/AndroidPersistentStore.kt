package com.animus.smartroom.core.port

import android.content.Context
import android.content.SharedPreferences

/**
 * SharedPreferences-backed implementation of [PersistentStore].
 */
class AndroidPersistentStore(
    context: Context,
    prefsName: String
) : PersistentStore {

    private val prefs: SharedPreferences = context.getSharedPreferences(prefsName, Context.MODE_PRIVATE)
    private val listeners = mutableMapOf<(String) -> Unit, SharedPreferences.OnSharedPreferenceChangeListener>()

    override fun getString(key: String, defaultValue: String?): String? {
        return prefs.getString(key, defaultValue)
    }

    override fun putString(key: String, value: String) {
        prefs.edit().putString(key, value).apply()
    }

    override fun remove(key: String) {
        prefs.edit().remove(key).apply()
    }

    override fun getAll(): Map<String, *> {
        return prefs.all
    }

    @Synchronized
    override fun registerChangeListener(listener: (String) -> Unit) {
        val spListener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key != null) {
                listener(key)
            }
        }
        listeners[listener] = spListener
        prefs.registerOnSharedPreferenceChangeListener(spListener)
    }

    @Synchronized
    override fun unregisterChangeListener(listener: (String) -> Unit) {
        val spListener = listeners.remove(listener)
        if (spListener != null) {
            prefs.unregisterOnSharedPreferenceChangeListener(spListener)
        }
    }
}
