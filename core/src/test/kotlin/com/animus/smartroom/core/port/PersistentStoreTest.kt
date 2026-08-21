package com.animus.smartroom.core.port

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PersistentStoreTest {

    @Test
    fun `FakePersistentStore basic CRUD and change listener operations`() {
        val store = FakePersistentStore()

        assertNull(store.getString("test_key"))
        assertEquals("default_val", store.getString("test_key", "default_val"))

        val changedKeys = mutableListOf<String>()
        val listener: (String) -> Unit = { changedKeys.add(it) }
        store.registerChangeListener(listener)

        store.putString("test_key", "hello_animus")
        assertEquals("hello_animus", store.getString("test_key"))
        assertEquals(listOf("test_key"), changedKeys)

        store.remove("test_key")
        assertNull(store.getString("test_key"))
        assertEquals(listOf("test_key", "test_key"), changedKeys)

        store.unregisterChangeListener(listener)
        store.putString("another_key", "val")
        assertEquals(2, changedKeys.size) // No extra event after unregister
    }
}
