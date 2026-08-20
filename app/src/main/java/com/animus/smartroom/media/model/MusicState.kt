package com.animus.smartroom.media.model

enum class PlaybackStatus {
    IDLE,
    PLAYING,
    PAUSED,
    BUFFERING
}

data class MusicUiState(
    val playbackStatus: PlaybackStatus = PlaybackStatus.IDLE,
    val currentTrackTitle: String? = null,
    val currentTrackArtist: String? = null,
    val volumePercent: Float = 0.5f,
    val isMuted: Boolean = false,
    val activeOutputDeviceName: String = "No Device Selected",
    val isOutputConnected: Boolean = false,
    val userNotice: String? = null
)
