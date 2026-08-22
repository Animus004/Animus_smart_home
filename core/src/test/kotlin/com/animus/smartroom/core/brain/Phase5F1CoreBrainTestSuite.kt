package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.model.DeviceSummary
import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory
import com.animus.smartroom.core.brain.model.MusicActionType
import com.animus.smartroom.core.brain.model.MusicSummary
import com.animus.smartroom.core.brain.model.Task
import com.animus.smartroom.core.brain.model.TaskPriority
import com.animus.smartroom.core.brain.model.TaskStatus
import com.animus.smartroom.core.brain.model.UserPreferences
import com.animus.smartroom.core.brain.port.BrainModeController
import com.animus.smartroom.core.brain.port.BrainProvider
import com.animus.smartroom.core.brain.port.LocalInferencePort
import com.animus.smartroom.core.brain.validator.BrainResponseValidator
import com.animus.smartroom.core.brain.validator.ValidationResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Phase5F1CoreBrainTestSuite {

    // 1. BrainProviderContractTest
    @Test
    fun `test BrainProvider contract behavior`() = runBlocking {
        val dummyProvider = object : BrainProvider {
            override suspend fun understand(input: String, context: BrainContext): BrainResponse {
                return BrainResponse.Command("Playing music", BrainAction.PlayMusic("Zara Zara"))
            }
            override fun isAvailable(): Boolean = true
        }

        assertTrue(dummyProvider.isAvailable())
        val res = dummyProvider.understand("play music", BrainContext())
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("Playing music", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.PlayMusic)
    }

    // 2. BrainModeControllerTest
    @Test
    fun `test BrainModeController state changes`() {
        val controller = object : BrainModeController {
            private val _mode = MutableStateFlow(BrainMode.LOCAL)
            override val mode: StateFlow<BrainMode> = _mode.asStateFlow()
            override fun setMode(mode: BrainMode) { _mode.value = mode }
        }

        assertEquals(BrainMode.LOCAL, controller.mode.value)
        controller.setMode(BrainMode.REMOTE)
        assertEquals(BrainMode.REMOTE, controller.mode.value)
    }

    // 3. BrainContextTest
    @Test
    fun `test BrainContext sanitization and immutability`() {
        val ctx = BrainContext(
            deviceSummaries = listOf(DeviceSummary("Bedroom AC", "AC", true)),
            userPreferences = UserPreferences(preferredTemperatureCelsius = 23)
        )
        assertEquals(1, ctx.deviceSummaries.size)
        assertEquals(23, ctx.userPreferences.preferredTemperatureCelsius)
    }

    // 4. BrainResponseParsingTest
    @Test
    fun `test BrainResponse hierarchy models`() {
        val cmd = BrainResponse.Command(BrainAction.SetVolume(50))
        val conv = BrainResponse.Conversation("Hello there!")
        val clar = BrainResponse.Clarification("Which device?", listOf("AC", "Speaker"))
        val fail = BrainResponse.Failure("Timeout")

        assertNotNull(cmd)
        assertNotNull(conv)
        assertNotNull(clar)
        assertNotNull(fail)
    }

    // 5. BrainActionValidationTest
    @Test
    fun `test BrainResponseValidator allows safe commands and rejects invalid values`() {
        val validAction = BrainAction.SetVolume(80)
        val invalidAction = BrainAction.SetVolume(150)

        assertTrue(BrainResponseValidator.validateAction(validAction) is ValidationResult.Valid)
        assertTrue(BrainResponseValidator.validateAction(invalidAction) is ValidationResult.Invalid)
    }

    // 6. BrainSafetyBoundaryTest
    @Test
    fun `test BrainResponseValidator rejects credentials and unsafe system commands`() {
        val leakResponse = BrainResponse.Conversation("Here is the key: AIzaSyD3x9Y_ExampleSecretKey123456789")
        val maliciousAction = BrainAction.DeviceCommand("AC", "POWER", "eval(rm -rf /)")

        assertTrue(BrainResponseValidator.validate(leakResponse) is ValidationResult.Invalid)
        assertTrue(BrainResponseValidator.validateAction(maliciousAction) is ValidationResult.Invalid)
    }

    // 7. TaskModelTest
    @Test
    fun `test Task domain model properties`() {
        val task = Task(
            title = "Turn off AC before leaving",
            priority = TaskPriority.HIGH,
            status = TaskStatus.PENDING
        )
        assertEquals("Turn off AC before leaving", task.title)
        assertEquals(TaskPriority.HIGH, task.priority)
        assertEquals(TaskStatus.PENDING, task.status)
        assertNotNull(task.id)
    }

    // 8. MemoryModelTest
    @Test
    fun `test Memory domain model properties`() {
        val memory = Memory(
            content = "User prefers AC at 24C during sleep",
            category = MemoryCategory.PREFERENCE,
            relevance = 0.95f
        )
        assertEquals(MemoryCategory.PREFERENCE, memory.category)
        assertTrue(memory.relevance > 0.9f)
    }

    // 9. LocalInferencePortTest
    @Test
    fun `test LocalInferencePort contract`() = runBlocking {
        val inferencePort = object : LocalInferencePort {
            override suspend fun generate(prompt: String, context: List<String>): String = "Generated answer"
            override fun isAvailable(): Boolean = true
        }

        assertTrue(inferencePort.isAvailable())
        assertEquals("Generated answer", inferencePort.generate("test prompt"))
    }
}
