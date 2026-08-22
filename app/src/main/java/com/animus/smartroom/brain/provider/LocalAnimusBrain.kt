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
    private val localBrainProvider: LocalBrainProvider? = null,
    private val localParser: CommandParser = LocalCommandParser(),
    private val voiceOutputPort: com.animus.smartroom.core.port.VoiceOutputPort? = null
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

        Log.i(TAG, "LOCAL_LLM_DEBUG: [local-brain] Interpreting: '$trimmed'")

        // 1. If LocalBrainProvider is configured, route to LocalBrainProvider (Ollama local LLM with readiness gating)
        if (localBrainProvider != null) {
            try {
                Log.i(TAG, "LOCAL_LLM_DEBUG: Calling LocalBrainProvider.understand for '$trimmed'")
                val response = localBrainProvider.understand(trimmed, com.animus.smartroom.core.brain.model.BrainContext())
                Log.i(TAG, "LOCAL_LLM_DEBUG: LocalBrainProvider response: $response")

                when (response) {
                    is com.animus.smartroom.core.brain.model.BrainResponse.Command -> {
                        val spoken = response.spokenResponse
                        if (!spoken.isNullOrBlank()) {
                            voiceOutputPort?.speak(spoken)
                        }

                        // Map brain actions to AnimusCommand
                        val commands = response.actions.mapNotNull { action ->
                            when (action) {
                                is com.animus.smartroom.core.brain.model.BrainAction.DeviceCommand -> {
                                    val cap = com.animus.smartroom.device.model.DeviceCapability.fromString(action.capability)
                                        ?: com.animus.smartroom.device.model.DeviceCapability.Power
                                    AnimusCommand.SetDeviceCapability(
                                        target = action.target,
                                        capability = cap,
                                        value = action.value
                                    )
                                }
                                is com.animus.smartroom.core.brain.model.BrainAction.PlayMusic -> {
                                    AnimusCommand.PlayMusic(title = action.title, artist = action.artist)
                                }
                                is com.animus.smartroom.core.brain.model.BrainAction.MusicControl -> {
                                    when (action.action) {
                                        com.animus.smartroom.core.brain.model.MusicActionType.PAUSE -> AnimusCommand.PauseMusic
                                        com.animus.smartroom.core.brain.model.MusicActionType.RESUME -> AnimusCommand.ResumeMusic
                                        com.animus.smartroom.core.brain.model.MusicActionType.NEXT -> AnimusCommand.NextTrack
                                        com.animus.smartroom.core.brain.model.MusicActionType.PREVIOUS -> AnimusCommand.PreviousTrack
                                    }
                                }
                                is com.animus.smartroom.core.brain.model.BrainAction.SetVolume -> {
                                    AnimusCommand.SetVolume(percentage = action.percentage)
                                }
                                is com.animus.smartroom.core.brain.model.BrainAction.ScheduleAction -> {
                                    AnimusCommand.ScheduleDeviceAction(
                                        target = action.target,
                                        action = action.action,
                                        delayMinutes = action.delayMinutes,
                                        scheduledTime = action.scheduledTime,
                                        recurrence = action.recurrence,
                                        parameters = action.parameters
                                    )
                                }
                                is com.animus.smartroom.core.brain.model.BrainAction.CancelScheduledAction -> {
                                    AnimusCommand.CancelScheduledAction(
                                        target = action.target,
                                        actionType = action.actionType
                                    )
                                }
                                else -> null
                            }
                        }

                        if (commands.isNotEmpty()) {
                            return BrainResult.Success(commands)
                        }
                    }
                    is com.animus.smartroom.core.brain.model.BrainResponse.Conversation -> {
                        voiceOutputPort?.speak(response.spokenResponse)
                        return BrainResult.Success(AnimusCommand.UnknownCommand(trimmed))
                    }
                    is com.animus.smartroom.core.brain.model.BrainResponse.Clarification -> {
                        voiceOutputPort?.speak(response.question)
                        return BrainResult.Success(AnimusCommand.UnknownCommand(trimmed))
                    }
                    is com.animus.smartroom.core.brain.model.BrainResponse.Failure -> {
                        voiceOutputPort?.speak(response.reason)
                        return BrainResult.Failure(response.reason)
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "LOCAL_LLM_DEBUG: LocalBrainProvider inference failed, falling back to rule parser", e)
            }
        }

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
                is AnimusCommand.SetDeviceCapability -> BrainCommandDto(
                    command = BrainCommandDto.CMD_SET_DEVICE,
                    target = parsedCommand.target,
                    capability = parsedCommand.capability.name,
                    value = parsedCommand.value as? Int,
                    valueString = parsedCommand.value?.toString()
                )
                is AnimusCommand.ActivateSleepMode -> BrainCommandDto(
                    command = BrainCommandDto.CMD_SLEEP_MODE,
                    durationMinutes = parsedCommand.durationMinutes,
                    wakeTime = parsedCommand.wakeTime
                )
                is AnimusCommand.CancelSleepMode -> BrainCommandDto(
                    command = BrainCommandDto.CMD_CANCEL_SLEEP
                )
                is AnimusCommand.ScheduleDeviceAction -> BrainCommandDto(
                    command = BrainCommandDto.CMD_SCHEDULE_DEVICE_ACTION,
                    target = parsedCommand.target,
                    action = parsedCommand.action,
                    delayMinutes = parsedCommand.delayMinutes,
                    scheduledTime = parsedCommand.scheduledTime,
                    recurrence = parsedCommand.recurrence,
                    parameters = parsedCommand.parameters
                )
                is AnimusCommand.CancelScheduledAction -> BrainCommandDto(
                    command = BrainCommandDto.CMD_CANCEL_SCHEDULED_ACTION,
                    target = parsedCommand.target,
                    action = parsedCommand.actionType
                )
                is AnimusCommand.QueryScheduledAction -> BrainCommandDto(
                    command = BrainCommandDto.CMD_QUERY_SCHEDULED_ACTION,
                    target = parsedCommand.target
                )
                is AnimusCommand.UnknownCommand -> BrainCommandDto(
                    command = BrainCommandDto.CMD_UNKNOWN,
                    rawText = parsedCommand.rawText
                )
            }

            when (val validation = BrainCommandValidator.validate(dto)) {
                is BrainValidationResult.Valid -> {
                    val count = validation.commands.size
                    Log.i(TAG, "[local-brain] Command count returned: $count (${validation.commands.map { it::class.simpleName }})")
                    BrainResult.Success(validation.commands)
                }
                is BrainValidationResult.Invalid -> {
                    Log.w(TAG, "[local-brain] Produced invalid command contract: ${validation.reason}")
                    BrainResult.InvalidResponse(validation.reason)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "[local-brain] Evaluation failed", e)
            BrainResult.Failure("Local brain evaluation failed: ${e.message}", e)
        }
    }
}
