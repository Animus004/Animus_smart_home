package com.animus.smartroom.core.port

import android.content.Context
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.routine.alarm.AlarmSoundPlayer

/**
 * Android implementation of [AudioPlaybackPort] delegating to [MusicController] and [AlarmSoundPlayer].
 */
class AndroidAudioPlaybackPort(
    private val context: Context,
    private val musicController: MusicController = MusicController(context)
) : AudioPlaybackPort {

    override fun play() {
        musicController.play()
    }

    override fun pause() {
        musicController.pause()
    }

    override fun togglePlayPause() {
        musicController.togglePlayPause()
    }

    override fun setVolume(percent: Float) {
        musicController.setVolume(percent)
    }

    override fun startAlarm() {
        AlarmSoundPlayer.startAlarm(context)
    }

    override fun stopAlarm() {
        AlarmSoundPlayer.stopAlarm()
    }
}
