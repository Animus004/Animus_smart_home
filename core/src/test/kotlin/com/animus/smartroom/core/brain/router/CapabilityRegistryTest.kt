package com.animus.smartroom.core.brain.router

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class CapabilityRegistryTest {

    @Test
    fun `test device target parsing aliases`() {
        assertEquals(CapabilityRegistry.DeviceTarget.AC, CapabilityRegistry.DeviceTarget.fromString("ac"))
        assertEquals(CapabilityRegistry.DeviceTarget.AC, CapabilityRegistry.DeviceTarget.fromString("AIR_CONDITIONER"))
        assertEquals(CapabilityRegistry.DeviceTarget.PROJECTOR, CapabilityRegistry.DeviceTarget.fromString("projector"))
        assertEquals(CapabilityRegistry.DeviceTarget.PROJECTOR, CapabilityRegistry.DeviceTarget.fromString("PIXAPLAY"))
        assertEquals(CapabilityRegistry.DeviceTarget.FIRE_TV, CapabilityRegistry.DeviceTarget.fromString("fire_tv"))
        assertEquals(CapabilityRegistry.DeviceTarget.FIRE_TV, CapabilityRegistry.DeviceTarget.fromString("firestick"))
        assertEquals(CapabilityRegistry.DeviceTarget.AUDIO, CapabilityRegistry.DeviceTarget.fromString("soundbar"))
        assertEquals(CapabilityRegistry.DeviceTarget.AUDIO, CapabilityRegistry.DeviceTarget.fromString("lg"))
        assertEquals(CapabilityRegistry.DeviceTarget.MEDIA, CapabilityRegistry.DeviceTarget.fromString("music"))
        assertEquals(CapabilityRegistry.DeviceTarget.ROUTINES, CapabilityRegistry.DeviceTarget.fromString("routine"))
        assertNull(CapabilityRegistry.DeviceTarget.fromString("toaster"))
    }

    @Test
    fun `test action capabilities mapping`() {
        assertEquals(
            CapabilityRegistry.ActionCapability.AC_POWER_ON,
            CapabilityRegistry.ActionCapability.fromString(CapabilityRegistry.DeviceTarget.AC, "POWER_ON")
        )
        assertEquals(
            CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            CapabilityRegistry.ActionCapability.fromString(CapabilityRegistry.DeviceTarget.AC, "SET_TEMPERATURE")
        )
        assertEquals(
            CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
            CapabilityRegistry.ActionCapability.fromString(CapabilityRegistry.DeviceTarget.PROJECTOR, "SET_INPUT")
        )
        assertEquals(
            CapabilityRegistry.ActionCapability.FIRE_TV_WAKE,
            CapabilityRegistry.ActionCapability.fromString(CapabilityRegistry.DeviceTarget.FIRE_TV, "WAKE")
        )
        assertEquals(
            CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
            CapabilityRegistry.ActionCapability.fromString(CapabilityRegistry.DeviceTarget.AUDIO, "CONNECT_LG")
        )
        assertNull(CapabilityRegistry.ActionCapability.fromString(CapabilityRegistry.DeviceTarget.AC, "WAKE"))
    }

    @Test
    fun `test parameter constraints`() {
        assertEquals(16, CapabilityRegistry.MIN_AC_TEMP)
        assertEquals(30, CapabilityRegistry.MAX_AC_TEMP)
        assertTrue(CapabilityRegistry.ALLOWED_AC_MODES.contains("COOL"))
        assertTrue(CapabilityRegistry.ALLOWED_AC_FAN_SPEEDS.contains("AUTO"))
        assertTrue(CapabilityRegistry.ALLOWED_PROJECTOR_INPUTS.contains("HDMI_1"))
        assertTrue(CapabilityRegistry.ALLOWED_FIRE_TV_NAV.contains("SELECT"))
        assertTrue(CapabilityRegistry.ALLOWED_FIRE_TV_APPS.containsKey("YOUTUBE"))
    }

    @Test
    fun `test isDeviceSupported and isCapabilitySupported`() {
        assertTrue(CapabilityRegistry.isDeviceSupported("AC"))
        assertTrue(CapabilityRegistry.isDeviceSupported("PROJECTOR"))
        assertFalse(CapabilityRegistry.isDeviceSupported("MICROWAVE"))

        assertTrue(CapabilityRegistry.isCapabilitySupported(CapabilityRegistry.DeviceTarget.AC, "SET_TEMPERATURE"))
        assertFalse(CapabilityRegistry.isCapabilitySupported(CapabilityRegistry.DeviceTarget.AC, "LAUNCH_APP"))
    }
}
