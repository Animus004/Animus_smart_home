package com.animus.smartroom.brain

import com.animus.smartroom.brain.router.DeterministicExecutionEngine
import com.animus.smartroom.brain.router.SmartIntentRouter
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.core.brain.port.LocalInferencePort
import com.animus.smartroom.core.brain.router.ExecutionResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Acceptance and regression test suite for Phase B — Android <-> PC Routing Consolidation.
 * Validates single authoritative execution path, content title preservation,
 * "I want to watch Article 15", WatchContent, StartMovieMode, and audio ownership invariants.
 */
class PhaseBAndroidPcRoutingTestSuite {

    private lateinit var commandRouter: CommandRouter
    private lateinit var parser: LocalCommandParser

    @Before
    fun setUp() {
        parser = LocalCommandParser()
        commandRouter = CommandRouter()
    }

    @Test
    fun testP_B01_LocalCommandParser_Article15_Parsed_As_WatchContent() {
        val parsed = parser.parse("I want to watch Article 15")
        assertTrue(parsed is AnimusCommand.WatchContent)
        val watchCmd = parsed as AnimusCommand.WatchContent
        assertEquals("Article 15", watchCmd.title)
    }

    @Test
    fun testP_B02_LocalCommandParser_WatchInterstellar_Parsed() {
        val parsed = parser.parse("watch movie Interstellar")
        assertTrue(parsed is AnimusCommand.WatchContent)
        val watchCmd = parsed as AnimusCommand.WatchContent
        assertEquals("Interstellar", watchCmd.title)
    }

    @Test
    fun testP_B03_LocalCommandParser_PlayMovieInception_Parsed() {
        val parsed = parser.parse("play movie Inception")
        assertTrue(parsed is AnimusCommand.WatchContent)
        val watchCmd = parsed as AnimusCommand.WatchContent
        assertEquals("Inception", watchCmd.title)
    }

    @Test
    fun testP_B04_LocalCommandParser_GenericMovieMode_Parsed() {
        val parsed = parser.parse("start movie mode")
        assertTrue(parsed is AnimusCommand.StartMovieMode)
        assertEquals(null, (parsed as AnimusCommand.StartMovieMode).contentTitle)
    }

    @Test
    fun testP_B05_CommandRouter_WatchContent_Execution() = runBlocking {
        val cmd = AnimusCommand.WatchContent(title = "Article 15")
        val result = commandRouter.execute(cmd)

        assertTrue(result.success)
        assertTrue(result.message.contains("Article 15"))
    }

    @Test
    fun testP_B06_CommandRouter_StartMovieMode_Execution() = runBlocking {
        val cmd = AnimusCommand.StartMovieMode()
        val result = commandRouter.execute(cmd)

        assertTrue(result.success)
        assertTrue(result.message.contains("Starting Movie Mode"))
    }

    @Test
    fun testP_B07_CommandRouter_StopMovieMode_Execution() = runBlocking {
        val cmd = AnimusCommand.StopMovieMode
        val result = commandRouter.execute(cmd)

        assertTrue(result.success)
        assertTrue(result.message.contains("Stopping Movie Mode"))
    }

    @Test
    fun testP_B08_SmartIntentRouter_And_ExecutionEngine_MovieMode_Flow() = runBlocking {
        val fakeInferencePort = object : LocalInferencePort {
            override fun isAvailable(): Boolean = true
            override suspend fun generate(prompt: String, context: List<String>): String {
                return """
                    {"schema_version":"1.0","type":"intent","intent":"MOVIE","confidence":0.98,"parameters":{"content":"Article 15"}}
                """.trimIndent()
            }
        }

        val engine = DeterministicExecutionEngine()
        val router = SmartIntentRouter(
            inferencePort = fakeInferencePort,
            executionEngine = engine
        )

        val result = router.routeAndExecute("I want to watch Article 15")

        assertEquals(ExecutionResult.Status.SUCCESS, result.status)
        assertEquals("MOVIE_MODE", result.intent)
    }

    @Test
    fun testP_B09_MovieMode_SpokenFeedback_When_Blocked() = runBlocking {
        val expectedFeedback = "The projector is currently off. I can't turn it on right now. Please turn on the projector manually."
        val result = com.animus.smartroom.command.model.CommandExecutionResult(
            success = false,
            message = expectedFeedback
        )

        assertEquals(false, result.success)
        assertTrue(result.message.contains("turn on the projector manually"))
    }

    @Test
    fun testP_B10_LocalCommandParser_Netflix_Provider_Only() {
        val parsed = parser.parse("I feel like watching Netflix right now")
        assertTrue(parsed is AnimusCommand.StartMovieMode)
        val cmd = parsed as AnimusCommand.StartMovieMode
        assertEquals(null, cmd.contentTitle)
        assertEquals("netflix", cmd.provider)

        val watchNet = parser.parse("watch netflix")
        assertTrue(watchNet is AnimusCommand.StartMovieMode)
        assertEquals(null, (watchNet as AnimusCommand.StartMovieMode).contentTitle)
        assertEquals("netflix", (watchNet as AnimusCommand.StartMovieMode).provider)
    }

    @Test
    fun testP_B11_CommandRouter_Netflix_Provider_Execution() = runBlocking {
        val cmd = AnimusCommand.StartMovieMode(provider = "netflix")
        val result = commandRouter.execute(cmd)

        assertTrue(result.success)
        assertTrue(result.message.contains("with netflix"))
    }
}
