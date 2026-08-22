package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine
import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.port.KnowledgeCapturePort
import com.animus.smartroom.core.brain.port.LocalInferencePort
import com.animus.smartroom.core.brain.validator.BrainResponseValidator
import com.animus.smartroom.core.brain.validator.ValidationResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class Phase5F2CoreBrainTestSuite {

    // 1. BrainContextLimitTest
    @Test
    fun `test BrainContext bounded limits on tasks, memories, and lengths`() {
        val manyTasks = (1..50).map { TaskSummary("id-$it", "Task $it", "NORMAL", "PENDING", null) }
        val longMemoryContent = "A".repeat(500)
        val manyMemories = (1..30).map { Memory(content = longMemoryContent, relevance = 0.8f) }

        val bounded = BrainContext.bounded(
            todayTasks = manyTasks,
            overdueTasks = manyTasks,
            upcomingTasks = manyTasks,
            relevantMemories = manyMemories
        )

        assertEquals(BrainContext.MAX_TASKS_PER_SECTION, bounded.todayTasks.size)
        assertEquals(BrainContext.MAX_TASKS_PER_SECTION, bounded.overdueTasks.size)
        assertEquals(BrainContext.MAX_TASKS_PER_SECTION, bounded.upcomingTasks.size)
        assertEquals(BrainContext.MAX_MEMORIES, bounded.relevantMemories.size)
        assertTrue(bounded.relevantMemories[0].content.length <= BrainContext.MAX_MEMORY_CONTENT_LENGTH + 3)
    }

    // 2. BrainContextSanitizationTest
    @Test
    fun `test BrainContext contains zero credentials or raw keys`() {
        val ctx = BrainContext.bounded(
            deviceSummaries = listOf(DeviceSummary("Living Room AC", "AC", true)),
            userPreferences = UserPreferences(preferredSpeaker = "LG SNC4R")
        )
        assertFalse(ctx.toString().contains("AIza"))
        assertFalse(ctx.toString().contains("Bearer"))
        assertFalse(ctx.toString().contains("secret"))
    }

    // 3. MemoryRelevanceEngineTest
    @Test
    fun `test MemoryRelevanceEngine ranks based on keyword overlap and category`() {
        val m1 = Memory(id = "1", content = "User prefers room temperature at 24 degrees Celsius", category = MemoryCategory.PREFERENCE, relevance = 0.9f)
        val m2 = Memory(id = "2", content = "User likes playing Zara Zara on soundbar", category = MemoryCategory.PREFERENCE, relevance = 0.8f)
        val m3 = Memory(id = "3", content = "SQL database migration completed", category = MemoryCategory.FACT, relevance = 0.5f)

        val rankedAc = MemoryRelevanceEngine.rankMemories("What is the preferred AC temperature?", listOf(m1, m2, m3))
        assertEquals(1, rankedAc.size)
        assertEquals("1", rankedAc[0].id)

        val rankedMusic = MemoryRelevanceEngine.rankMemories("play music Zara Zara", listOf(m1, m2, m3))
        assertEquals("2", rankedMusic[0].id)
    }

    // 4. LocalBrainConfigTest
    @Test
    fun `test LocalBrainConfig validation and endpoint formatting`() {
        val validConfig = LocalBrainConfig(host = "192.168.1.50", port = 11434, model = "qwen2.5-3b")
        assertTrue(validConfig.isValid())
        assertEquals("http://192.168.1.50:11434/v1/chat/completions", validConfig.endpointUrl)

        val invalidPort = LocalBrainConfig(port = 70000)
        assertFalse(invalidPort.isValid())

        val emptyHost = LocalBrainConfig(host = "")
        assertFalse(emptyHost.isValid())
    }

    // 5. KnowledgeCaptureContractTest
    @Test
    fun `test KnowledgeCapturePort contract`() = runBlocking {
        val capturedList = mutableListOf<String>()
        val port = object : KnowledgeCapturePort {
            override suspend fun capture(source: String, content: String, relevance: Float): Boolean {
                capturedList.add("$source: $content")
                return true
            }
        }
        assertTrue(port.capture("USER", "Remember that I like AC at 24C", 0.9f))
        assertEquals(1, capturedList.size)
    }

    // 6. BrainActionSafetyTest
    @Test
    fun `test BrainAction validation blocks shell commands and invalid delays`() {
        val badSchedule = BrainAction.ScheduleAction("AC", "TURN_OFF", delayMinutes = -5)
        assertTrue(BrainResponseValidator.validateAction(badSchedule) is ValidationResult.Invalid)

        val goodSchedule = BrainAction.ScheduleAction("AC", "TURN_OFF", delayMinutes = 30)
        assertTrue(BrainResponseValidator.validateAction(goodSchedule) is ValidationResult.Valid)
    }

    // 7. MemoryCategoryCoverageTest
    @Test
    fun `test all MemoryCategory enum values`() {
        assertEquals(8, MemoryCategory.values().size)
        assertTrue(MemoryCategory.values().contains(MemoryCategory.PREFERENCE))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.DEVICE_USAGE))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.FACT))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.ROUTINE_SCHEDULE))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.PROJECT))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.GOAL))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.EXPLICIT_MEMORY))
        assertTrue(MemoryCategory.values().contains(MemoryCategory.GENERAL))
    }

    // 8. TaskPriorityAndStatusCoverageTest
    @Test
    fun `test TaskPriority and TaskStatus enum values`() {
        assertEquals(4, TaskPriority.values().size)
        assertEquals(4, TaskStatus.values().size)
        assertTrue(TaskStatus.values().contains(TaskStatus.PENDING))
        assertTrue(TaskStatus.values().contains(TaskStatus.IN_PROGRESS))
        assertTrue(TaskStatus.values().contains(TaskStatus.COMPLETED))
        assertTrue(TaskStatus.values().contains(TaskStatus.CANCELLED))
    }

    // 9. TaskActionTypeCoverageTest
    @Test
    fun `test TaskActionType enum values`() {
        assertEquals(4, TaskActionType.values().size)
        assertTrue(TaskActionType.values().contains(TaskActionType.CREATE))
        assertTrue(TaskActionType.values().contains(TaskActionType.COMPLETE))
        assertTrue(TaskActionType.values().contains(TaskActionType.CANCEL))
        assertTrue(TaskActionType.values().contains(TaskActionType.LIST))
    }

    // 10. MusicActionTypeCoverageTest
    @Test
    fun `test MusicActionType enum values`() {
        assertEquals(4, MusicActionType.values().size)
        assertTrue(MusicActionType.values().contains(MusicActionType.PAUSE))
        assertTrue(MusicActionType.values().contains(MusicActionType.RESUME))
        assertTrue(MusicActionType.values().contains(MusicActionType.NEXT))
        assertTrue(MusicActionType.values().contains(MusicActionType.PREVIOUS))
    }

    // 11. UserPreferencesDefaultsTest
    @Test
    fun `test UserPreferences defaults and custom aliases`() {
        val prefs = UserPreferences(
            preferredSpeaker = "LG SNC4R",
            preferredTemperatureCelsius = 22,
            customAliases = mapOf("my cooler" to "AC")
        )
        assertEquals("LG SNC4R", prefs.preferredSpeaker)
        assertEquals(22, prefs.preferredTemperatureCelsius)
        assertEquals("AC", prefs.customAliases["my cooler"])
    }

    // 12. BrainResponseValidationEdgeCasesTest
    @Test
    fun `test BrainResponseValidator catches blank conversation and invalid volume`() {
        val blankConv = BrainResponse.Conversation("   ")
        assertTrue(BrainResponseValidator.validate(blankConv) is ValidationResult.Invalid)

        val badVolHigh = BrainAction.SetVolume(105)
        assertTrue(BrainResponseValidator.validateAction(badVolHigh) is ValidationResult.Invalid)

        val badVolLow = BrainAction.SetVolume(-1)
        assertTrue(BrainResponseValidator.validateAction(badVolLow) is ValidationResult.Invalid)
    }

    // 13. BrainResponseValidatorCancelActionTargetTest
    @Test
    fun `test BrainResponseValidator rejects blank cancel action target`() {
        val badCancel = BrainAction.CancelScheduledAction("")
        assertTrue(BrainResponseValidator.validateAction(badCancel) is ValidationResult.Invalid)

        val goodCancel = BrainAction.CancelScheduledAction("AC")
        assertTrue(BrainResponseValidator.validateAction(goodCancel) is ValidationResult.Valid)
    }

    // 14. BrainResponseValidatorTaskActionTitleTest
    @Test
    fun `test BrainResponseValidator rejects blank task title`() {
        val badTask = BrainAction.TaskAction(TaskActionType.CREATE, Task(title = ""))
        assertTrue(BrainResponseValidator.validateAction(badTask) is ValidationResult.Invalid)

        val goodTask = BrainAction.TaskAction(TaskActionType.CREATE, Task(title = "Valid Task"))
        assertTrue(BrainResponseValidator.validateAction(goodTask) is ValidationResult.Valid)
    }

    // 15. MemoryRelevanceCategoryFilterTest
    @Test
    fun `test MemoryRelevanceEngine category filtering`() {
        val m1 = Memory(id = "1", content = "AC temperature 24", category = MemoryCategory.PREFERENCE)
        val m2 = Memory(id = "2", content = "AC temperature recorded at 24", category = MemoryCategory.DEVICE_USAGE)

        val filtered = MemoryRelevanceEngine.rankMemories("AC", listOf(m1, m2), categoryFilter = MemoryCategory.PREFERENCE)
        assertEquals(1, filtered.size)
        assertEquals("1", filtered[0].id)
    }

    // 16. MemoryRelevanceEmptyQueryTest
    @Test
    fun `test MemoryRelevanceEngine empty query returns top relevance memories`() {
        val m1 = Memory(id = "1", content = "A", relevance = 0.4f)
        val m2 = Memory(id = "2", content = "B", relevance = 0.9f)

        val top = MemoryRelevanceEngine.rankMemories("", listOf(m1, m2), limit = 1)
        assertEquals(1, top.size)
        assertEquals("2", top[0].id)
    }
}
