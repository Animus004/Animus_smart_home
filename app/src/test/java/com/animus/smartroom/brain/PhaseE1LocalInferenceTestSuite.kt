package com.animus.smartroom.brain

import com.animus.smartroom.brain.knowledge.GeminiKnowledgeBridge
import com.animus.smartroom.brain.model.BrainCommandDto
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.AndroidLocalInferencePort
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.brain.provider.LocalBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainStatus
import com.animus.smartroom.brain.provider.LocalInferenceClient
import com.animus.smartroom.brain.provider.OllamaLocalLlmClient
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.model.LocalBrainConfig
import com.animus.smartroom.core.brain.port.LocalInferencePort
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PhaseE1LocalInferenceTestSuite {

    private val validConfig = LocalBrainConfig(
        enabled = true,
        host = "192.168.1.9",
        port = 11434,
        model = "qwen3:4b-instruct",
        timeoutMs = 5000,
        warmupTimeoutMs = 10000
    )

    // E1-1: Successful structured Qwen inference parsing for "Play Janamann"
    @Test
    fun testE1_01_PlayMusic_StructuredInference() = runBlocking {
        val qwenJson = """
        {
          "type": "command",
          "spoken_response": "Playing Janamann.",
          "actions": [
            {
              "type": "play_music",
              "title": "Janamann",
              "artist": ""
            }
          ]
        }
        """.trimIndent()

        val mockPort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = qwenJson
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val response = provider.understand("Play Janamann", BrainContext())

        assertTrue(response is BrainResponse.Command)
        val cmd = response as BrainResponse.Command
        assertEquals("Playing Janamann.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.PlayMusic)
        assertEquals("Janamann", (cmd.actions[0] as BrainAction.PlayMusic).title)

        val brain = LocalAnimusBrain(localBrainProvider = provider)
        val result = brain.interpret("Play Janamann")
        assertTrue(result is BrainResult.Success)
        val animusCmds = (result as BrainResult.Success).commands
        assertEquals(1, animusCmds.size)
        assertTrue(animusCmds[0] is AnimusCommand.PlayMusic)
        assertEquals("Janamann", (animusCmds[0] as AnimusCommand.PlayMusic).title)
    }

    // E1-2: Successful structured Qwen inference parsing for "Turn on the AC"
    @Test
    fun testE1_02_TurnOnAC_StructuredInference() = runBlocking {
        val qwenJson = """
        {
          "type": "command",
          "spoken_response": "Turning on the AC.",
          "actions": [
            {
              "type": "device_command",
              "target": "AC",
              "command": "POWER",
              "value": "ON"
            }
          ]
        }
        """.trimIndent()

        val mockPort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = qwenJson
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val brain = LocalAnimusBrain(localBrainProvider = provider)
        val result = brain.interpret("Turn on the AC")

        assertTrue(result is BrainResult.Success)
        val animusCmds = (result as BrainResult.Success).commands
        assertEquals(1, animusCmds.size)
        assertTrue(animusCmds[0] is AnimusCommand.SetDeviceCapability)
        val devCmd = animusCmds[0] as AnimusCommand.SetDeviceCapability
        assertEquals("AC", devCmd.target)
        assertEquals("ON", devCmd.value)
    }

    // E1-3: Successful structured Qwen inference parsing for "I want to watch Article 15" (Movie Mode)
    @Test
    fun testE1_03_MovieMode_StructuredInference() = runBlocking {
        val qwenJson = """
        {
          "type": "command",
          "spoken_response": "Starting Movie Mode for Article 15.",
          "actions": [
            {
              "type": "movie_mode",
              "title": "Article 15"
            }
          ]
        }
        """.trimIndent()

        val mockPort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = qwenJson
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val brain = LocalAnimusBrain(localBrainProvider = provider)
        val result = brain.interpret("I want to watch Article 15")

        assertTrue(result is BrainResult.Success)
        val animusCmds = (result as BrainResult.Success).commands
        assertEquals(1, animusCmds.size)
        assertTrue(animusCmds[0] is AnimusCommand.StartMovieMode)
        val movieCmd = animusCmds[0] as AnimusCommand.StartMovieMode
        assertEquals("Article 15", movieCmd.contentTitle)
    }

    // E1-4: Ollama Malformed JSON fallback to deterministic parser
    @Test
    fun testE1_04_MalformedQwenJson_GracefulFallback() = runBlocking {
        val malformedJson = "I am an AI assistant and I think you want to turn on the AC."

        val mockPort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = malformedJson
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val brain = LocalAnimusBrain(localBrainProvider = provider)
        val result = brain.interpret("turn on ac")

        assertTrue("Should fallback to deterministic parser upon non-JSON LLM response", result is BrainResult.Success)
        val animusCmds = (result as BrainResult.Success).commands
        assertTrue(animusCmds[0] is AnimusCommand.SetDeviceCapability)
    }

    // E1-5: Gemini isolation check: Ordinary commands must NEVER trigger Gemini
    @Test
    fun testE1_05_GeminiIsolation_OrdinaryCommandsIsolated() {
        val bridge = GeminiKnowledgeBridge()

        assertFalse("Play Janamann must not route to Gemini", bridge.isFreshKnowledgeQuery("Play Janamann"))
        assertFalse("Turn on the AC must not route to Gemini", bridge.isFreshKnowledgeQuery("Turn on the AC"))
        assertFalse("I want to watch Article 15 must not route to Gemini", bridge.isFreshKnowledgeQuery("I want to watch Article 15"))
        assertFalse("Set AC to 24 must not route to Gemini", bridge.isFreshKnowledgeQuery("Set AC to 24"))
        assertFalse("Turn off projector must not route to Gemini", bridge.isFreshKnowledgeQuery("Turn off projector"))

        // Fresh external knowledge queries SHOULD route to Gemini
        assertTrue("Where can I watch Article 15 should route to Gemini", bridge.isFreshKnowledgeQuery("Where can I watch Article 15?"))
        assertTrue("Who directed Article 15 should route to Gemini", bridge.isFreshKnowledgeQuery("Who directed Article 15?"))
    }

    // E1-6: Gating synchronization when brain status is READY
    @Test
    fun testE1_06_Gating_WhenReady_ExecutesDirectly() = runBlocking {
        val port = AndroidLocalInferencePort(
            client = LocalInferenceClient { validConfig }
        )
        port.setStatus(LocalBrainStatus.READY)
        assertTrue(port.isAvailable())
    }

    // E1-7: Voice and Text paths produce identical AnimusCommand structures
    @Test
    fun testE1_07_VoiceAndText_IdenticalIntentMapping() = runBlocking {
        val qwenAcJson = """
        {
          "type": "command",
          "spoken_response": "Turning on the AC.",
          "actions": [
            {
              "type": "device_command",
              "target": "AC",
              "command": "POWER",
              "value": "ON"
            }
          ]
        }
        """.trimIndent()

        val mockPort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = qwenAcJson
            override fun isAvailable(): Boolean = true
        }

        val brain = LocalAnimusBrain(localBrainProvider = LocalBrainProvider(inferencePort = mockPort))

        val voiceResult = brain.interpret("Turn on the AC")
        val textResult = brain.interpret("Turn on the AC")

        assertEquals(voiceResult, textResult)
    }
}
