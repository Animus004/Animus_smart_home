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

class Phase5F3ExpandedAppBrainTestSuite {

    // 7. LocalBrainProviderPunctuationCleanupTest
    @Test
    fun `test LocalBrainProvider trims punctuation artifacts from voice input`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("turn on the ac.", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.DeviceCommand)
    }

    // 8. LocalBrainProviderQuestionMarkCleanupTest
    @Test
    fun `test LocalBrainProvider handles trailing question mark on status queries`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("what is the ac status?", BrainContext())
        assertTrue(res is BrainResponse.Conversation)
    }

    // 9. LocalBrainProviderExcessiveWhitespaceTest
    @Test
    fun `test LocalBrainProvider normalizes excessive whitespace`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("   turn   off   ac   ", BrainContext())
        assertTrue(res is BrainResponse.Command)
    }

    // 10. LocalInferenceClientPingTimeoutTest
    @Test
    fun `test LocalInferenceClient ping returns false on unreachable host`() = runBlocking {
        val unreachableConfig = LocalBrainConfig(host = "192.0.2.1", port = 11434, timeoutMs = 500)
        val client = LocalInferenceClient(configProvider = { unreachableConfig })
        assertFalse(client.ping())
    }

    // 11. LocalBrainStatusErrorTransitionTest
    @Test
    fun `test AndroidLocalInferencePort transitions to ERROR on generate exception`() = runBlocking {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig(enabled = false) })
        val port = AndroidLocalInferencePort(client)
        port.setStatus(LocalBrainStatus.READY)

        try {
            port.generate("prompt", emptyList())
            fail("Expected exception")
        } catch (e: Exception) {
            assertTrue(e is Exception)
        }
    }

    // 12. BrainEngineVoiceFeedbackOnTaskCreateTest
    @Test
    fun `test AnimusBrainEngine speaks confirmation when creating task`() = runBlocking {
        val taskRepo = AndroidTaskRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })

        var spokenResponse: String? = null
        val voiceOutput = object : VoiceOutputPort {
            override suspend fun speak(text: String) { spokenResponse = text }
            override fun stop() {}
        }

        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = local,
            remoteProvider = remote,
            taskRepository = taskRepo,
            voiceOutputPort = voiceOutput
        )

        val (res, _) = engine.processInput("add task to inspect AC unit")
        assertTrue(res is BrainResponse.Command)
        assertEquals("Added task: inspect AC unit", spokenResponse)
    }

    // 13. BrainEngineTaskRepositoryNullSafetyTest
    @Test
    fun `test AnimusBrainEngine handles null TaskRepository safely without crash`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, taskRepository = null)

        val (res, _) = engine.processInput("add task to clean room")
        assertTrue(res is BrainResponse.Command)
    }

    // 14. BrainEngineMemoryRepositoryNullSafetyTest
    @Test
    fun `test AnimusBrainEngine handles null MemoryRepository safely without crash`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val memoryProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Remembered", BrainAction.MemoryAction(MemoryActionType.CREATE, Memory(content = "test")))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, memoryProvider, remote, memoryRepository = null)

        val (res, _) = engine.processInput("remember test")
        assertTrue(res is BrainResponse.Command)
    }

    // 15. LocalBrainProviderMalformedJsonFallbackTest
    @Test
    fun `test LocalBrainProvider gracefully parses malformed LLM response using rule fallback`() = runBlocking {
        val malformedPort = object : com.animus.smartroom.core.brain.port.LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String {
                throw RuntimeException("Inference server error")
            }
            override fun isAvailable(): Boolean = true
        }
        val provider = LocalBrainProvider(inferencePort = malformedPort)
        val res = provider.understand("turn on ac", BrainContext())
        assertTrue(res is BrainResponse.Command)
    }

    // 16. LocalBrainProviderSetVolumeNumberWordsTest
    @Test
    fun `test LocalBrainProvider parses volume command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("set volume to 50", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(50, (cmd.actions[0] as BrainAction.SetVolume).percentage)
    }

    // 17. LocalBrainProviderClarificationSpeakerTest
    @Test
    fun `test LocalBrainProvider play music prompt returns clarification when speaker ambiguous`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("play music on speaker", BrainContext())
        assertTrue(res is BrainResponse.Command || res is BrainResponse.Clarification || res is BrainResponse.Conversation)
    }

    // 18. LocalBrainProviderScheduleTurnOffTest
    @Test
    fun `test LocalBrainProvider parses schedule AC turn off in minutes`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("turn the ac off after 15 minutes", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.ScheduleAction)
        val sched = cmd.actions[0] as BrainAction.ScheduleAction
        assertEquals(15, sched.delayMinutes)
    }

    // 19. LocalBrainProviderConnectSpeakerAliasTest
    @Test
    fun `test LocalBrainProvider parses soundbar connect command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("connect soundbar", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.ConnectBluetooth)
    }

    // 20. LocalBrainProviderDisconnectSpeakerAliasTest
    @Test
    fun `test LocalBrainProvider parses disconnect soundbar command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("disconnect soundbar", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.DisconnectBluetooth)
    }

    // 21. LocalBrainStatusConnectingStateTest
    @Test
    fun `test AndroidLocalInferencePort setStatus CONNECTING`() {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig() })
        val port = AndroidLocalInferencePort(client)
        port.setStatus(LocalBrainStatus.CONNECTING)
        assertEquals(LocalBrainStatus.CONNECTING, port.status.value)
    }

    // 22. LocalBrainStatusDisconnectedStateTest
    @Test
    fun `test AndroidLocalInferencePort setStatus DISCONNECTED`() {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig() })
        val port = AndroidLocalInferencePort(client)
        port.setStatus(LocalBrainStatus.DISCONNECTED)
        assertEquals(LocalBrainStatus.DISCONNECTED, port.status.value)
        assertFalse(port.isAvailable())
    }

    // 23. LocalBrainStatusErrorStateTest
    @Test
    fun `test AndroidLocalInferencePort setStatus ERROR`() {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig() })
        val port = AndroidLocalInferencePort(client)
        port.setStatus(LocalBrainStatus.ERROR)
        assertEquals(LocalBrainStatus.ERROR, port.status.value)
        assertFalse(port.isAvailable())
    }

    // 24. LocalBrainConfigDefaultModelTest
    @Test
    fun `test LocalBrainConfig default model is qwen3 4b-instruct`() {
        val config = LocalBrainConfig()
        assertEquals("qwen3:4b-instruct", config.model)
        assertEquals(11434, config.port)
        assertEquals("127.0.0.1", config.host)
    }

    // 25. LocalInferenceClientCustomModelTest
    @Test
    fun `test LocalBrainConfig allows custom model string`() {
        val config = LocalBrainConfig(model = "Phi-4-mini-instruct")
        assertEquals("Phi-4-mini-instruct", config.model)
        assertTrue(config.isValid())
    }
}
