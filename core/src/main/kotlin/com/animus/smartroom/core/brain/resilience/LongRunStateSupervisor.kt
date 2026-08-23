package com.animus.smartroom.core.brain.resilience

import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceArbitrator
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.health.DeviceHealthStatus
import com.animus.smartroom.core.brain.health.HealthVerificationEngine
import com.animus.smartroom.core.brain.health.RoomHealthState
import com.animus.smartroom.core.brain.health.RoutineRequirements
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * Long-Run State Supervisor.
 * Continuously reconciles authoritative physical device telemetry with internal cached state.
 * Purges stale state, enforces single-flight recovery gating, and prevents duplicate recovery loops.
 */
class LongRunStateSupervisor(
    val healthEngine: HealthVerificationEngine = HealthVerificationEngine(),
    val arbitrator: ResourceArbitrator = ResourceArbitrator()
) {
    private val cachedDeviceStates = ConcurrentHashMap<CapabilityRegistry.DeviceTarget, DeviceHealthStatus>()
    private val cachedResourceOwners = ConcurrentHashMap<PhysicalResource, ResourceOwner>()

    private val flightMutex = Mutex()
    private var inFlightDeferred: CompletableDeferred<Any?>? = null

    val isRecovering = AtomicBoolean(false)
    val totalRecoveryTriggers = AtomicInteger(0)

    /**
     * Reconciles internal state against live physical sensors.
     * Invariant: Live physical state ALWAYS overrides cached state.
     */
    suspend fun reconcileState(requirements: RoutineRequirements): RoomHealthState {
        val liveHealth = healthEngine.verifyHealthParallel(requirements)

        // Stale state detection & invalidation
        for ((target, liveDev) in liveHealth.deviceStates) {
            cachedDeviceStates[target] = liveDev.status
        }

        // Reconcile physical resource ownerships
        for (res in PhysicalResource.entries) {
            val liveOwner = arbitrator.registry.getCurrentOwner(res)
            cachedResourceOwners[res] = liveOwner
        }

        return liveHealth
    }

    /**
     * Executes single-flight recovery: multiple concurrent requests await the same recovery execution
     * without spawning redundant recovery processes.
     */
    suspend fun <T> executeSingleFlightRecovery(recoveryAction: suspend () -> T): T {
        var deferredToAwait: CompletableDeferred<Any?>? = null
        var isLeader = false

        flightMutex.withLock {
            val existing = inFlightDeferred
            if (existing != null && !existing.isCompleted) {
                deferredToAwait = existing
            } else {
                val newDeferred = CompletableDeferred<Any?>()
                inFlightDeferred = newDeferred
                deferredToAwait = newDeferred
                isLeader = true
                totalRecoveryTriggers.incrementAndGet()
                isRecovering.set(true)
            }
        }

        if (isLeader) {
            try {
                val result = recoveryAction.invoke()
                deferredToAwait?.complete(result)
            } catch (t: Throwable) {
                deferredToAwait?.completeExceptionally(t)
            } finally {
                flightMutex.withLock {
                    isRecovering.set(false)
                    inFlightDeferred = null
                }
            }
        }

        @Suppress("UNCHECKED_CAST")
        return deferredToAwait!!.await() as T
    }

    fun getCachedStatus(target: CapabilityRegistry.DeviceTarget): DeviceHealthStatus? {
        return cachedDeviceStates[target]
    }

    fun injectStaleStateForTesting(target: CapabilityRegistry.DeviceTarget, staleStatus: DeviceHealthStatus) {
        cachedDeviceStates[target] = staleStatus
    }
}
