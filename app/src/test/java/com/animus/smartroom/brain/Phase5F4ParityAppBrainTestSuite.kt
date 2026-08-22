package com.animus.smartroom.brain

import com.animus.smartroom.brain.provider.GeminiBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainProvider
import com.animus.smartroom.brain.repository.AndroidMemoryRepository
import com.animus.smartroom.brain.repository.AndroidTaskRepository
import com.animus.smartroom.brain.session.AndroidSessionContextRepository
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.session.AssistantSessionContext
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class Phase5F4ParityAppBrainTestSuite {

    @Before
    fun setup() {
        AndroidSessionContextRepository.reset()
    }

    // 12. TurnHistoryAssitantSpokenResponseRecordedOnCommandTest
    @Test
    fun `test assistant spoken response recorded in turn history on command`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set AC to 22")
        val summary = AndroidSessionContextRepository.getSummary()
        assertTrue(summary.recentTurns.size >= 2)
        assertEquals("ASSISTANT", summary.recentTurns[1].speaker)
    }

    // 13. TurnHistoryAssitantSpokenResponseRecordedOnConversationTest
    @Test
    fun `test assistant spoken response recorded in turn history on conversation`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("what are my tasks today")
        val summary = AndroidSessionContextRepository.getSummary()
        assertTrue(summary.recentTurns.size >= 2)
        assertEquals("ASSISTANT", summary.recentTurns[1].speaker)
    }

    // 14. TurnHistoryAssistantQuestionRecordedOnClarificationTest
    @Test
    fun `test assistant question recorded in turn history on clarification`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Zara Zara")
        engine.processInput("set AC to 24")
        engine.processInput("turn it off")

        val summary = AndroidSessionContextRepository.getSummary()
        assertEquals("Do you mean the AC or the music?", summary.pendingClarification)
    }

    // 15. TaskActionUpdatesLastTaskInSessionTest
    @Test
    fun `test creating a task updates lastTaskId and lastTaskTitle in session`() = runBlocking {
        val taskRepo = AndroidTaskRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, taskRepository = taskRepo)

        engine.processInput("add task to inspect AC filters")
        val summary = AndroidSessionContextRepository.getSummary()
        assertEquals("inspect AC filters", summary.lastTaskTitle)
        assertNotNull(summary.lastTaskId)
    }

    // 16. ScheduleActionUpdatesLastScheduledActionInSessionTest
    @Test
    fun `test schedule command updates lastScheduledActionTarget in session`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("turn the ac off after 30 minutes")
        val summary = AndroidSessionContextRepository.getSummary()
        assertEquals("AC", summary.lastScheduledActionTarget)
        assertEquals(30, summary.lastScheduledActionDelayMinutes)
    }

    // 17. ResetSessionCommandAliasTest
    @Test
    fun `test reset session command clears context`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set AC to 24")
        engine.processInput("reset session")

        val summary = AndroidSessionContextRepository.getSummary()
        assertNull(summary.lastRequestedTemperature)
        assertTrue(summary.recentTurns.isEmpty())
    }

    // 18. MultiTurnTemperatureDecrementTest
    @Test
    fun `test multi-turn temperature adjustment Set AC 25 then Make it 22`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set AC to 25")
        val (res, cmds) = engine.processInput("make it 22")
        assertTrue(res is BrainResponse.Command)
        assertEquals(22, (cmds[0] as AnimusCommand.SetDeviceCapability).value)
        assertEquals(22, AndroidSessionContextRepository.getSummary().lastRequestedTemperature)
    }

    // 19. MultiTurnVolumeIncrementTest
    @Test
    fun `test multi-turn volume adjustment Play Kesariya then Make it louder`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Kesariya")
        val (res, cmds) = engine.processInput("make it louder")
        assertTrue(res is BrainResponse.Command)
        assertEquals(60, (cmds[0] as AnimusCommand.SetVolume).percentage)
    }

    // 20. MultiTurnVolumeQuieterTest
    @Test
    fun `test multi-turn volume adjustment Play Kesariya then Make it quieter`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Kesariya")
        val (res, cmds) = engine.processInput("make it quieter")
        assertTrue(res is BrainResponse.Command)
        assertEquals(40, (cmds[0] as AnimusCommand.SetVolume).percentage)
    }

    // 21. MultiTurnBareVolumeResolutionTest
    @Test
    fun `test multi-turn bare number 80 after music playback sets volume to 80`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Kesariya")
        val (res, cmds) = engine.processInput("80")
        assertTrue(res is BrainResponse.Command)
        assertEquals(80, (cmds[0] as AnimusCommand.SetVolume).percentage)
        assertEquals(80, AndroidSessionContextRepository.getSummary().lastRequestedVolume)
    }

    // 22. MultiTurnBareTempResolutionTest
    @Test
    fun `test multi-turn bare number 21 after AC command sets temp to 21`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set AC to 25")
        val (res, cmds) = engine.processInput("21")
        assertTrue(res is BrainResponse.Command)
        assertEquals(21, (cmds[0] as AnimusCommand.SetDeviceCapability).value)
        assertEquals(21, AndroidSessionContextRepository.getSummary().lastRequestedTemperature)
    }

    // 23. TaskActionCancelFollowUpTest
    @Test
    fun `test TaskAction CANCEL updates repository`() = runBlocking {
        val taskRepo = AndroidTaskRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val task = Task(id = "task-cancel-id", title = "Inspect filter")
        taskRepo.addTask(task)

        val cancelProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Cancelled", BrainAction.TaskAction(TaskActionType.CANCEL, task))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, cancelProvider, remote, taskRepository = taskRepo)

        engine.processInput("cancel task")
        val active = taskRepo.getActiveTasks()
        assertEquals(0, active.size)
    }

    // 24. MultiTurnScheduleUpdateMinutesTest
    @Test
    fun `test schedule timer follow up actually 45 minutes updates state`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("turn the ac off after 30 minutes")
        val (res, cmds) = engine.processInput("actually 45 minutes")
        assertTrue(res is BrainResponse.Command)
        assertEquals(45, (cmds[0] as AnimusCommand.ScheduleDeviceAction).delayMinutes)
    }

    // 25. MultiTurnScheduleUpdateHoursTest
    @Test
    fun `test schedule timer follow up make that 1 hour updates state`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("turn the ac off after 30 minutes")
        val (res, cmds) = engine.processInput("make that 1 hour")
        assertTrue(res is BrainResponse.Command)
        assertEquals(60, (cmds[0] as AnimusCommand.ScheduleDeviceAction).delayMinutes)
    }

    // 26. TurnHistoryMaxBoundsEnforcedInEngineTest
    @Test
    fun `test AnimusBrainEngine ensures session turn history stays bounded`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        for (i in 1..15) {
            engine.processInput("set volume to $i")
        }
        val summary = AndroidSessionContextRepository.getSummary()
        assertTrue(summary.recentTurns.size <= AssistantSessionContext.MAX_TURNS)
    }

    // 27. AmbiguousTurnItOffOptionsListTest
    @Test
    fun `test ambiguous turn it off includes options AC and Music`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Zara Zara")
        engine.processInput("set AC to 24")

        val (res, _) = engine.processInput("stop it")
        assertTrue(res is BrainResponse.Clarification)
        val clar = res as BrainResponse.Clarification
        assertTrue(clar.options.contains("AC"))
        assertTrue(clar.options.contains("Music"))
    }

    // 28. NullVoiceOutputSafeHandlingTest
    @Test
    fun `test AnimusBrainEngine handles null voiceOutputPort safely`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote, voiceOutputPort = null)

        val (res, _) = engine.processInput("play Zara Zara")
        assertTrue(res is BrainResponse.Command)
    }

    // 29. PlayMusicFollowUpTrackPreservedTest
    @Test
    fun `test PlayMusic updates lastActiveTrack in session`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Ramta Jogi")
        assertEquals("Ramta Jogi", AndroidSessionContextRepository.getSummary().lastActiveTrack)
    }

    // 30. SetVolumeFollowUpVolumePreservedTest
    @Test
    fun `test SetVolume updates lastRequestedVolume in session`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set volume to 65")
        assertEquals(65, AndroidSessionContextRepository.getSummary().lastRequestedVolume)
    }

    // 31. SetAcTempFollowUpTempPreservedTest
    @Test
    fun `test SetAcTemp updates lastRequestedTemperature in session`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set AC to 23")
        assertEquals(23, AndroidSessionContextRepository.getSummary().lastRequestedTemperature)
        assertEquals("AC", AndroidSessionContextRepository.getSummary().lastActiveDevice)
    }

    // 32. DisconnectedLocalBrainVoiceSpokenTest
    @Test
    fun `test disconnected local brain speaks offline notification and does not corrupt session`() = runBlocking {
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

        val (res, cmds) = engine.processInput("turn on ac")
        assertTrue(res is BrainResponse.Failure)
        assertEquals(0, cmds.size)
        assertEquals("Your local brain is currently offline.", spoken)
    }
}
