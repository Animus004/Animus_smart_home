package com.animus.smartroom.command.model

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

    data class UnknownCommand(
        val rawText: String
    ) : AnimusCommand()
}

data class CommandExecutionResult(
    val success: Boolean,
    val message: String
)
