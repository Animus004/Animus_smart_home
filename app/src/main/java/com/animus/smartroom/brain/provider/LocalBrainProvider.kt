package com.animus.smartroom.brain.provider

import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.CommandParser
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.model.MusicActionType
import com.animus.smartroom.core.brain.model.Task
import com.animus.smartroom.core.brain.model.TaskActionType
import com.animus.smartroom.core.brain.port.BrainProvider
import com.animus.smartroom.core.brain.port.LocalInferencePort
import org.json.JSONObject

class LocalBrainProvider(
    private val inferencePort: LocalInferencePort? = null,
    private val localParser: CommandParser = LocalCommandParser()
) : BrainProvider {

    override fun isAvailable(): Boolean {
        // Considered available if inferencePort exists and is not permanently disconnected/failed
        return inferencePort?.isAvailable() ?: true
    }

    override suspend fun understand(input: String, context: BrainContext): BrainResponse {
        val trimmed = input.trim()
            .replace(Regex("[?.!,]+$"), "")
            .replace(Regex("\\s+"), " ")
            .trim()
        if (trimmed.isBlank()) {
            return BrainResponse.Failure("Empty command input")
        }

        // 1. If local inference port is configured, try structured inference (gating will wait for READY if warming up)
        if (inferencePort != null) {
            try {
                val systemPrompt = com.animus.smartroom.core.brain.prompt.LocalSystemPromptBuilder.build(context)
                val generated = inferencePort.generate(trimmed, listOf(systemPrompt))
                val structured = parseStructuredLocalResponse(generated, trimmed)
                if (structured != null) {
                    return structured
                }
            } catch (e: Exception) {
                // Graceful fallback to deterministic rule parser
            }
        }

        // 2. Deterministic Rule-Based Parsing (Offline Fallback)
        return try {
            // Check for task queries/commands
            if (trimmed.startsWith("add task", ignoreCase = true) || trimmed.startsWith("remind me", ignoreCase = true)) {
                val title = trimmed.replace(Regex("(?i)^(add task to |add task |remind me to |remind me )"), "").trim()
                val task = Task(title = title)
                return BrainResponse.Command(
                    spokenResponse = "Added task: $title",
                    actions = listOf(BrainAction.TaskAction(TaskActionType.CREATE, task))
                )
            } else if (trimmed.contains("what are my tasks", ignoreCase = true) || trimmed.contains("list tasks", ignoreCase = true) || trimmed.contains("what do i have today", ignoreCase = true)) {
                return BrainResponse.Conversation(
                    spokenResponse = if (context.todayTasks.isEmpty()) "You have no tasks scheduled for today."
                    else "You have ${context.todayTasks.size} tasks remaining today."
                )
            }

            // Check for personal knowledge learning & queries
            if (trimmed.startsWith("remember that", ignoreCase = true) || trimmed.startsWith("remember ", ignoreCase = true)) {
                val content = trimmed.replace(Regex("(?i)^(remember that |remember )"), "").trim()
                val cat = when {
                    content.contains("prefer", ignoreCase = true) -> com.animus.smartroom.core.brain.model.MemoryCategory.PREFERENCE
                    content.contains("speaker", ignoreCase = true) -> com.animus.smartroom.core.brain.model.MemoryCategory.FACT
                    content.contains("project", ignoreCase = true) -> com.animus.smartroom.core.brain.model.MemoryCategory.PROJECT
                    content.contains("goal", ignoreCase = true) -> com.animus.smartroom.core.brain.model.MemoryCategory.GOAL
                    else -> com.animus.smartroom.core.brain.model.MemoryCategory.EXPLICIT_MEMORY
                }
                val mem = com.animus.smartroom.core.brain.model.Memory(content = content, category = cat)
                return BrainResponse.Command(
                    spokenResponse = "I'll remember that $content.",
                    actions = listOf(BrainAction.MemoryAction(com.animus.smartroom.core.brain.model.MemoryActionType.CREATE, mem))
                )
            } else if (trimmed.startsWith("forget that", ignoreCase = true) || trimmed.startsWith("forget ", ignoreCase = true) || trimmed.startsWith("remove memory", ignoreCase = true)) {
                val content = trimmed.replace(Regex("(?i)^(forget that |forget |remove memory )"), "").trim()
                val mem = com.animus.smartroom.core.brain.model.Memory(content = content)
                return BrainResponse.Command(
                    spokenResponse = "I've forgotten that information.",
                    actions = listOf(BrainAction.MemoryAction(com.animus.smartroom.core.brain.model.MemoryActionType.DELETE, mem))
                )
            } else if (trimmed.contains("what do you know about me", ignoreCase = true) || trimmed.contains("what are my projects", ignoreCase = true) || trimmed.contains("what preferences do you remember", ignoreCase = true)) {
                val p = context.personalContext
                val projects = p?.activeProjects?.joinToString() ?: "Animus"
                val speaker = p?.primarySpeaker ?: "LG SNC4R"
                val temp = p?.preferredAcTemp ?: 24
                return BrainResponse.Conversation(
                    spokenResponse = "I know your preferred AC temperature is $temp°C, your primary speaker is $speaker, and you are working on $projects."
                )
            } else if (trimmed.contains("preferred ac temperature", ignoreCase = true) || trimmed.contains("temperature do i prefer", ignoreCase = true) || trimmed.contains("temperature do i usually", ignoreCase = true)) {
                val temp = context.personalContext?.preferredAcTemp ?: context.userPreferences.preferredTemperatureCelsius
                return BrainResponse.Conversation(
                    spokenResponse = "Your preferred AC temperature is $temp degrees Celsius."
                )
            } else if (trimmed.contains("which speaker do i use", ignoreCase = true) || trimmed.contains("bedroom speaker", ignoreCase = true)) {
                val speaker = context.personalContext?.primarySpeaker ?: context.userPreferences.preferredSpeaker ?: "LG SNC4R"
                return BrainResponse.Conversation(
                    spokenResponse = "Your bedroom speaker is the $speaker."
                )
            }

            val command = localParser.parse(trimmed)
            val action = mapAnimusCommandToBrainAction(command)
            if (action != null) {
                val spoken = generateSpokenResponse(action)
                BrainResponse.Command(spokenResponse = spoken, actions = listOf(action))
            } else {
                BrainResponse.Conversation("I understood '$input'.")
            }
        } catch (e: Exception) {
            BrainResponse.Failure("Local evaluation failed: ${e.localizedMessage}", e)
        }
    }

    private fun parseStructuredLocalResponse(raw: String, originalInput: String): BrainResponse? {
        return try {
            val json = JSONObject(raw)
            val type = json.optString("type", "conversation")
            val speech = (json.optString("spoken_response").takeIf { it.isNotBlank() }
                ?: json.optString("speech").takeIf { it.isNotBlank() })

            when (type.lowercase()) {
                "command" -> {
                    val actionsArray = json.optJSONArray("actions")
                    val actions = mutableListOf<BrainAction>()
                    if (actionsArray != null) {
                        for (i in 0 until actionsArray.length()) {
                            val actObj = actionsArray.getJSONObject(i)
                            val actType = actObj.optString("type").lowercase()
                            when (actType) {
                                "device_command" -> {
                                    val target = actObj.optString("target", "AC")
                                    val command = actObj.optString("command", "POWER")
                                    val rawVal = actObj.opt("value")
                                    val capability = when (command.uppercase()) {
                                        "SET_TEMPERATURE", "TEMPERATURE" -> "TEMPERATURE"
                                        "POWER" -> "POWER"
                                        "SET_MODE", "MODE" -> "HVAC_MODE"
                                        "SET_FAN_SPEED", "FAN_SPEED" -> "FAN_SPEED"
                                        else -> command
                                    }
                                    actions.add(
                                        BrainAction.DeviceCommand(
                                            target = target,
                                            capability = capability,
                                            value = rawVal
                                        )
                                    )
                                }
                                "play_music" -> {
                                    actions.add(
                                        BrainAction.PlayMusic(
                                            title = actObj.optString("title", originalInput),
                                            artist = actObj.optString("artist").takeIf { it.isNotBlank() }
                                        )
                                    )
                                }
                                "music_control" -> {
                                    val actionStr = actObj.optString("action", "PAUSE").uppercase()
                                    val actEnum = try {
                                        MusicActionType.valueOf(actionStr)
                                    } catch (e: Exception) {
                                        MusicActionType.PAUSE
                                    }
                                    actions.add(BrainAction.MusicControl(actEnum))
                                }
                                "set_volume" -> {
                                    actions.add(
                                        BrainAction.SetVolume(
                                            percentage = actObj.optInt("percentage", 50)
                                        )
                                    )
                                }
                                "connect_bluetooth" -> {
                                    actions.add(
                                        BrainAction.ConnectBluetooth(
                                            deviceName = actObj.optString("deviceName").takeIf { it.isNotBlank() }
                                        )
                                    )
                                }
                                "disconnect_bluetooth" -> {
                                    actions.add(BrainAction.DisconnectBluetooth)
                                }
                                "schedule_action" -> {
                                    actions.add(
                                        BrainAction.ScheduleAction(
                                            target = actObj.optString("target", "AC"),
                                            action = actObj.optString("action", "POWER_OFF"),
                                            delayMinutes = if (actObj.has("delayMinutes")) actObj.optInt("delayMinutes") else null,
                                            scheduledTime = actObj.optString("scheduledTime").takeIf { it.isNotBlank() }
                                        )
                                    )
                                }
                                "cancel_schedule" -> {
                                    actions.add(
                                        BrainAction.CancelScheduledAction(
                                            target = actObj.optString("target", "AC")
                                        )
                                    )
                                }
                                "task_action" -> {
                                    val actStr = actObj.optString("action", "CREATE").uppercase()
                                    val actEnum = try {
                                        TaskActionType.valueOf(actStr)
                                    } catch (e: Exception) {
                                        TaskActionType.CREATE
                                    }
                                    val title = actObj.optString("title", originalInput)
                                    actions.add(BrainAction.TaskAction(actEnum, Task(title = title)))
                                }
                            }
                        }
                    }
                    if (actions.isNotEmpty()) BrainResponse.Command(speech, actions) else BrainResponse.Conversation(speech ?: raw)
                }
                "conversation" -> BrainResponse.Conversation(speech ?: raw)
                "clarification" -> BrainResponse.Clarification(speech ?: raw)
                "failure" -> BrainResponse.Failure(speech ?: "Local brain failed to process command")
                else -> BrainResponse.Conversation(speech ?: raw)
            }
        } catch (e: Exception) {
            BrainResponse.Conversation(raw)
        }
    }

    private fun mapAnimusCommandToBrainAction(command: AnimusCommand): BrainAction? {
        return when (command) {
            is AnimusCommand.PlayMusic -> BrainAction.PlayMusic(command.title, command.artist)
            is AnimusCommand.PauseMusic -> BrainAction.MusicControl(MusicActionType.PAUSE)
            is AnimusCommand.ResumeMusic -> BrainAction.MusicControl(MusicActionType.RESUME)
            is AnimusCommand.NextTrack -> BrainAction.MusicControl(MusicActionType.NEXT)
            is AnimusCommand.PreviousTrack -> BrainAction.MusicControl(MusicActionType.PREVIOUS)
            is AnimusCommand.SetVolume -> BrainAction.SetVolume(command.percentage)
            is AnimusCommand.ConnectBluetoothDevice -> BrainAction.ConnectBluetooth(command.deviceName)
            is AnimusCommand.DisconnectBluetoothDevice -> BrainAction.DisconnectBluetooth
            is AnimusCommand.SetDeviceCapability -> BrainAction.DeviceCommand(
                target = command.target,
                capability = command.capability.name,
                value = command.value
            )
            is AnimusCommand.ScheduleDeviceAction -> BrainAction.ScheduleAction(
                target = command.target,
                action = command.action,
                delayMinutes = command.delayMinutes,
                scheduledTime = command.scheduledTime,
                recurrence = command.recurrence,
                parameters = command.parameters
            )
            is AnimusCommand.CancelScheduledAction -> BrainAction.CancelScheduledAction(
                target = command.target,
                actionType = command.actionType
            )
            else -> null
        }
    }

    private fun generateSpokenResponse(action: BrainAction): String? {
        return when (action) {
            is BrainAction.PlayMusic -> "Playing ${action.title}."
            is BrainAction.SetVolume -> "Setting volume to ${action.percentage}%."
            is BrainAction.DeviceCommand -> "Adjusting ${action.target}."
            is BrainAction.ScheduleAction -> "Scheduling ${action.target} action."
            is BrainAction.CancelScheduledAction -> "Cancelling scheduled action on ${action.target}."
            else -> null
        }
    }
}
