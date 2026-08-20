package com.animus.smartroom.brain.provider

import android.util.Log
import com.animus.smartroom.brain.AnimusBrain
import com.animus.smartroom.brain.model.BrainCommandDto
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.CommandParser
import com.animus.smartroom.command.parser.LocalCommandParser

class LocalAnimusBrain(
    private val localParser: CommandParser = LocalCommandParser()
) : AnimusBrain {

    companion object {
        private const val TAG = "LocalAnimusBrain"
    }

    override val providerType: BrainProviderType = BrainProviderType.LOCAL

    override suspend fun interpret(input: String): BrainResult {
        val trimmed = input.trim()
        if (trimmed.isBlank()) {
            return BrainResult.Success(AnimusCommand.UnknownCommand(input))
        }

        Log.d(TAG, "[interpret] Local brain interpreting: '$trimmed'")

        return try {
            val parsedCommand = localParser.parse(trimmed)

            // Convert to structured DTO to ensure full contract validation pipeline
            val dto = when (parsedCommand) {
                is AnimusCommand.PlayMusic -> BrainCommandDto(
                    command = BrainCommandDto.CMD_PLAY_MUSIC,
                    title = parsedCommand.title,
                    artist = parsedCommand.artist
                )
                is AnimusCommand.PauseMusic -> BrainCommandDto(command = BrainCommandDto.CMD_PAUSE_MUSIC)
                is AnimusCommand.ResumeMusic -> BrainCommandDto(command = BrainCommandDto.CMD_RESUME_MUSIC)
                is AnimusCommand.NextTrack -> BrainCommandDto(command = BrainCommandDto.CMD_NEXT_TRACK)
                is AnimusCommand.PreviousTrack -> BrainCommandDto(command = BrainCommandDto.CMD_PREVIOUS_TRACK)
                is AnimusCommand.SetVolume -> BrainCommandDto(
                    command = BrainCommandDto.CMD_SET_VOLUME,
                    value = parsedCommand.percentage
                )
                is AnimusCommand.ConnectBluetoothDevice -> BrainCommandDto(
                    command = BrainCommandDto.CMD_CONNECT_BLUETOOTH,
                    target = parsedCommand.deviceName
                )
                is AnimusCommand.DisconnectBluetoothDevice -> BrainCommandDto(command = BrainCommandDto.CMD_DISCONNECT_BLUETOOTH)
                is AnimusCommand.SwitchBluetoothDevice -> BrainCommandDto(
                    command = BrainCommandDto.CMD_SWITCH_BLUETOOTH,
                    target = parsedCommand.deviceName
                )
                is AnimusCommand.UnknownCommand -> BrainCommandDto(
                    command = BrainCommandDto.CMD_UNKNOWN,
                    rawText = parsedCommand.rawText
                )
            }

            when (val validation = BrainCommandValidator.validate(dto)) {
                is BrainValidationResult.Valid -> {
                    Log.i(TAG, "[interpret] Local brain resolved valid command: ${validation.command::class.simpleName}")
                    BrainResult.Success(validation.command)
                }
                is BrainValidationResult.Invalid -> {
                    Log.w(TAG, "[interpret] Local brain produced invalid command contract: ${validation.reason}")
                    BrainResult.InvalidResponse(validation.reason)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "[interpret] Local brain error", e)
            BrainResult.Failure("Local brain evaluation failed: ${e.message}", e)
        }
    }
}
