package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.prompt.LocalSystemPromptBuilder
import com.animus.smartroom.core.brain.validator.BrainResponseValidator
import com.animus.smartroom.core.brain.validator.ValidationResult
import org.junit.Assert.*
import org.junit.Test

class Phase5F3CoreBrainTestSuite {

    // 1. PromptGenerationStructureTest
    @Test
    fun `test LocalSystemPromptBuilder includes context and rules`() {
        val ctx = BrainContext.bounded(
            todayTasks = listOf(TaskSummary("1", "Check AC filter", "HIGH", "PENDING", null)),
            relevantMemories = listOf(Memory(content = "User prefers AC at 24C")),
            userPreferences = UserPreferences(preferredTemperatureCelsius = 24)
        )

        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Animus Local Brain"))
        assertTrue(prompt.contains("24°C"))
        assertTrue(prompt.contains("Check AC filter"))
        assertTrue(prompt.contains("User prefers AC at 24C"))
        assertTrue(prompt.contains("ALLOWED OUTPUT SCHEMAS"))
    }

    // 2. PromptBoundedLengthTest
    @Test
    fun `test LocalSystemPromptBuilder stays bounded with large number of tasks and memories`() {
        val manyTasks = (1..50).map { TaskSummary("id-$it", "Task title number $it", "NORMAL", "PENDING", null) }
        val manyMemories = (1..50).map { Memory(content = "User memory description item number $it") }

        val ctx = BrainContext.bounded(
            todayTasks = manyTasks,
            relevantMemories = manyMemories
        )

        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.length < 5000)
    }

    // 3. PromptZeroSecretsTest
    @Test
    fun `test LocalSystemPromptBuilder contains zero credentials`() {
        val ctx = BrainContext.bounded(
            deviceSummaries = listOf(DeviceSummary("Living Room AC", "AC", true)),
            currentMusicSummary = MusicSummary("Zara Zara", true, "LG SNC4R", true)
        )
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertFalse(prompt.contains("AIza"))
        assertFalse(prompt.contains("Bearer"))
        assertFalse(prompt.contains("secret"))
        assertFalse(prompt.contains("client_secret"))
    }

    // 4. MemoryActionValidationTest
    @Test
    fun `test MemoryAction creation and validation`() {
        val validMemory = Memory(content = "User prefers AC at 23 degrees", category = MemoryCategory.PREFERENCE)
        val action = BrainAction.MemoryAction(
            MemoryActionType.CREATE,
            validMemory
        )
        assertTrue(BrainResponseValidator.validateAction(action) is ValidationResult.Valid)
    }

    // 5. MemoryActionBlankContentRejectedValidationTest
    @Test
    fun `test MemoryAction with blank content is rejected by validator`() {
        val blankMemory = Memory(content = "   ")
        val action = BrainAction.MemoryAction(
            MemoryActionType.CREATE,
            blankMemory
        )
        assertTrue(BrainResponseValidator.validateAction(action) is ValidationResult.Invalid)
    }

    // 6. MemoryActionTypeValuesTest
    @Test
    fun `test MemoryActionType enum coverage`() {
        val values = MemoryActionType.values()
        assertEquals(3, values.size)
        assertTrue(values.contains(MemoryActionType.CREATE))
        assertTrue(values.contains(MemoryActionType.DELETE))
        assertTrue(values.contains(MemoryActionType.QUERY))
    }

    // 7. PromptInjectionDefenseTest
    @Test
    fun `test PromptInjection defense instructions present in system prompt`() {
        val prompt = LocalSystemPromptBuilder.build(BrainContext())
        assertTrue(prompt.contains("Never output code, shell scripts, or raw markdown outside JSON"))
        assertTrue(prompt.contains("spoken_response must be brief"))
        assertTrue(prompt.contains("Never claim that an action has already succeeded"))
    }

    // 8. PromptNoDevicesFallbackTest
    @Test
    fun `test LocalSystemPromptBuilder default device when deviceSummaries empty`() {
        val ctx = BrainContext.bounded(deviceSummaries = emptyList())
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("AC (AIR_CONDITIONER)"))
    }

    // 9. PromptMusicPlayingDetailsTest
    @Test
    fun `test LocalSystemPromptBuilder formats active music state`() {
        val ctx = BrainContext.bounded(
            currentMusicSummary = MusicSummary(
                trackTitle = "Tum Hi Ho",
                isPlaying = true,
                activeOutputDeviceName = "LG SNC4R",
                isOutputConnected = true
            )
        )
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Tum Hi Ho"))
        assertTrue(prompt.contains("LG SNC4R"))
    }

    // 10. PromptEmptyTasksTest
    @Test
    fun `test LocalSystemPromptBuilder formats empty tasks as None`() {
        val ctx = BrainContext.bounded(todayTasks = emptyList())
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Active Tasks Today: None"))
    }

    // 11. PromptEmptyMemoriesTest
    @Test
    fun `test LocalSystemPromptBuilder formats empty memories as None`() {
        val ctx = BrainContext.bounded(relevantMemories = emptyList())
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Relevant Memories: None"))
    }

    // 12. BrainActionMemoryActionDeleteValidationTest
    @Test
    fun `test MemoryAction DELETE with valid memory content passes validation`() {
        val mem = Memory(id = "mem-1", content = "Temporary memory")
        val action = BrainAction.MemoryAction(MemoryActionType.DELETE, mem)
        assertTrue(BrainResponseValidator.validateAction(action) is ValidationResult.Valid)
    }

    // 13. BrainActionMemoryActionQueryValidationTest
    @Test
    fun `test MemoryAction QUERY with valid memory content passes validation`() {
        val mem = Memory(id = "mem-query-1", content = "Music query preference")
        val action = BrainAction.MemoryAction(MemoryActionType.QUERY, mem)
        assertTrue(BrainResponseValidator.validateAction(action) is ValidationResult.Valid)
    }

    // 14. BrainActionScheduleActionParametersValidationTest
    @Test
    fun `test BrainAction ScheduleAction parameter map`() {
        val params = mapOf("temp" to 24, "fan" to "auto")
        val schedule = BrainAction.ScheduleAction("AC", "POWER_ON", delayMinutes = 10, parameters = params)
        assertEquals(10, schedule.delayMinutes)
        assertEquals(24, schedule.parameters["temp"])
        assertTrue(BrainResponseValidator.validateAction(schedule) is ValidationResult.Valid)
    }

    // 15. BrainActionConnectBluetoothBlankTargetTest
    @Test
    fun `test ConnectBluetooth with null deviceName is valid (auto-connect)`() {
        val autoConnect = BrainAction.ConnectBluetooth(deviceName = null)
        assertTrue(BrainResponseValidator.validateAction(autoConnect) is ValidationResult.Valid)
    }

    // 16. BrainActionDisconnectBluetoothTest
    @Test
    fun `test DisconnectBluetooth object is valid action`() {
        val disconnect = BrainAction.DisconnectBluetooth
        assertTrue(BrainResponseValidator.validateAction(disconnect) is ValidationResult.Valid)
    }

    // 17. LocalSystemPromptBuilderCurrentTimeTest
    @Test
    fun `test LocalSystemPromptBuilder includes currentTimeMillis`() {
        val ctx = BrainContext.bounded(currentTimeMillis = 1770000000000L)
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("1770000000000"))
    }

    // 18. LocalSystemPromptBuilderBrainModeTest
    @Test
    fun `test LocalSystemPromptBuilder includes brainMode`() {
        val ctx = BrainContext.bounded(brainMode = "LOCAL")
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Brain Mode: LOCAL"))
    }

    // 19. LocalSystemPromptBuilderUserPreferredSpeakerTest
    @Test
    fun `test LocalSystemPromptBuilder includes preferred speaker`() {
        val ctx = BrainContext.bounded(userPreferences = UserPreferences(preferredSpeaker = "LG SNC4R"))
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Preferred Speaker: LG SNC4R"))
    }

    // 20. LocalSystemPromptBuilderMultipleDevicesTest
    @Test
    fun `test LocalSystemPromptBuilder formats multiple devices`() {
        val ctx = BrainContext.bounded(
            deviceSummaries = listOf(
                DeviceSummary("Inverter AC", "AC", true),
                DeviceSummary("Smart Bulb", "LIGHT", true)
            )
        )
        val prompt = LocalSystemPromptBuilder.build(ctx)
        assertTrue(prompt.contains("Inverter AC (AC)"))
        assertTrue(prompt.contains("Smart Bulb (LIGHT)"))
    }

    // 21. LocalBrainConfigEqualityTest
    @Test
    fun `test LocalBrainConfig data class copy and equality`() {
        val c1 = LocalBrainConfig(port = 11434)
        val c2 = c1.copy(port = 8080)
        assertNotEquals(c1, c2)
        assertEquals(8080, c2.port)
    }

    // 22. BrainActionTaskActionCompleteValidationTest
    @Test
    fun `test TaskAction COMPLETE with valid title passes validation`() {
        val task = Task(id = "t1", title = "Task 1")
        val action = BrainAction.TaskAction(TaskActionType.COMPLETE, task)
        assertTrue(BrainResponseValidator.validateAction(action) is ValidationResult.Valid)
    }

    // 23. BrainActionTaskActionCancelValidationTest
    @Test
    fun `test TaskAction CANCEL with valid title passes validation`() {
        val task = Task(id = "t2", title = "Task 2")
        val action = BrainAction.TaskAction(TaskActionType.CANCEL, task)
        assertTrue(BrainResponseValidator.validateAction(action) is ValidationResult.Valid)
    }

    // 24. BrainActionMusicControlNextPreviousValidationTest
    @Test
    fun `test MusicControl NEXT and PREVIOUS actions pass validation`() {
        val next = BrainAction.MusicControl(MusicActionType.NEXT)
        val prev = BrainAction.MusicControl(MusicActionType.PREVIOUS)
        assertTrue(BrainResponseValidator.validateAction(next) is ValidationResult.Valid)
        assertTrue(BrainResponseValidator.validateAction(prev) is ValidationResult.Valid)
    }
}
