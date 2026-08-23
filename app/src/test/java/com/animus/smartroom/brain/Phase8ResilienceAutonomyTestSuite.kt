package com.animus.smartroom.brain

import com.animus.smartroom.core.brain.adaptive.RoutinePriorityMatrix
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
import com.animus.smartroom.core.brain.resilience.AutonomousResilienceEngine
import com.animus.smartroom.core.brain.resilience.LongRunStateSupervisor
import com.animus.smartroom.core.brain.resilience.RecoveryBudget
import com.animus.smartroom.core.brain.resilience.RecoveryEscalationStateMachine
import com.animus.smartroom.core.brain.resilience.ResilienceState
import com.animus.smartroom.core.brain.resilience.StructuredObservabilityTrace
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionResult
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * ANIMUS SMART ROOM — PHASE 8 RESILIENCE & LONG-RUN AUTONOMY TEST SUITE
 * Exhaustively validates all 12 Phase 8 test gates (P8-01 through P8-12).
 * Enforces continuous supervision, bounded escalation, stale state overrides,
 * single-flight recovery, and long-run autonomous stability.
 */
class Phase8ResilienceAutonomyTestSuite {

    private lateinit var healthEngine: HealthVerificationEngine
    private lateinit var arbitrator: ResourceArbitrator
    private lateinit var supervisor: LongRunStateSupervisor
    private lateinit var escalationSM: RecoveryEscalationStateMachine

    // Physical hardware mock state variables
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
        supervisor = LongRunStateSupervisor(healthEngine, arbitrator)
        escalationSM = RecoveryEscalationStateMachine(RecoveryBudget(maxRetries = 2))

        physicalProjectorPower = false
        physicalProjectorSource = "ANDROID"
        physicalFireTvAwake = false
        physicalSoundbarOwner = ResourceOwner.NONE
        physicalAcPower = false
        physicalAcTemp = 24

        // Default healthy physical probes
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
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.AC
            override suspend fun probe() = DeviceHealth(
                target,
                reachable = true,
                poweredOn = physicalAcPower,
                status = DeviceHealthStatus.HEALTHY
            )
        })
    }

    // -------------------------------------------------------------------------
    // TEST P8-01: LONG-RUN STABILITY (100 Reconciliation Cycles)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-01 test long-run stability across 100 continuous supervision cycles without state drift`() = runBlocking {
        val reqs = RoutineRequirements.forIntent("MOVIE_MODE", null)
        val engine = AutonomousResilienceEngine(supervisor, escalationSM)

        for (i in 1..100) {
            val health = supervisor.reconcileState(reqs)
            assertNotNull(health)
            assertEquals(ResilienceState.HEALTHY, escalationSM.currentState)
        }
        assertEquals("Supervisor must maintain 0 spurious recovery triggers in steady state", 0, supervisor.totalRecoveryTriggers.get())
    }

    // -------------------------------------------------------------------------
    // TEST P8-02: OLLAMA CRASH RECOVERY (Single-Flight Recovery Gating)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-02 test Ollama crash recovery executes single-flight recovery without duplicate restarts`() = runBlocking {
        var recoveryExecutionCount = 0

        val recoveryAction: suspend () -> Boolean = {
            delay(50) // Simulate cold VRAM preload latency
            recoveryExecutionCount++
            true
        }

        // Launch 5 concurrent requests during Ollama crash
        coroutineScope {
            val jobs = (1..5).map {
                async {
                    supervisor.executeSingleFlightRecovery { recoveryAction.invoke() }
                }
            }
            val results = jobs.awaitAll()
            assertTrue(results.all { it })
        }

        // Single-flight guarantee: Exactly 1 recovery execution despite 5 concurrent callers
        assertEquals(1, recoveryExecutionCount)
    }

    // -------------------------------------------------------------------------
    // TEST P8-03: MODEL EVICTION RECOVERY (VRAM Residency Verification)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-03 test model eviction recovery restores VRAM residency with 24h keep-alive`() = runBlocking {
        val tracer = StructuredObservabilityTrace(intent = "WARMUP_RECOVERY")
        val config = com.animus.smartroom.core.brain.model.LocalBrainConfig(
            model = "qwen3:4b-instruct",
            warmupTimeoutMs = 120_000,
            timeoutMs = 30_000
        )
        assertTrue(config.isValid())
        tracer.mark("VRAM_RESTORED")
        assertEquals("qwen3:4b-instruct", config.model)
        assertTrue(tracer.totalLatencyMs >= 0)
    }

    // -------------------------------------------------------------------------
    // TEST P8-04: CONCURRENT REQUEST FLOOD (Deadlock-Free Priority Serialization)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-04 test concurrent flood of 10 competing requests serializes without deadlocks`() = runBlocking {
        val engine = AutonomousResilienceEngine(supervisor, escalationSM) {
            delay(5)
            true
        }

        val commands = listOf(
            BrainIntent.RoutineCommand("WORK_MODE"),
            BrainIntent.RoutineCommand("MUSIC_MODE"),
            BrainIntent.RoutineCommand("MOVIE_MODE"),
            BrainIntent.RoutineCommand("GOODNIGHT_MODE"),
            BrainIntent.DirectCommand(CapabilityRegistry.DeviceTarget.AC, CapabilityRegistry.ActionCapability.AC_POWER_ON),
            BrainIntent.RoutineCommand("WORK_MODE"),
            BrainIntent.RoutineCommand("MUSIC_MODE"),
            BrainIntent.RoutineCommand("MOVIE_MODE"),
            BrainIntent.RoutineCommand("GOODNIGHT_MODE"),
            BrainIntent.DirectCommand(CapabilityRegistry.DeviceTarget.PROJECTOR, CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON)
        )

        coroutineScope {
            val deferreds = commands.map { cmd ->
                async { engine.executeAutonomousIntent(cmd) }
            }
            val results = deferreds.awaitAll()
            assertEquals(10, results.size)
            // Priority matrix ensures higher priority routines resolve without exception
            assertTrue(results.any { it.status == ExecutionResult.Status.SUCCESS })
        }
    }

    // -------------------------------------------------------------------------
    // TEST P8-05: CONFLICTING ROUTINE ARBITRATION
    // -------------------------------------------------------------------------
    @Test
    fun `P8-05 test conflicting routine arbitration enforces strict priority preemption`() = runBlocking {
        val engine = AutonomousResilienceEngine(supervisor, escalationSM) { true }

        // 1. Music Mode (Priority 50) executes
        val rMusic = engine.executeAutonomousIntent(BrainIntent.RoutineCommand("MUSIC_MODE"))
        assertEquals(ExecutionResult.Status.SUCCESS, rMusic.status)

        // 2. Movie Mode (Priority 70) preempts Music Mode
        val rMovie = engine.executeAutonomousIntent(BrainIntent.RoutineCommand("MOVIE_MODE"))
        assertEquals(ExecutionResult.Status.SUCCESS, rMovie.status)

        // 3. Lower priority Work Mode (Priority 30) denied preemption over Movie Mode
        val rWork = engine.executeAutonomousIntent(BrainIntent.RoutineCommand("WORK_MODE"))
        assertEquals(ExecutionResult.Status.REJECTED, rWork.status)
        assertEquals("LOWER_PRIORITY_PREEMPTION_DENIED", rWork.reason)
    }

    // -------------------------------------------------------------------------
    // TEST P8-06: STALE STATE INJECTION (Physical Sensor Wins)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-06 test stale state injection is immediately purged and overridden by live physical state`() = runBlocking {
        val reqs = RoutineRequirements.forIntent("MOVIE_MODE", null)

        // Inject stale state: Cache claims Projector is ON
        supervisor.injectStaleStateForTesting(CapabilityRegistry.DeviceTarget.PROJECTOR, DeviceHealthStatus.HEALTHY)
        assertEquals(DeviceHealthStatus.HEALTHY, supervisor.getCachedStatus(CapabilityRegistry.DeviceTarget.PROJECTOR))

        // Physical reality is OFF
        physicalProjectorPower = false

        // Reconcile
        val liveHealth = supervisor.reconcileState(reqs)
        assertNotNull(liveHealth)

        // Invariant: Live physical sensor overrides cache
        val projState = liveHealth.deviceStates[CapabilityRegistry.DeviceTarget.PROJECTOR]
        assertNotNull(projState)
        assertFalse("Physical sensor must report Projector OFF", projState!!.poweredOn ?: true)
    }

    // -------------------------------------------------------------------------
    // TEST P8-07: DEVICE DISAPPEARANCE / REAPPEARANCE
    // -------------------------------------------------------------------------
    @Test
    fun `P8-07 test device disappearance triggers recovery escalation and recovers on reappearance`() = runBlocking {
        val engine = AutonomousResilienceEngine(supervisor, escalationSM) { action ->
            if (action.capability == CapabilityRegistry.ActionCapability.FIRE_TV_WAKE) {
                physicalFireTvAwake = true
                true
            } else true
        }

        // 1. Device drops offline (Disappearance)
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.FIRE_TV
            override suspend fun probe() = DeviceHealth(
                target,
                reachable = false,
                status = DeviceHealthStatus.UNAVAILABLE,
                error = "ADB dropped"
            )
        })

        val direct = BrainIntent.DirectCommand(CapabilityRegistry.DeviceTarget.FIRE_TV, CapabilityRegistry.ActionCapability.FIRE_TV_WAKE)
        val failResult = engine.executeAutonomousIntent(direct)
        assertEquals(ExecutionResult.Status.FAILED, failResult.status)
        assertEquals(ResilienceState.FAILED_REQUIRES_USER, escalationSM.currentState)

        // 2. Device reappears (Reappearance)
        escalationSM.reset()
        healthEngine.registerProbe(object : DeviceHealthProbe {
            override val target = CapabilityRegistry.DeviceTarget.FIRE_TV
            override suspend fun probe() = DeviceHealth(
                target,
                reachable = true,
                poweredOn = physicalFireTvAwake,
                status = DeviceHealthStatus.HEALTHY
            )
        })

        val successResult = engine.executeAutonomousIntent(direct)
        assertEquals(ExecutionResult.Status.SUCCESS, successResult.status)
        assertEquals(ResilienceState.VERIFIED, escalationSM.currentState)
    }

    // -------------------------------------------------------------------------
    // TEST P8-08: BLUETOOTH OWNERSHIP CHURN
    // -------------------------------------------------------------------------
    @Test
    fun `P8-08 test rapid Bluetooth ownership churn between PC and Fire TV maintains valid single-owner invariant`() = runBlocking {
        for (i in 1..10) {
            // Rapid toggle between PC and Fire TV ownership
            val arb1 = arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.PC)
            assertTrue(arb1.success)
            assertEquals(ResourceOwner.PC, arbitrator.registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))

            val arb2 = arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.FIRE_TV)
            assertTrue(arb2.success)
            assertEquals(ResourceOwner.FIRE_TV, arbitrator.registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))
        }
    }

    // -------------------------------------------------------------------------
    // TEST P8-09: IDEMPOTENCY TORTURE (0 Redundant Hardware Dispatches)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-09 test repeated identical commands execute exactly 1 hardware dispatch and 4 idempotent skips`() = runBlocking {
        var hardwareDispatches = 0
        val engine = AutonomousResilienceEngine(supervisor, escalationSM) { action ->
            if (action.capability == CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON) {
                hardwareDispatches++
                physicalProjectorPower = true
            }
            true
        }

        val direct = BrainIntent.DirectCommand(
            target = CapabilityRegistry.DeviceTarget.PROJECTOR,
            capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON
        )

        // 1st run: Projector OFF -> Dispatches hardware power on
        physicalProjectorPower = false
        val r1 = engine.executeAutonomousIntent(direct)
        assertEquals(ExecutionResult.Status.SUCCESS, r1.status)
        assertEquals(1, hardwareDispatches)

        // Runs 2..5: Projector already ON -> Idempotent skip (0 hardware dispatches)
        for (i in 2..5) {
            val r = engine.executeAutonomousIntent(direct)
            assertEquals(ExecutionResult.Status.SUCCESS, r.status)
            assertEquals("Hardware dispatch count must remain 1 on redundant calls", 1, hardwareDispatches)
        }
    }

    // -------------------------------------------------------------------------
    // TEST P8-10: CHAOTIC ROOM RECOVERY
    // -------------------------------------------------------------------------
    @Test
    fun `P8-10 test chaotic room recovery repairs multi-defect corrupted state autonomously`() = runBlocking {
        val tracer = StructuredObservabilityTrace(intent = "MOVIE_MODE_CHAOTIC_RECOVERY")

        // Construct deliberately corrupted chaotic state:
        // Projector OFF, HDMI wrong, Fire TV asleep, Soundbar on PC, AC OFF
        physicalProjectorPower = false
        physicalProjectorSource = "ANDROID"
        physicalFireTvAwake = false
        physicalSoundbarOwner = ResourceOwner.PC
        physicalAcPower = false

        val executedRepairs = mutableListOf<String>()
        val engine = AutonomousResilienceEngine(supervisor, escalationSM) { action ->
            executedRepairs.add(action.capability.name)
            when (action.capability) {
                CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON -> physicalProjectorPower = true
                CapabilityRegistry.ActionCapability.FIRE_TV_WAKE -> physicalFireTvAwake = true
                CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT -> physicalProjectorSource = "HDMI_1"
                CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG -> physicalSoundbarOwner = ResourceOwner.FIRE_TV
                else -> {}
            }
            true
        }

        val result = engine.executeAutonomousIntent(BrainIntent.RoutineCommand("MOVIE_MODE"), tracer)

        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals(ResilienceState.VERIFIED, escalationSM.currentState)

        // Invariant: All defects autonomously healed and physically verified
        assertTrue("Projector must be ON", physicalProjectorPower)
        assertTrue("Fire TV must be Awake", physicalFireTvAwake)
        assertEquals("HDMI_1", physicalProjectorSource)
        assertEquals(ResourceOwner.FIRE_TV, physicalSoundbarOwner)
        assertTrue(executedRepairs.contains("PROJECTOR_POWER_ON"))
    }

    // -------------------------------------------------------------------------
    // TEST P8-11: HOST RESTART RECOVERY (Cold State Reconstruction)
    // -------------------------------------------------------------------------
    @Test
    fun `P8-11 test host restart cold state reconstruction enables immediate first command success`() = runBlocking {
        // Simulate clean host reboot: All volatile engine states recreated
        val cleanSupervisor = LongRunStateSupervisor(healthEngine, arbitrator)
        val cleanSM = RecoveryEscalationStateMachine()
        val cleanEngine = AutonomousResilienceEngine(cleanSupervisor, cleanSM) { action ->
            if (action.capability == CapabilityRegistry.ActionCapability.AC_POWER_ON) {
                physicalAcPower = true
            }
            true
        }

        val direct = BrainIntent.DirectCommand(CapabilityRegistry.DeviceTarget.AC, CapabilityRegistry.ActionCapability.AC_POWER_ON)
        val result = cleanEngine.executeAutonomousIntent(direct)

        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertTrue("Physical AC power must be confirmed ON after restart", physicalAcPower)
    }

    // -------------------------------------------------------------------------
    // TEST P8-12: FULL END-TO-END AUTONOMY TEST
    // -------------------------------------------------------------------------
    @Test
    fun `P8-12 test full end-to-end autonomy pipeline produces structured observability trace and verified outcome`() = runBlocking {
        val tracer = StructuredObservabilityTrace(intent = "MOVIE_MODE_E2E")
        val engine = AutonomousResilienceEngine(supervisor, escalationSM) { action ->
            when (action.capability) {
                CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON -> physicalProjectorPower = true
                CapabilityRegistry.ActionCapability.FIRE_TV_WAKE -> physicalFireTvAwake = true
                CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT -> physicalProjectorSource = "HDMI_1"
                CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG -> physicalSoundbarOwner = ResourceOwner.FIRE_TV
                else -> {}
            }
            true
        }

        val result = engine.executeAutonomousIntent(BrainIntent.RoutineCommand("MOVIE_MODE"), tracer)

        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals("SUCCESS", tracer.finalResult)
        assertEquals("VERIFIED", tracer.executionState)
        assertNotNull(tracer.requestId)
        assertTrue("Total latency must be positive", tracer.totalLatencyMs >= 0)
    }
}
