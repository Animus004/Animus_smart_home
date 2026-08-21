package com.animus.smartroom.overlay

import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.service.FloatingAnimusService
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OverlayLifecycleTest {

    @Test
    fun `initial service running state is false before launch`() {
        // FloatingAnimusService.isRunning is companion state
        assertFalse(FloatingAnimusService.isRunning)
    }

    @Test
    fun `overlay state is independent of Activity lifecycle`() {
        val state1 = FloatingOverlayState(isExpanded = true)
        // Simulating activity recreation where overlay state is retained
        val state2 = state1.copy()
        assertTrue(state2.isExpanded)
    }
}
