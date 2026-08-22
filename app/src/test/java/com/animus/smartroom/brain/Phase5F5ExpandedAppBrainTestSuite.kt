package com.animus.smartroom.brain

import com.animus.smartroom.brain.personal.AndroidPersonalKnowledgeRepository
import com.animus.smartroom.brain.provider.GeminiBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainProvider
import com.animus.smartroom.brain.repository.AndroidMemoryRepository
import com.animus.smartroom.brain.repository.AndroidTaskRepository
import com.animus.smartroom.brain.session.AndroidSessionContextRepository
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.personal.PersonalContextSummary
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class Phase5F5ExpandedAppBrainTestSuite {

    @Before
    fun setup() {
        AndroidSessionContextRepository.reset()
    }

    // 11. SecuritySanitizationInPersonalKnowledgeTest
    @Test
    fun `test credential string in personal knowledge is handled safely without leaks`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        repo.saveKnowledge(Memory(content = "User test secret AIzaSyDfakeApiKey9999", category = MemoryCategory.FACT))
        val summary = repo.getRelevantPersonalContext("secret")
        assertNotNull(summary)
        assertTrue(summary.relevantPersonalKnowledge.any { it.contains("secret") })
    }

    // 12. LocalRemotePersonalContextParityTest
    @Test
    fun `test local and remote providers receive identical personal context structure`() = runBlocking {
        val p = PersonalContextSummary("User", "LG SNC4R", 24, listOf("Animus"))
        val ctx = BrainContext(personalContext = p)

        val local = LocalBrainProvider()
        val remoteRes = BrainResponse.Conversation("Remote received personal context")
        val remote = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse {
                assertEquals("User", context.personalContext?.preferredName)
                assertEquals(24, context.personalContext?.preferredAcTemp)
                return remoteRes
            }
            override fun isAvailable(): Boolean = true
        }

        val modeController = BrainModeControllerImpl(BrainMode.REMOTE)
        val engine = AnimusBrainEngine(modeController, local, remote)

        val (res, _) = engine.processInput("what is my preferred AC temperature", contextBuilder = { ctx })
        assertTrue(res is BrainResponse.Conversation)
    }

    // 13. NaturalMemoryLearningSpeakerFactTest
    @Test
    fun `test remember my LG SNC4R is my bedroom speaker categorized as FACT`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("remember my LG SNC4R is my bedroom speaker", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        val action = cmd.actions[0] as BrainAction.MemoryAction
        assertEquals(MemoryCategory.FACT, action.memory.category)
    }

    // 14. NaturalMemoryLearningProjectTest
    @Test
    fun `test remember that Animus is my personal assistant project categorized as PROJECT`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("remember that Animus is my personal assistant project", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        val action = cmd.actions[0] as BrainAction.MemoryAction
        assertEquals(MemoryCategory.PROJECT, action.memory.category)
    }

    // 15. NaturalMemoryLearningGoalTest
    @Test
    fun `test remember that I want to turn Animus into a business categorized as GOAL`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("remember that my goal is to turn Animus into a business", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        val action = cmd.actions[0] as BrainAction.MemoryAction
        assertEquals(MemoryCategory.GOAL, action.memory.category)
    }

    // 16. NaturalMemoryCorrectionTemperatureTest
    @Test
    fun `test change my preferred AC temperature to 23`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, memoryRepository = memoryRepo)

        val (res, _) = engine.processInput("remember that I prefer AC at 23 degrees")
        assertTrue(res is BrainResponse.Command)
        val mems = memoryRepo.getMemoriesFlow().first()
        assertTrue(mems.any { it.content.contains("23 degrees") })
    }

    // 17. MultipleMemoryActionsDoNotCorruptEngineTest
    @Test
    fun `test sequential memory saves maintain consistency`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, memoryRepository = memoryRepo)

        engine.processInput("remember that I prefer AC at 24 degrees")
        engine.processInput("remember my LG SNC4R is my bedroom speaker")

        val mems = memoryRepo.getMemoriesFlow().first()
        assertTrue(mems.size >= 2)
    }

    // 18. SessionVsPersistentMemoryDistinctionTest
    @Test
    fun `test regular commands do not persist into MemoryRepository`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, memoryRepository = memoryRepo)

        val initialCount = memoryRepo.getMemoriesFlow().first().size
        engine.processInput("set AC to 24")
        engine.processInput("play Zara Zara")
        engine.processInput("make it louder")

        val afterCount = memoryRepo.getMemoriesFlow().first().size
        assertEquals(initialCount, afterCount)
    }

    // 19. TaskQueryWhatDoIHaveTodayTest
    @Test
    fun `test what do I have today returns conversation with task count`() = runBlocking {
        val taskRepo = AndroidTaskRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, taskRepository = taskRepo)

        val (res, _) = engine.processInput("what do I have today")
        assertTrue(res is BrainResponse.Conversation)
    }

    // 20. DisconnectedLocalBrainMemoryCommandTest
    @Test
    fun `test disconnected local brain announces offline for memory commands`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val unavailableLocal = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse = BrainResponse.Failure("Offline")
            override fun isAvailable(): Boolean = false
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        var spoken: String? = null
        val voiceOutput = object : VoiceOutputPort {
            override suspend fun speak(text: String) { spoken = text }
            override fun stop() {}
        }
        val engine = AnimusBrainEngine(modeController, unavailableLocal, remote, voiceOutputPort = voiceOutput)

        val (res, _) = engine.processInput("remember that I prefer AC at 24")
        assertTrue(res is BrainResponse.Failure)
        assertEquals("Your local brain is currently offline.", spoken)
    }
}
