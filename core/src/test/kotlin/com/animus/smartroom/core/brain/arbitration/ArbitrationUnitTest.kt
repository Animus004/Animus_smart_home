package com.animus.smartroom.core.brain.arbitration

import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ArbitrationUnitTest {

    private lateinit var registry: OwnershipRegistry
    private lateinit var arbitrator: ResourceArbitrator

    @Before
    fun setUp() {
        registry = OwnershipRegistry()
        arbitrator = ResourceArbitrator(registry)
    }

    @Test
    fun `test resource available acquisition succeeds`() = runBlocking {
        val result = arbitrator.arbitrateOwnership(
            resource = PhysicalResource.LG_SNC4R_AUDIO,
            desiredOwner = ResourceOwner.PHONE
        )

        assertTrue(result.success)
        assertEquals("ACQUIRED", result.decision)
        assertEquals(ResourceOwner.PHONE, result.finalOwner)
        assertEquals(ResourceState.OWNED, result.state)
        assertEquals(ResourceOwner.PHONE, registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))
    }

    @Test
    fun `test resource already owned is idempotent no-op`() = runBlocking {
        // Step 1: Initial acquisition
        arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.FIRE_TV)

        // Step 2: Re-request same owner
        val result = arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.FIRE_TV)

        assertTrue(result.success)
        assertEquals("ALREADY_OWNED", result.decision)
        assertEquals(ResourceOwner.FIRE_TV, result.finalOwner)
    }

    @Test
    fun `test resource transfer from Fire TV to Phone`() = runBlocking {
        // Initial state: Fire TV owns soundbar
        arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.FIRE_TV)
        assertEquals(ResourceOwner.FIRE_TV, registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))

        // Transfer to Phone for music
        val result = arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.PHONE)

        assertTrue(result.success)
        assertEquals("TRANSFERRED", result.decision)
        assertEquals(ResourceOwner.FIRE_TV, result.previousOwner)
        assertEquals(ResourceOwner.PHONE, result.finalOwner)
        assertEquals(ResourceOwner.PHONE, registry.getCurrentOwner(PhysicalResource.LG_SNC4R_AUDIO))
    }

    @Test
    fun `test release failure produces structured error and preserves state`() = runBlocking {
        val failingReleaseAdapter = object : DefaultResourceOwnershipAdapter() {
            override suspend fun queryPhysicalOwner(resource: PhysicalResource): ResourceOwner = ResourceOwner.FIRE_TV
            override suspend fun releaseResource(resource: PhysicalResource, currentOwner: ResourceOwner): Boolean {
                return false
            }
        }

        // Set initial owner
        registry.updateResourceState(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.FIRE_TV, ResourceState.OWNED)

        val result = arbitrator.arbitrateOwnership(
            resource = PhysicalResource.LG_SNC4R_AUDIO,
            desiredOwner = ResourceOwner.PHONE,
            adapter = failingReleaseAdapter
        )

        assertFalse(result.success)
        assertEquals("RELEASE_FAILED", result.reason)
        assertEquals(ResourceState.FAILED, result.state)
    }

    @Test
    fun `test acquisition failure produces structured error`() = runBlocking {
        val failingAcquireAdapter = object : DefaultResourceOwnershipAdapter() {
            override suspend fun acquireResource(resource: PhysicalResource, desiredOwner: ResourceOwner): Boolean {
                return false
            }
        }

        val result = arbitrator.arbitrateOwnership(
            resource = PhysicalResource.LG_SNC4R_AUDIO,
            desiredOwner = ResourceOwner.PHONE,
            adapter = failingAcquireAdapter
        )

        assertFalse(result.success)
        assertEquals("ACQUISITION_FAILED", result.reason)
        assertEquals(ResourceState.FAILED, result.state)
    }

    @Test
    fun `test verification failure produces structured error`() = runBlocking {
        val failingVerificationAdapter = object : DefaultResourceOwnershipAdapter() {
            override suspend fun verifyOwnership(resource: PhysicalResource, expectedOwner: ResourceOwner): Boolean {
                return false // Simulates hardware reporting not owned
            }
        }

        val result = arbitrator.arbitrateOwnership(
            resource = PhysicalResource.LG_SNC4R_AUDIO,
            desiredOwner = ResourceOwner.PHONE,
            adapter = failingVerificationAdapter
        )

        assertFalse(result.success)
        assertEquals("VERIFICATION_FAILED", result.reason)
        assertEquals(ResourceState.FAILED, result.state)
    }

    @Test
    fun `test concurrent arbitration on independent resources run in parallel`() = runBlocking {
        val slowAdapter = object : DefaultResourceOwnershipAdapter() {
            override suspend fun acquireResource(resource: PhysicalResource, desiredOwner: ResourceOwner): Boolean {
                delay(100)
                return super.acquireResource(resource, desiredOwner)
            }
        }

        val t0 = System.currentTimeMillis()
        val job1 = async { arbitrator.arbitrateOwnership(PhysicalResource.LG_SNC4R_AUDIO, ResourceOwner.PHONE, slowAdapter) }
        val job2 = async { arbitrator.arbitrateOwnership(PhysicalResource.PROJECTOR_HDMI_INPUT, ResourceOwner.FIRE_TV, slowAdapter) }

        val res1 = job1.await()
        val res2 = job2.await()
        val totalTime = System.currentTimeMillis() - t0

        assertTrue(res1.success)
        assertTrue(res2.success)
        // If parallel, totalTime should be ~100ms-150ms rather than sequential 200ms+
        assertTrue("Concurrent independent arbitration took $totalTime ms", totalTime < 190)
    }

    @Test
    fun `test policy preferred device mapping`() {
        assertEquals(ResourceOwner.FIRE_TV, ArbitrationPolicy.resolveDesiredOwner(PhysicalResource.LG_SNC4R_AUDIO, "MOVIE_MODE"))
        assertEquals(ResourceOwner.PHONE, ArbitrationPolicy.resolveDesiredOwner(PhysicalResource.LG_SNC4R_AUDIO, "MUSIC_MODE"))
        assertEquals(ResourceOwner.PC, ArbitrationPolicy.resolveDesiredOwner(PhysicalResource.LG_SNC4R_AUDIO, "WORK_MODE"))
        assertEquals("HDMI_1", ArbitrationPolicy.resolveProjectorInput(ResourceOwner.FIRE_TV))
        assertEquals("HDMI_2", ArbitrationPolicy.resolveProjectorInput(ResourceOwner.PC))
    }
}
