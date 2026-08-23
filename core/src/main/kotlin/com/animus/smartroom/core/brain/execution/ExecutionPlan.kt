package com.animus.smartroom.core.brain.execution

import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.health.RoomHealthState
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import java.util.UUID

/**
 * Execution Engine State Machine states.
 */
enum class ExecutionLifecycleState {
    PLANNED,
    VALIDATING,
    PREFLIGHT,
    ARBITRATING,
    READY,
    EXECUTING,
    VERIFYING,
    COMPLETED,
    RECOVERING,
    BLOCKED,
    FAILED,
    CANCELLED,
    REJECTED
}

/**
 * Single executable action item within an execution plan.
 */
data class PlanAction(
    val actionId: String = UUID.randomUUID().toString(),
    val target: CapabilityRegistry.DeviceTarget,
    val capability: CapabilityRegistry.ActionCapability,
    val parameters: Map<String, Any?> = emptyMap(),
    val preconditions: List<String> = emptyList(),
    val rollbackAction: PlanAction? = null,
    val timeoutMs: Long = 5000L,
    val isIdempotent: Boolean = true
)

/**
 * Stage of parallel independent actions in a multi-stage execution graph.
 */
data class ExecutionStage(
    val stageIndex: Int,
    val actions: List<PlanAction>
)

/**
 * Strongly-typed deterministic Execution Plan.
 */
data class ExecutionPlan(
    val planId: String = UUID.randomUUID().toString(),
    val intent: String,
    val priority: Int = 100, // 0 = Emergency, 50 = Direct command, 100 = Routine
    val stages: List<ExecutionStage> = emptyList(),
    val requiredArbitrations: Map<PhysicalResource, ResourceOwner> = emptyMap(),
    val verificationCheckpoints: List<String> = emptyList(),
    val rollbackSteps: List<PlanAction> = emptyList(),
    val idempotencyKey: String? = null,
    val timeoutMs: Long = 15000L
)

/**
 * Precondition verification checker.
 */
object PreconditionChecker {

    fun checkPreconditions(
        action: PlanAction,
        healthState: RoomHealthState
    ): Boolean {
        // Required device must be reachable
        val dev = healthState.deviceStates[action.target]
        if (dev != null && !dev.reachable) {
            return false
        }

        // Projector input requires projector to be powered ON
        if (action.capability == CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT) {
            val proj = healthState.deviceStates[CapabilityRegistry.DeviceTarget.PROJECTOR]
            if (proj?.poweredOn == false) {
                return false
            }
        }

        return true
    }
}
