package com.animus.smartroom.media.model

enum class PlaybackStatus {
    IDLE,
    PLAYING,
    PAUSED,
    BUFFERING,
    SEARCH_OPENED,
    ACTION_REQUIRED
}

data class MusicUiState(
    val playbackStatus: PlaybackStatus = PlaybackStatus.IDLE,
    val currentTrackTitle: String? = null,
    val currentTrackArtist: String? = null,
    val volumePercent: Float = 0.5f,
    val isMuted: Boolean = false,
    val activeOutputDeviceName: String = "No Device Selected",
    val isOutputConnected: Boolean = false,
    val activeProviderId: String = "youtube_music",
    val activeProviderName: String = "YouTube Music",
    val isPresetReady: Boolean = false,
    val userNotice: String? = null
)
