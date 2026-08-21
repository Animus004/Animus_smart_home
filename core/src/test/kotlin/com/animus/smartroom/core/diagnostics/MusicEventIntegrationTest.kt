package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.query.ActionEventQuery
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class MusicEventIntegrationTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `music playback emits resolving and completed events with sanitized metadata`() {
        val corrId = "corr-music-1"

        // 1. Resolving
        DiagnosticBus.publish {
            create(
                correlationId = corrId,
                source = ActionSource.MUSIC,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "PLAY_MUSIC",
                stage = ActionStage.RESOLVING,
                status = ActionStatus.IN_PROGRESS,
                message = "Resolving 'Zara Zara'",
                metadata = mapOf("track" to "Zara Zara", "outputDevice" to "LG SNC4R")
            )
        }

        // 2. Completed / Playing
        DiagnosticBus.publish {
            completed(
                correlationId = corrId,
                source = ActionSource.MUSIC,
                targetDevice = DeviceType.BLUETOOTH_AUDIO,
                action = "PLAY_MUSIC",
                message = "Playing Zara Zara",
                metadata = mapOf(
                    "track" to "Zara Zara",
                    "provider" to "YouTube Music",
                    "videoId" to "IWjbBSMsQJg",
                    "outputDevice" to "LG SNC4R"
                )
            )
        }

        val events = DiagnosticBus.getRecentActionEvents()
        val musicEvents = ActionEventQuery.bySource(events, ActionSource.MUSIC)
        assertEquals(2, musicEvents.size)

        assertEquals(ActionStage.RESOLVING, musicEvents[0].stage)
        assertEquals(ActionStage.COMPLETED, musicEvents[1].stage)
        assertEquals("IWjbBSMsQJg", musicEvents[1].metadata["videoId"])
        assertEquals("LG SNC4R", musicEvents[1].metadata["outputDevice"])
    }
}
