package com.animus.smartroom.device

import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DeviceCapabilityTest {

    @Test
    fun testCapabilityFromStringParsing() {
        assertEquals(DeviceCapability.Power, DeviceCapability.fromString("POWER"))
        assertEquals(DeviceCapability.Power, DeviceCapability.fromString("power_state"))
        assertEquals(DeviceCapability.Temperature, DeviceCapability.fromString("TEMPERATURE"))
        assertEquals(DeviceCapability.Temperature, DeviceCapability.fromString("temp"))
        assertEquals(DeviceCapability.HvacMode, DeviceCapability.fromString("MODE"))
        assertEquals(DeviceCapability.HvacMode, DeviceCapability.fromString("hvac_mode"))
        assertEquals(DeviceCapability.FanSpeed, DeviceCapability.fromString("FAN_SPEED"))
        assertEquals(DeviceCapability.FanSpeed, DeviceCapability.fromString("fan"))
        assertEquals(DeviceCapability.Swing, DeviceCapability.fromString("SWING"))
        assertEquals(DeviceCapability.Connect, DeviceCapability.fromString("CONNECT"))
        assertEquals(DeviceCapability.Disconnect, DeviceCapability.fromString("DISCONNECT"))
        assertEquals(DeviceCapability.Play, DeviceCapability.fromString("PLAY"))
        assertEquals(DeviceCapability.Pause, DeviceCapability.fromString("PAUSE"))
        assertEquals(DeviceCapability.Next, DeviceCapability.fromString("NEXT"))
        assertEquals(DeviceCapability.Previous, DeviceCapability.fromString("PREVIOUS"))
        assertEquals(DeviceCapability.Volume, DeviceCapability.fromString("VOLUME"))
        assertEquals(DeviceCapability.SelectInput, DeviceCapability.fromString("SELECT_INPUT"))
        assertEquals(DeviceCapability.CurrentInput, DeviceCapability.fromString("CURRENT_INPUT"))
        assertEquals(DeviceCapability.Brightness, DeviceCapability.fromString("BRIGHTNESS"))
        assertEquals(DeviceCapability.Color, DeviceCapability.fromString("COLOR"))
        assertEquals(DeviceCapability.ColorTemperature, DeviceCapability.fromString("COLOR_TEMPERATURE"))
        assertNull(DeviceCapability.fromString("UNSUPPORTED_RANDOM_CAP"))
    }

    @Test
    fun testRoomDeviceCapabilitySupport() {
        val speaker = RoomDevice(
            id = "bt-1",
            displayName = "Bedroom Speaker",
            type = DeviceType.BLUETOOTH_AUDIO,
            supportedCapabilities = setOf(
                DeviceCapability.Connect,
                DeviceCapability.Disconnect,
                DeviceCapability.Volume,
                DeviceCapability.Play
            )
        )

        assertTrue(speaker.supportsCapability(DeviceCapability.Connect))
        assertTrue(speaker.supportsCapability(DeviceCapability.Volume))
        assertFalse(speaker.supportsCapability(DeviceCapability.Temperature))
        assertFalse(speaker.supportsCapability(DeviceCapability.Swing))

        val ac = RoomDevice(
            id = "ac-1",
            displayName = "Bedroom AC",
            type = DeviceType.AIR_CONDITIONER,
            supportedCapabilities = setOf(
                DeviceCapability.Power,
                DeviceCapability.Temperature,
                DeviceCapability.HvacMode,
                DeviceCapability.FanSpeed,
                DeviceCapability.Swing
            )
        )

        assertTrue(ac.supportsCapability(DeviceCapability.Temperature))
        assertTrue(ac.supportsCapability(DeviceCapability.Power))
        assertFalse(ac.supportsCapability(DeviceCapability.Volume))
        assertFalse(ac.supportsCapability(DeviceCapability.Next))
    }
}
