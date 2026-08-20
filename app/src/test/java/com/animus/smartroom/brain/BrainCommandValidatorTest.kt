package com.animus.smartroom.brain

import com.animus.smartroom.brain.model.BrainCommandDto
import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult
import com.animus.smartroom.command.model.AnimusCommand
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BrainCommandValidatorTest {

    @Test
    fun testValidPlayMusicCommand() {
        val dtoWithArtist = BrainCommandDto(
            command = BrainCommandDto.CMD_PLAY_MUSIC,
            title = "Zara Zara",
            artist = "Bombay Jayashri"
        )
        val result1 = BrainCommandValidator.validate(dtoWithArtist)
        assertTrue(result1 is BrainValidationResult.Valid)
        val cmd1 = (result1 as BrainValidationResult.Valid).command as AnimusCommand.PlayMusic
        assertEquals("Zara Zara", cmd1.title)
        assertEquals("Bombay Jayashri", cmd1.artist)

        val dtoWithoutArtist = BrainCommandDto(
            command = BrainCommandDto.CMD_PLAY_MUSIC,
            title = "Zara Zara"
        )
        val result2 = BrainCommandValidator.validate(dtoWithoutArtist)
        assertTrue(result2 is BrainValidationResult.Valid)
        val cmd2 = (result2 as BrainValidationResult.Valid).command as AnimusCommand.PlayMusic
        assertEquals("Zara Zara", cmd2.title)
        assertEquals(null, cmd2.artist)
    }

    @Test
    fun testInvalidPlayMusicMissingTitle() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_PLAY_MUSIC,
            title = "   "
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue(result is BrainValidationResult.Invalid)
    }

    @Test
    fun testValidSetVolume() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SET_VOLUME,
            value = 40
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue(result is BrainValidationResult.Valid)
        val cmd = (result as BrainValidationResult.Valid).command as AnimusCommand.SetVolume
        assertEquals(40, cmd.percentage)
    }

    @Test
    fun testInvalidSetVolumeOutOfRange() {
        val dtoTooHigh = BrainCommandDto(
            command = BrainCommandDto.CMD_SET_VOLUME,
            value = 150
        )
        val resultHigh = BrainCommandValidator.validate(dtoTooHigh)
        assertTrue(resultHigh is BrainValidationResult.Invalid)

        val dtoNegative = BrainCommandDto(
            command = BrainCommandDto.CMD_SET_VOLUME,
            value = -5
        )
        val resultNeg = BrainCommandValidator.validate(dtoNegative)
        assertTrue(resultNeg is BrainValidationResult.Invalid)

        val dtoNull = BrainCommandDto(
            command = BrainCommandDto.CMD_SET_VOLUME,
            value = null
        )
        val resultNull = BrainCommandValidator.validate(dtoNull)
        assertTrue(resultNull is BrainValidationResult.Invalid)
    }

    @Test
    fun testValidSwitchBluetoothDevice() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SWITCH_BLUETOOTH,
            target = "Bedroom Speaker"
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue(result is BrainValidationResult.Valid)
        val cmd = (result as BrainValidationResult.Valid).command as AnimusCommand.SwitchBluetoothDevice
        assertEquals("Bedroom Speaker", cmd.deviceName)
    }

    @Test
    fun testInvalidSwitchBluetoothDeviceMissingTarget() {
        val dto = BrainCommandDto(
            command = BrainCommandDto.CMD_SWITCH_BLUETOOTH,
            target = "  "
        )
        val result = BrainCommandValidator.validate(dto)
        assertTrue(result is BrainValidationResult.Invalid)
    }

    @Test
    fun testJsonParsingAndValidation() {
        val validJson = """
            {
                "command": "PLAY_MUSIC",
                "title": "Zara Zara",
                "artist": "Bombay Jayashri"
            }
        """.trimIndent()
        val result1 = BrainCommandValidator.parseAndValidateJson(validJson)
        assertTrue(result1 is BrainValidationResult.Valid)

        val invalidVolumeJson = """
            {
                "command": "SET_VOLUME",
                "value": 120
            }
        """.trimIndent()
        val result2 = BrainCommandValidator.parseAndValidateJson(invalidVolumeJson)
        assertTrue(result2 is BrainValidationResult.Invalid)

        val malformedJson = "{ broken json"
        val result3 = BrainCommandValidator.parseAndValidateJson(malformedJson)
        assertTrue(result3 is BrainValidationResult.Invalid)
    }
}
