package com.animus.smartroom.brain

import com.animus.smartroom.brain.provider.GeminiBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainProvider
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.model.DeviceSummary
import com.animus.smartroom.core.brain.port.BrainProvider
import com.animus.smartroom.core.brain.port.LocalInferencePort
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Phase5F1AppBrainTestSuite {

    @Test
    fun `test LocalBrainProvider parses commands and provides spoken feedback`() = runBlocking {
        val provider = LocalBrainProvider()
        val response = provider.understand("set volume to 40", BrainContext())

        assertTrue(response is BrainResponse.Command)
        val cmd = response as BrainResponse.Command
        assertEquals("Setting volume to 40%.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.SetVolume)
        assertEquals(40, (cmd.actions[0] as BrainAction.SetVolume).percentage)
    }

    @Test
    fun `test GeminiBrainProvider returns Failure when API key missing`() = runBlocking {
        val provider = GeminiBrainProvider(apiKeyProvider = { null })
        assertFalse(provider.isAvailable())
        val response = provider.understand("turn on ac", BrainContext())
        assertTrue(response is BrainResponse.Failure)
    }

    @Test
    fun `test AnimusBrainEngine thread-safe mode switching and execution`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })

        var spokenResult: String? = null
        val voiceOutput = object : VoiceOutputPort {
            override suspend fun speak(text: String) { spokenResult = text }
            override fun stop() {}
        }

        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = local,
            remoteProvider = remote,
            voiceOutputPort = voiceOutput
        )

        // 1. Process under LOCAL mode
        val (localRes, localCommands) = engine.processInput("play Ramta Jogi")
        assertTrue(localRes is BrainResponse.Command)
        assertEquals(1, localCommands.size)
        assertTrue(localCommands[0] is AnimusCommand.PlayMusic)
        assertEquals("Playing Ramta Jogi.", spokenResult)

        // 2. Switch to REMOTE mode without key -> Failure without silent fallback
        modeController.setMode(BrainMode.REMOTE)
        val (remoteRes, remoteCommands) = engine.processInput("play Ramta Jogi")
        assertTrue(remoteRes is BrainResponse.Failure)
        assertEquals(0, remoteCommands.size)
    }

    @Test
    fun `test LocalBrainProvider with LocalInferencePort`() = runBlocking {
        val mockPort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = "Local AI output"
            override fun isAvailable(): Boolean = true
        }
        val provider = LocalBrainProvider(inferencePort = mockPort)
        val response = provider.understand("Tell me a joke", BrainContext())

        assertTrue(response is BrainResponse.Conversation)
        assertEquals("Local AI output", (response as BrainResponse.Conversation).spokenResponse)
    }
}
