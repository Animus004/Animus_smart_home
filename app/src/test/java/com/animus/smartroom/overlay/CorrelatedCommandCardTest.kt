package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.overlay.model.CorrelatedCommandCard
import com.animus.smartroom.overlay.model.SubActionItem
import org.junit.Assert.*
import org.junit.Test

class CorrelatedCommandCardTest {

    @Test
    fun `three sub-actions under one correlationId are grouped correctly`() {
        val corrId = "cmd-12345"
        val subActions = listOf(
            SubActionItem("s1", DeviceType.AIR_CONDITIONER, "SET_TEMPERATURE", "Bedroom AC → 23°C", ActionStatus.SUCCESS, true),
            SubActionItem("s2", DeviceType.BLUETOOTH_AUDIO, "SET_VOLUME", "Volume → 25%", ActionStatus.SUCCESS, true),
            SubActionItem("s3", DeviceType.BLUETOOTH_AUDIO, "PLAY_MUSIC", "♪ Zara Zara → LG SNC4R", ActionStatus.SUCCESS, true)
        )

        val card = CorrelatedCommandCard(
            correlationId = corrId,
            rawPrompt = "Set AC to 23, volume 25, play Zara Zara",
            subActions = subActions,
            overallStatus = ActionStatus.SUCCESS
        )

        assertEquals(corrId, card.correlationId)
        assertEquals(3, card.subActions.size)
        assertEquals(ActionStatus.SUCCESS, card.overallStatus)
    }

    @Test
    fun `partial failure preserves successful sub-actions and flags overall failure`() {
        val corrId = "cmd-67890"
        val subActions = listOf(
            SubActionItem("s1", DeviceType.AIR_CONDITIONER, "SET_TEMPERATURE", "Bedroom AC → 23°C", ActionStatus.SUCCESS, true),
            SubActionItem("s2", DeviceType.BLUETOOTH_AUDIO, "PLAY_MUSIC", "Music resolution failed", ActionStatus.FAILED, false),
            SubActionItem("s3", DeviceType.BLUETOOTH_AUDIO, "SET_VOLUME", "Volume → 25%", ActionStatus.SUCCESS, true)
        )

        val card = CorrelatedCommandCard(
            correlationId = corrId,
            rawPrompt = "Set AC to 23, volume 25, play Zara Zara",
            subActions = subActions,
            overallStatus = ActionStatus.FAILED
        )

        assertEquals(3, card.subActions.size)
        assertEquals(ActionStatus.FAILED, card.overallStatus)
        assertEquals(2, card.subActions.count { it.status == ActionStatus.SUCCESS })
        assertEquals(1, card.subActions.count { it.status == ActionStatus.FAILED })
    }
}
