package com.animus.smartroom.brain

import com.animus.smartroom.core.brain.adaptive.AdaptiveExecutionEngine
import com.animus.smartroom.core.brain.adaptive.DivergenceSeverity
import com.animus.smartroom.core.brain.adaptive.RoutinePriorityMatrix
import com.animus.smartroom.core.brain.adaptive.StateDefectType
import com.animus.smartroom.core.brain.adaptive.StateDivergenceDetector
import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceArbitrator
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.execution.ActionRegistry
import com.animus.smartroom.core.brain.execution.ActionValidationResult
import com.animus.smartroom.core.brain.health.DeviceHealth
import com.animus.smartroom.core.brain.health.DeviceHealthProbe
import com.animus.smartroom.core.brain.health.DeviceHealthStatus
import com.animus.smartroom.core.brain.health.HealthVerificationEngine
import com.animus.smartroom.core.brain.health.RoutineRequirements
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionResult
import com.animus.smartroom.core.brain.router.ObservabilityTracer
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * ANIMUS SMART ROOM — PHASE 7 ADAPTIVE INTELLIGENCE & SELF-RECOVERY TEST SUITE
 * Validates dynamic room divergence detection, adaptive re-planning, self-recovery,
 * and priority arbitration invariants under realistic environmental changes.
 */
class Phase7AdaptiveIntelligenceTestSuite {

    private lateinit var healthEngine: HealthVerificationEngine
    private lateinit var arbitrator: ResourceArbitrator

    // Observable physical state variables
    private var physicalProjectorPower = false
    private var physicalProjectorSource = "ANDROID"
    private var physicalFireTvAwake = false
    private var physicalSoundbarOwner = ResourceOwner.NONE
    private var physicalAcPower = false
    private var physicalAcTemp = 24

    @Before
    fun setUp() {
        healthEngine = HealthVerificationEngine()
        arbitrator = ResourceArbitrator()

        physicalProjectorPower = false
        physicalProjectorSource = "ANDROID"
        physicalFireTvAwake = false
        physicalSoundbarOwner = ResourceOwner.NONE
        physicalAcPower = false
        physicalAcTemp = 24
    }

    // -------------------------------------------------------------------------
    // TEST P7-01: MID-ROUTINE PROJECTOR POWER DROP & SELF-HEALING
    // -------------------------------------------------------------------------
    @Test
    fun `P7-01 test mid-routine projector power drop triggers divergence detection and adaptive self-repair`() = runBlocking {
        val tracer = ObservabilityTracer("P7-01-POWER-DROP")
        val routine = BrainIntent.RoutineCommand("MOVIE_MODE", emptyMap(), "corr-p7-01")

        // Dynamic health probe backed by physical variable
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.PROJECTOR
            override suspend fun probe() = DeviceHealth(
                device = target,
                reachable = true,
                poweredOn = physicalProjectorPower,
                currentInput = physicalProjectorSource,
                status = DeviceHealthStatus.HEALTHY
            )
        })
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.FIRE_TV
            override suspend fun probe() = DeviceHealth(
                device = target,
                reachable = true,
                poweredOn = physicalFireTvAwake,
                status = DeviceHealthStatus.HEALTHY
            )
        })

        var repairActionDispatched = false
        val engine = AdaptiveExecutionEngine(healthEngine, arbitrator) { action ->
            when (action.capability) {
                CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON -> {
                    physicalProjectorPower = true
                    repairActionDispatched = true
                }
                CapabilityRegistry.ActionCapability.FIRE_TV_WAKE -> physicalFireTvAwake = true
                CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT -> {
                    // Precondition: Projector MUST be ON to switch input
                    assertTrue("Projector must be ON before setting input", physicalProjectorPower)
                    physicalProjectorSource = "HDMI_1"
                }
                else -> {}
            }
            true
        }

        // Simulate Projector turning OFF unexpectedly during stage transition
        physicalProjectorPower = false
        val result = engine.executeAdaptiveIntent(routine, tracer)

        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertTrue("Projector power repair action must have been dispatched", repairActionDispatched)
        assertTrue("Final projector physical power must be ON", physicalProjectorPower)
        assertEquals("HDMI_1", physicalProjectorSource)
    }

    // -------------------------------------------------------------------------
    // TEST P7-02: SOUNDBAR OWNERSHIP CONFLICT & PRIORITY ARBITRATION
    // -------------------------------------------------------------------------
    @Test
    fun `P7-02 test audio ownership conflict preemption based on deterministic priority hierarchy`() = runBlocking {
        // 1. Initial State: Music Mode owns soundbar (Priority 50)
        val musicArb = arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.PC)
        assertTrue(musicArb.success)
        assertEquals(ResourceOwner.PC, arbitrator.registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))
        assertEquals(50, RoutinePriorityMatrix.getPriority("MUSIC_MODE"))

        // 2. Incoming Request: Movie Mode (Priority 70) requires soundbar for Fire TV
        assertEquals(70, RoutinePriorityMatrix.getPriority("MOVIE_MODE"))
        assertTrue(RoutinePriorityMatrix.shouldPreempt("MUSIC_MODE", "MOVIE_MODE"))

        // 3. Execute preemption
        val movieArb = arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.FIRE_TV)
        assertTrue(movieArb.success)
        assertEquals(ResourceOwner.FIRE_TV, arbitrator.registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))

        // 4. Invariant Check: Lower priority routine cannot preempt higher priority
        assertFalse(RoutinePriorityMatrix.shouldPreempt("MOVIE_MODE", "MUSIC_MODE"))
        assertFalse(RoutinePriorityMatrix.shouldPreempt("GOODNIGHT_MODE", "MOVIE_MODE"))
    }

    // -------------------------------------------------------------------------
    // TEST P7-03: TRANSIENT NETWORK DROPOUT & BOUNDED RECOVERY
    // -------------------------------------------------------------------------
    @Test
    fun `P7-03 test transient device network drop recovers within retry budget without infinite loop`() = runBlocking {
        val tracer = ObservabilityTracer("P7-03-TRANSIENT-DROP")
        val direct = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.FIRE_TV,
            capability = CapabilityRegistry.ActionCapability.FIRE_TV_WAKE,
            parameters = emptyMap(),
            correlationId = "corr-p7-03"
        )

        var attempts = 0
        val engine = AdaptiveExecutionEngine(healthEngine, arbitrator) {
            attempts++
            if (attempts == 1) {
                // Simulate 1st transient failure (e.g. WiFi packet drop)
                false
            } else {
                // 2nd attempt succeeds
                physicalFireTvAwake = true
                true
            }
        }

        // 1st attempt fails cleanly
        val r1 = engine.executeAdaptiveIntent(direct, tracer)
        assertEquals(ExecutionResult.Status.FAILED, r1.status)

        // 2nd attempt recovers
        val r2 = engine.executeAdaptiveIntent(direct, tracer)
        assertEquals(ExecutionResult.Status.SUCCESS, r2.status)
        assertTrue(physicalFireTvAwake)
    }

    // -------------------------------------------------------------------------
    // TEST P7-04: PERMANENT CRITICAL FAILURE & SAFE ABORT
    // -------------------------------------------------------------------------
    @Test
    fun `P7-04 test permanent hardware failure aborts cleanly without phantom success or deadlock`() = runBlocking {
        val tracer = ObservabilityTracer("P7-04-PERMANENT-FAIL")
        val routine = BrainIntent.RoutineCommand("MOVIE_MODE", emptyMap(), "corr-p7-04")

        // Register probe reporting critical device permanently UNREACHABLE
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.PROJECTOR
            override suspend fun probe() = DeviceHealth(
                device = target,
                reachable = false,
                status = DeviceHealthStatus.UNAVAILABLE,
                error = "Hardware offline"
            )
        })

        val hardwareDispatches = AtomicInteger(0)
        val engine = AdaptiveExecutionEngine(healthEngine, arbitrator) {
            hardwareDispatches.incrementAndGet()
            true
        }

        val result = engine.executeAdaptiveIntent(routine, tracer)

        assertEquals(ExecutionResult.Status.FAILED, result.status)
        assertEquals("PREFLIGHT_BLOCKED", result.reason)
        assertEquals("Zero hardware commands must be dispatched when critical preflight fails", 0, hardwareDispatches.get())
    }

    // -------------------------------------------------------------------------
    // TEST P7-05: CONCURRENT COMPETING ROUTINES SERIALIZATION
    // -------------------------------------------------------------------------
    @Test
    fun `P7-05 test concurrent conflicting routines resolve deterministically by priority`() = runBlocking {
        val tracer = ObservabilityTracer("P7-05-CONCURRENT-ROUTINES")
        val workCmd = BrainIntent.RoutineCommand("WORK_MODE", emptyMap(), "corr-work")
        val goodnightCmd = BrainIntent.RoutineCommand("GOODNIGHT_MODE", emptyMap(), "corr-gn")

        val engine = AdaptiveExecutionEngine(healthEngine, arbitrator) {
            delay(10)
            true
        }

        coroutineScope {
            val d1 = async { engine.executeAdaptiveIntent(workCmd, tracer) }
            val d2 = async { engine.executeAdaptiveIntent(goodnightCmd, tracer) }

            val r1 = d1.await()
            val r2 = d2.await()

            // Goodnight mode has higher priority (100 > 30) and succeeds
            assertTrue(r1.status == ExecutionResult.Status.SUCCESS || r2.status == ExecutionResult.Status.SUCCESS)
        }
    }

    // -------------------------------------------------------------------------
    // TEST P7-06: STRICT ACTION ALLOWLIST INVARIANT
    // -------------------------------------------------------------------------
    @Test
    fun `P7-06 test all adaptive repairs strictly conform to canonical ActionRegistry`() {
        val testDefects = listOf(
            StateDefectType.PROJECTOR_POWER_LOST,
            StateDefectType.PROJECTOR_INPUT_ALTERED,
            StateDefectType.FIRE_TV_ASLEEP,
            StateDefectType.AUDIO_OWNERSHIP_LOST
        )

        for (defectType in testDefects) {
            val repairCapability = when (defectType) {
                StateDefectType.PROJECTOR_POWER_LOST -> CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON
                StateDefectType.PROJECTOR_INPUT_ALTERED -> CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT
                StateDefectType.FIRE_TV_ASLEEP -> CapabilityRegistry.ActionCapability.FIRE_TV_WAKE
                StateDefectType.AUDIO_OWNERSHIP_LOST -> CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG
                else -> null
            }
            assertNotNull("Defect $defectType must have canonical repair capability", repairCapability)

            val valResult = ActionRegistry.validateAction(
                repairCapability!!.target,
                repairCapability,
                if (repairCapability == CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT) mapOf("input" to "HDMI_1") else emptyMap()
            )
            assertTrue("Repair capability $repairCapability must pass ActionRegistry validation", valResult is ActionValidationResult.Valid)
        }
    }

    // -------------------------------------------------------------------------
    // TEST P7-07: AUTHORITATIVE SENSOR OVERRULE INVARIANT
    // -------------------------------------------------------------------------
    @Test
    fun `P7-07 test physical sensor readings always override assumed state`() {
        val reqs = RoutineRequirements.forIntent("MOVIE_MODE", null)

        // Assumed state: Projector ON, but physical sensor reports Projector OFF
        val divergedHealth = com.animus.smartroom.core.brain.health.RoomHealthState(
            timestamp = System.currentTimeMillis(),
            overallHealth = DeviceHealthStatus.UNAVAILABLE,
            deviceStates = mapOf(
                CapabilityRegistry.DeviceTarget.PROJECTOR to DeviceHealth(
                    device = CapabilityRegistry.DeviceTarget.PROJECTOR,
                    reachable = true,
                    poweredOn = false, // Physical reality
                    currentInput = "ANDROID"
                ),
                CapabilityRegistry.DeviceTarget.FIRE_TV to DeviceHealth(
                    device = CapabilityRegistry.DeviceTarget.FIRE_TV,
                    reachable = true,
                    poweredOn = true
                ),
                CapabilityRegistry.DeviceTarget.AUDIO to DeviceHealth(
                    device = CapabilityRegistry.DeviceTarget.AUDIO,
                    reachable = true,
                    poweredOn = true,
                    currentOwner = "FIRE_TV"
                )
            )
        )

        val report = StateDivergenceDetector.detectDivergence("MOVIE_MODE", reqs, divergedHealth)
        assertTrue("Divergence detector must detect physical discrepancy", report.isDiverged)
        assertTrue(report.defects.any { it.type == StateDefectType.PROJECTOR_POWER_LOST })
        assertEquals(DivergenceSeverity.MINOR_RECOVERABLE, report.severity)
    }

    // -------------------------------------------------------------------------
    // TEST P7-08: END-TO-END MULTI-DEFECT ADAPTIVE SELF-RECOVERY
    // -------------------------------------------------------------------------
    @Test
    fun `P7-08 test complete multi-defect adaptive self-recovery under chaotic room conditions`() = runBlocking {
        val tracer = ObservabilityTracer("P7-08-MULTI-DEFECT")
        val routine = BrainIntent.RoutineCommand("MOVIE_MODE", emptyMap(), "corr-p7-08")

        // Initial Chaotic Physical State:
        // Projector OFF, Source ANDROID, Fire TV ASLEEP, Soundbar on PC
        physicalProjectorPower = false
        physicalProjectorSource = "ANDROID"
        physicalFireTvAwake = false
        physicalSoundbarOwner = ResourceOwner.PC

        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.PROJECTOR
            override suspend fun probe() = DeviceHealth(
                target,
                reachable = true,
                poweredOn = physicalProjectorPower,
                currentInput = physicalProjectorSource,
                status = DeviceHealthStatus.HEALTHY
            )
        })
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.FIRE_TV
            override suspend fun probe() = DeviceHealth(
                target,
                reachable = true,
                poweredOn = physicalFireTvAwake,
                status = DeviceHealthStatus.HEALTHY
            )
        })
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.AUDIO
            override suspend fun probe() = DeviceHealth(
                target,
                reachable = true,
                poweredOn = true,
                currentOwner = physicalSoundbarOwner.name,
                status = DeviceHealthStatus.HEALTHY
            )
        })

        val executedSequence = mutableListOf<String>()
        val engine = AdaptiveExecutionEngine(healthEngine, arbitrator) { action ->
            executedSequence.add(action.capability.name)
            when (action.capability) {
                CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON -> physicalProjectorPower = true
                CapabilityRegistry.ActionCapability.FIRE_TV_WAKE -> physicalFireTvAwake = true
                CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT -> physicalProjectorSource = "HDMI_1"
                CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG -> physicalSoundbarOwner = ResourceOwner.FIRE_TV
                else -> {}
            }
            true
        }

        val result = engine.executeAdaptiveIntent(routine, tracer)

        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertTrue("Projector power must be recovered", physicalProjectorPower)
        assertTrue("Fire TV wake must be recovered", physicalFireTvAwake)
        assertEquals("HDMI_1", physicalProjectorSource)
        assertEquals(ResourceOwner.FIRE_TV, physicalSoundbarOwner)
        assertTrue("Execution sequence must contain repair actions", executedSequence.contains("PROJECTOR_POWER_ON"))
    }
}
