package com.animus.smartroom.core.brain.resilience

import com.animus.smartroom.core.brain.adaptive.AdaptiveExecutionEngine
import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceArbitrator
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.execution.PlanAction
import com.animus.smartroom.core.brain.health.DeviceHealthStatus
import com.animus.smartroom.core.brain.health.HealthVerificationEngine
import com.animus.smartroom.core.brain.health.RoutineRequirements
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionResult
import com.animus.smartroom.core.brain.router.ObservabilityTracer
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

/**
 * Autonomous Resilience Engine for Phase 8.
 * High-level coordinator unifying State Supervision, Bounded Escalation,
 * Idempotency Deduplication, and Deterministic Autonomous Self-Recovery.
 */
class AutonomousResilienceEngine(
    val supervisor: LongRunStateSupervisor = LongRunStateSupervisor(),
    val escalationSM: RecoveryEscalationStateMachine = RecoveryEscalationStateMachine(),
    private val actionExecutor: (suspend (PlanAction) -> Boolean)? = null
) {
    val adaptiveEngine = AdaptiveExecutionEngine(
        healthEngine = supervisor.healthEngine,
        arbitrator = supervisor.arbitrator,
        actionExecutor = actionExecutor
    )

    private val engineMutex = Mutex()
    val hardwareDispatchCounter = AtomicInteger(0)

    suspend fun executeAutonomousIntent(
        intent: BrainIntent,
        tracer: StructuredObservabilityTrace? = null
    ): ExecutionResult = engineMutex.withLock {
        tracer?.mark("INTENT_RECEIVED")

        val intentName = when (intent) {
            is BrainIntent.RoutineCommand -> intent.routineName
            is BrainIntent.DirectCommand -> intent.capability.name
            is BrainIntent.MultiActionCommand -> "MULTI_ACTION"
            is BrainIntent.ClarificationRequired -> return ExecutionResult(
                status = ExecutionResult.Status.CLARIFICATION_REQUIRED,
                correlationId = intent.correlationId,
                intent = "CLARIFICATION_REQUIRED",
                message = intent.question,
                reason = intent.reason
            )
            is BrainIntent.Rejection -> return ExecutionResult(
                status = ExecutionResult.Status.REJECTED,
                correlationId = intent.correlationId,
                intent = "REJECTED",
                message = intent.message,
                reason = intent.reason
            )
            is BrainIntent.ConversationalOnly -> return ExecutionResult(
                status = ExecutionResult.Status.SUCCESS,
                correlationId = intent.correlationId,
                intent = "CONVERSATION",
                message = intent.spokenResponse
            )
        }

        tracer?.currentState = "EVALUATING_RECONCILIATION"

        // 1. Reconcile Live State with Supervisor (Stale Cache Invalidation)
        val targetDevice = (intent as? BrainIntent.DirectCommand)?.target
        val reqs = RoutineRequirements.forIntent(intentName, targetDevice)
        val liveHealth = supervisor.reconcileState(reqs)
        tracer?.healthState = liveHealth.overallHealth.name
        tracer?.mark("STATE_RECONCILED")

        // 2. Idempotency Check: If physical state already matches requested direct command, avoid redundant hardware dispatch
        if (intent is BrainIntent.DirectCommand) {
            val isAlreadySatisfied = when (intent.capability) {
                CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON -> liveHealth.deviceStates[CapabilityRegistry.DeviceTarget.PROJECTOR]?.poweredOn == true
                CapabilityRegistry.ActionCapability.PROJECTOR_POWER_OFF -> liveHealth.deviceStates[CapabilityRegistry.DeviceTarget.PROJECTOR]?.poweredOn == false
                CapabilityRegistry.ActionCapability.FIRE_TV_WAKE -> liveHealth.deviceStates[CapabilityRegistry.DeviceTarget.FIRE_TV]?.poweredOn == true
                else -> false
            }

            if (isAlreadySatisfied) {
                tracer?.finalResult = "IDEMPOTENT_SKIPPED"
                tracer?.mark("IDEMPOTENT_VERIFIED")
                return ExecutionResult(
                    status = ExecutionResult.Status.SUCCESS,
                    correlationId = intent.correlationId,
                    intent = intentName,
                    target = intent.target.name,
                    message = "Hardware state for ${intent.capability.name} already satisfied physically. Redundant dispatch skipped.",
                    verified = true,
                    latencyTraceMs = tracer?.milestoneTimestamps ?: emptyMap()
                )
            }
        }

        // 3. Recovery Escalation Management
        if (liveHealth.overallHealth != DeviceHealthStatus.HEALTHY) {
            escalationSM.transitionTo(ResilienceState.REPAIRING, "Live preflight detected defect in $intentName")
            tracer?.addRecoveryEvent("Escalated to REPAIRING for $intentName")
        }

        // 4. Delegate to Adaptive Engine with Observability Tracer
        val legacyTracer = ObservabilityTracer(intent.correlationId)
        val execResult = adaptiveEngine.executeAdaptiveIntent(intent, legacyTracer)

        // 5. Final State Verification & Escalation Completion
        if (execResult.status == ExecutionResult.Status.SUCCESS) {
            escalationSM.transitionTo(ResilienceState.VERIFIED, "Execution verified physically for $intentName")
            tracer?.executionState = "VERIFIED"
            tracer?.finalResult = "SUCCESS"
        } else {
            escalationSM.transitionTo(ResilienceState.FAILED_REQUIRES_USER, "Adaptive execution failed: ${execResult.message}")
            tracer?.executionState = "FAILED"
            tracer?.finalResult = "FAILED"
        }

        tracer?.mark("FINAL_COMPLETION")
        return execResult
    }
}
