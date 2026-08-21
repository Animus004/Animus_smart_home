package com.animus.smartroom.routine

import com.animus.smartroom.brain.model.BrainCommandDto
import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import org.junit.Assert.*
import org.junit.Test

class SleepModeIntentValidationTest {

    private val localParser = LocalCommandParser()

    @Test
    fun testSleepModeWithDurationMinutesValidation() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SLEEP_MODE,
            durationMinutes = 45
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue("Expected Valid result", result is BrainValidationResult.Valid)
        val cmd = (result as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.ActivateSleepMode)
        val sleepCmd = cmd as AnimusCommand.ActivateSleepMode
        assertEquals(45, sleepCmd.durationMinutes)
        assertNull(sleepCmd.wakeTime)
    }

    @Test
    fun testSleepModeWithAbsoluteWakeTimeValidation() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SLEEP_MODE,
            wakeTime = "16:00"
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue("Expected Valid result", result is BrainValidationResult.Valid)
        val cmd = (result as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.ActivateSleepMode)
        val sleepCmd = cmd as AnimusCommand.ActivateSleepMode
        assertNull(sleepCmd.durationMinutes)
        assertEquals("16:00", sleepCmd.wakeTime)
    }

    @Test
    fun testSleepModeWithoutDurationReturnsUnparameterizedIntent() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SLEEP_MODE,
            durationMinutes = null,
            wakeTime = null
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue("Expected Valid result for unparameterized sleep", result is BrainValidationResult.Valid)
        val cmd = (result as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.ActivateSleepMode)
        val sleepCmd = cmd as AnimusCommand.ActivateSleepMode
        assertNull(sleepCmd.durationMinutes)
        assertNull(sleepCmd.wakeTime)
    }

    @Test
    fun testSleepModeNegativeDurationRejected() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SLEEP_MODE,
            durationMinutes = -10
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue("Expected Invalid result for negative duration", result is BrainValidationResult.Invalid)
    }

    @Test
    fun testCancelSleepModeValidation() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_CANCEL_SLEEP
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue("Expected Valid result", result is BrainValidationResult.Valid)
        val cmd = (result as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.CancelSleepMode)
    }

    @Test
    fun testJsonParsingForSleepModeWithDuration() {
        val json = """
        {
          "commands": [
            {
              "command": "SLEEP_MODE",
              "durationMinutes": 30,
              "wakeTime": null
            }
          ]
        }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Valid)
        val commands = (validation as BrainValidationResult.Valid).commands
        assertEquals(1, commands.size)
        assertTrue(commands[0] is AnimusCommand.ActivateSleepMode)
        assertEquals(30, (commands[0] as AnimusCommand.ActivateSleepMode).durationMinutes)
    }

    @Test
    fun testJsonParsingForCancelSleep() {
        val json = """
        {
          "commands": [
            {
              "command": "CANCEL_SLEEP"
            }
          ]
        }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Valid)
        val commands = (validation as BrainValidationResult.Valid).commands
        assertEquals(1, commands.size)
        assertTrue(commands[0] is AnimusCommand.CancelSleepMode)
    }

    @Test
    fun testLocalParserSleepCommands() {
        // "I need to sleep for 30 minutes"
        val cmd1 = localParser.parse("I need to sleep for 30 minutes")
        assertTrue(cmd1 is AnimusCommand.ActivateSleepMode)
        assertEquals(30, (cmd1 as AnimusCommand.ActivateSleepMode).durationMinutes)

        // "sleep for an hour"
        val cmd2 = localParser.parse("sleep for an hour")
        assertTrue(cmd2 is AnimusCommand.ActivateSleepMode)
        assertEquals(60, (cmd2 as AnimusCommand.ActivateSleepMode).durationMinutes)

        // "wake me up at 4 PM"
        val cmd3 = localParser.parse("wake me up at 4 PM")
        assertTrue(cmd3 is AnimusCommand.ActivateSleepMode)
        assertEquals("4 pm", (cmd3 as AnimusCommand.ActivateSleepMode).wakeTime?.lowercase())

        // "cancel my sleep timer"
        val cmd4 = localParser.parse("cancel my sleep timer")
        assertTrue(cmd4 is AnimusCommand.CancelSleepMode)

        // "I am tired and want to sleep"
        val cmd5 = localParser.parse("I am tired and want to sleep")
        assertTrue(cmd5 is AnimusCommand.ActivateSleepMode)
        assertNull((cmd5 as AnimusCommand.ActivateSleepMode).durationMinutes)
        assertNull((cmd5 as AnimusCommand.ActivateSleepMode).wakeTime)
    }
}
