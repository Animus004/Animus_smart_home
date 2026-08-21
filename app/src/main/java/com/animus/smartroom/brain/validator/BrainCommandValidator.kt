package com.animus.smartroom.brain.validator

import android.util.Log
import com.animus.smartroom.brain.model.BrainCommandDto
import com.animus.smartroom.command.model.AnimusCommand
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

sealed interface BrainValidationResult {
    data class Valid(val commands: List<AnimusCommand>) : BrainValidationResult {
        constructor(command: AnimusCommand) : this(listOf(command))
        val command: AnimusCommand
            get() = commands.firstOrNull() ?: AnimusCommand.UnknownCommand("")
    }

    data class Invalid(val reason: String) : BrainValidationResult
}

object BrainCommandValidator {

    private const val TAG = "BrainCommandValidator"

    fun validate(dto: BrainCommandDto): BrainValidationResult {
        val normalizedType = dto.command.trim().uppercase(Locale.ROOT)

        return when (normalizedType) {
            BrainCommandDto.CMD_PLAY_MUSIC -> {
                val title = dto.title?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }
                if (title.isNullOrBlank()) {
                    BrainValidationResult.Invalid("PLAY_MUSIC requires a non-empty 'title' parameter.")
                } else {
                    val artist = dto.artist?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }
                    val rawUrl = dto.playbackUrl?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }
                    val directId = dto.directVideoId?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }

                    Log.d(TAG, "[play-debug] Gemini PLAY_MUSIC parsed: title='$title', artist='$artist', playbackUrl='$rawUrl', directVideoId='$directId'")

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
                    } else if (directId != null) {
                        if (directId.length == 11 && directId.matches(Regex("^[a-zA-Z0-9_-]{11}$"))) {
                            BrainValidationResult.Valid(
                                AnimusCommand.PlayMusic(
                                    title = title,
                                    artist = artist,
                                    directVideoId = directId
                                )
                            )
                        } else {
                            BrainValidationResult.Invalid("Invalid direct video ID format: '$directId'.")
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
                val target = dto.target?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }
                BrainValidationResult.Valid(AnimusCommand.ConnectBluetoothDevice(deviceName = target))
            }

            BrainCommandDto.CMD_DISCONNECT_BLUETOOTH -> {
                BrainValidationResult.Valid(AnimusCommand.DisconnectBluetoothDevice)
            }

            BrainCommandDto.CMD_SWITCH_BLUETOOTH -> {
                val target = dto.target?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }
                if (target.isNullOrBlank()) {
                    BrainValidationResult.Invalid("SWITCH_BLUETOOTH_DEVICE requires a non-empty 'target' parameter.")
                } else {
                    BrainValidationResult.Valid(AnimusCommand.SwitchBluetoothDevice(deviceName = target))
                }
            }

            BrainCommandDto.CMD_SET_DEVICE,
            BrainCommandDto.CMD_SET_DEVICE_CAPABILITY -> {
                val target = dto.target?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }
                val capabilityStr = dto.capability?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it }

                if (target.isNullOrBlank()) {
                    BrainValidationResult.Invalid("SET_DEVICE requires a non-empty 'target' parameter.")
                } else if (capabilityStr.isNullOrBlank()) {
                    BrainValidationResult.Invalid("SET_DEVICE requires a valid 'capability' parameter.")
                } else {
                    val cap = com.animus.smartroom.device.model.DeviceCapability.fromString(capabilityStr)
                    if (cap == null) {
                        BrainValidationResult.Invalid("Unknown device capability: '$capabilityStr'.")
                    } else {
                        val effectiveValue: Any? = dto.value ?: dto.valueString
                        BrainValidationResult.Valid(
                            AnimusCommand.SetDeviceCapability(
                                target = target,
                                capability = cap,
                                value = effectiveValue
                            )
                        )
                    }
                }
            }

            BrainCommandDto.CMD_SET_AC -> {
                val target = dto.target?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it } ?: "AC"
                val capabilityStr = dto.capability?.trim()?.let { if (it.equals("null", ignoreCase = true) || it.isBlank()) null else it } ?: "TEMPERATURE"
                val cap = com.animus.smartroom.device.model.DeviceCapability.fromString(capabilityStr)
                if (cap == null) {
                    BrainValidationResult.Invalid("Unknown AC capability: '$capabilityStr'.")
                } else {
                    val effectiveValue: Any? = dto.value ?: dto.valueString
                    BrainValidationResult.Valid(
                        AnimusCommand.SetDeviceCapability(
                            target = target,
                            capability = cap,
                            value = effectiveValue
                        )
                    )
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

    private fun parseDto(json: JSONObject): BrainCommandDto? {
        val command = if (json.has("command") && !json.isNull("command")) {
            json.optString("command", "").trim()
        } else if (json.has("type") && !json.isNull("type")) {
            json.optString("type", "").trim()
        } else {
            ""
        }

        if (command.isBlank() || command.equals("null", ignoreCase = true)) return null

        val title = if (json.has("title") && !json.isNull("title")) {
            val s = json.optString("title").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val artist = if (json.has("artist") && !json.isNull("artist")) {
            val s = json.optString("artist").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val target = if (json.has("target") && !json.isNull("target")) {
            val s = json.optString("target").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val capability = if (json.has("capability") && !json.isNull("capability")) {
            val s = json.optString("capability").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val value = if (json.has("value") && !json.isNull("value")) {
            val v = json.opt("value")
            when (v) {
                is Number -> v.toInt()
                is String -> v.toIntOrNull()
                else -> null
            }
        } else null

        val valueString = if (json.has("value") && !json.isNull("value")) {
            val s = json.optString("value").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val playbackUrl = if (json.has("playbackUrl") && !json.isNull("playbackUrl")) {
            val s = json.optString("playbackUrl").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val directVideoId = if (json.has("directVideoId") && !json.isNull("directVideoId")) {
            val s = json.optString("directVideoId").trim()
            if (s.equals("null", ignoreCase = true) || s.isBlank()) null else s
        } else null

        val rawText = if (json.has("rawText") && !json.isNull("rawText")) {
            val s = json.optString("rawText")
            if (s.equals("null", ignoreCase = true)) null else s
        } else null

        return BrainCommandDto(
            command = command,
            title = title,
            artist = artist,
            target = target,
            capability = capability,
            value = value,
            valueString = valueString,
            playbackUrl = playbackUrl,
            directVideoId = directVideoId,
            rawText = rawText
        )
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

            if (cleaned.startsWith("[")) {
                // Direct JSON Array of commands: [ { ... }, { ... } ]
                val jsonArray = JSONArray(cleaned)
                val validatedCommands = mutableListOf<AnimusCommand>()
                for (i in 0 until jsonArray.length()) {
                    val obj = jsonArray.getJSONObject(i)
                    val dto = parseDto(obj) ?: return BrainValidationResult.Invalid("Missing 'command' or 'type' in array element $i.")
                    when (val res = validate(dto)) {
                        is BrainValidationResult.Valid -> validatedCommands.addAll(res.commands)
                        is BrainValidationResult.Invalid -> return res
                    }
                }
                if (validatedCommands.isEmpty()) {
                    BrainValidationResult.Invalid("Empty command array received.")
                } else {
                    BrainValidationResult.Valid(validatedCommands)
                }
            } else {
                val json = JSONObject(cleaned)

                // Check for multi-command array in "commands" property
                if (json.has("commands") && !json.isNull("commands")) {
                    val jsonArray = json.getJSONArray("commands")
                    val validatedCommands = mutableListOf<AnimusCommand>()
                    for (i in 0 until jsonArray.length()) {
                        val obj = jsonArray.getJSONObject(i)
                        val dto = parseDto(obj) ?: return BrainValidationResult.Invalid("Missing 'command' or 'type' in 'commands' element $i.")
                        when (val res = validate(dto)) {
                            is BrainValidationResult.Valid -> validatedCommands.addAll(res.commands)
                            is BrainValidationResult.Invalid -> return res
                        }
                    }
                    if (validatedCommands.isEmpty()) {
                        BrainValidationResult.Invalid("Empty 'commands' array received.")
                    } else {
                        BrainValidationResult.Valid(validatedCommands)
                    }
                } else {
                    // Single command object
                    val dto = parseDto(json) ?: return BrainValidationResult.Invalid("Missing 'command' or 'type' field in JSON response.")
                    validate(dto)
                }
            }
        } catch (e: Exception) {
            BrainValidationResult.Invalid("Malformed JSON response: ${e.message}")
        }
    }
}
