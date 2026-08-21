package com.animus.smartroom.brain.model

data class BrainCommandDto(
    val command: String,
    val title: String? = null,
    val artist: String? = null,
    val target: String? = null,
    val capability: String? = null,
    val value: Int? = null,
    val valueString: String? = null,
    val action: String? = null,
    val delayMinutes: Int? = null,
    val scheduledTime: String? = null,
    val recurrence: String? = null,
    val durationMinutes: Int? = null,
    val wakeTime: String? = null,
    val playbackUrl: String? = null,
    val directVideoId: String? = null,
    val rawText: String? = null,
    val parameters: Map<String, Any> = emptyMap()
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
        const val CMD_SET_DEVICE = "SET_DEVICE"
        const val CMD_SET_DEVICE_CAPABILITY = "SET_DEVICE_CAPABILITY"
        const val CMD_SET_AC = "SET_AC"
        const val CMD_SLEEP_MODE = "SLEEP_MODE"
        const val CMD_CANCEL_SLEEP = "CANCEL_SLEEP"
        const val CMD_SCHEDULE_DEVICE_ACTION = "SCHEDULE_DEVICE_ACTION"
        const val CMD_CANCEL_SCHEDULED_ACTION = "CANCEL_SCHEDULED_ACTION"
        const val CMD_QUERY_SCHEDULED_ACTION = "QUERY_SCHEDULED_ACTION"
        const val CMD_UNKNOWN = "UNKNOWN"
    }
}
