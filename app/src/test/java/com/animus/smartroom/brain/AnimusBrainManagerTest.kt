package com.animus.smartroom.brain

import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.command.model.AnimusCommand
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AnimusBrainManagerTest {

    private lateinit var manager: AnimusBrainManager

    @Before
    fun setUp() {
        manager = AnimusBrainManager(
            localBrain = LocalAnimusBrain(),
            cloudBrain = CloudAnimusBrain(apiKeyProvider = { null })
        )
    }

    @Test
    fun testDefaultProviderIsLocal() {
        assertEquals(BrainProviderType.LOCAL, manager.providerType)
        assertEquals(BrainProviderType.LOCAL, manager.activeProvider.value)
    }

    @Test
    fun testLocalProviderExecution() = runBlocking {
        val result = manager.interpret("pause")
        assertTrue(result is BrainResult.Success)
        assertEquals(AnimusCommand.PauseMusic, (result as BrainResult.Success).command)
    }

    @Test
    fun testCloudUnavailableFallbackToLocal() = runBlocking {
        val fakeLocal = LocalAnimusBrain()
        val fakeCloud = object : AnimusBrain {
            override val providerType = BrainProviderType.GEMINI
            override suspend fun interpret(input: String): BrainResult = BrainResult.Unavailable
        }

        val managerWithFallback = AnimusBrainManager(localBrain = fakeLocal, cloudBrain = fakeCloud)
        managerWithFallback.setProvider(BrainProviderType.GEMINI)
        assertEquals(BrainProviderType.GEMINI, managerWithFallback.providerType)

        // Cloud brain is unavailable, manager should gracefully fall back to local brain
        val result = managerWithFallback.interpret("volume 30")
        assertTrue(result is BrainResult.Success)
        val cmd = (result as BrainResult.Success).command as AnimusCommand.SetVolume
        assertEquals(30, cmd.percentage)
    }
}
