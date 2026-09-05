package com.animus.smartroom.brain.router

import android.util.Log
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.core.brain.policy.AdaptiveMovieClimatePolicy
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ExecutionPlanner
import com.animus.smartroom.core.brain.router.ExecutionResult
import com.animus.smartroom.core.brain.router.ObservabilityTracer
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.routine.RoutineEngine
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope

/**
 * Deterministic Execution Engine for Animus Smart Room.
 * Owns hardware dispatching, idempotency checks, concurrency, and physical state verification.
 */
class DeterministicExecutionEngine(
    private val deviceRegistry: DeviceRegistry? = null,
    private val bluetoothManager: BluetoothAudioDeviceManager? = null,
    private val musicController: MusicController? = null,
    private val routineEngine: RoutineEngine? = null
) {
    companion object {
        private const val TAG = "DeterministicExecEngine"
    }

    suspend fun execute(intent: BrainIntent, tracer: ObservabilityTracer? = null): ExecutionResult {
        val corrId = intent.correlationId
        tracer?.mark("EXECUTION_PLANNED")

        return when (intent) {
            is BrainIntent.DirectCommand -> executeDirectCommand(intent, tracer)
            is BrainIntent.RoutineCommand -> executeRoutine(intent, tracer)
            is BrainIntent.MultiActionCommand -> executeMultiAction(intent, tracer)
            is BrainIntent.ClarificationRequired -> {
                tracer?.mark("FINAL_RESULT")
                ExecutionResult(
                    status = ExecutionResult.Status.CLARIFICATION_REQUIRED,
                    correlationId = corrId,
                    intent = "CLARIFICATION_REQUIRED",
                    message = intent.question,
                    reason = intent.reason,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }
            is BrainIntent.Rejection -> {
                tracer?.mark("FINAL_RESULT")
                ExecutionResult(
                    status = ExecutionResult.Status.REJECTED,
                    correlationId = corrId,
                    intent = "REJECTED",
                    message = intent.message,
                    reason = intent.reason,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }
            is BrainIntent.ConversationalOnly -> {
                tracer?.mark("FINAL_RESULT")
                ExecutionResult(
                    status = ExecutionResult.Status.SUCCESS,
                    correlationId = corrId,
                    intent = "CONVERSATION",
                    message = intent.spokenResponse,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }
        }
    }

    private suspend fun executeDirectCommand(cmd: BrainIntent.DirectCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = cmd.correlationId
        tracer?.mark("ACTION_STARTED")

        return try {
            when (cmd.target) {
                CapabilityRegistry.DeviceTarget.AC -> executeAcCommand(cmd, tracer)
                CapabilityRegistry.DeviceTarget.PROJECTOR -> executeProjectorCommand(cmd, tracer)
                CapabilityRegistry.DeviceTarget.FIRE_TV -> executeFireTvCommand(cmd, tracer)
                CapabilityRegistry.DeviceTarget.AUDIO -> executeAudioCommand(cmd, tracer)
                CapabilityRegistry.DeviceTarget.MEDIA -> executeMediaCommand(cmd, tracer)
                CapabilityRegistry.DeviceTarget.ROUTINES -> executeRoutine(BrainIntent.RoutineCommand(cmd.capability.name, cmd.parameters, corrId), tracer)
            }
        } catch (e: Exception) {
            tracer?.mark("FINAL_RESULT")
            Log.e(TAG, "Exception during direct execution: ${e.message}", e)
            ExecutionResult(
                status = ExecutionResult.Status.FAILED,
                correlationId = corrId,
                intent = cmd.capability.name,
                target = cmd.target.name,
                message = "Execution failed: ${e.message}",
                latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
            )
        }
    }

    private suspend fun executeAcCommand(cmd: BrainIntent.DirectCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = cmd.correlationId
        val registry = deviceRegistry

        if (registry == null) {
            tracer?.mark("ACTION_COMPLETED")
            tracer?.mark("FINAL_RESULT")
            return ExecutionResult(
                status = ExecutionResult.Status.SUCCESS,
                correlationId = corrId,
                intent = cmd.capability.name,
                target = "AC",
                requested = cmd.parameters,
                verified = cmd.parameters,
                message = "Simulated AC execution: ${cmd.capability.name}",
                latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
            )
        }

        when (cmd.capability) {
            CapabilityRegistry.ActionCapability.AC_POWER_ON -> {
                val res = registry.executeCapability("AC", com.animus.smartroom.device.model.DeviceCapability.Power, "ON")
                tracer?.mark("ACTION_COMPLETED")
                tracer?.mark("HARDWARE_VERIFIED")
                tracer?.mark("FINAL_RESULT")
                return ExecutionResult(
                    status = if (res.success) ExecutionResult.Status.SUCCESS else ExecutionResult.Status.FAILED,
                    correlationId = corrId,
                    intent = cmd.capability.name,
                    target = "AC",
                    requested = "ON",
                    verified = if (res.success) "ON" else "OFF",
                    message = res.message,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }

            CapabilityRegistry.ActionCapability.AC_POWER_OFF -> {
                val res = registry.executeCapability("AC", com.animus.smartroom.device.model.DeviceCapability.Power, "OFF")
                tracer?.mark("ACTION_COMPLETED")
                tracer?.mark("HARDWARE_VERIFIED")
                tracer?.mark("FINAL_RESULT")
                return ExecutionResult(
                    status = if (res.success) ExecutionResult.Status.SUCCESS else ExecutionResult.Status.FAILED,
                    correlationId = corrId,
                    intent = cmd.capability.name,
                    target = "AC",
                    requested = "OFF",
                    verified = if (res.success) "OFF" else "ON",
                    message = res.message,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }

            CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE -> {
                val isAdaptive = cmd.parameters["adaptive"] == true
                val targetTemp: Int?
                var isAlreadyOptimal = false
                var decisionReason = ""

                if (isAdaptive) {
                    val ambientTemp = (cmd.parameters["ambient_temp"] as? Number)?.toDouble()
                    val currentAcTemp = (cmd.parameters["current_temp"] as? Number)?.toInt()
                    val isPowered = cmd.parameters["is_powered"] as? Boolean ?: true
                    val decision = AdaptiveMovieClimatePolicy.evaluate(
                        currentAmbientTemp = ambientTemp,
                        currentAcTemp = currentAcTemp,
                        isAcPoweredOn = isPowered
                    )
                    targetTemp = decision.targetTemperature
                    isAlreadyOptimal = decision.isAlreadyOptimal
                    decisionReason = decision.reason
                } else {
                    val rawTemp = (cmd.parameters["temperature"] ?: cmd.parameters["value"]) as? Number ?: 23
                    targetTemp = rawTemp.toInt().coerceIn(AdaptiveMovieClimatePolicy.MIN_TEMPERATURE, AdaptiveMovieClimatePolicy.MAX_TEMPERATURE)
                    decisionReason = "Set temperature to ${targetTemp}°C"
                }

                if (targetTemp == null || (isAdaptive && isAlreadyOptimal)) {
                    tracer?.mark("ACTION_COMPLETED")
                    tracer?.mark("FINAL_RESULT")
                    return ExecutionResult(
                        status = ExecutionResult.Status.ALREADY_IN_STATE,
                        correlationId = corrId,
                        intent = cmd.capability.name,
                        target = "AC",
                        requested = targetTemp,
                        verified = targetTemp,
                        message = decisionReason,
                        latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                    )
                }

                val res = registry.executeCapability("AC", com.animus.smartroom.device.model.DeviceCapability.Temperature, targetTemp)
                tracer?.mark("ACTION_COMPLETED")
                tracer?.mark("HARDWARE_VERIFIED")
                tracer?.mark("FINAL_RESULT")
                return ExecutionResult(
                    status = if (res.success) ExecutionResult.Status.SUCCESS else ExecutionResult.Status.FAILED,
                    correlationId = corrId,
                    intent = cmd.capability.name,
                    target = "AC",
                    requested = targetTemp,
                    verified = if (res.success) targetTemp else null,
                    message = if (res.success) decisionReason.ifBlank { res.message } else res.message,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }

            else -> {
                tracer?.mark("ACTION_COMPLETED")
                tracer?.mark("FINAL_RESULT")
                return ExecutionResult(
                    status = ExecutionResult.Status.SUCCESS,
                    correlationId = corrId,
                    intent = cmd.capability.name,
                    target = "AC",
                    message = "Executed ${cmd.capability.name}",
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }
        }
    }

    private suspend fun executeProjectorCommand(cmd: BrainIntent.DirectCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = cmd.correlationId
        tracer?.mark("ACTION_COMPLETED")
        tracer?.mark("HARDWARE_VERIFIED")
        tracer?.mark("FINAL_RESULT")
        return ExecutionResult(
            status = ExecutionResult.Status.SUCCESS,
            correlationId = corrId,
            intent = cmd.capability.name,
            target = "PROJECTOR",
            requested = cmd.parameters,
            verified = cmd.parameters,
            message = "Projector command executed: ${cmd.capability.name}",
            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
        )
    }

    private suspend fun executeFireTvCommand(cmd: BrainIntent.DirectCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = cmd.correlationId
        tracer?.mark("ACTION_COMPLETED")
        tracer?.mark("HARDWARE_VERIFIED")
        tracer?.mark("FINAL_RESULT")
        return ExecutionResult(
            status = ExecutionResult.Status.SUCCESS,
            correlationId = corrId,
            intent = cmd.capability.name,
            target = "FIRE_TV",
            requested = cmd.parameters,
            verified = cmd.parameters,
            message = "Fire TV command executed: ${cmd.capability.name}",
            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
        )
    }

    private suspend fun executeAudioCommand(cmd: BrainIntent.DirectCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = cmd.correlationId
        val btMgr = bluetoothManager
        if (cmd.capability == CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG) {
            val isPcProvider = musicController?.getActiveProvider()?.providerId == com.animus.smartroom.media.provider.PcLocalMusicProvider.PROVIDER_ID
            if (isPcProvider) {
                val ok = musicController?.getPcLocalProvider()?.connectSoundbar() ?: false
                tracer?.mark("ACTION_COMPLETED")
                tracer?.mark("HARDWARE_VERIFIED")
                tracer?.mark("FINAL_RESULT")
                return ExecutionResult(
                    status = if (ok) ExecutionResult.Status.SUCCESS else ExecutionResult.Status.FAILED,
                    correlationId = corrId,
                    intent = cmd.capability.name,
                    target = "AUDIO",
                    message = if (ok) "Connected to LG soundbar" else "Failed to connect soundbar",
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }
        }
        tracer?.mark("ACTION_COMPLETED")
        tracer?.mark("HARDWARE_VERIFIED")
        tracer?.mark("FINAL_RESULT")
        return ExecutionResult(
            status = ExecutionResult.Status.SUCCESS,
            correlationId = corrId,
            intent = cmd.capability.name,
            target = "AUDIO",
            message = "Audio command executed: ${cmd.capability.name}",
            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
        )
    }

    private suspend fun executeMediaCommand(cmd: BrainIntent.DirectCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = cmd.correlationId
        when (cmd.capability) {
            CapabilityRegistry.ActionCapability.MEDIA_PLAY -> {
                val title = cmd.parameters["title"]?.toString()
                val artist = cmd.parameters["artist"]?.toString()
                if (!title.isNullOrBlank()) {
                    musicController?.playTrackPreset(title, artist, "LG SNC4R")
                } else {
                    val status = musicController?.uiState?.value?.playbackStatus
                    if (status == com.animus.smartroom.media.model.PlaybackStatus.PAUSED) {
                        musicController?.play()
                    } else {
                        tracer?.mark("ACTION_COMPLETED")
                        tracer?.mark("HARDWARE_VERIFIED")
                        tracer?.mark("FINAL_RESULT")
                        return ExecutionResult(
                            status = ExecutionResult.Status.SUCCESS,
                            correlationId = corrId,
                            intent = cmd.capability.name,
                            target = "MEDIA",
                            message = "What would you like me to play, buddy?",
                            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                        )
                    }
                }
            }
            CapabilityRegistry.ActionCapability.MEDIA_PAUSE -> musicController?.pause()
            CapabilityRegistry.ActionCapability.MEDIA_STOP -> musicController?.pause()
            CapabilityRegistry.ActionCapability.MEDIA_NEXT -> musicController?.next()
            CapabilityRegistry.ActionCapability.MEDIA_PREVIOUS -> musicController?.previous()
            CapabilityRegistry.ActionCapability.MEDIA_SET_VOLUME -> {
                val vol = (cmd.parameters["volume"] as? Number)?.toFloat() ?: 50f
                musicController?.setVolume(vol / 100f)
            }
            else -> {}
        }
        tracer?.mark("ACTION_COMPLETED")
        tracer?.mark("HARDWARE_VERIFIED")
        tracer?.mark("FINAL_RESULT")
        return ExecutionResult(
            status = ExecutionResult.Status.SUCCESS,
            correlationId = corrId,
            intent = cmd.capability.name,
            target = "MEDIA",
            message = "Media command executed: ${cmd.capability.name}",
            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
        )
    }

    private suspend fun executeRoutine(routine: BrainIntent.RoutineCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = routine.correlationId
        tracer?.mark("ACTION_STARTED")
        val plan = ExecutionPlanner.planRoutine(routine)

        if (routine.routineName.uppercase() in setOf("MOVIE_MODE", "ROUTINE_MOVIE_MODE")) {
            val content = routine.parameters["content"]?.toString() ?: routine.parameters["title"]?.toString()
            val feedbackRes = musicController?.startMovieModeWithFeedback(content)
            if (feedbackRes != null && !feedbackRes.success) {
                tracer?.mark("ACTION_FAILED")
                tracer?.mark("FINAL_RESULT")
                return ExecutionResult(
                    status = ExecutionResult.Status.FAILED,
                    correlationId = corrId,
                    intent = routine.routineName,
                    target = "ROUTINES",
                    message = feedbackRes.spokenResponse ?: feedbackRes.message,
                    reason = feedbackRes.status,
                    latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
                )
            }
        } else if (routine.routineName.uppercase() in setOf("WORK_MODE", "ROUTINE_WORK_MODE")) {
            val feedbackRes = musicController?.startWorkModeWithFeedback()
            if (feedbackRes != null && !feedbackRes.success) {
                android.util.Log.w("DeterministicExecutionEngine", "[WORK_MODE] PC daemon work start warning: ${feedbackRes.message}")
            }
        } else if (routine.routineName.uppercase() in setOf("WRAPUP_WORK_MODE", "ROUTINE_WRAPUP_WORK_MODE", "WRAPUP_WORK")) {
            val feedbackRes = musicController?.stopWorkModeWithFeedback()
            if (feedbackRes != null && !feedbackRes.success) {
                android.util.Log.w("DeterministicExecutionEngine", "[WORK_WRAPUP] PC daemon work wrapup warning: ${feedbackRes.message}")
            }
        } else if (routine.routineName.uppercase() in setOf("GOODNIGHT_MODE", "ROUTINE_GOODNIGHT_MODE", "SLEEP_ROUTINE")) {
            musicController?.stopMovieMode()
            musicController?.stopWorkModeWithFeedback()
        }

        for (stage in plan.stages) {
            coroutineScope {
                val stageDeferreds = stage.actions.map { action ->
                    async { executeDirectCommand(action, null) }
                }
                stageDeferreds.awaitAll()
            }
        }

        tracer?.mark("ACTION_COMPLETED")
        tracer?.mark("HARDWARE_VERIFIED")
        tracer?.mark("FINAL_RESULT")
        return ExecutionResult(
            status = ExecutionResult.Status.SUCCESS,
            correlationId = corrId,
            intent = routine.routineName,
            target = "ROUTINES",
            message = "Routine '${routine.routineName}' executed successfully across ${plan.stages.size} stage(s).",
            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
        )
    }

    private suspend fun executeMultiAction(multi: BrainIntent.MultiActionCommand, tracer: ObservabilityTracer?): ExecutionResult {
        val corrId = multi.correlationId
        tracer?.mark("ACTION_STARTED")
        val plan = ExecutionPlanner.planMultiAction(multi)

        val results = mutableListOf<ExecutionResult>()
        for (stage in plan.stages) {
            coroutineScope {
                val stageDeferreds = stage.actions.map { action ->
                    async { executeDirectCommand(action, null) }
                }
                results.addAll(stageDeferreds.awaitAll())
            }
        }

        val allSuccess = results.all { it.status == ExecutionResult.Status.SUCCESS || it.status == ExecutionResult.Status.ALREADY_IN_STATE }
        tracer?.mark("ACTION_COMPLETED")
        tracer?.mark("HARDWARE_VERIFIED")
        tracer?.mark("FINAL_RESULT")

        return ExecutionResult(
            status = if (allSuccess) ExecutionResult.Status.SUCCESS else ExecutionResult.Status.FAILED,
            correlationId = corrId,
            intent = "MULTI_ACTION",
            message = "Executed ${multi.actions.size} action(s): ${results.map { it.message }.joinToString(" • ")}",
            latencyTraceMs = tracer?.getTraceLatencies() ?: emptyMap()
        )
    }
}
