package com.animus.smartroom.overlay

import com.animus.smartroom.overlay.storage.OverlayPositionStorage
import org.junit.Assert.assertEquals
import org.junit.Test

class OverlayPositionTest {

    @Test
    fun `clamping within bounds preserves coordinates`() {
        val (x, y) = OverlayPositionStorage.clampStatic(
            x = 100,
            y = 200,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )

        assertEquals(100, x)
        assertEquals(200, y)
    }

    @Test
    fun `clamping past right boundary clamps to maxX`() {
        val (x, _) = OverlayPositionStorage.clampStatic(
            x = 2000,
            y = 200,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )

        assertEquals(930, x) // 1080 - 150
    }

    @Test
    fun `clamping past bottom boundary clamps to maxY`() {
        val (_, y) = OverlayPositionStorage.clampStatic(
            x = 100,
            y = 3000,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )

        assertEquals(2250, y) // 2400 - 150
    }

    @Test
    fun `clamping negative coordinates clamps to zero`() {
        val (x, y) = OverlayPositionStorage.clampStatic(
            x = -50,
            y = -100,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )

        assertEquals(0, x)
        assertEquals(0, y)
    }
}
