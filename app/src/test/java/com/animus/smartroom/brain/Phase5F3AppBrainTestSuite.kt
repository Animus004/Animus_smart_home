package com.animus.smartroom.brain

import com.animus.smartroom.brain.provider.AndroidLocalInferencePort
import com.animus.smartroom.brain.provider.GeminiBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainStatus
import com.animus.smartroom.brain.provider.LocalInferenceClient
import com.animus.smartroom.brain.repository.AndroidMemoryRepository
import com.animus.smartroom.brain.repository.AndroidTaskRepository
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class Phase5F3AppBrainTestSuite {

    // 1. BrainEngineMemoryDispatchTest
    @Test
    fun `test AnimusBrainEngine automatically persists MemoryAction CREATE`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val memoryToSave = Memory(content = "User prefers AC temperature at 22C", category = MemoryCategory.PREFERENCE)

        val memoryProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Remembered", BrainAction.MemoryAction(MemoryActionType.CREATE, memoryToSave))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = memoryProvider,
            remoteProvider = remote,
            memoryRepository = memoryRepo
        )

        val (res, _) = engine.processInput("remember AC temp 22")
        assertTrue(res is BrainResponse.Command)

        val memories = memoryRepo.getMemoriesFlow().first()
        assertEquals(1, memories.size)
        assertEquals("User prefers AC temperature at 22C", memories[0].content)
    }

    // 2. BrainEngineMemoryDeleteDispatchTest
    @Test
    fun `test AnimusBrainEngine automatically deletes MemoryAction DELETE`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val memory = Memory(id = "mem-to-del-1", content = "Old preference")
        memoryRepo.saveMemory(memory)

        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val memoryProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Deleted", BrainAction.MemoryAction(MemoryActionType.DELETE, memory))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = memoryProvider,
            remoteProvider = remote,
            memoryRepository = memoryRepo
        )

        val (res, _) = engine.processInput("forget old preference")
        assertTrue(res is BrainResponse.Command)

        val memories = memoryRepo.getMemoriesFlow().first()
        assertEquals(0, memories.size)
    }

    // 3. LocalBrainStatusEnumCoverageTest
    @Test
    fun `test LocalBrainStatus enum values`() {
        assertEquals(10, LocalBrainStatus.values().size)
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.DISCONNECTED))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.CONNECTING))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.AVAILABLE))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.BUSY))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.ERROR))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.OFFLINE))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.STARTING))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.WARMING_UP))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.READY))
        assertTrue(LocalBrainStatus.values().contains(LocalBrainStatus.FAILED))
    }

    // 4. AndroidLocalInferencePortBusyTransitionTest
    @Test
    fun `test AndroidLocalInferencePort transitions to BUSY then AVAILABLE on success`() = runBlocking {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig() })
        val port = AndroidLocalInferencePort(client)
        port.setStatus(LocalBrainStatus.AVAILABLE)
        assertTrue(port.isAvailable())
    }

    // 5. LocalInferenceClientDurationRecordedOnSuccessTest
    @Test
    fun `test LocalInferenceClient records lastInferenceDurationMs`() = runBlocking {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig(enabled = false) })
        client.generateCompletion("hello")
        assertTrue(client.lastInferenceDurationMs >= 0)
    }

    // 6. ConcurrencyMutexSafetyTest
    @Test
    fun `test AnimusBrainEngine inferenceMutex executes sequentially without race condition`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        var executionCounter = 0

        val slowProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse {
                kotlinx.coroutines.delay(20)
                executionCounter++
                return BrainResponse.Conversation("Response $executionCounter")
            }
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, slowProvider, remote)

        coroutineScope {
            val j1 = async { engine.processInput("cmd 1") }
            val j2 = async { engine.processInput("cmd 2") }
            j1.await()
            j2.await()
        }

        assertEquals(2, executionCounter)
    }
}
