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

class Phase5F5AppBrainTestSuite {

    @Before
    fun setup() {
        AndroidSessionContextRepository.reset()
    }

    // 1. PersonalKnowledgeRepositoryBootstrapTest
    @Test
    fun `test AndroidPersonalKnowledgeRepository loads bootstrap memories initially`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        val all = repo.listAllKnowledge()
        assertTrue(all.isNotEmpty())
        assertTrue(all.any { it.category == MemoryCategory.PREFERENCE })
        assertTrue(all.any { it.category == MemoryCategory.PROJECT })
    }

    // 2. PersonalKnowledgeRepositorySaveAndDeleteTest
    @Test
    fun `test AndroidPersonalKnowledgeRepository saves and deletes memory`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        val mem = Memory(id = "mem-test-1", content = "User likes jazz music", category = MemoryCategory.PREFERENCE)
        repo.saveKnowledge(mem)

        val relevant = repo.getRelevantPersonalContext("jazz")
        assertTrue(relevant.relevantPersonalKnowledge.any { it.contains("jazz") })

        val deleted = repo.deleteKnowledge("mem-test-1")
        assertTrue(deleted)
        val after = repo.getRelevantPersonalContext("jazz")
        assertFalse(after.relevantPersonalKnowledge.any { it.contains("jazz") })
    }

    // 3. NaturalMemoryLearningRuleTest
    @Test
    fun `test LocalBrainProvider parses remember that into MemoryAction CREATE`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("remember that I prefer AC at 24 degrees", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("I'll remember that I prefer AC at 24 degrees.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.MemoryAction)
        assertEquals(MemoryActionType.CREATE, (cmd.actions[0] as BrainAction.MemoryAction).actionType)
    }

    // 4. NaturalMemoryForgettingRuleTest
    @Test
    fun `test LocalBrainProvider parses forget that into MemoryAction DELETE`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("forget that I prefer 24 degrees", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("I've forgotten that information.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.MemoryAction)
        assertEquals(MemoryActionType.DELETE, (cmd.actions[0] as BrainAction.MemoryAction).actionType)
    }

    // 5. PersonalKnowledgeQueryWhatDoYouKnowAboutMeTest
    @Test
    fun `test LocalBrainProvider answers what do you know about me`() = runBlocking {
        val provider = LocalBrainProvider()
        val p = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 24,
            activeProjects = listOf("Animus")
        )
        val ctx = BrainContext(personalContext = p)
        val res = provider.understand("what do you know about me", ctx)
        assertTrue(res is BrainResponse.Conversation)
        val conv = res as BrainResponse.Conversation
        assertTrue(conv.spokenResponse.contains("24°C"))
        assertTrue(conv.spokenResponse.contains("LG SNC4R"))
        assertTrue(conv.spokenResponse.contains("Animus"))
    }

    // 6. PersonalKnowledgeQuerySpeakerTest
    @Test
    fun `test LocalBrainProvider answers which speaker do I use in bedroom`() = runBlocking {
        val provider = LocalBrainProvider()
        val p = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 24
        )
        val ctx = BrainContext(personalContext = p)
        val res = provider.understand("which speaker do I use in the bedroom", ctx)
        assertTrue(res is BrainResponse.Conversation)
        val conv = res as BrainResponse.Conversation
        assertTrue(conv.spokenResponse.contains("LG SNC4R"))
    }

    // 7. PersonalKnowledgeQueryPreferredAcTempTest
    @Test
    fun `test LocalBrainProvider answers what is my preferred AC temperature`() = runBlocking {
        val provider = LocalBrainProvider()
        val p = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 23
        )
        val ctx = BrainContext(personalContext = p)
        val res = provider.understand("what is my preferred AC temperature", ctx)
        assertTrue(res is BrainResponse.Conversation)
        val conv = res as BrainResponse.Conversation
        assertTrue(conv.spokenResponse.contains("23 degrees"))
    }

    // 8. PersonalKnowledgeEngineIntegrationTest
    @Test
    fun `test AnimusBrainEngine passes remember that through memory repository`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, memoryRepository = memoryRepo)

        val (res, cmds) = engine.processInput("remember that I like 24 degrees")
        assertTrue(res is BrainResponse.Command)
        assertEquals(0, cmds.size) // Pure memory action, zero hardware commands
        val saved = memoryRepo.getMemoriesFlow().first()
        assertTrue(saved.any { it.content.contains("24 degrees") })
    }

    // 9. PersonalKnowledgeDeleteMatchingTest
    @Test
    fun `test AndroidPersonalKnowledgeRepository deleteMatching removes target entries`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        repo.saveKnowledge(Memory(content = "User preference old temp 21C", category = MemoryCategory.PREFERENCE))
        val count = repo.deleteKnowledgeMatching("21C")
        assertTrue(count >= 1)
        val after = repo.listAllKnowledge()
        assertFalse(after.any { it.content.contains("21C") })
    }

    // 10. IrrelevantMemoriesNotInjectedOnMusicPlaybackTest
    @Test
    fun `test music playback query produces PlayMusic without memory injection corruption`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        val (res, cmds) = engine.processInput("play Zara Zara")
        assertTrue(res is BrainResponse.Command)
        assertEquals(1, cmds.size)
        assertTrue(cmds[0] is AnimusCommand.PlayMusic)
    }
}
