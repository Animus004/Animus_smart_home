package com.animus.smartroom.core.port

/**
 * Platform-independent key-value storage interface.
 */
interface PersistentStore {
    fun getString(key: String, defaultValue: String? = null): String?
    fun putString(key: String, value: String)
    fun remove(key: String)
    fun getAll(): Map<String, *>
    fun registerChangeListener(listener: (String) -> Unit)
    fun unregisterChangeListener(listener: (String) -> Unit)
}
