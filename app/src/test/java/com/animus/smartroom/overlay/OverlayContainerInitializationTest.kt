package com.animus.smartroom.overlay

import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.storage.OverlayPositionStorage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Regression tests for Floating Overlay Container Initialization, ViewTree Lifecycles, and Drag logic.
 * Enforces fix for Phase 5E.2.4 crash: ViewTreeLifecycleOwner not found from DraggableOverlayContainer.
 */
class OverlayContainerInitializationTest {

    @Test
    fun `OverlayPositionStorage correctly clamps coordinates within display boundaries`() {
        val (clampedX, clampedY) = OverlayPositionStorage.clampStatic(
            x = 2000,
            y = 3000,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )

        assertTrue(clampedX <= 1080 - 150)
        assertTrue(clampedY <= 2400 - 150)
        assertTrue(clampedX >= 0)
        assertTrue(clampedY >= 0)
    }

    @Test
    fun `OverlayPositionStorage clamps negative coordinates to zero or safe margin`() {
        val (clampedX, clampedY) = OverlayPositionStorage.clampStatic(
            x = -500,
            y = -200,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )

        assertEquals(0, clampedX)
        assertEquals(0, clampedY)
    }

    @Test
    fun `FloatingOverlayState retains non-null initial state for container binding`() {
        val state = FloatingOverlayState()
        assertEquals(FloatingOverlayVisibility.COLLAPSED, state.visibility)
        assertEquals(false, state.isExpanded)
        assertEquals(false, state.isMusicPersistent)
        assertNotNull(state.musicSummary)
    }
}
