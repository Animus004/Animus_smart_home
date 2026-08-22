package com.animus.smartroom.overlay

import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.core.runtime.RuntimeControlPort
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.runtime.RuntimeControlPortImpl
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class FloatingCommandRoutingTest {

    private lateinit var runtimeControlPort: RuntimeControlPort
    private lateinit var brainManager: AnimusBrainManager
    private lateinit var localBrain: LocalAnimusBrain
    private var lastExecutedCommands: List<AnimusCommand>? = null

    @Before
    fun setup() {
        localBrain = LocalAnimusBrain()
        brainManager = AnimusBrainManager(
            localBrain = localBrain,
            cloudBrain = localBrain,
            initialProvider = com.animus.smartroom.brain.model.BrainProviderType.LOCAL
        )

        // Mock CommandRouter execution without calling hardware
        val commandRouter = CommandRouter()
        val scheduler = DeviceSchedulerEngine(
            storage = ScheduledActionStorage(com.animus.smartroom.core.port.FakePersistentStore()),
            clock = com.animus.smartroom.core.port.AndroidClock()
        )

        runtimeControlPort = RuntimeControlPortImpl(
            brainManager = brainManager,
            commandRouter = commandRouter,
            deviceSchedulerEngine = scheduler
        )
    }

    @Test
    fun `submitting voice command through RuntimeControlPort executes without direct hardware calls`() = runBlocking {
        val result = runtimeControlPort.submitCommand("set volume to 45%")
        assertTrue(result is BrainResult.Success)
        val success = result as BrainResult.Success
        assertEquals(1, success.commands.size)
        val cmd = success.commands.first() as AnimusCommand.SetVolume
        assertEquals(45, cmd.percentage)
    }

    @Test
    fun `submitting blank command returns failure gracefully`() = runBlocking {
        val result = runtimeControlPort.submitCommand("   ")
        assertTrue(result is BrainResult.Failure)
    }

    @Test
    fun `cancelAction with blank id returns false`() = runBlocking {
        val result = runtimeControlPort.cancelAction("")
        assertFalse(result)
    }
}
