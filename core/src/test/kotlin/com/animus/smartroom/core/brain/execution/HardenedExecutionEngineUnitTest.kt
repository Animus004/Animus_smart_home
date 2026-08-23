package com.animus.smartroom.core.brain.execution

import com.animus.smartroom.core.brain.arbitration.ArbitrationUnitTest
import com.animus.smartroom.core.brain.health.DefaultDeviceHealthProbe
import com.animus.smartroom.core.brain.health.DeviceHealth
import com.animus.smartroom.core.brain.health.DeviceHealthStatus
import com.animus.smartroom.core.brain.health.HealthVerificationEngine
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class HardenedExecutionEngineUnitTest {

    private lateinit var engine: HardenedExecutionEngine

    @Before
    fun setUp() {
        engine = HardenedExecutionEngine()
    }

    @Test
    fun `test direct AC command executes successfully through pipeline`() = runBlocking {
        val intent = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("temperature" to 22)
        )

        val result = engine.executeIntent(intent)
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals("AC", result.target)
    }

    @Test
    fun `test security violation injection is strictly rejected`() = runBlocking {
        val injectionIntent = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_POWER_ON,
            parameters = mapOf("payload" to "adb shell reboot")
        )

        val result = engine.executeIntent(injectionIntent)
        assertEquals(ExecutionResult.Status.REJECTED, result.status)
        assertEquals("SECURITY_VIOLATION", result.reason)
    }

    @Test
    fun `test invalid parameter range is strictly rejected`() = runBlocking {
        val invalidTempIntent = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.AC,
            capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
            parameters = mapOf("temperature" to 40) // Out of range 16-30
        )

        val result = engine.executeIntent(invalidTempIntent)
        assertEquals(ExecutionResult.Status.REJECTED, result.status)
        assertEquals("INVALID_PARAMETER_RANGE", result.reason)
    }

    @Test
    fun `test movie mode routine runs full preflight, arbitration and execution pipeline`() = runBlocking {
        val routineIntent = BrainIntent.RoutineCommand("MOVIE_MODE")

        val result = engine.executeIntent(routineIntent)
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals("MOVIE_MODE", result.intent)
    }

    @Test
    fun `test multi action command separates stages and executes sequentially`() = runBlocking {
        val executedActions = mutableListOf<String>()
        val customExecutorEngine = HardenedExecutionEngine(
            actionExecutor = { action ->
                executedActions.add(action.capability.name)
                true
            }
        )

        val multiIntent = BrainIntent.MultiActionCommand(
            actions = listOf(
                BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                    capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON
                ),
                BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.FIRE_TV,
                    capability = CapabilityRegistry.ActionCapability.FIRE_TV_WAKE
                ),
                BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                    capability = CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
                    parameters = mapOf("input" to "HDMI_1")
                )
            )
        )

        val result = customExecutorEngine.executeIntent(multiIntent)
        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals(3, executedActions.size)
        // Stage 1 independent actions before Stage 2 dependent action
        assertTrue(executedActions.indexOf("PROJECTOR_POWER_ON") < executedActions.indexOf("PROJECTOR_SET_INPUT"))
    }
}
