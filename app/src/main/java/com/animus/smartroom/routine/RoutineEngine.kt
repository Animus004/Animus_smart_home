package com.animus.smartroom.routine

import android.app.NotificationManager
import android.content.Context
import android.util.Log
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.command.model.CommandExecutionResult
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.resolver.YouTubeMusicResolver
import com.animus.smartroom.routine.alarm.AlarmSoundPlayer
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.receiver.SleepWakeReceiver
import com.animus.smartroom.routine.scheduler.RoutineScheduler
import com.animus.smartroom.routine.sleep.SleepModeRoutine
import com.animus.smartroom.routine.storage.RoutineStorage
import kotlinx.coroutines.flow.StateFlow

class RoutineEngine(
    private val context: Context,
    deviceRegistry: DeviceRegistry,
    bluetoothManager: BluetoothAudioDeviceManager?,
    musicController: MusicController?,
    musicResolver: YouTubeMusicResolver?
) {
    companion object {
        private const val TAG = "RoutineEngine"
    }

    private val routineStorage = RoutineStorage(context.applicationContext)
    private val routineScheduler = RoutineScheduler(context.applicationContext)

    val sleepModeRoutine = SleepModeRoutine(
        deviceRegistry = deviceRegistry,
        bluetoothManager = bluetoothManager,
        musicController = musicController,
        musicResolver = musicResolver,
        routineScheduler = routineScheduler,
        routineStorage = routineStorage
    )

    // Direct binding to RoutineStorage reactive flow ensuring zero lag across Receiver, Engine & UI
    val activeRoutine: StateFlow<RoutineState?> = routineStorage.activeRoutineFlow

    init {
        restorePersistedRoutines()
    }

    fun restorePersistedRoutines() {
        val stored = routineStorage.getActiveRoutine()
        if (stored != null) {
            when {
                stored.status == RoutineStatus.ALARMING -> {
                    Log.i(TAG, "[restore] Restored ALARMING routine '${stored.id}'")
                    DiagnosticBus.log(
                        tag = "engine",
                        stage = DiagnosticStage.STATE,
                        message = "ALARMING (Restored)"
                    )
                    // Ensure alarm sound is ringing if app was reopened while alarming
                    AlarmSoundPlayer.startAlarm(context.applicationContext)
                }
                stored.status == RoutineStatus.ACTIVE && stored.scheduledWakeTime != null && stored.scheduledWakeTime <= System.currentTimeMillis() -> {
                    // When scheduled time has passed, routine MUST become ALARMING so user sees STOP UI
                    val alarming = stored.copy(status = RoutineStatus.ALARMING)
                    routineStorage.saveActiveRoutine(alarming)
                    AlarmSoundPlayer.startAlarm(context.applicationContext)
                    Log.i(TAG, "[restore] Restored expired active routine '${stored.id}' as ALARMING")
                    DiagnosticBus.log(
                        tag = "engine",
                        stage = DiagnosticStage.STATE,
                        message = "ACTIVE -> ALARMING (Expired)"
                    )
                }
                else -> {
                    Log.i(TAG, "[restore] Restored active routine '${stored.id}' (Status: ${stored.status})")
                }
            }
        }
    }

    suspend fun activateSleep(durationMinutes: Int?, wakeTime: String?): CommandExecutionResult {
        Log.i(TAG, "[engine] Activating Sleep Mode routine (duration=$durationMinutes, wakeTime='$wakeTime')")
        return sleepModeRoutine.enter(durationMinutes, wakeTime)
    }

    fun cancelSleep(): CommandExecutionResult {
        Log.i(TAG, "[engine] Cancelling Sleep Mode routine")
        return sleepModeRoutine.cancel()
    }

    fun stopAlarm(): CommandExecutionResult {
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.STOP_REQUESTED,
            message = "User pressed STOP on wake alarm"
        )
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.ALARM,
            message = "stop requested"
        )

        AlarmSoundPlayer.stopAlarm()
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.ALARM,
            message = "audio stopped"
        )

        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        notificationManager?.cancel(SleepWakeReceiver.NOTIFICATION_ID)
        DiagnosticBus.log(
            tag = "wake",
            stage = DiagnosticStage.NOTIFICATION,
            message = "dismissed"
        )

        DiagnosticBus.log(
            tag = "routine",
            stage = DiagnosticStage.STATE,
            message = "ALARMING -> COMPLETED"
        )

        val current = routineStorage.getActiveRoutine()
        if (current != null) {
            val completed = current.copy(status = RoutineStatus.COMPLETED)
            routineStorage.saveActiveRoutine(completed)
        } else {
            routineStorage.clearActiveRoutine()
        }

        DiagnosticBus.log(
            tag = "engine",
            stage = DiagnosticStage.STATE,
            message = "COMPLETED"
        )
        DiagnosticBus.log(
            tag = "ui",
            stage = DiagnosticStage.STATE,
            message = "COMPLETED"
        )

        return CommandExecutionResult(
            success = true,
            message = "Alarm stopped."
        )
    }

    fun canScheduleExactAlarms(): Boolean = routineScheduler.canScheduleExactAlarms()
}
