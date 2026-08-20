package com.animus.smartroom.brain.model

data class BrainCommandDto(
    val command: String,
    val title: String? = null,
    val artist: String? = null,
    val target: String? = null,
    val value: Int? = null,
    val playbackUrl: String? = null,
    val directVideoId: String? = null,
    val rawText: String? = null
) {
    companion object {
        const val CMD_PLAY_MUSIC = "PLAY_MUSIC"
        const val CMD_PAUSE_MUSIC = "PAUSE_MUSIC"
        const val CMD_RESUME_MUSIC = "RESUME_MUSIC"
        const val CMD_NEXT_TRACK = "NEXT_TRACK"
        const val CMD_PREVIOUS_TRACK = "PREVIOUS_TRACK"
        const val CMD_SET_VOLUME = "SET_VOLUME"
        const val CMD_CONNECT_BLUETOOTH = "CONNECT_BLUETOOTH_DEVICE"
        const val CMD_DISCONNECT_BLUETOOTH = "DISCONNECT_BLUETOOTH_DEVICE"
        const val CMD_SWITCH_BLUETOOTH = "SWITCH_BLUETOOTH_DEVICE"
        const val CMD_UNKNOWN = "UNKNOWN"
    }
}
