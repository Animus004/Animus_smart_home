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

class Phase5F5ParityAppBrainTestSuite {

    @Before
    fun setup() {
        AndroidSessionContextRepository.reset()
    }

    // 21. PersonalKnowledgeQueryWhatAreMyProjectsTest
    @Test
    fun `test LocalBrainProvider answers what are my projects`() = runBlocking {
        val provider = LocalBrainProvider()
        val p = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 24,
            activeProjects = listOf("Animus Smart Room")
        )
        val ctx = BrainContext(personalContext = p)
        val res = provider.understand("what are my projects", ctx)
        assertTrue(res is BrainResponse.Conversation)
        val conv = res as BrainResponse.Conversation
        assertTrue(conv.spokenResponse.contains("Animus Smart Room"))
    }

    // 22. PersonalKnowledgeQueryWhatPreferencesDoYouRememberTest
    @Test
    fun `test LocalBrainProvider answers what preferences do you remember`() = runBlocking {
        val provider = LocalBrainProvider()
        val p = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 23
        )
        val ctx = BrainContext(personalContext = p)
        val res = provider.understand("what preferences do you remember", ctx)
        assertTrue(res is BrainResponse.Conversation)
        val conv = res as BrainResponse.Conversation
        assertTrue(conv.spokenResponse.contains("23°C"))
        assertTrue(conv.spokenResponse.contains("LG SNC4R"))
    }

    // 23. PersonalKnowledgeRepositoryFlowEmissionTest
    @Test
    fun `test AndroidPersonalKnowledgeRepository emits updated list on save`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        val initialSize = repo.getKnowledgeFlow().first().size
        repo.saveKnowledge(Memory(content = "User preference dim light", category = MemoryCategory.PREFERENCE))
        val newSize = repo.getKnowledgeFlow().first().size
        assertEquals(initialSize + 1, newSize)
    }

    // 24. PersonalKnowledgeRepositoryFlowEmissionOnDeleteTest
    @Test
    fun `test AndroidPersonalKnowledgeRepository emits updated list on delete`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        val mem = Memory(id = "del-test-id", content = "Temporary memory", category = MemoryCategory.GENERAL)
        repo.saveKnowledge(mem)
        val countAfterSave = repo.getKnowledgeFlow().first().size

        repo.deleteKnowledge("del-test-id")
        val countAfterDel = repo.getKnowledgeFlow().first().size
        assertEquals(countAfterSave - 1, countAfterDel)
    }

    // 25. AnimusBrainEngineMemoryDeleteHandlingTest
    @Test
    fun `test AnimusBrainEngine executes memory deletion without hardware side-effects`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val mem = Memory(id = "mem-to-forget", content = "Old preference", category = MemoryCategory.PREFERENCE)
        memoryRepo.saveMemory(mem)

        val deleteProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Forgot", BrainAction.MemoryAction(MemoryActionType.DELETE, mem))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val engine = AnimusBrainEngine(modeController, deleteProvider, remote, memoryRepository = memoryRepo)

        val (res, cmds) = engine.processInput("forget that")
        assertTrue(res is BrainResponse.Command)
        assertEquals(0, cmds.size)
    }

    // 26. AnimusBrainEngineMemoryQueryHandlingTest
    @Test
    fun `test AnimusBrainEngine handles MemoryAction QUERY safely`() = runBlocking {
        val memoryRepo = AndroidMemoryRepository(context = null)
        val mem = Memory(content = "Query memory", category = MemoryCategory.PREFERENCE)

        val queryProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Queried", BrainAction.MemoryAction(MemoryActionType.QUERY, mem))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val engine = AnimusBrainEngine(modeController, queryProvider, remote, memoryRepository = memoryRepo)

        val (res, cmds) = engine.processInput("query memory")
        assertTrue(res is BrainResponse.Command)
        assertEquals(0, cmds.size)
    }

    // 27. AndroidPersonalKnowledgeRepositoryEmptyPrefsHandledTest
    @Test
    fun `test AndroidPersonalKnowledgeRepository handles empty context gracefully`() = runBlocking {
        val repo = AndroidPersonalKnowledgeRepository(context = null)
        assertNotNull(repo.getKnowledgeFlow().first())
    }

    // 28. TemperatureDoIUsuallyQueryTest
    @Test
    fun `test temperature do I usually keep the AC returns preferred temperature`() = runBlocking {
        val provider = LocalBrainProvider()
        val p = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 24
        )
        val ctx = BrainContext(personalContext = p)
        val res = provider.understand("what temperature do I usually keep the AC at", ctx)
        assertTrue(res is BrainResponse.Conversation)
        assertTrue((res as BrainResponse.Conversation).spokenResponse.contains("24 degrees"))
    }

    // 29. RememberCommandWithoutThatPrefixTest
    @Test
    fun `test remember command without that prefix parses correctly`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("remember my goal is to automate everything", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        val action = cmd.actions[0] as BrainAction.MemoryAction
        assertEquals(MemoryCategory.GOAL, action.memory.category)
    }

    // 30. ForgetCommandWithoutThatPrefixTest
    @Test
    fun `test forget command without that prefix parses correctly`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("forget my old temperature preference", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        val action = cmd.actions[0] as BrainAction.MemoryAction
        assertEquals(MemoryActionType.DELETE, action.actionType)
    }
}
