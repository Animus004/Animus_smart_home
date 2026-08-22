package com.animus.smartroom.brain

import android.util.Log
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.model.DeviceSummary
import com.animus.smartroom.core.brain.model.MemoryActionType
import com.animus.smartroom.core.brain.model.MusicActionType
import com.animus.smartroom.core.brain.model.MusicSummary
import com.animus.smartroom.core.brain.model.RecentActionSummary
import com.animus.smartroom.core.brain.model.ScheduledActionSummary
import com.animus.smartroom.core.brain.model.TaskActionType
import com.animus.smartroom.core.brain.model.TaskSummary
import com.animus.smartroom.core.brain.model.UserPreferences
import com.animus.smartroom.core.brain.port.BrainModeController
import com.animus.smartroom.core.brain.port.BrainProvider
import com.animus.smartroom.core.brain.repository.MemoryRepository
import com.animus.smartroom.core.brain.repository.TaskRepository
import com.animus.smartroom.core.brain.validator.BrainResponseValidator
import com.animus.smartroom.core.brain.validator.ValidationResult
import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.port.VoiceOutputPort
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.diagnostics.DiagnosticBus
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.UUID

import com.animus.smartroom.brain.session.AndroidSessionContextRepository
import com.animus.smartroom.core.brain.session.ConversationReferenceResolver

class AnimusBrainEngine(
    private val modeController: BrainModeController,
    private val localProvider: BrainProvider,
    private val remoteProvider: BrainProvider,
    private val taskRepository: TaskRepository? = null,
    private val memoryRepository: MemoryRepository? = null,
    private val voiceOutputPort: VoiceOutputPort? = null
) {
    companion object {
        private const val TAG = "AnimusBrainEngine"
    }

    private val inferenceMutex = Mutex()

    suspend fun processInput(
        input: String,
        correlationId: String = "corr-brain-${UUID.randomUUID().toString().take(8)}",
        contextBuilder: (suspend () -> BrainContext)? = null
    ): Pair<BrainResponse, List<AnimusCommand>> = inferenceMutex.withLock {
        val trimmed = input.trim()
        if (trimmed.isBlank()) {
            return@withLock Pair(BrainResponse.Failure("Empty command input"), emptyList())
        }

        // Explicit session reset command
        if (trimmed.equals("forget this conversation", ignoreCase = true) || trimmed.equals("reset session", ignoreCase = true)) {
            AndroidSessionContextRepository.reset()
            val resetMsg = "I have cleared the conversational session."
            voiceOutputPort?.speak(resetMsg)
            return@withLock Pair(BrainResponse.Conversation(resetMsg), emptyList())
        }

        val session = AndroidSessionContextRepository.getSession()
        val sessionSummary = session.toSummary()
        session.addTurn("USER", trimmed)

        val mode = modeController.mode.value
        Log.i(TAG, "[$correlationId] Processing input in $mode mode: '$trimmed'")

        publishDiagnostic(
            correlationId = correlationId,
            stage = ActionStage.RECEIVED,
            status = ActionStatus.IN_PROGRESS,
            message = "Brain received input in $mode mode"
        )

        val provider = when (mode) {
            BrainMode.LOCAL -> localProvider
            BrainMode.REMOTE -> remoteProvider
        }

        if (mode == BrainMode.LOCAL && !provider.isAvailable()) {
            publishDiagnostic(
                correlationId = correlationId,
                stage = ActionStage.FAILED,
                status = ActionStatus.FAILED,
                message = "Local brain unavailable"
            )
            val unavailableMsg = "Your local brain is currently offline."
            voiceOutputPort?.speak(unavailableMsg)
            return@withLock Pair(BrainResponse.Failure("Local brain unavailable"), emptyList())
        }

        val baseContext = contextBuilder?.invoke() ?: BrainContext()
        val context = baseContext.copy(sessionSummary = sessionSummary)

        publishDiagnostic(
            correlationId = correlationId,
            stage = ActionStage.PARSING,
            status = ActionStatus.IN_PROGRESS,
            message = "Brain interpreting input"
        )

        // 1. Check deterministic contextual reference resolver first
        val referenceResponse = ConversationReferenceResolver.resolveReference(trimmed, sessionSummary)
        val response = referenceResponse ?: provider.understand(trimmed, context)

        // Strict Validation
        val validation = BrainResponseValidator.validate(response)
        if (validation is ValidationResult.Invalid) {
            publishDiagnostic(
                correlationId = correlationId,
                stage = ActionStage.FAILED,
                status = ActionStatus.FAILED,
                message = "Validation failed: ${validation.reason}"
            )
            return@withLock Pair(BrainResponse.Failure("Validation failed: ${validation.reason}"), emptyList())
        }

        // Voice Feedback before command execution
        if (response is BrainResponse.Command) {
            val spoken = response.spokenResponse
            if (!spoken.isNullOrBlank()) {
                voiceOutputPort?.speak(spoken)
                session.addTurn("ASSISTANT", spoken)
            }
        } else if (response is BrainResponse.Conversation) {
            val spoken = response.spokenResponse
            if (spoken.isNotBlank()) {
                voiceOutputPort?.speak(spoken)
                session.addTurn("ASSISTANT", spoken)
            }
        } else if (response is BrainResponse.Clarification) {
            voiceOutputPort?.speak(response.question)
            session.setPendingClarification(response.question)
            session.addTurn("ASSISTANT", response.question)
        }

        // Handle Task & Memory Actions if present & update session
        if (response is BrainResponse.Command) {
            for (action in response.actions) {
                when (action) {
                    is BrainAction.PlayMusic -> session.updateActiveMusic(action.title)
                    is BrainAction.SetVolume -> session.updateVolume(action.percentage)
                    is BrainAction.DeviceCommand -> {
                        if (action.target.equals("AC", ignoreCase = true) && action.capability.contains("TEMP", ignoreCase = true)) {
                            val temp = (action.value as? Number)?.toInt() ?: 24
                            session.updateTemperature(temp)
                        }
                    }
                    is BrainAction.ScheduleAction -> session.updateScheduledAction(action.target, action.delayMinutes)
                    is BrainAction.TaskAction -> {
                        session.updateLastTask(action.task.id, action.task.title)
                        if (taskRepository != null) {
                            when (action.actionType) {
                                TaskActionType.CREATE -> taskRepository.addTask(action.task)
                                TaskActionType.COMPLETE -> taskRepository.updateTaskStatus(action.task.id, com.animus.smartroom.core.brain.model.TaskStatus.COMPLETED)
                                TaskActionType.CANCEL -> taskRepository.updateTaskStatus(action.task.id, com.animus.smartroom.core.brain.model.TaskStatus.CANCELLED)
                                TaskActionType.LIST -> {}
                            }
                        }
                    }
                    is BrainAction.MemoryAction -> {
                        if (memoryRepository != null) {
                            when (action.actionType) {
                                MemoryActionType.CREATE -> memoryRepository.saveMemory(action.memory)
                                MemoryActionType.DELETE -> memoryRepository.deleteMemory(action.memory.id)
                                MemoryActionType.QUERY -> {}
                            }
                        }
                    }
                    else -> {}
                }
            }
        }

        // Convert BrainActions to AnimusCommands
        val commands = if (response is BrainResponse.Command) {
            response.actions.mapNotNull { mapBrainActionToAnimusCommand(it) }
        } else {
            emptyList()
        }

        publishDiagnostic(
            correlationId = correlationId,
            stage = ActionStage.RESOLVING,
            status = ActionStatus.SUCCESS,
            message = "Brain resolved ${commands.size} executable command(s)"
        )

        return@withLock Pair(response, commands)
    }

    private fun mapBrainActionToAnimusCommand(action: BrainAction): AnimusCommand? {
        return when (action) {
            is BrainAction.PlayMusic -> AnimusCommand.PlayMusic(action.title, action.artist)
            is BrainAction.MusicControl -> when (action.action) {
                MusicActionType.PAUSE -> AnimusCommand.PauseMusic
                MusicActionType.RESUME -> AnimusCommand.ResumeMusic
                MusicActionType.NEXT -> AnimusCommand.NextTrack
                MusicActionType.PREVIOUS -> AnimusCommand.PreviousTrack
            }
            is BrainAction.SetVolume -> AnimusCommand.SetVolume(action.percentage)
            is BrainAction.ConnectBluetooth -> AnimusCommand.ConnectBluetoothDevice(action.deviceName)
            is BrainAction.DisconnectBluetooth -> AnimusCommand.DisconnectBluetoothDevice
            is BrainAction.DeviceCommand -> {
                val cap = DeviceCapability.fromString(action.capability) ?: DeviceCapability.Power
                AnimusCommand.SetDeviceCapability(action.target, cap, action.value)
            }
            is BrainAction.ScheduleAction -> AnimusCommand.ScheduleDeviceAction(
                target = action.target,
                action = action.action,
                delayMinutes = action.delayMinutes,
                scheduledTime = action.scheduledTime,
                recurrence = action.recurrence,
                parameters = action.parameters
            )
            is BrainAction.CancelScheduledAction -> AnimusCommand.CancelScheduledAction(
                target = action.target,
                actionType = action.actionType
            )
            is BrainAction.TaskAction,
            is BrainAction.MemoryAction -> null // Handled directly by repository
        }
    }

    private fun publishDiagnostic(
        correlationId: String,
        stage: ActionStage,
        status: ActionStatus,
        message: String
    ) {
        DiagnosticBus.publish {
            create(
                source = ActionSource.BRAIN,
                targetDevice = null,
                action = "BRAIN_UNDERSTANDING",
                stage = stage,
                status = status,
                message = message,
                correlationId = correlationId
            )
        }
    }
}
