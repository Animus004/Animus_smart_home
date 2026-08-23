package com.animus.smartroom.core.brain.router

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class IntentNormalizerTest {

    @Test
    fun `test linguistic normalization for AC power`() {
        val target = CapabilityRegistry.DeviceTarget.AC
        assertEquals(CapabilityRegistry.ActionCapability.AC_POWER_ON, IntentNormalizer.normalizeAction(target, "ON"))
        assertEquals(CapabilityRegistry.ActionCapability.AC_POWER_ON, IntentNormalizer.normalizeAction(target, "START"))
        assertEquals(CapabilityRegistry.ActionCapability.AC_POWER_ON, IntentNormalizer.normalizeAction(target, "POWER_ON"))
        assertEquals(CapabilityRegistry.ActionCapability.AC_POWER_OFF, IntentNormalizer.normalizeAction(target, "OFF"))
        assertEquals(CapabilityRegistry.ActionCapability.AC_POWER_OFF, IntentNormalizer.normalizeAction(target, "STOP"))
        assertEquals(CapabilityRegistry.ActionCapability.AC_POWER_OFF, IntentNormalizer.normalizeAction(target, "SHUTDOWN"))
    }

    @Test
    fun `test linguistic normalization for Projector`() {
        val target = CapabilityRegistry.DeviceTarget.PROJECTOR
        assertEquals(CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON, IntentNormalizer.normalizeAction(target, "WAKE"))
        assertEquals(CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON, IntentNormalizer.normalizeAction(target, "START"))
        assertEquals(CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT, IntentNormalizer.normalizeAction(target, "HDMI_1"))
        assertEquals(CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT, IntentNormalizer.normalizeAction(target, "SOURCE"))
    }

    @Test
    fun `test linguistic normalization for Routines`() {
        val target = CapabilityRegistry.DeviceTarget.ROUTINES
        assertEquals(CapabilityRegistry.ActionCapability.ROUTINE_MOVIE_MODE, IntentNormalizer.normalizeAction(target, "MOVIE"))
        assertEquals(CapabilityRegistry.ActionCapability.ROUTINE_MOVIE_MODE, IntentNormalizer.normalizeAction(target, "CINEMA"))
        assertEquals(CapabilityRegistry.ActionCapability.ROUTINE_WORK_MODE, IntentNormalizer.normalizeAction(target, "FOCUS"))
        assertEquals(CapabilityRegistry.ActionCapability.ROUTINE_WORK_MODE, IntentNormalizer.normalizeAction(target, "STUDY"))
        assertEquals(CapabilityRegistry.ActionCapability.ROUTINE_GOODNIGHT_MODE, IntentNormalizer.normalizeAction(target, "SLEEP"))
        assertEquals(CapabilityRegistry.ActionCapability.ROUTINE_GOODNIGHT_MODE, IntentNormalizer.normalizeAction(target, "ALL_OFF"))
    }
}
