package com.animus.smartroom.core.brain.health

import com.animus.smartroom.core.brain.router.CapabilityRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class HealthVerificationUnitTest {

    private lateinit var healthEngine: HealthVerificationEngine

    @Before
    fun setUp() {
        healthEngine = HealthVerificationEngine()
    }

    @Test
    fun `test parallel health checks execute concurrently with max latency rather than sum`() = runBlocking {
        // 4 probes with 50ms delay each -> sequential = 200ms, parallel = ~50ms
        val customProbes = mapOf(
            CapabilityRegistry.DeviceTarget.PROJECTOR to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.PROJECTOR, delayMs = 50),
            CapabilityRegistry.DeviceTarget.FIRE_TV to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.FIRE_TV, delayMs = 50),
            CapabilityRegistry.DeviceTarget.AUDIO to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.AUDIO, delayMs = 50),
            CapabilityRegistry.DeviceTarget.AC to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.AC, delayMs = 50)
        )

        val reqs = RoutineRequirements(
            routineOrIntent = "MOVIE_MODE",
            requiredDevices = setOf(
                CapabilityRegistry.DeviceTarget.PROJECTOR,
                CapabilityRegistry.DeviceTarget.FIRE_TV,
                CapabilityRegistry.DeviceTarget.AUDIO
            ),
            optionalDevices = setOf(CapabilityRegistry.DeviceTarget.AC)
        )

        val t0 = System.currentTimeMillis()
        val result = healthEngine.verifyHealthParallel(reqs, customProbes)
        val elapsed = System.currentTimeMillis() - t0

        assertEquals(DeviceHealthStatus.HEALTHY, result.overallHealth)
        assertEquals(4, result.deviceStates.size)
        // Parallel time should be well below sequential 200ms
        assertTrue("Parallel health check took $elapsed ms (expected <150ms)", elapsed < 150)
    }

    @Test
    fun `test routine dependency filtering queries only required devices`() = runBlocking {
        val acReqs = RoutineRequirements.forIntent("AC_CONTROL", CapabilityRegistry.DeviceTarget.AC)
        assertEquals(setOf(CapabilityRegistry.DeviceTarget.AC), acReqs.requiredDevices)
        assertTrue(acReqs.optionalDevices.isEmpty())

        val result = healthEngine.verifyHealthParallel(acReqs)
        assertEquals(1, result.deviceStates.size)
        assertTrue(result.deviceStates.containsKey(CapabilityRegistry.DeviceTarget.AC))
        assertFalse(result.deviceStates.containsKey(CapabilityRegistry.DeviceTarget.PROJECTOR))
    }

    @Test
    fun `test optional device failure marks room degraded but routine can proceed`() = runBlocking {
        val customProbes = mapOf(
            CapabilityRegistry.DeviceTarget.PROJECTOR to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.PROJECTOR, healthy = true),
            CapabilityRegistry.DeviceTarget.FIRE_TV to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.FIRE_TV, healthy = true),
            CapabilityRegistry.DeviceTarget.AUDIO to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.AUDIO, healthy = true),
            CapabilityRegistry.DeviceTarget.AC to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.AC, healthy = false) // Optional failed
        )

        val reqs = RoutineRequirements(
            routineOrIntent = "MOVIE_MODE",
            requiredDevices = setOf(
                CapabilityRegistry.DeviceTarget.PROJECTOR,
                CapabilityRegistry.DeviceTarget.FIRE_TV,
                CapabilityRegistry.DeviceTarget.AUDIO
            ),
            optionalDevices = setOf(CapabilityRegistry.DeviceTarget.AC)
        )

        val healthState = healthEngine.verifyHealthParallel(reqs, customProbes)
        assertEquals(DeviceHealthStatus.DEGRADED, healthState.overallHealth)

        val preflightPlan = PreflightRepairPlanner.planPreflight(reqs, healthState)
        assertEquals(PreflightDecision.PROCEED_WITH_DEGRADED_MODE, preflightPlan.decision)
    }

    @Test
    fun `test required device failure blocks routine`() = runBlocking {
        val customProbes = mapOf(
            CapabilityRegistry.DeviceTarget.PROJECTOR to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.PROJECTOR, healthy = false), // Required failed
            CapabilityRegistry.DeviceTarget.FIRE_TV to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.FIRE_TV, healthy = true),
            CapabilityRegistry.DeviceTarget.AUDIO to DefaultDeviceHealthProbe(CapabilityRegistry.DeviceTarget.AUDIO, healthy = true)
        )

        val reqs = RoutineRequirements(
            routineOrIntent = "MOVIE_MODE",
            requiredDevices = setOf(
                CapabilityRegistry.DeviceTarget.PROJECTOR,
                CapabilityRegistry.DeviceTarget.FIRE_TV,
                CapabilityRegistry.DeviceTarget.AUDIO
            )
        )

        val healthState = healthEngine.verifyHealthParallel(reqs, customProbes)
        assertEquals(DeviceHealthStatus.UNAVAILABLE, healthState.overallHealth)

        val preflightPlan = PreflightRepairPlanner.planPreflight(reqs, healthState)
        assertEquals(PreflightDecision.BLOCK_REQUIRES_USER_ACTION, preflightPlan.decision)
        assertNotNull(preflightPlan.reason)
    }

    @Test
    fun `test defect analysis generates deterministic repair actions`() = runBlocking {
        // Projector is OFF and input is not HDMI1
        val customProbes = mapOf(
            CapabilityRegistry.DeviceTarget.PROJECTOR to object : DeviceHealthProbe {
                override val target = CapabilityRegistry.DeviceTarget.PROJECTOR
                override suspend fun probe(): DeviceHealth = DeviceHealth(
                    device = CapabilityRegistry.DeviceTarget.PROJECTOR,
                    reachable = true,
                    poweredOn = false, // Defect 1: OFF
                    currentInput = "ANDROID", // Defect 2: Not HDMI1
                    status = DeviceHealthStatus.HEALTHY
                )
            },
            CapabilityRegistry.DeviceTarget.FIRE_TV to object : DeviceHealthProbe {
                override val target = CapabilityRegistry.DeviceTarget.FIRE_TV
                override suspend fun probe(): DeviceHealth = DeviceHealth(
                    device = CapabilityRegistry.DeviceTarget.FIRE_TV,
                    reachable = true,
                    poweredOn = false, // Defect 3: Asleep
                    status = DeviceHealthStatus.HEALTHY
                )
            },
            CapabilityRegistry.DeviceTarget.AUDIO to object : DeviceHealthProbe {
                override val target = CapabilityRegistry.DeviceTarget.AUDIO
                override suspend fun probe(): DeviceHealth = DeviceHealth(
                    device = CapabilityRegistry.DeviceTarget.AUDIO,
                    reachable = true,
                    connected = true,
                    currentOwner = "PHONE", // Defect 4: Owned by Phone instead of Fire TV
                    status = DeviceHealthStatus.HEALTHY
                )
            }
        )

        val reqs = RoutineRequirements.forIntent("MOVIE_MODE")
        val healthState = healthEngine.verifyHealthParallel(reqs, customProbes)
        val plan = PreflightRepairPlanner.planPreflight(reqs, healthState)

        assertEquals(PreflightDecision.REPAIR_THEN_PROCEED, plan.decision)
        assertTrue(plan.repairs.contains(CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON))
        assertTrue(plan.repairs.contains(CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT))
        assertTrue(plan.repairs.contains(CapabilityRegistry.ActionCapability.FIRE_TV_WAKE))
        assertTrue(plan.repairs.contains(CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG))
    }
}
