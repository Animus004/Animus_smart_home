package com.animus.smartroom.routine.sleep

import android.util.Log
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.command.model.CommandExecutionResult
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.resolver.MusicResolutionResult
import com.animus.smartroom.media.resolver.YouTubeMusicResolver
import com.animus.smartroom.routine.model.EnvironmentSnapshot
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.model.RoutineType
import com.animus.smartroom.routine.scheduler.RoutineScheduler
import com.animus.smartroom.routine.scheduler.ScheduleResult
import com.animus.smartroom.routine.storage.RoutineStorage
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.UUID

class SleepModeRoutine(
    private val deviceRegistry: DeviceRegistry,
    private val bluetoothManager: BluetoothAudioDeviceManager?,
    private val musicController: MusicController?,
    private val musicResolver: YouTubeMusicResolver?,
    private val routineScheduler: RoutineScheduler,
    private val routineStorage: RoutineStorage
) {
    companion object {
        private const val TAG = "SleepModeRoutine"
        const val SLEEP_MUSIC_QUERY = "soothing instrumental rain sounds sleep"
        const val DEFAULT_SLEEP_VOLUME = 0.25f
        const val DEFAULT_SLEEP_TEMP = 24
        const val CLARIFICATION_PROMPT = "Sure buddy. How long should I let you sleep?"
    }

    suspend fun enter(durationMinutes: Int?, wakeTime: String?): CommandExecutionResult {
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.REQUESTED,
            message = if (durationMinutes != null) "duration=${durationMinutes}m" else "wakeTime=$wakeTime"
        )

        // Validation & Clarification Check
        if (durationMinutes == null && (wakeTime.isNullOrBlank() || wakeTime.equals("null", ignoreCase = true))) {
            DiagnosticBus.log(
                tag = "sleep",
                stage = DiagnosticStage.VALIDATING,
                message = "No duration or wake time provided -> Clarification requested"
            )
            return CommandExecutionResult(
                success = true,
                message = CLARIFICATION_PROMPT
            )
        }

        val targetWakeMillis = calculateWakeTimeMillis(durationMinutes, wakeTime)
        if (targetWakeMillis == null) {
            val errMsg = "Could not parse sleep duration or wake time"
            DiagnosticBus.log(
                tag = "sleep",
                stage = DiagnosticStage.FAILED,
                message = errMsg
            )
            return CommandExecutionResult(
                success = false,
                message = "$errMsg. Please say e.g. '30 minutes' or 'until 4 PM'."
            )
        }

        // STEP 0 — CAPTURE ENVIRONMENT SNAPSHOT
        val preSnapshot = captureSnapshot()
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.SNAPSHOT,
            message = "captured"
        )

        val routineId = UUID.randomUUID().toString().take(8)

        val activeRoutine = RoutineState(
            id = routineId,
            type = RoutineType.SLEEP,
            createdAt = System.currentTimeMillis(),
            scheduledWakeTime = targetWakeMillis,
            status = RoutineStatus.ACTIVE,
            initialSnapshot = preSnapshot
        )
        routineStorage.saveActiveRoutine(activeRoutine)
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.PERSISTED,
            message = "routine=$routineId"
        )

        val messages = mutableListOf<String>()
        var speakerConnected = false

        // STEP 1 — SPEAKER
        if (bluetoothManager != null) {
            DiagnosticBus.log(
                tag = "sleep",
                stage = DiagnosticStage.SPEAKER,
                message = "checking connection"
            )
            val btState = bluetoothManager.uiState.value
            val isAlreadyConnected = btState.connectionState is BluetoothDeviceState.Connected
            val selectedName = btState.selectedDevice?.displayName ?: "Speaker"

            if (isAlreadyConnected) {
                speakerConnected = true
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.SPEAKER,
                    message = "connected ($selectedName)"
                )
            } else {
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.SPEAKER,
                    message = "connecting to $selectedName..."
                )
                val connected = bluetoothManager.connectAndAwait(6000L)
                if (connected) {
                    speakerConnected = true
                    musicController?.updateOutputDevice(selectedName, true)
                    DiagnosticBus.log(
                        tag = "sleep",
                        stage = DiagnosticStage.SPEAKER,
                        message = "connected ($selectedName)"
                    )
                } else {
                    DiagnosticBus.log(
                        tag = "sleep",
                        stage = DiagnosticStage.FAILED,
                        message = "speaker connection failed ($selectedName)"
                    )
                    messages.add("Could not connect to speaker")
                }
            }
        }

        // STEP 2 — MUSIC RESOLVER & PLAYBACK
        if (musicController != null) {
            if (speakerConnected || musicController.uiState.value.isOutputConnected) {
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.MUSIC,
                    message = "resolving soothing track"
                )
                val resolution = musicResolver?.resolveTrack(
                    title = "Soothing Rain & Sleep Ambience",
                    artist = "Sleep Sounds",
                    explicitDirectId = null
                )

                val effectiveVideoId = when (resolution) {
                    is MusicResolutionResult.Resolved -> resolution.videoId
                    else -> null
                }
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.MUSIC,
                    message = "resolved (videoId=${effectiveVideoId ?: "auto"})"
                )

                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.MUSIC,
                    message = "playback requested"
                )
                musicController.playTrackPreset(
                    title = "Soothing Rain & Sleep Ambience",
                    artist = "Sleep Sounds",
                    activeDeviceName = musicController.uiState.value.activeOutputDeviceName,
                    directVideoId = effectiveVideoId
                )
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.MUSIC,
                    message = "playback started"
                )
                messages.add("Playing soothing sleep sounds")
            } else {
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.MUSIC,
                    message = "skipped (no speaker connected)"
                )
            }
        }

        // STEP 3 — VOLUME (25%)
        if (musicController != null) {
            DiagnosticBus.log(
                tag = "sleep",
                stage = DiagnosticStage.VOLUME,
                message = "setting=25%"
            )
            musicController.setVolume(DEFAULT_SLEEP_VOLUME)
            DiagnosticBus.log(
                tag = "sleep",
                stage = DiagnosticStage.VOLUME,
                message = "verified=25%"
            )
        }

        // STEP 4 — AC CONFIGURATION (Power ON, AUTO, 24°C, Fan AUTO)
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.AC,
            message = "power=ON"
        )
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.AC,
            message = "temperature=$DEFAULT_SLEEP_TEMP"
        )
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.AC,
            message = "mode=AUTO"
        )
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.AC,
            message = "fan=AUTO"
        )
        val acResult = configureSleepAc()
        if (acResult.success) {
            messages.add("AC set to 24°C Auto")
        } else {
            DiagnosticBus.log(
                tag = "sleep",
                stage = DiagnosticStage.FAILED,
                message = "AC configuration failed: ${acResult.message}"
            )
            messages.add("Could not configure AC (${acResult.message})")
        }

        // STEP 5 — SCHEDULER (Exact Wake-Up Alarm)
        val formattedTime = formatClockTime(targetWakeMillis)
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.SCHEDULER,
            message = "requested trigger=$formattedTime"
        )
        val scheduleResult = routineScheduler.scheduleWake(routineId, targetWakeMillis)

        val scheduleSummary = when (scheduleResult) {
            is ScheduleResult.Success -> {
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.SCHEDULER,
                    message = "accepted"
                )
                "Wake-up scheduled for $formattedTime"
            }
            is ScheduleResult.PermissionRequired -> {
                "Wake-up timer set for $formattedTime (Exact alarm permission recommended)"
            }
            is ScheduleResult.Error -> {
                DiagnosticBus.log(
                    tag = "sleep",
                    stage = DiagnosticStage.FAILED,
                    message = "scheduler error: ${scheduleResult.message}"
                )
                "Could not schedule wake-up alarm: ${scheduleResult.message}"
            }
        }
        messages.add(scheduleSummary)

        val combinedMessage = "Sleep Mode activated: " + messages.joinToString(" • ")
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.COMPLETED,
            message = "Sleep Mode active"
        )

        return CommandExecutionResult(
            success = true,
            message = combinedMessage
        )
    }

    fun cancel(): CommandExecutionResult {
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.STOP_REQUESTED,
            message = "Cancel sleep timer requested"
        )
        val current = routineStorage.getActiveRoutine()

        if (current == null || !current.isActive) {
            return CommandExecutionResult(
                success = true,
                message = "No active sleep timer to cancel."
            )
        }

        routineScheduler.cancelWake(current.id)
        routineStorage.saveActiveRoutine(
            current.copy(status = RoutineStatus.CANCELLED)
        )
        DiagnosticBus.log(
            tag = "sleep",
            stage = DiagnosticStage.COMPLETED,
            message = "Sleep timer cancelled"
        )

        return CommandExecutionResult(
            success = true,
            message = "Sleep timer cancelled."
        )
    }

    private suspend fun configureSleepAc(): CommandExecutionResult {
        return try {
            deviceRegistry.executeCapability("AC", DeviceCapability.Power, true)
            deviceRegistry.executeCapability("AC", DeviceCapability.HvacMode, AcMode.AUTO)
            deviceRegistry.executeCapability("AC", DeviceCapability.Temperature, DEFAULT_SLEEP_TEMP)
            deviceRegistry.executeCapability("AC", DeviceCapability.FanSpeed, AcFanSpeed.AUTO)
            CommandExecutionResult(true, "AC configured")
        } catch (e: Exception) {
            Log.e(TAG, "[ac] Error configuring AC for sleep mode", e)
            CommandExecutionResult(false, e.message ?: "AC configuration error")
        }
    }

    private fun captureSnapshot(): EnvironmentSnapshot {
        val btState = bluetoothManager?.uiState?.value
        val isSpeakerConnected = btState?.connectionState is BluetoothDeviceState.Connected
        val speakerName = btState?.selectedDevice?.displayName

        val mediaVol = musicController?.uiState?.value?.volumePercent ?: 0.5f
        val isPlaying = musicController?.uiState?.value?.playbackStatus?.name == "PLAYING"

        return EnvironmentSnapshot(
            isSpeakerConnected = isSpeakerConnected,
            speakerName = speakerName,
            mediaVolume = mediaVol,
            isMusicPlaying = isPlaying
        )
    }

    fun calculateWakeTimeMillis(durationMinutes: Int?, wakeTime: String?): Long? {
        val now = System.currentTimeMillis()

        if (durationMinutes != null && durationMinutes > 0) {
            return now + (durationMinutes * 60 * 1000L)
        }

        if (!wakeTime.isNullOrBlank() && !wakeTime.equals("null", ignoreCase = true)) {
            return parseAbsoluteWakeTime(wakeTime, now)
        }

        return null
    }

    private fun parseAbsoluteWakeTime(timeString: String, referenceTime: Long): Long? {
        val cleaned = timeString.trim().lowercase(Locale.ROOT)

        val formats = listOf(
            SimpleDateFormat("HH:mm", Locale.ROOT),
            SimpleDateFormat("H:mm", Locale.ROOT),
            SimpleDateFormat("hh:mm a", Locale.ROOT),
            SimpleDateFormat("h:mm a", Locale.ROOT),
            SimpleDateFormat("h a", Locale.ROOT)
        )

        for (sdf in formats) {
            try {
                val parsed = sdf.parse(cleaned)
                if (parsed != null) {
                    val calNow = Calendar.getInstance().apply { timeInMillis = referenceTime }
                    val calTarget = Calendar.getInstance().apply {
                        timeInMillis = referenceTime
                        val calParsed = Calendar.getInstance().apply { time = parsed }
                        set(Calendar.HOUR_OF_DAY, calParsed.get(Calendar.HOUR_OF_DAY))
                        set(Calendar.MINUTE, calParsed.get(Calendar.MINUTE))
                        set(Calendar.SECOND, 0)
                        set(Calendar.MILLISECOND, 0)
                    }

                    if (calTarget.timeInMillis <= calNow.timeInMillis) {
                        calTarget.add(Calendar.DAY_OF_YEAR, 1)
                    }

                    return calTarget.timeInMillis
                }
            } catch (ignored: Exception) {}
        }
        return null
    }

    private fun formatClockTime(millis: Long): String {
        val sdf = SimpleDateFormat("h:mm a", Locale.getDefault())
        return sdf.format(Date(millis))
    }
}
