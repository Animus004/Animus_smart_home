package com.animus.smartroom.routine.alarm

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.util.Log
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage

object AlarmSoundPlayer {
    private const val TAG = "AlarmSoundPlayer"
    private var mediaPlayer: MediaPlayer? = null

    @Synchronized
    fun startAlarm(context: Context) {
        if (mediaPlayer?.isPlaying == true) {
            Log.d(TAG, "[alarm] MediaPlayer already playing")
            return
        }

        try {
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.ALARM,
                message = "Starting local wake-up alarm sound"
            )

            var alarmUri: Uri? = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            if (alarmUri == null) {
                alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            }
            if (alarmUri == null) {
                alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            }

            val finalUri = alarmUri ?: run {
                Log.w(TAG, "[alarm] No valid alarm ringtone URI found")
                return
            }

            mediaPlayer?.release()
            mediaPlayer = MediaPlayer().apply {
                setDataSource(context.applicationContext, finalUri)
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build()
                )
                isLooping = true
                prepare()
                start()
            }
            Log.i(TAG, "[alarm] Local alarm sound started successfully")
        } catch (e: Exception) {
            Log.e(TAG, "[alarm] Failed to start alarm sound", e)
            DiagnosticBus.log(
                tag = "wake",
                stage = DiagnosticStage.FAILED,
                message = "Failed to start local alarm sound: ${e.message}"
            )
        }
    }

    @Synchronized
    fun stopAlarm() {
        try {
            if (mediaPlayer != null) {
                DiagnosticBus.log(
                    tag = "wake",
                    stage = DiagnosticStage.ALARM,
                    message = "Stopping local wake-up alarm sound"
                )
                if (mediaPlayer?.isPlaying == true) {
                    mediaPlayer?.stop()
                }
                mediaPlayer?.release()
                mediaPlayer = null
                Log.i(TAG, "[alarm] Local alarm sound stopped and released")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[alarm] Error stopping alarm sound", e)
        }
    }
}
