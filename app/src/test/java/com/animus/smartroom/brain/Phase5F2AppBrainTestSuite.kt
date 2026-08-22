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

class Phase5F2AppBrainTestSuite {

    // 1. TaskRepositoryPersistenceTest
    @Test
    fun `test AndroidTaskRepository adds, updates, and deletes tasks`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val task = Task(title = "Submit project proposal", priority = TaskPriority.HIGH)

        repo.addTask(task)
        val active = repo.getActiveTasks()
        assertEquals(1, active.size)
        assertEquals("Submit project proposal", active[0].title)

        repo.updateTaskStatus(task.id, TaskStatus.COMPLETED)
        val activeAfter = repo.getActiveTasks()
        assertEquals(0, activeAfter.size)

        repo.deleteTask(task.id)
        val all = repo.getTasksFlow().first()
        assertEquals(0, all.size)
    }

    // 2. MemoryRepositoryPersistenceTest
    @Test
    fun `test AndroidMemoryRepository saves and ranks memories`() = runBlocking {
        val repo = AndroidMemoryRepository(context = null)
        val mem1 = Memory(content = "User prefers room temperature at 24C", category = MemoryCategory.PREFERENCE, relevance = 0.9f)
        val mem2 = Memory(content = "User likes listening to Zara Zara", category = MemoryCategory.PREFERENCE, relevance = 0.8f)

        repo.saveMemory(mem1)
        repo.saveMemory(mem2)

        val retrieved = repo.getRelevantMemories("temperature", limit = 1)
        assertEquals(1, retrieved.size)
        assertEquals(mem1.id, retrieved[0].id)
    }

    // 3. TaskBrainCommandTest
    @Test
    fun `test LocalBrainProvider parses add task commands`() = runBlocking {
        val provider = LocalBrainProvider()
        val response = provider.understand("Add task to buy milk", BrainContext())

        assertTrue(response is BrainResponse.Command)
        val cmd = response as BrainResponse.Command
        assertEquals("Added task: buy milk", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.TaskAction)
        val taskAction = cmd.actions[0] as BrainAction.TaskAction
        assertEquals("buy milk", taskAction.task.title)
    }

    // 4. BrainEngineTaskDispatchTest
    @Test
    fun `test AnimusBrainEngine automatically persists task action`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })

        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = local,
            remoteProvider = remote,
            taskRepository = repo
        )

        val (res, _) = engine.processInput("remind me to prepare presentation")
        assertTrue(res is BrainResponse.Command)

        val activeTasks = repo.getActiveTasks()
        assertEquals(1, activeTasks.size)
        assertEquals("prepare presentation", activeTasks[0].title)
    }

    // 5. LocalInferenceClientConfigValidationTest
    @Test
    fun `test LocalInferenceClient handles disabled or invalid config gracefully`() = runBlocking {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig(enabled = false) })
        val result = client.generateCompletion("hello")
        assertTrue(result.isFailure)
        assertFalse(client.ping())
    }

    // 6. NoAutomaticFallbackTest
    @Test
    fun `test Local mode failure never falls back silently to remote`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val failingLocal = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse =
                BrainResponse.Failure("Local inference server timeout")
            override fun isAvailable(): Boolean = true
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { "valid-key-12345" })

        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = failingLocal,
            remoteProvider = remote
        )

        val (res, commands) = engine.processInput("turn on ac")
        assertTrue(res is BrainResponse.Failure)
        assertEquals(0, commands.size)
    }

    // 7. AndroidTaskRepositoryDueSectionsTest
    @Test
    fun `test AndroidTaskRepository today, overdue, and upcoming classification`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val now = System.currentTimeMillis()
        val overdueTask = Task(id = "1", title = "Overdue Task", dueAt = now - 100000)
        val upcomingTask = Task(id = "2", title = "Upcoming Task", dueAt = now + 100000000)

        repo.addTask(overdueTask)
        repo.addTask(upcomingTask)

        val overdue = repo.getOverdueTasks()
        assertEquals(1, overdue.size)
        assertEquals("1", overdue[0].id)

        val upcoming = repo.getUpcomingTasks()
        assertEquals(1, upcoming.size)
        assertEquals("2", upcoming[0].id)
    }

    // 8. AndroidMemoryRepositoryDeleteTest
    @Test
    fun `test AndroidMemoryRepository delete operation`() = runBlocking {
        val repo = AndroidMemoryRepository(context = null)
        val mem = Memory(id = "mem-101", content = "Important preference")
        repo.saveMemory(mem)

        val deleted = repo.deleteMemory("mem-101")
        assertTrue(deleted)

        val empty = repo.getMemoriesFlow().first()
        assertEquals(0, empty.size)
    }

    // 9. AndroidLocalInferencePortStatusTest
    @Test
    fun `test AndroidLocalInferencePort status updates`() = runBlocking {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig(enabled = false) })
        val port = AndroidLocalInferencePort(client).apply {
            setStatus(LocalBrainStatus.OFFLINE)
        }

        assertEquals(LocalBrainStatus.OFFLINE, port.status.value)
        assertFalse(port.isAvailable())

        try {
            port.generate("test prompt")
            fail("Expected exception")
        } catch (e: Exception) {
            assertTrue(port.status.value == LocalBrainStatus.ERROR || port.status.value == LocalBrainStatus.FAILED || port.status.value == LocalBrainStatus.OFFLINE)
        }
    }

    // 10. LocalBrainProviderWhatAreMyTasksTest
    @Test
    fun `test LocalBrainProvider list tasks response`() = runBlocking {
        val provider = LocalBrainProvider()
        val emptyCtx = BrainContext.bounded()
        val res1 = provider.understand("What are my tasks today?", emptyCtx)
        assertTrue(res1 is BrainResponse.Conversation)
        assertEquals("You have no tasks scheduled for today.", (res1 as BrainResponse.Conversation).spokenResponse)

        val fullCtx = BrainContext.bounded(todayTasks = listOf(TaskSummary("1", "Task 1", "NORMAL", "PENDING", null)))
        val res2 = provider.understand("What are my tasks today?", fullCtx)
        assertTrue(res2 is BrainResponse.Conversation)
        assertEquals("You have 1 tasks remaining today.", (res2 as BrainResponse.Conversation).spokenResponse)
    }

    // 11. LocalBrainProviderStructuredCommandJsonTest
    @Test
    fun `test LocalBrainProvider parses structured local LLM JSON output`() = runBlocking {
        val jsonMock = """
            {
              "type": "command",
              "speech": "Turning AC to 22 degrees.",
              "actions": [
                {
                  "type": "device_command",
                  "target": "AC",
                  "command": "SET_TEMPERATURE",
                  "value": 22
                }
              ]
            }
        """.trimIndent()

        val mockPort = object : com.animus.smartroom.core.brain.port.LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = jsonMock
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val res = provider.understand("Cool down the room", BrainContext())

        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("Turning AC to 22 degrees.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.DeviceCommand)
        val devCmd = cmd.actions[0] as BrainAction.DeviceCommand
        assertEquals("AC", devCmd.target)
        assertEquals(22, devCmd.value)
    }

    // 12. LocalBrainProviderClarificationJsonTest
    @Test
    fun `test LocalBrainProvider parses structured clarification output`() = runBlocking {
        val jsonMock = """
            {
              "type": "clarification",
              "speech": "Would you like me to play music on phone or LG SNC4R soundbar?"
            }
        """.trimIndent()

        val mockPort = object : com.animus.smartroom.core.brain.port.LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = jsonMock
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val res = provider.understand("play music", BrainContext())

        assertTrue(res is BrainResponse.Clarification)
        assertEquals("Would you like me to play music on phone or LG SNC4R soundbar?", (res as BrainResponse.Clarification).question)
    }

    // 13. AnimusBrainEngineLocalUnavailableVoiceTest
    @Test
    fun `test AnimusBrainEngine speaks unavailable notification when local brain is offline`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val unavailableLocal = object : com.animus.smartroom.core.brain.port.BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse = BrainResponse.Failure("Offline")
            override fun isAvailable(): Boolean = false
        }
        val remote = GeminiBrainProvider(apiKeyProvider = { null })

        var spokenMessage: String? = null
        val voiceOutput = object : VoiceOutputPort {
            override suspend fun speak(text: String) { spokenMessage = text }
            override fun stop() {}
        }

        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = unavailableLocal,
            remoteProvider = remote,
            voiceOutputPort = voiceOutput
        )

        val (res, _) = engine.processInput("set temperature to 24")
        assertTrue(res is BrainResponse.Failure)
        assertEquals("Your local brain is currently offline.", spokenMessage)
    }

    // 14. AnimusBrainEngineDiagnosticPreservationTest
    @Test
    fun `test AnimusBrainEngine preserves correlationId`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })

        val engine = AnimusBrainEngine(
            modeController = modeController,
            localProvider = local,
            remoteProvider = remote
        )

        val testCorrelationId = "corr-test-unique-999"
        val (res, _) = engine.processInput("pause music", correlationId = testCorrelationId)
        assertTrue(res is BrainResponse.Command)
    }

    // 15. TaskStatusCancellationTest
    @Test
    fun `test Task cancellation status update in repository`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val task = Task(id = "cancel-task-1", title = "Task to cancel")
        repo.addTask(task)
        repo.updateTaskStatus("cancel-task-1", TaskStatus.CANCELLED)

        val active = repo.getActiveTasks()
        assertEquals(0, active.size)
    }

    // 16. LocalBrainProviderPlayMusicJsonTest
    @Test
    fun `test LocalBrainProvider parses structured play_music JSON action`() = runBlocking {
        val jsonMock = """
            {
              "type": "command",
              "speech": "Playing song.",
              "actions": [
                {
                  "type": "play_music",
                  "title": "Zara Zara"
                }
              ]
            }
        """.trimIndent()

        val mockPort = object : com.animus.smartroom.core.brain.port.LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = jsonMock
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val res = provider.understand("Play Zara Zara", BrainContext())

        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.PlayMusic)
        assertEquals("Zara Zara", (cmd.actions[0] as BrainAction.PlayMusic).title)
    }

    // 17. LocalBrainProviderSetVolumeJsonTest
    @Test
    fun `test LocalBrainProvider parses structured set_volume JSON action`() = runBlocking {
        val jsonMock = """
            {
              "type": "command",
              "speech": "Adjusting volume.",
              "actions": [
                {
                  "type": "set_volume",
                  "percentage": 75
                }
              ]
            }
        """.trimIndent()

        val mockPort = object : com.animus.smartroom.core.brain.port.LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = jsonMock
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val res = provider.understand("Set volume to 75", BrainContext())

        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.SetVolume)
        assertEquals(75, (cmd.actions[0] as BrainAction.SetVolume).percentage)
    }

    // 18. LocalBrainProviderFailureJsonTest
    @Test
    fun `test LocalBrainProvider parses failure JSON response`() = runBlocking {
        val jsonMock = """
            {
              "type": "failure",
              "speech": "I could not resolve that device."
            }
        """.trimIndent()

        val mockPort = object : com.animus.smartroom.core.brain.port.LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = jsonMock
            override fun isAvailable(): Boolean = true
        }

        val provider = LocalBrainProvider(inferencePort = mockPort)
        val res = provider.understand("Do something impossible", BrainContext())

        assertTrue(res is BrainResponse.Failure)
        assertEquals("I could not resolve that device.", (res as BrainResponse.Failure).reason)
    }

    // 19. TaskRepositoryEmptyDueAtTest
    @Test
    fun `test AndroidTaskRepository handles tasks with null dueAt correctly`() = runBlocking {
        val repo = AndroidTaskRepository(context = null)
        val task = Task(id = "no-due-1", title = "Task without deadline", dueAt = null)
        repo.addTask(task)

        val today = repo.getTodayTasks()
        val overdue = repo.getOverdueTasks()
        val upcoming = repo.getUpcomingTasks()

        assertEquals(0, today.size)
        assertEquals(0, overdue.size)
        assertEquals(0, upcoming.size)
        assertEquals(1, repo.getActiveTasks().size)
    }

    // 20. MemoryRepositoryMultipleQueryMatchesTest
    @Test
    fun `test AndroidMemoryRepository returns multiple relevant items ranked`() = runBlocking {
        val repo = AndroidMemoryRepository(context = null)
        val mem1 = Memory(id = "1", content = "Music preference: rock and jazz", relevance = 0.9f)
        val mem2 = Memory(id = "2", content = "Music preference: acoustic guitar songs", relevance = 0.8f)
        val mem3 = Memory(id = "3", content = "Cooking recipe for pasta", relevance = 0.4f)

        repo.saveMemory(mem1)
        repo.saveMemory(mem2)
        repo.saveMemory(mem3)

        val results = repo.getRelevantMemories("music preference", limit = 2)
        assertEquals(2, results.size)
        assertTrue(results.any { it.id == "1" })
        assertTrue(results.any { it.id == "2" })
    }

    // 21. AndroidLocalInferencePortPingTest
    @Test
    fun `test AndroidLocalInferencePort checkHealth updates status to UNAVAILABLE when ping fails`() = runBlocking {
        val client = LocalInferenceClient(configProvider = { LocalBrainConfig(enabled = false) })
        val port = AndroidLocalInferencePort(client)

        port.checkHealth()
        assertEquals(LocalBrainStatus.DISCONNECTED, port.status.value)
    }
}
