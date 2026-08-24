package com.animus.smartroom.core.brain.policy

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AdaptiveMovieClimatePolicyTest {

    @Test
    fun `very warm room sets aggressive energy-aware target of 24C`() {
        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 31.5,
            isAcPoweredOn = false
        )

        assertEquals(24, decision.targetTemperature)
        assertTrue(decision.shouldPowerOn)
        assertFalse(decision.isAlreadyOptimal)
        assertTrue(decision.reason.contains("24°C"))
    }

    @Test
    fun `warm room sets target of 25C`() {
        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 27.0,
            isAcPoweredOn = false
        )

        assertEquals(25, decision.targetTemperature)
        assertTrue(decision.shouldPowerOn)
        assertFalse(decision.isAlreadyOptimal)
        assertTrue(decision.reason.contains("25°C"))
    }

    @Test
    fun `comfortable room sets target of 26C`() {
        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 25.0,
            isAcPoweredOn = false
        )

        assertEquals(26, decision.targetTemperature)
        assertTrue(decision.shouldPowerOn)
        assertFalse(decision.isAlreadyOptimal)
        assertTrue(decision.reason.contains("26°C"))
    }

    @Test
    fun `already cool room avoids unnecessary cooling`() {
        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 22.5,
            isAcPoweredOn = false
        )

        assertNull(decision.targetTemperature)
        assertFalse(decision.shouldPowerOn)
        assertTrue(decision.isAlreadyOptimal)
        assertTrue(decision.reason.contains("Avoiding unnecessary cooling"))
    }

    @Test
    fun `already running at optimal target is idempotent`() {
        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 29.0,
            currentAcTemp = 24,
            isAcPoweredOn = true
        )

        assertEquals(24, decision.targetTemperature)
        assertTrue(decision.shouldPowerOn)
        assertTrue(decision.isAlreadyOptimal)
        assertTrue(decision.reason.contains("already running at optimal temperature"))
    }

    @Test
    fun `custom thresholds are respected and clamped to 16-30 bounds`() {
        val custom = AdaptiveMovieClimatePolicy.ClimateThresholds(
            veryWarmThreshold = 35.0,
            veryWarmTarget = 15 // Below min bound 16
        )

        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 36.0,
            thresholds = custom
        )

        assertEquals(16, decision.targetTemperature) // Clamped to MIN_TEMPERATURE
    }
}
