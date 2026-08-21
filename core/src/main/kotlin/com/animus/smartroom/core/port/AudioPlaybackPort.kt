package com.animus.smartroom.core.port

/**
 * Platform-independent audio playback, volume, and alarm port interface.
 */
interface AudioPlaybackPort {
    fun play()
    fun pause()
    fun togglePlayPause()
    fun setVolume(percent: Float)
    fun startAlarm()
    fun stopAlarm()
}
