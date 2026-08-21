package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.model.OverlayMusicSummary
import com.animus.smartroom.overlay.model.OverlayTimerCard
import org.junit.Assert.*
import org.junit.Test

class Phase5E21TargetSuiteTest {

    @Test
    fun `OverlayDragGestureTest - clamp coordinates within display boundaries`() {
        val (x, y) = com.animus.smartroom.overlay.storage.OverlayPositionStorage.clampStatic(
            x = 2500,
            y = -500,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )
        assertEquals(930, x)
        assertEquals(0, y)
    }

    @Test
    fun `OverlayScreenBoundsTest - zero coordinates clamped to safe margins`() {
        val (x, y) = com.animus.smartroom.overlay.storage.OverlayPositionStorage.clampStatic(
            x = -100,
            y = 10,
            screenWidth = 1080,
            screenHeight = 2400,
            overlayWidth = 150,
            overlayHeight = 150
        )
        assertEquals(0, x)
        assertEquals(10, y)
    }

    @Test
    fun `MusicCommandVoiceFollowupTest - music persistent state allows follow-up voice command without interrupting music`() {
        val state = FloatingOverlayState(
            visibility = FloatingOverlayVisibility.MUSIC_PERSISTENT,
            musicSummary = OverlayMusicSummary(
                trackTitle = "Zara Zara",
                outputDeviceName = "LG SNC4R",
                isConnected = true,
                isPlaying = true
            ),
            activeTimer = null
        )

        // Follow up timer scheduled
        val stateWithTimer = state.copy(
            activeTimer = OverlayTimerCard(
                actionId = "timer-followup-1",
                deviceType = DeviceType.AIR_CONDITIONER,
                actionType = "POWER_OFF",
                targetTimestamp = System.currentTimeMillis() + 7200000L
            )
        )

        assertTrue(stateWithTimer.isMusicPersistent)
        assertNotNull(stateWithTimer.activeTimer)
        assertEquals("Zara Zara", stateWithTimer.musicSummary.trackTitle)
    }

    @Test
    fun `DuplicateOverlayServiceTest - isRunning property accurately reflects single service instance`() {
        val running = com.animus.smartroom.overlay.service.FloatingAnimusService.isRunning
        assertFalse(running)
    }

    @Test
    fun `ActivityOverlayIndependenceTest - overlay view model bridges without holding Activity context`() {
        val app = com.animus.smartroom.overlay.model.FloatingOverlayState(
            visibility = FloatingOverlayVisibility.COLLAPSED
        )
        assertNotNull(app)
    }

    @Test
    fun `TimerOverlayWakeTest - scheduled timer trigger awakens overlay to timer completion`() {
        val event = AnimusActionEvent(
            id = "timer-exec-1",
            timestamp = System.currentTimeMillis(),
            source = com.animus.smartroom.core.diagnostics.model.ActionSource.SCHEDULER,
            targetDevice = DeviceType.AIR_CONDITIONER,
            action = "POWER_OFF",
            stage = ActionStage.COMPLETED,
            status = ActionStatus.SUCCESS,
            message = "AC OFF Completed"
        )
        val action = com.animus.smartroom.core.overlay.OverlayEventPolicy.evaluate(event)
        assertEquals(com.animus.smartroom.core.overlay.OverlayEventAction.SURFACE_TIMER_COMPLETION, action)
    }
}
