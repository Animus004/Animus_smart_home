package com.animus.smartroom.core.port

/**
 * In-memory test implementation of [PersistentStore] for app module tests.
 */
class FakePersistentStore : PersistentStore {

    private val map = mutableMapOf<String, String>()
    private val listeners = mutableListOf<(String) -> Unit>()

    override fun getString(key: String, defaultValue: String?): String? {
        return map[key] ?: defaultValue
    }

    override fun putString(key: String, value: String) {
        map[key] = value
        listeners.forEach { it(key) }
    }

    override fun remove(key: String) {
        map.remove(key)
        listeners.forEach { it(key) }
    }

    override fun getAll(): Map<String, *> {
        return HashMap(map)
    }

    override fun registerChangeListener(listener: (String) -> Unit) {
        listeners.add(listener)
    }

    override fun unregisterChangeListener(listener: (String) -> Unit) {
        listeners.remove(listener)
    }
}
