package com.animus.smartroom.overlay

import com.animus.smartroom.core.port.OverlayPermissionPort
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OverlayPermissionTest {

    private class FakeOverlayPermissionPort(var granted: Boolean) : OverlayPermissionPort {
        override fun canDrawOverlays(): Boolean = granted
    }

    @Test
    fun `when permission is granted canDrawOverlays returns true`() {
        val port = FakeOverlayPermissionPort(granted = true)
        assertTrue(port.canDrawOverlays())
    }

    @Test
    fun `when permission is denied canDrawOverlays returns false`() {
        val port = FakeOverlayPermissionPort(granted = false)
        assertFalse(port.canDrawOverlays())
    }

    @Test
    fun `permission status change is reflected dynamically`() {
        val port = FakeOverlayPermissionPort(granted = false)
        assertFalse(port.canDrawOverlays())

        port.granted = true
        assertTrue(port.canDrawOverlays())
    }
}
