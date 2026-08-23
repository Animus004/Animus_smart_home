package com.animus.smartroom.core.brain.arbitration

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.ConcurrentHashMap

/**
 * Concurrency-safe registry for physical resource ownership.
 * Uses resource-scoped mutexes to allow independent resources to arbitrate concurrently,
 * while strictly serializing competing requests for the same exclusive resource.
 */
class OwnershipRegistry {

    private val descriptors = ConcurrentHashMap<PhysicalResource, ResourceDescriptor>()
    private val resourceLocks = ConcurrentHashMap<PhysicalResource, Mutex>()

    init {
        // Initialize default descriptors
        PhysicalResource.entries.forEach { res ->
            val type = when (res) {
                PhysicalResource.LG_SNC4R_AUDIO -> ResourceType.BLUETOOTH_AUDIO_SINK
                PhysicalResource.PROJECTOR_DISPLAY -> ResourceType.DISPLAY_OUTPUT
                PhysicalResource.PROJECTOR_HDMI_INPUT -> ResourceType.HDMI_SOURCE
                PhysicalResource.FIRE_TV_PLAYBACK -> ResourceType.MEDIA_SESSION
                PhysicalResource.AC_CLIMATE -> ResourceType.CLIMATE_CONTROLLER
            }
            descriptors[res] = ResourceDescriptor(
                resourceId = res,
                resourceType = type,
                currentOwner = ResourceOwner.NONE,
                state = ResourceState.AVAILABLE
            )
            resourceLocks[res] = Mutex()
        }
    }

    fun getResourceMutex(resource: PhysicalResource): Mutex {
        return resourceLocks.computeIfAbsent(resource) { Mutex() }
    }

    fun getResourceState(resource: PhysicalResource): ResourceDescriptor {
        return descriptors[resource] ?: ResourceDescriptor(
            resourceId = resource,
            resourceType = ResourceType.BLUETOOTH_AUDIO_SINK,
            currentOwner = ResourceOwner.UNKNOWN,
            state = ResourceState.UNKNOWN
        )
    }

    fun getCurrentOwner(resource: PhysicalResource): ResourceOwner {
        return getResourceState(resource).currentOwner
    }

    suspend fun <T> withResourceLock(resource: PhysicalResource, block: suspend () -> T): T {
        val mutex = getResourceMutex(resource)
        return mutex.withLock {
            block()
        }
    }

    fun updateResourceState(
        resource: PhysicalResource,
        owner: ResourceOwner,
        state: ResourceState,
        confidence: Float = 1.0f,
        metadata: Map<String, Any?> = emptyMap()
    ): ResourceDescriptor {
        val current = getResourceState(resource)
        val updated = current.copy(
            currentOwner = owner,
            state = state,
            lastVerifiedAtMs = System.currentTimeMillis(),
            confidence = confidence,
            metadata = metadata
        )
        descriptors[resource] = updated
        return updated
    }

    fun markTransitioning(resource: PhysicalResource, desiredOwner: ResourceOwner): ResourceDescriptor {
        val current = getResourceState(resource)
        val updated = current.copy(
            desiredOwner = desiredOwner,
            state = ResourceState.TRANSITIONING,
            lastVerifiedAtMs = System.currentTimeMillis()
        )
        descriptors[resource] = updated
        return updated
    }

    fun markFailed(resource: PhysicalResource, reason: String): ResourceDescriptor {
        val current = getResourceState(resource)
        val updated = current.copy(
            state = ResourceState.FAILED,
            lastVerifiedAtMs = System.currentTimeMillis(),
            metadata = current.metadata + ("error" to reason)
        )
        descriptors[resource] = updated
        return updated
    }
}
