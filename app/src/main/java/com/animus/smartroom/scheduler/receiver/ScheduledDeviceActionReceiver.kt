package com.animus.smartroom.scheduler.receiver

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.PowerManager
import android.util.Log
import com.animus.smartroom.AnimusApplication
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class ScheduledDeviceActionReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "ScheduledActionReceiver"
        private const val WAKE_LOCK_TAG = "animus:scheduled_action_wakelock"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val actionId = intent.getStringExtra(DeviceSchedulerEngine.EXTRA_ACTION_ID)
            ?: intent.getStringExtra("action_id")
            ?: intent.getStringExtra("extra_action_id")
        Log.i(TAG, "[receiver] onReceive called with actionId='$actionId', intentAction='${intent.action}'")

        if (actionId.isNullOrBlank()) {
            Log.e(TAG, "[receiver] Missing actionId extra in broadcast intent")
            return
        }

        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.TRIGGERED,
            message = "Triggered scheduled action: $actionId"
        )

        val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
        val wakeLock = powerManager?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, WAKE_LOCK_TAG)?.apply {
            acquire(30_000L) // 30-second bounded wakelock for network write + readback
        }

        val pendingResult = goAsync()

        CoroutineScope(Dispatchers.IO).launch {
            try {
                executeScheduledDeviceAction(context.applicationContext, actionId)
            } catch (e: Exception) {
                Log.e(TAG, "[receiver] Error executing scheduled action $actionId", e)
                DiagnosticBus.log(
                    tag = "scheduler",
                    stage = DiagnosticStage.FAILED,
                    message = "Execution exception: ${e.message}"
                )
            } finally {
                wakeLock?.let {
                    if (it.isHeld) it.release()
                }
                pendingResult.finish()
            }
        }
    }

    private suspend fun executeScheduledDeviceAction(appContext: Context, actionId: String) {
        val storage = ScheduledActionStorage(appContext)
        val action = storage.getAction(actionId)

        if (action == null) {
            Log.e(TAG, "[receiver] Action $actionId not found in storage.")
            DiagnosticBus.log(
                tag = "scheduler",
                stage = DiagnosticStage.FAILED,
                message = "Action $actionId not found in storage."
            )
            return
        }

        if (action.status == ScheduledActionStatus.CANCELLED) {
            Log.i(TAG, "[receiver] Action $actionId was cancelled. Aborting execution.")
            return
        }

        storage.updateStatus(actionId, ScheduledActionStatus.EXECUTING)
        DiagnosticBus.log(
            tag = "scheduler",
            stage = DiagnosticStage.EXECUTING,
            message = "Executing ${action.targetDeviceType} -> ${action.actionType}"
        )

        val app = appContext as? AnimusApplication
        val deviceRegistry = app?.deviceRegistry
        val tuyaAcAdapter = app?.tuyaAcAdapter

        when (action.targetDeviceType) {
            DeviceType.AIR_CONDITIONER -> {
                if (tuyaAcAdapter == null) {
                    val msg = "TuyaAirConditionerAdapter is unavailable."
                    storage.updateStatus(actionId, ScheduledActionStatus.FAILED, msg)
                    DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = msg)
                    return
                }

                val acDevice = deviceRegistry?.devices?.value?.values?.firstOrNull { it.type == DeviceType.AIR_CONDITIONER }
                if (acDevice == null) {
                    val msg = "Registered AC device not found in DeviceRegistry."
                    storage.updateStatus(actionId, ScheduledActionStatus.FAILED, msg)
                    DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = msg)
                    return
                }

                // 1. Live Readback Check (Deterministic Manual Override)
                val refreshedState = tuyaAcAdapter.refreshState(acDevice.id).getOrNull()
                val currentState = refreshedState ?: tuyaAcAdapter.acState.value
                val isPowerOff = action.actionType == DeviceActionType.POWER_OFF
                val isPowerOn = action.actionType == DeviceActionType.POWER_ON

                if (isPowerOff && refreshedState != null && !currentState.power) {
                    Log.i(TAG, "[ac] AC is already physically OFF. Marking COMPLETED_WITH_NO_CHANGE.")
                    storage.updateStatus(actionId, ScheduledActionStatus.COMPLETED_WITH_NO_CHANGE)
                    DiagnosticBus.log(
                        tag = "ac",
                        stage = DiagnosticStage.COMPLETED,
                        message = "AC already OFF. Completed with no change."
                    )
                    handleRecurrence(appContext, action)
                    return
                }

                if (isPowerOn && refreshedState != null && currentState.power) {
                    Log.i(TAG, "[ac] AC is already physically ON. Marking COMPLETED_WITH_NO_CHANGE.")
                    storage.updateStatus(actionId, ScheduledActionStatus.COMPLETED_WITH_NO_CHANGE)
                    DiagnosticBus.log(
                        tag = "ac",
                        stage = DiagnosticStage.COMPLETED,
                        message = "AC already ON. Completed with no change."
                    )
                    handleRecurrence(appContext, action)
                    return
                }

                // 2. Execute AC Command

                val commandResult = when (action.actionType) {
                    DeviceActionType.POWER_ON -> tuyaAcAdapter.executeCapability(acDevice, DeviceCapability.Power, true)
                    DeviceActionType.POWER_OFF -> tuyaAcAdapter.executeCapability(acDevice, DeviceCapability.Power, false)
                    DeviceActionType.SET_TEMPERATURE -> {
                        val temp = action.parameters["temperature"] as? Int ?: 24
                        tuyaAcAdapter.executeCapability(acDevice, DeviceCapability.Temperature, temp)
                    }
                    DeviceActionType.SET_MODE -> {
                        val modeStr = action.parameters["mode"] as? String ?: "COOL"
                        val mode = AcMode.fromString(modeStr) ?: AcMode.COOL
                        tuyaAcAdapter.executeCapability(acDevice, DeviceCapability.HvacMode, mode)
                    }
                    DeviceActionType.SET_FAN_SPEED -> {
                        val fanStr = action.parameters["fanSpeed"] as? String ?: "AUTO"
                        val fan = AcFanSpeed.fromString(fanStr) ?: AcFanSpeed.AUTO
                        tuyaAcAdapter.executeCapability(acDevice, DeviceCapability.FanSpeed, fan)
                    }
                    else -> {
                        com.animus.smartroom.device.model.DeviceCommandResult(false, "Unsupported action ${action.actionType}")
                    }
                }

                // 3. Evaluate Result & Readback Verification
                if (commandResult.success) {
                    storage.updateStatus(actionId, ScheduledActionStatus.COMPLETED)
                    DiagnosticBus.log(
                        tag = "ac",
                        stage = DiagnosticStage.COMPLETED,
                        message = "Successfully executed and verified ${action.actionType}"
                    )
                    handleRecurrence(appContext, action)
                } else {
                    storage.updateStatus(actionId, ScheduledActionStatus.FAILED, commandResult.message)
                    DiagnosticBus.log(
                        tag = "ac",
                        stage = DiagnosticStage.FAILED,
                        message = "Execution/verification failed: ${commandResult.message}"
                    )
                }
            }

            DeviceType.BLUETOOTH_AUDIO -> {
                val btController = app?.bluetoothController
                val musicController = app?.musicController

                when (action.actionType) {
                    DeviceActionType.CONNECT -> {
                        btController?.connect()
                        storage.updateStatus(actionId, ScheduledActionStatus.COMPLETED)
                    }
                    DeviceActionType.DISCONNECT -> {
                        btController?.disconnect()
                        storage.updateStatus(actionId, ScheduledActionStatus.COMPLETED)
                    }
                    DeviceActionType.PAUSE_MUSIC -> {
                        musicController?.pause()
                        storage.updateStatus(actionId, ScheduledActionStatus.COMPLETED)
                    }
                    else -> {
                        storage.updateStatus(actionId, ScheduledActionStatus.FAILED, "Unsupported Bluetooth action")
                    }
                }
                handleRecurrence(appContext, action)
            }

            else -> {
                storage.updateStatus(actionId, ScheduledActionStatus.FAILED, "Unsupported device type: ${action.targetDeviceType}")
            }
        }
    }

    private fun handleRecurrence(context: Context, action: com.animus.smartroom.scheduler.model.ScheduledDeviceAction) {
        val recurrence = action.recurrenceRule ?: return
        if (recurrence.frequency.equals("DAILY", ignoreCase = true)) {
            val nextTime = action.scheduledExecutionTimeMillis + (24 * 60 * 60 * 1000L)
            Log.i(TAG, "[recurrence] Re-scheduling daily action ${action.id} for next occurrence at $nextTime")
            val engine = DeviceSchedulerEngine(context)
            engine.scheduleAction(
                targetDeviceType = action.targetDeviceType,
                actionType = action.actionType,
                parameters = action.parameters,
                recurrence = recurrence.frequency,
                explicitTimeMillis = nextTime
            )
        }
    }
}
