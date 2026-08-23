package com.animus.smartroom.core.brain.arbitration

/**
 * Hardware bridge interface for performing physical resource ownership operations.
 */
interface ResourceOwnershipAdapter {
    suspend fun queryPhysicalOwner(resource: PhysicalResource): ResourceOwner
    suspend fun releaseResource(resource: PhysicalResource, currentOwner: ResourceOwner): Boolean
    suspend fun acquireResource(resource: PhysicalResource, desiredOwner: ResourceOwner): Boolean
    suspend fun verifyOwnership(resource: PhysicalResource, expectedOwner: ResourceOwner): Boolean
}

/**
 * Default simulated adapter for unit tests and fallback.
 */
open class DefaultResourceOwnershipAdapter : ResourceOwnershipAdapter {
    private var simulatedOwner: ResourceOwner = ResourceOwner.NONE

    override suspend fun queryPhysicalOwner(resource: PhysicalResource): ResourceOwner = simulatedOwner
    override suspend fun releaseResource(resource: PhysicalResource, currentOwner: ResourceOwner): Boolean {
        simulatedOwner = ResourceOwner.NONE
        return true
    }
    override suspend fun acquireResource(resource: PhysicalResource, desiredOwner: ResourceOwner): Boolean {
        simulatedOwner = desiredOwner
        return true
    }
    override suspend fun verifyOwnership(resource: PhysicalResource, expectedOwner: ResourceOwner): Boolean {
        return simulatedOwner == expectedOwner
    }
}

/**
 * Deterministic Resource Arbitrator.
 * Coordinates exclusive resource ownership transfers, verifies physical states,
 * and handles failures without LLM intervention.
 */
class ResourceArbitrator(
    val registry: OwnershipRegistry = OwnershipRegistry(),
    private val defaultAdapter: ResourceOwnershipAdapter = DefaultResourceOwnershipAdapter()
) {

    suspend fun arbitrateOwnership(
        resource: PhysicalResource,
        desiredOwner: ResourceOwner,
        adapter: ResourceOwnershipAdapter = defaultAdapter
    ): ArbitrationResult {
        val t0 = System.currentTimeMillis()

        return registry.withResourceLock(resource) {
            // 1. Query physical reality
            val currentPhysicalOwner = adapter.queryPhysicalOwner(resource)
            registry.updateResourceState(
                resource = resource,
                owner = currentPhysicalOwner,
                state = if (currentPhysicalOwner == ResourceOwner.NONE) ResourceState.AVAILABLE else ResourceState.OWNED
            )

            // 2. Idempotency Check: Already owned by requested owner?
            if (currentPhysicalOwner == desiredOwner && desiredOwner != ResourceOwner.NONE) {
                val tEnd = System.currentTimeMillis()
                return@withResourceLock ArbitrationResult(
                    success = true,
                    resourceId = resource,
                    requestedOwner = desiredOwner,
                    previousOwner = currentPhysicalOwner,
                    finalOwner = desiredOwner,
                    state = ResourceState.OWNED,
                    decision = "ALREADY_OWNED",
                    totalLatencyMs = tEnd - t0,
                    message = "Resource $resource is already owned by $desiredOwner"
                )
            }

            // 3. Mark Transitioning
            registry.markTransitioning(resource, desiredOwner)

            var releaseDuration = 0L
            var acquireDuration = 0L
            var verifyDuration = 0L

            // 4. Release current owner if occupied
            if (currentPhysicalOwner != ResourceOwner.NONE && currentPhysicalOwner != desiredOwner) {
                val tRel0 = System.currentTimeMillis()
                val releaseOk = adapter.releaseResource(resource, currentPhysicalOwner)
                releaseDuration = System.currentTimeMillis() - tRel0

                if (!releaseOk) {
                    registry.markFailed(resource, "RELEASE_FAILED")
                    val tEnd = System.currentTimeMillis()
                    return@withResourceLock ArbitrationResult(
                        success = false,
                        resourceId = resource,
                        requestedOwner = desiredOwner,
                        previousOwner = currentPhysicalOwner,
                        finalOwner = currentPhysicalOwner,
                        state = ResourceState.FAILED,
                        decision = "RELEASE_FAILED",
                        releaseLatencyMs = releaseDuration,
                        totalLatencyMs = tEnd - t0,
                        reason = "RELEASE_FAILED",
                        message = "Failed to release resource $resource from $currentPhysicalOwner"
                    )
                }

                // Verify release
                val postReleaseOwner = adapter.queryPhysicalOwner(resource)
                if (postReleaseOwner == currentPhysicalOwner) {
                    registry.markFailed(resource, "VERIFY_RELEASE_FAILED")
                    val tEnd = System.currentTimeMillis()
                    return@withResourceLock ArbitrationResult(
                        success = false,
                        resourceId = resource,
                        requestedOwner = desiredOwner,
                        previousOwner = currentPhysicalOwner,
                        finalOwner = currentPhysicalOwner,
                        state = ResourceState.FAILED,
                        decision = "VERIFY_RELEASE_FAILED",
                        releaseLatencyMs = releaseDuration,
                        totalLatencyMs = tEnd - t0,
                        reason = "VERIFY_RELEASE_FAILED",
                        message = "Hardware reports resource $resource still owned by $currentPhysicalOwner after release"
                    )
                }
            }

            // 5. If desired owner is NONE, release was the only goal
            if (desiredOwner == ResourceOwner.NONE) {
                registry.updateResourceState(resource, ResourceOwner.NONE, ResourceState.AVAILABLE)
                val tEnd = System.currentTimeMillis()
                return@withResourceLock ArbitrationResult(
                    success = true,
                    resourceId = resource,
                    requestedOwner = desiredOwner,
                    previousOwner = currentPhysicalOwner,
                    finalOwner = ResourceOwner.NONE,
                    state = ResourceState.AVAILABLE,
                    decision = "RELEASED",
                    releaseLatencyMs = releaseDuration,
                    totalLatencyMs = tEnd - t0,
                    message = "Resource $resource successfully released to AVAILABLE"
                )
            }

            // 6. Acquire desired owner
            val tAcq0 = System.currentTimeMillis()
            val acquireOk = adapter.acquireResource(resource, desiredOwner)
            acquireDuration = System.currentTimeMillis() - tAcq0

            if (!acquireOk) {
                // Attempt rollback to available
                registry.markFailed(resource, "ACQUISITION_FAILED")
                val tEnd = System.currentTimeMillis()
                return@withResourceLock ArbitrationResult(
                    success = false,
                    resourceId = resource,
                    requestedOwner = desiredOwner,
                    previousOwner = currentPhysicalOwner,
                    finalOwner = ResourceOwner.NONE,
                    state = ResourceState.FAILED,
                    decision = "ACQUISITION_FAILED",
                    releaseLatencyMs = releaseDuration,
                    acquisitionLatencyMs = acquireDuration,
                    totalLatencyMs = tEnd - t0,
                    reason = "ACQUISITION_FAILED",
                    message = "Failed to acquire resource $resource for $desiredOwner"
                )
            }

            // 7. Physically verify acquisition
            val tVer0 = System.currentTimeMillis()
            val verified = adapter.verifyOwnership(resource, desiredOwner)
            verifyDuration = System.currentTimeMillis() - tVer0

            if (!verified) {
                registry.markFailed(resource, "VERIFICATION_FAILED")
                val tEnd = System.currentTimeMillis()
                return@withResourceLock ArbitrationResult(
                    success = false,
                    resourceId = resource,
                    requestedOwner = desiredOwner,
                    previousOwner = currentPhysicalOwner,
                    finalOwner = ResourceOwner.UNKNOWN,
                    state = ResourceState.FAILED,
                    decision = "VERIFICATION_FAILED",
                    releaseLatencyMs = releaseDuration,
                    acquisitionLatencyMs = acquireDuration,
                    verificationLatencyMs = verifyDuration,
                    totalLatencyMs = tEnd - t0,
                    reason = "VERIFICATION_FAILED",
                    message = "Hardware verification failed: $resource is not owned by $desiredOwner"
                )
            }

            // 8. Success: Update registry
            registry.updateResourceState(resource, desiredOwner, ResourceState.OWNED)
            val tEnd = System.currentTimeMillis()

            ArbitrationResult(
                success = true,
                resourceId = resource,
                requestedOwner = desiredOwner,
                previousOwner = currentPhysicalOwner,
                finalOwner = desiredOwner,
                state = ResourceState.OWNED,
                decision = if (currentPhysicalOwner == ResourceOwner.NONE) "ACQUIRED" else "TRANSFERRED",
                releaseLatencyMs = releaseDuration,
                acquisitionLatencyMs = acquireDuration,
                verificationLatencyMs = verifyDuration,
                totalLatencyMs = tEnd - t0,
                message = "Resource $resource successfully transferred to $desiredOwner"
            )
        }
    }
}
