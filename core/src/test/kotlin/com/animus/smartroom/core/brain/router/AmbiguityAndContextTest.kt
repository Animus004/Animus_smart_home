package com.animus.smartroom.core.brain.router

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AmbiguityAndContextTest {

    @Test
    fun `test ambiguity detector catches underspecified turn on without context`() {
        val res = AmbiguityDetector.checkAmbiguity("Turn it on", null)
        assertTrue(res.isAmbiguous)
        assertEquals("AMBIGUOUS_TARGET", res.reason)
        assertNotNull(res.question)
    }

    @Test
    fun `test ambiguity detector passes turn on when context target is available`() {
        val res = AmbiguityDetector.checkAmbiguity("Turn it on", CapabilityRegistry.DeviceTarget.PROJECTOR)
        assertFalse(res.isAmbiguous)
    }

    @Test
    fun `test ambiguity detector catches generic play something`() {
        val res = AmbiguityDetector.checkAmbiguity("Put something on", null)
        assertTrue(res.isAmbiguous)
        assertEquals("AMBIGUOUS_ACTION", res.reason)
    }

    @Test
    fun `test context resolver pronoun resolution`() {
        val resolver = ContextResolver()
        resolver.updateContext(CapabilityRegistry.DeviceTarget.PROJECTOR)

        val resolved = resolver.resolveTarget("Set it to HDMI 1", null)
        assertEquals(CapabilityRegistry.DeviceTarget.PROJECTOR, resolved)
    }

    @Test
    fun `test explicit target overrides context in context resolver`() {
        val resolver = ContextResolver()
        resolver.updateContext(CapabilityRegistry.DeviceTarget.PROJECTOR)

        val resolved = resolver.resolveTarget("Actually turn off the AC", "AC")
        assertEquals(CapabilityRegistry.DeviceTarget.AC, resolved)
        assertEquals(CapabilityRegistry.DeviceTarget.AC, resolver.getLastTarget())
    }

    @Test
    fun `test security violation rejected in validator`() {
        val injectionCmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_POWER_ON,
            parameters = mapOf("cmd" to "adb shell reboot")
        )
        val res = IntentValidator.validate(injectionCmd)
        assertTrue(res is IntentValidator.ValidationResult.Invalid)
        assertEquals("SECURITY_VIOLATION", (res as IntentValidator.ValidationResult.Invalid).reason)
    }

    @Test
    fun `test out of range temperature rejected`() {
        val hotCmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("temperature" to 35)
        )
        val res = IntentValidator.validate(hotCmd)
        assertTrue(res is IntentValidator.ValidationResult.Invalid)
        assertEquals("INVALID_PARAMETER_RANGE", (res as IntentValidator.ValidationResult.Invalid).reason)
    }
}
