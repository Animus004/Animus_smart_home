package com.animus.smartroom.command.model

import com.animus.smartroom.device.model.DeviceCapability

sealed class AnimusCommand {
    data class PlayMusic(
        val title: String,
        val artist: String? = null,
        val directVideoId: String? = null
    ) : AnimusCommand()

    object PauseMusic : AnimusCommand()
    object ResumeMusic : AnimusCommand()
    object NextTrack : AnimusCommand()
    object PreviousTrack : AnimusCommand()

    data class SetVolume(
        val percentage: Int
    ) : AnimusCommand()

    data class ConnectBluetoothDevice(
        val deviceName: String? = null
    ) : AnimusCommand()

    object DisconnectBluetoothDevice : AnimusCommand()

    data class SwitchBluetoothDevice(
        val deviceName: String
    ) : AnimusCommand()

    data class SetDeviceCapability(
        val target: String,
        val capability: DeviceCapability,
        val value: Any? = null
    ) : AnimusCommand()

    data class ActivateSleepMode(
        val durationMinutes: Int? = null,
        val wakeTime: String? = null
    ) : AnimusCommand()

    object CancelSleepMode : AnimusCommand()

    data class ScheduleDeviceAction(
        val target: String,
        val action: String,
        val delayMinutes: Int? = null,
        val scheduledTime: String? = null,
        val recurrence: String? = null,
        val parameters: Map<String, Any> = emptyMap()
    ) : AnimusCommand()

    data class CancelScheduledAction(
        val target: String,
        val actionType: String? = null
    ) : AnimusCommand()

    data class QueryScheduledAction(
        val target: String
    ) : AnimusCommand()

    data class UnknownCommand(
        val rawText: String
    ) : AnimusCommand()
}

data class CommandExecutionResult(
    val success: Boolean,
    val message: String
)
