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
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class Phase5F2ExpandedAppBrainTestSuite {

    // 22. AndroidTaskRepositorySearchTest
    @Test
    fun `test AndroidTaskRepository search by title`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        repo.addTask(Task(id = "1", title = "Buy groceries"))
        repo.addTask(Task(id = "2", title = "Write thesis chapter"))

        val active = repo.getActiveTasks()
        val matching = active.filter { it.title.contains("groceries", ignoreCase = true) }
        assertEquals(1, matching.size)
        assertEquals("Buy groceries", matching[0].title)
    }

    // 23. AndroidMemoryRepositorySearchTest
    @Test
    fun `test AndroidMemoryRepository search by content keyword`() = runBlocking {
        val repo = AndroidMemoryRepository(context = null)
        repo.saveMemory(Memory(id = "1", content = "User enjoys AC at 24C"))
        repo.saveMemory(Memory(id = "2", content = "User enjoys coffee in morning"))

        val active = repo.getMemoriesFlow().first()
        val matching = active.filter { it.content.contains("coffee", ignoreCase = true) }
        assertEquals(1, matching.size)
        assertEquals("2", matching[0].id)
    }

    // 24. LocalBrainProviderResumeMusicCommandTest
    @Test
    fun `test LocalBrainProvider parse resume music command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("resume music", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.MusicControl)
        assertEquals(MusicActionType.RESUME, (cmd.actions[0] as BrainAction.MusicControl).action)
    }

    // 25. LocalBrainProviderNextTrackCommandTest
    @Test
    fun `test LocalBrainProvider parse next track command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("next song", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.MusicControl)
        assertEquals(MusicActionType.NEXT, (cmd.actions[0] as BrainAction.MusicControl).action)
    }

    // 26. LocalBrainProviderPreviousTrackCommandTest
    @Test
    fun `test LocalBrainProvider parse previous track command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("previous song", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.MusicControl)
        assertEquals(MusicActionType.PREVIOUS, (cmd.actions[0] as BrainAction.MusicControl).action)
    }

    // 27. LocalBrainProviderConnectBluetoothCommandTest
    @Test
    fun `test LocalBrainProvider parse connect bluetooth command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("connect to LG SNC4R", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.ConnectBluetooth)
    }

    // 28. LocalBrainProviderDisconnectBluetoothCommandTest
    @Test
    fun `test LocalBrainProvider parse disconnect bluetooth command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("disconnect bluetooth", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.DisconnectBluetooth)
    }

    // 29. LocalBrainProviderCancelScheduleCommandTest
    @Test
    fun `test LocalBrainProvider parse cancel scheduled timer command`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("cancel AC timer", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.CancelScheduledAction)
    }

    // 30. AnimusBrainEngineBlankInputHandledTest
    @Test
    fun `test AnimusBrainEngine returns Failure on blank input string`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        val (res, cmds) = engine.processInput("   ")
        assertTrue(res is BrainResponse.Failure)
        assertEquals(0, cmds.size)
    }

    // 31. AnimusBrainEngineCompleteTaskActionTest
    @Test
    fun `test AnimusBrainEngine executes TaskAction COMPLETE`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val task = Task(id = "complete-me-1", title = "Task 1")
        repo.addTask(task)

        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val completeActionProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Completed", BrainAction.TaskAction(TaskActionType.COMPLETE, task))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, completeActionProvider, remote, taskRepository = repo)

        val (res, _) = engine.processInput("done with Task 1")
        assertTrue(res is BrainResponse.Command)

        val active = repo.getActiveTasks()
        assertEquals(0, active.size)
    }

    // 32. AnimusBrainEngineCancelTaskActionTest
    @Test
    fun `test AnimusBrainEngine executes TaskAction CANCEL`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val task = Task(id = "cancel-me-1", title = "Task 2")
        repo.addTask(task)

        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val cancelActionProvider = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Command("Cancelled", BrainAction.TaskAction(TaskActionType.CANCEL, task))
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, cancelActionProvider, remote, taskRepository = repo)

        val (res, _) = engine.processInput("cancel Task 2")
        assertTrue(res is BrainResponse.Command)

        val active = repo.getActiveTasks()
        assertEquals(0, active.size)
    }

    // 33. LocalBrainProviderSetVolumeSpokenResponseTest
    @Test
    fun `test LocalBrainProvider spoken response on set volume`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("volume 65", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("Setting volume to 65%.", cmd.spokenResponse)
    }

    // 34. LocalBrainProviderPlayMusicSpokenResponseTest
    @Test
    fun `test LocalBrainProvider spoken response on play music`() = runBlocking {
        val provider = LocalBrainProvider()
        val res = provider.understand("play Kesariya", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("Playing Kesariya.", cmd.spokenResponse)
    }
}
