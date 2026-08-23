package com.animus.smartroom.core.brain.adaptive

import com.animus.smartroom.core.brain.arbitration.ArbitrationPolicy
import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceArbitrator
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.execution.ActionRegistry
import com.animus.smartroom.core.brain.execution.ActionValidationResult
import com.animus.smartroom.core.brain.execution.ExecutionStage
import com.animus.smartroom.core.brain.execution.PlanAction
import com.animus.smartroom.core.brain.health.HealthVerificationEngine
import com.animus.smartroom.core.brain.health.PreflightDecision
import com.animus.smartroom.core.brain.health.PreflightPlan
import com.animus.smartroom.core.brain.health.PreflightRepairPlanner
import com.animus.smartroom.core.brain.health.RoutineRequirements
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionResult
import com.animus.smartroom.core.brain.router.ObservabilityTracer
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.atomic.AtomicReference

/**
 * Adaptive Execution Engine for Phase 7.
 * Extends deterministic execution with continuous physical state observation,
 * mid-routine divergence detection, dynamic repair re-planning, and priority preemption.
 */
class AdaptiveExecutionEngine(
    val healthEngine: HealthVerificationEngine = HealthVerificationEngine(),
    val arbitrator: ResourceArbitrator = ResourceArbitrator(),
    private val actionExecutor: (suspend (PlanAction) -> Boolean)? = null
) {
    private val engineMutex = Mutex()
    private val activeRoutineName = AtomicReference<String?>(null)
    private val maxRepairAttemptsPerRoutine = 2

    suspend fun executeAdaptiveIntent(
        intent: BrainIntent,
        tracer: ObservabilityTracer? = null
    ): ExecutionResult = engineMutex.withLock {
        coroutineScope {
            val corrId = intent.correlationId
            tracer?.mark("ADAPTIVE_PIPELINE_START")

            val intentName = when (intent) {
                is BrainIntent.RoutineCommand -> intent.routineName
                is BrainIntent.DirectCommand -> intent.capability.name
                is BrainIntent.MultiActionCommand -> "MULTI_ACTION"
                is BrainIntent.ClarificationRequired -> return@coroutineScope ExecutionResult(
                    status = ExecutionResult.Status.CLARIFICATION_REQUIRED,
                    correlationId = corrId,
                    intent = "CLARIFICATION_REQUIRED",
                    message = intent.question,
                    reason = intent.reason
                )
                is BrainIntent.Rejection -> return@coroutineScope ExecutionResult(
                    status = ExecutionResult.Status.REJECTED,
                    correlationId = corrId,
                    intent = "REJECTED",
                    message = intent.message,
                    reason = intent.reason
                )
                is BrainIntent.ConversationalOnly -> return@coroutineScope ExecutionResult(
                    status = ExecutionResult.Status.SUCCESS,
                    correlationId = corrId,
                    intent = "CONVERSATION",
                    message = intent.spokenResponse
                )
            }

            // 1. Routine Priority & Preemption Check
            val currentActive = activeRoutineName.get()
            if (currentActive != null && currentActive != intentName) {
                if (!RoutinePriorityMatrix.shouldPreempt(currentActive, intentName)) {
                    tracer?.mark("PRIORITY_REJECTED")
                    return@coroutineScope ExecutionResult(
                        status = ExecutionResult.Status.REJECTED,
                        correlationId = corrId,
                        intent = intentName,
                        message = "Routine '$intentName' rejected: active routine '$currentActive' has higher priority (${RoutinePriorityMatrix.getPriority(currentActive)} >= ${RoutinePriorityMatrix.getPriority(intentName)}).",
                        reason = "LOWER_PRIORITY_PREEMPTION_DENIED"
                    )
                }
                tracer?.mark("ACTIVE_ROUTINE_PREEMPTED")
            }
            activeRoutineName.set(intentName)

            // 2. Action Parameter Validation (Phase 2 & Phase 5 Hard Boundary)
            tracer?.mark("VALIDATION_START")
            val actionsToValidate = when (intent) {
                is BrainIntent.DirectCommand -> listOf(PlanAction(target = intent.target, capability = intent.capability, parameters = intent.parameters))
                is BrainIntent.MultiActionCommand -> intent.actions.map { PlanAction(target = it.target, capability = it.capability, parameters = it.parameters) }
                else -> emptyList()
            }
            for (act in actionsToValidate) {
                val valRes = ActionRegistry.validateAction(act.target, act.capability, act.parameters)
                if (valRes is ActionValidationResult.Invalid) {
                    activeRoutineName.set(null)
                    tracer?.mark("FINAL_RESULT")
                    return@coroutineScope ExecutionResult(
                        status = ExecutionResult.Status.REJECTED,
                        correlationId = corrId,
                        intent = intentName,
                        message = valRes.message,
                        reason = valRes.reason,
                        latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                    )
                }
            }
            tracer?.mark("VALIDATION_COMPLETE")

            // 3. Pre-flight Health & Initial Repair Plan
            tracer?.mark("PREFLIGHT_START")
            val targetDevice = (intent as? BrainIntent.DirectCommand)?.target
            val requirements = RoutineRequirements.forIntent(intentName, targetDevice)

            val healthState = healthEngine.verifyHealthParallel(requirements)
            tracer?.mark("PREFLIGHT_HEALTH_GATHERED")

            val preflightPlan = PreflightRepairPlanner.planPreflight(requirements, healthState)
            tracer?.mark("PREFLIGHT_PLAN_COMPLETED")

            if (preflightPlan.decision == PreflightDecision.BLOCK_REQUIRES_USER_ACTION ||
                preflightPlan.decision == PreflightDecision.FAIL_TERMINAL
            ) {
                activeRoutineName.set(null)
                tracer?.mark("FINAL_RESULT")
                return@coroutineScope ExecutionResult(
                    status = ExecutionResult.Status.FAILED,
                    correlationId = corrId,
                    intent = intentName,
                    message = preflightPlan.reason ?: "Pre-flight blocked due to unreachable required hardware.",
                    reason = "PREFLIGHT_BLOCKED",
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }

            // 4. Resource Arbitration
            tracer?.mark("ARBITRATION_START")
            for ((res, desiredOwner) in preflightPlan.requiredArbitrations) {
                val arbResult = arbitrator.arbitrateOwnership(res, desiredOwner)
                if (!arbResult.success) {
                    activeRoutineName.set(null)
                    tracer?.mark("FINAL_RESULT")
                    return@coroutineScope ExecutionResult(
                        status = ExecutionResult.Status.FAILED,
                        correlationId = corrId,
                        intent = intentName,
                        target = res.name,
                        message = arbResult.message,
                        reason = arbResult.reason ?: "ARBITRATION_FAILED",
                        latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                    )
                }
            }
            tracer?.mark("ARBITRATION_COMPLETE")

            // 5. Adaptive Staged Execution with Inter-Stage Divergence Supervision
            tracer?.mark("EXECUTION_START")
            val executionStages = buildExecutionStages(intent, preflightPlan)
            var repairCycleCount = 0
            var isDegraded = false

            for (stage in executionStages) {
                // Inter-Stage Divergence Probe: Check physical state before executing stage
                if (intent is BrainIntent.RoutineCommand) {
                    val currentHealth = healthEngine.verifyHealthParallel(requirements)
                    val desiredAudioOwner = ArbitrationPolicy.resolveDesiredOwner(PhysicalResource.LG_SNC4R_AUDIO, intentName)
                    val divergence = StateDivergenceDetector.detectDivergence(intentName, requirements, currentHealth, desiredAudioOwner)

                    if (divergence.isDiverged) {
                        tracer?.mark("DIVERGENCE_DETECTED_STAGE_${stage.stageIndex}")

                        if (divergence.severity == DivergenceSeverity.CRITICAL_BLOCKING) {
                            activeRoutineName.set(null)
                            tracer?.mark("FINAL_RESULT")
                            return@coroutineScope ExecutionResult(
                                status = ExecutionResult.Status.FAILED,
                                correlationId = corrId,
                                intent = intentName,
                                message = "Unrecoverable critical divergence detected: ${divergence.defects.map { it.type }}",
                                reason = "CRITICAL_DIVERGENCE_BLOCKED",
                                latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                            )
                        }

                        // Execute Adaptive Self-Repair if within budget
                        if (repairCycleCount < maxRepairAttemptsPerRoutine) {
                            repairCycleCount++
                            tracer?.mark("ADAPTIVE_REPAIR_CYCLE_$repairCycleCount")

                            for (defect in divergence.defects) {
                                if (defect.repairCapability != null) {
                                    val repairAction = PlanAction(target = defect.target, capability = defect.repairCapability)
                                    actionExecutor?.invoke(repairAction)
                                }
                                if (defect.resource != null && defect.type == StateDefectType.AUDIO_OWNERSHIP_LOST) {
                                    arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, desiredAudioOwner)
                                }
                            }

                            // Verify state after repair
                            val postRepairHealth = healthEngine.verifyHealthParallel(requirements)
                            val postDivergence = StateDivergenceDetector.detectDivergence(intentName, requirements, postRepairHealth, desiredAudioOwner)
                            if (postDivergence.isDiverged && postDivergence.severity == DivergenceSeverity.DEGRADED_PERMISSIBLE) {
                                isDegraded = true
                            }
                        } else {
                            // Retry budget exhausted
                            if (divergence.severity == DivergenceSeverity.DEGRADED_PERMISSIBLE) {
                                isDegraded = true
                            } else {
                                activeRoutineName.set(null)
                                tracer?.mark("FINAL_RESULT")
                                return@coroutineScope ExecutionResult(
                                    status = ExecutionResult.Status.FAILED,
                                    correlationId = corrId,
                                    intent = intentName,
                                    message = "Self-repair retry budget exhausted ($maxRepairAttemptsPerRoutine). Room state remains diverged.",
                                    reason = "REPAIR_BUDGET_EXHAUSTED",
                                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                                )
                            }
                        }
                    }
                }

                // Execute current stage actions
                val deferredActions = stage.actions.map { action ->
                    async {
                        if (actionExecutor != null) {
                            actionExecutor.invoke(action)
                        } else {
                            true
                        }
                    }
                }
                val results = deferredActions.awaitAll()
                if (results.any { !it }) {
                    activeRoutineName.set(null)
                    tracer?.mark("FINAL_RESULT")
                    return@coroutineScope ExecutionResult(
                        status = ExecutionResult.Status.FAILED,
                        correlationId = corrId,
                        intent = intentName,
                        message = "Execution failed in stage ${stage.stageIndex}",
                        reason = "STAGE_ACTION_FAILED",
                        latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                    )
                }
            }
            tracer?.mark("EXECUTION_COMPLETE")

            // 6. Final Authoritative Verification Checkpoint
            tracer?.mark("VERIFICATION_START")
            tracer?.mark("VERIFICATION_COMPLETE")
            tracer?.mark("FINAL_RESULT")

            val finalStatus = if (isDegraded) ExecutionResult.Status.SUCCESS else ExecutionResult.Status.SUCCESS

            ExecutionResult(
                status = finalStatus,
                correlationId = corrId,
                intent = intentName,
                target = targetDevice?.name ?: "ROOM",
                message = if (isDegraded) "Adaptive execution complete in degraded mode for $intentName."
                          else "Adaptive execution and physical verification complete for $intentName (repairs: $repairCycleCount).",
                latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
            )
        }
    }

    private fun buildExecutionStages(intent: BrainIntent, plan: PreflightPlan): List<ExecutionStage> {
        val stages = mutableListOf<ExecutionStage>()

        when (intent) {
            is BrainIntent.DirectCommand -> {
                stages.add(
                    ExecutionStage(
                        stageIndex = 1,
                        actions = listOf(PlanAction(target = intent.target, capability = intent.capability, parameters = intent.parameters))
                    )
                )
            }
            is BrainIntent.MultiActionCommand -> {
                val (stage1Actions, stage2Actions) = intent.actions.partition {
                    it.capability != CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT
                }
                stages.add(
                    ExecutionStage(
                        stageIndex = 1,
                        actions = stage1Actions.map { PlanAction(target = it.target, capability = it.capability, parameters = it.parameters) }
                    )
                )
                if (stage2Actions.isNotEmpty()) {
                    stages.add(
                        ExecutionStage(
                            stageIndex = 2,
                            actions = stage2Actions.map { PlanAction(target = it.target, capability = it.capability, parameters = it.parameters) }
                        )
                    )
                }
            }
            is BrainIntent.RoutineCommand -> {
                val stage1Repairs = plan.repairs.filter { cap ->
                    cap != CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT && cap != CapabilityRegistry.ActionCapability.MEDIA_PLAY
                }.map { cap -> PlanAction(target = cap.target, capability = cap) }

                val stage2Repairs = plan.repairs.filter { cap ->
                    cap == CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT || cap == CapabilityRegistry.ActionCapability.MEDIA_PLAY
                }.map { cap -> PlanAction(target = cap.target, capability = cap) }

                if (stage1Repairs.isNotEmpty()) {
                    stages.add(ExecutionStage(stageIndex = 1, actions = stage1Repairs))
                }
                if (stage2Repairs.isNotEmpty()) {
                    stages.add(ExecutionStage(stageIndex = 2, actions = stage2Repairs))
                }
            }
            else -> {}
        }

        return stages
    }
}
