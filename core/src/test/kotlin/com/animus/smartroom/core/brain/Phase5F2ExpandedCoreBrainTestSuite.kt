package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine
import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.port.BrainModeController
import com.animus.smartroom.core.brain.port.BrainProvider
import com.animus.smartroom.core.brain.port.KnowledgeCapturePort
import com.animus.smartroom.core.brain.port.LocalInferencePort
import com.animus.smartroom.core.brain.validator.BrainResponseValidator
import com.animus.smartroom.core.brain.validator.ValidationResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class Phase5F2ExpandedCoreBrainTestSuite {

    // 17. BrainContextTimezoneTest
    @Test
    fun `test BrainContext custom timezone preservation`() {
        val ctx = BrainContext.bounded(timezone = "Asia/Kolkata")
        assertEquals("Asia/Kolkata", ctx.timezone)
    }

    // 18. BrainContextBrainModeFieldTest
    @Test
    fun `test BrainContext brainMode string field`() {
        val localCtx = BrainContext.bounded(brainMode = "LOCAL")
        assertEquals("LOCAL", localCtx.brainMode)

        val remoteCtx = BrainContext.bounded(brainMode = "REMOTE")
        assertEquals("REMOTE", remoteCtx.brainMode)
    }

    // 19. LocalBrainConfigTemperatureLimitsTest
    @Test
    fun `test LocalBrainConfig temperature bounds validation`() {
        val validLow = LocalBrainConfig(temperature = 0.0f)
        val validHigh = LocalBrainConfig(temperature = 2.0f)
        val invalidNeg = LocalBrainConfig(temperature = -0.1f)
        val invalidHigh = LocalBrainConfig(temperature = 2.5f)

        assertTrue(validLow.isValid())
        assertTrue(validHigh.isValid())
        assertFalse(invalidNeg.isValid())
        assertFalse(invalidHigh.isValid())
    }

    // 20. LocalBrainConfigTokenBoundsTest
    @Test
    fun `test LocalBrainConfig token bounds validation`() {
        val lowTokens = LocalBrainConfig(maxTokens = 8)
        val highTokens = LocalBrainConfig(maxTokens = 8192)
        val validTokens = LocalBrainConfig(maxTokens = 1024)

        assertFalse(lowTokens.isValid())
        assertFalse(highTokens.isValid())
        assertTrue(validTokens.isValid())
    }

    // 21. LocalBrainConfigTimeoutBoundsTest
    @Test
    fun `test LocalBrainConfig timeout bounds validation`() {
        val lowTimeout = LocalBrainConfig(timeoutMs = 100)
        val highTimeout = LocalBrainConfig(timeoutMs = 400_000)
        val validTimeout = LocalBrainConfig(timeoutMs = 120_000)

        assertFalse(lowTimeout.isValid())
        assertFalse(highTimeout.isValid())
        assertTrue(validTimeout.isValid())
    }

    // 22. BrainResponseClarificationOptionsTest
    @Test
    fun `test BrainResponse Clarification options list`() {
        val clar = BrainResponse.Clarification("Select action", listOf("Turn Off AC", "Set to 24C"))
        assertEquals("Select action", clar.question)
        assertEquals(2, clar.options.size)
        assertEquals("Turn Off AC", clar.options[0])
    }

    // 23. BrainResponseFailureCauseTest
    @Test
    fun `test BrainResponse Failure with Throwable cause`() {
        val cause = IllegalArgumentException("Invalid state")
        val fail = BrainResponse.Failure("Failed to resolve", cause)
        assertEquals("Failed to resolve", fail.reason)
        assertEquals(cause, fail.cause)
    }

    // 24. ScheduledActionSummaryPropertiesTest
    @Test
    fun `test ScheduledActionSummary properties`() {
        val summary = ScheduledActionSummary(
            id = "sch-1",
            target = "AC",
            actionType = "POWER_OFF",
            scheduledTimeMillis = 1700000000L,
            status = "PENDING"
        )
        assertEquals("sch-1", summary.id)
        assertEquals("AC", summary.target)
        assertEquals("POWER_OFF", summary.actionType)
        assertEquals(1700000000L, summary.scheduledTimeMillis)
        assertEquals("PENDING", summary.status)
    }

    // 25. RecentActionSummaryPropertiesTest
    @Test
    fun `test RecentActionSummary properties`() {
        val summary = RecentActionSummary(
            id = "act-1",
            action = "SET_TEMP",
            targetDevice = "AC",
            status = "SUCCESS",
            timestamp = 1700000000L
        )
        assertEquals("act-1", summary.id)
        assertEquals("SET_TEMP", summary.action)
        assertEquals("AC", summary.targetDevice)
        assertEquals("SUCCESS", summary.status)
    }

    // 26. MusicSummaryPropertiesTest
    @Test
    fun `test MusicSummary properties`() {
        val music = MusicSummary(
            trackTitle = "Zara Zara",
            isPlaying = true,
            activeOutputDeviceName = "LG SNC4R",
            isOutputConnected = true
        )
        assertEquals("Zara Zara", music.trackTitle)
        assertTrue(music.isPlaying)
        assertEquals("LG SNC4R", music.activeOutputDeviceName)
        assertTrue(music.isOutputConnected)
    }

    // 27. DeviceSummaryPropertiesTest
    @Test
    fun `test DeviceSummary state map and properties`() {
        val dev = DeviceSummary(
            name = "Inverter AC",
            type = "AIR_CONDITIONER",
            isOnline = true,
            state = mapOf("temp_set" to 24, "power" to true)
        )
        assertEquals("Inverter AC", dev.name)
        assertEquals("AIR_CONDITIONER", dev.type)
        assertTrue(dev.isOnline)
        assertEquals(24, dev.state["temp_set"])
    }

    // 28. TaskSummaryPropertiesTest
    @Test
    fun `test TaskSummary properties`() {
        val taskSum = TaskSummary(
            id = "ts-1",
            title = "Check AC filter",
            priority = "HIGH",
            status = "PENDING",
            dueAt = 1750000000L
        )
        assertEquals("ts-1", taskSum.id)
        assertEquals("Check AC filter", taskSum.title)
        assertEquals("HIGH", taskSum.priority)
        assertEquals("PENDING", taskSum.status)
        assertEquals(1750000000L, taskSum.dueAt)
    }

    // 29. MemoryRelevanceScoreDecayTest
    @Test
    fun `test MemoryRelevanceEngine computes deterministic positive scores`() {
        val mem = Memory(id = "m1", content = "Music preference track Zara Zara by Aditya", relevance = 0.9f)
        val ranked = MemoryRelevanceEngine.rankMemories("play Zara Zara music", listOf(mem))
        assertEquals(1, ranked.size)
        assertEquals("m1", ranked[0].id)
    }

    // 30. MemoryRelevanceNoMatchEmptyListTest
    @Test
    fun `test MemoryRelevanceEngine returns empty list when no token overlaps`() {
        val mem = Memory(id = "m1", content = "AC temperature setting 24", relevance = 0.9f)
        val ranked = MemoryRelevanceEngine.rankMemories("football stadium tickets", listOf(mem))
        assertEquals(0, ranked.size)
    }

    // 31. BrainResponseValidatorCustomDeviceTargetPrefixTest
    @Test
    fun `test BrainResponseValidator allows custom target starting with DEV_`() {
        val customDevAction = BrainAction.DeviceCommand("DEV_CUSTOM_FAN", "SPEED", 3)
        assertTrue(BrainResponseValidator.validateAction(customDevAction) is ValidationResult.Valid)
    }

    // 32. BrainResponseValidatorScheduleCustomDevicePrefixTest
    @Test
    fun `test BrainResponseValidator allows schedule target starting with DEV_`() {
        val scheduleDev = BrainAction.ScheduleAction("DEV_HEATER", "TURN_ON", delayMinutes = 15)
        assertTrue(BrainResponseValidator.validateAction(scheduleDev) is ValidationResult.Valid)
    }
}
