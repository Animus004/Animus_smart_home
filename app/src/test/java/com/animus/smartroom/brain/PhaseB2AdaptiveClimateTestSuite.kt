package com.animus.smartroom.brain

import com.animus.smartroom.brain.router.DeterministicExecutionEngine
import com.animus.smartroom.core.brain.policy.AdaptiveMovieClimatePolicy
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionResult
import com.animus.smartroom.device.adapter.MockAirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class PhaseB2AdaptiveClimateTestSuite {

    private lateinit var registry: DeviceRegistry
    private lateinit var mockAcAdapter: MockAirConditionerAdapter
    private lateinit var engine: DeterministicExecutionEngine

    @Before
    fun setUp() {
        registry = DeviceRegistry()
        mockAcAdapter = MockAirConditionerAdapter()

        val acDevice = RoomDevice(
            id = "AC",
            displayName = "Living Room AC",
            type = DeviceType.AIR_CONDITIONER,
            connectionState = DeviceConnectionState.Available,
            supportedCapabilities = setOf(
                DeviceCapability.Power,
                DeviceCapability.Temperature
            )
        )
        registry.registerDevice(acDevice)
        registry.registerAdapterForType(DeviceType.AIR_CONDITIONER, mockAcAdapter)

        engine = DeterministicExecutionEngine(
            deviceRegistry = registry
        )
    }

    @Test
    fun `test P_B2_01 Adaptive AC Temperature Selection for Very Warm Room`() = runBlocking {
        val cmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("adaptive" to true, "ambient_temp" to 30.0)
        )

        val result = engine.execute(cmd)
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals(24, result.verified)
        assertEquals(24, mockAcAdapter.currentTemperature)
    }

    @Test
    fun `test P_B2_02 Adaptive AC Temperature Selection for Warm Room`() = runBlocking {
        val cmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("adaptive" to true, "ambient_temp" to 27.0)
        )

        val result = engine.execute(cmd)
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals(25, result.verified)
        assertEquals(25, mockAcAdapter.currentTemperature)
    }

    @Test
    fun `test P_B2_03 Adaptive AC Temperature Selection for Comfortable Room`() = runBlocking {
        val cmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("adaptive" to true, "ambient_temp" to 25.0)
        )

        val result = engine.execute(cmd)
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals(26, result.verified)
        assertEquals(26, mockAcAdapter.currentTemperature)
    }

    @Test
    fun `test P_B2_04 Already Cool Room Skips Cooling Idempotently`() = runBlocking {
        val cmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("adaptive" to true, "ambient_temp" to 22.0)
        )

        val result = engine.execute(cmd)
        assertEquals(ExecutionResult.Status.ALREADY_IN_STATE, result.status)
        assertTrue(result.message.contains("Avoiding unnecessary cooling"))
    }

    @Test
    fun `test P_B2_05 Already at Optimal Target Skips Unnecessary Command`() = runBlocking {
        mockAcAdapter.currentTemperature = 24
        mockAcAdapter.powerState = true

        val cmd = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf(
                "adaptive" to true,
                "ambient_temp" to 29.0,
                "current_temp" to 24,
                "is_powered" to true
            )
        )

        val result = engine.execute(cmd)
        assertEquals(ExecutionResult.Status.ALREADY_IN_STATE, result.status)
        assertTrue(result.message.contains("already running at optimal temperature"))
    }

    @Test
    fun `test P_B2_06 Capability Bounds 16-30 Clamping`() = runBlocking {
        val cmdHigh = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("temperature" to 40)
        )
        val resultHigh = engine.execute(cmdHigh)
        assertEquals(ExecutionResult.Status.SUCCESS, resultHigh.status)
        assertEquals(30, resultHigh.verified)

        val cmdLow = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("temperature" to 10)
        )
        val resultLow = engine.execute(cmdLow)
        assertEquals(ExecutionResult.Status.SUCCESS, resultLow.status)
        assertEquals(16, resultLow.verified)
    }

    @Test
    fun `test P_B2_07 LLM Temperature Hallucination Is Overridden by Deterministic Policy`() = runBlocking {
        // Even if an external prompt/LLM attempts to set 18°C in Movie Mode adaptive climate,
        // the deterministic policy determines the actual temperature based on room state.
        val decision = AdaptiveMovieClimatePolicy.evaluate(
            currentAmbientTemp = 27.5 // Warm -> should select 25°C, not 18°C
        )

        assertEquals(25, decision.targetTemperature)
    }

    @Test
    fun `test P_B2_08 AC Unavailable Degrades Comfort Stage Without Aborting Routine`() = runBlocking {
        val emptyRegistry = DeviceRegistry() // No AC registered
        val unconfiguredEngine = DeterministicExecutionEngine(
            deviceRegistry = emptyRegistry
        )

        val routine = BrainIntent.RoutineCommand(
            routineName = "MOVIE_MODE",
            parameters = emptyMap()
        )

        val result = unconfiguredEngine.execute(routine)
        assertNotNull(result)
        // Movie routine completes across stages even if AC is unavailable
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertTrue(result.message.contains("executed successfully"))
    }
}
