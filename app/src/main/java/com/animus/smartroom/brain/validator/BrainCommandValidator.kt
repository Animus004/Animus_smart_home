package com.animus.smartroom.brain.validator

import com.animus.smartroom.brain.model.BrainCommandDto
import com.animus.smartroom.command.model.AnimusCommand
import org.json.JSONObject
import java.util.Locale

sealed interface BrainValidationResult {
    data class Valid(val command: AnimusCommand) : BrainValidationResult
    data class Invalid(val reason: String) : BrainValidationResult
}

object BrainCommandValidator {

    fun validate(dto: BrainCommandDto): BrainValidationResult {
        val normalizedType = dto.command.trim().uppercase(Locale.ROOT)

        return when (normalizedType) {
            BrainCommandDto.CMD_PLAY_MUSIC -> {
                val title = dto.title?.trim()
                if (title.isNullOrBlank()) {
                    BrainValidationResult.Invalid("PLAY_MUSIC requires a non-empty 'title' parameter.")
                } else {
                    val artist = dto.artist?.trim()?.ifBlank { null }
                    val rawUrl = dto.playbackUrl?.trim()?.ifBlank { null }

                    if (rawUrl != null) {
                        when (val urlValidation = YouTubeUrlValidator.validateAndExtractVideoId(rawUrl)) {
                            is UrlValidationResult.Valid -> {
                                BrainValidationResult.Valid(
                                    AnimusCommand.PlayMusic(
                                        title = title,
                                        artist = artist,
                                        directVideoId = urlValidation.videoId
                                    )
                                )
                            }
                            is UrlValidationResult.Invalid -> {
                                BrainValidationResult.Invalid("Invalid candidate playback URL: ${urlValidation.reason}")
                            }
                        }
                    } else if (!dto.directVideoId.isNullOrBlank()) {
                        val videoId = dto.directVideoId.trim()
                        if (videoId.length == 11 && videoId.matches(Regex("^[a-zA-Z0-9_-]{11}$"))) {
                            BrainValidationResult.Valid(
                                AnimusCommand.PlayMusic(
                                    title = title,
                                    artist = artist,
                                    directVideoId = videoId
                                )
                            )
                        } else {
                            BrainValidationResult.Invalid("Invalid direct video ID format: '$videoId'.")
                        }
                    } else {
                        BrainValidationResult.Valid(
                            AnimusCommand.PlayMusic(
                                title = title,
                                artist = artist,
                                directVideoId = null
                            )
                        )
                    }
                }
            }

            BrainCommandDto.CMD_PAUSE_MUSIC -> {
                BrainValidationResult.Valid(AnimusCommand.PauseMusic)
            }

            BrainCommandDto.CMD_RESUME_MUSIC -> {
                BrainValidationResult.Valid(AnimusCommand.ResumeMusic)
            }

            BrainCommandDto.CMD_NEXT_TRACK -> {
                BrainValidationResult.Valid(AnimusCommand.NextTrack)
            }

            BrainCommandDto.CMD_PREVIOUS_TRACK -> {
                BrainValidationResult.Valid(AnimusCommand.PreviousTrack)
            }

            BrainCommandDto.CMD_SET_VOLUME -> {
                val value = dto.value
                if (value == null) {
                    BrainValidationResult.Invalid("SET_VOLUME requires a numeric 'value' parameter (0..100).")
                } else if (value !in 0..100) {
                    BrainValidationResult.Invalid("SET_VOLUME value must be within 0..100, received: $value.")
                } else {
                    BrainValidationResult.Valid(AnimusCommand.SetVolume(percentage = value))
                }
            }

            BrainCommandDto.CMD_CONNECT_BLUETOOTH -> {
                val target = dto.target?.trim()?.ifBlank { null }
                BrainValidationResult.Valid(AnimusCommand.ConnectBluetoothDevice(deviceName = target))
            }

            BrainCommandDto.CMD_DISCONNECT_BLUETOOTH -> {
                BrainValidationResult.Valid(AnimusCommand.DisconnectBluetoothDevice)
            }

            BrainCommandDto.CMD_SWITCH_BLUETOOTH -> {
                val target = dto.target?.trim()
                if (target.isNullOrBlank()) {
                    BrainValidationResult.Invalid("SWITCH_BLUETOOTH_DEVICE requires a non-empty 'target' parameter.")
                } else {
                    BrainValidationResult.Valid(AnimusCommand.SwitchBluetoothDevice(deviceName = target))
                }
            }

            BrainCommandDto.CMD_UNKNOWN -> {
                val raw = dto.rawText ?: "unknown"
                BrainValidationResult.Valid(AnimusCommand.UnknownCommand(rawText = raw))
            }

            else -> {
                BrainValidationResult.Invalid("Unsupported or unrecognized command type: '${dto.command}'.")
            }
        }
    }

    fun parseAndValidateJson(jsonString: String): BrainValidationResult {
        return try {
            // Clean any potential markdown wrapper from LLM
            val cleaned = jsonString.trim()
                .removePrefix("```json")
                .removePrefix("```JSON")
                .removePrefix("```")
                .removeSuffix("```")
                .trim()

            val json = JSONObject(cleaned)
            val command = json.optString("command", "").trim()
            if (command.isBlank()) {
                return BrainValidationResult.Invalid("Missing 'command' field in JSON response.")
            }

            val title = if (json.has("title")) json.optString("title").trim() else null
            val artist = if (json.has("artist")) json.optString("artist").trim() else null
            val target = if (json.has("target")) json.optString("target").trim() else null
            val value = if (json.has("value") && !json.isNull("value")) json.optInt("value") else null
            val playbackUrl = if (json.has("playbackUrl")) json.optString("playbackUrl").trim() else null
            val directVideoId = if (json.has("directVideoId")) json.optString("directVideoId").trim() else null
            val rawText = if (json.has("rawText")) json.optString("rawText") else null

            val dto = BrainCommandDto(
                command = command,
                title = title,
                artist = artist,
                target = target,
                value = value,
                playbackUrl = playbackUrl,
                directVideoId = directVideoId,
                rawText = rawText
            )
            validate(dto)
        } catch (e: Exception) {
            BrainValidationResult.Invalid("Malformed JSON response: ${e.message}")
        }
    }
}
