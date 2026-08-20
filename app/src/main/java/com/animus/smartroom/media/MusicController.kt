package com.animus.smartroom.media

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioManager
import android.net.Uri
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.model.PlaybackStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class MusicController(
    private val context: Context
) {
    companion object {
        private const val TAG = "MusicController"
        private const val VOLUME_CHANGED_ACTION = "android.media.VOLUME_CHANGED_ACTION"
        private const val YOUTUBE_MUSIC_PACKAGE = "com.google.android.apps.youtube.music"
        private const val ZARA_ZARA_SEARCH_URI = "https://music.youtube.com/search?q=Zara+Zara"
    }

    private val audioManager: AudioManager? =
        context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager

    private val _uiState = MutableStateFlow(MusicUiState())
    val uiState: StateFlow<MusicUiState> = _uiState.asStateFlow()

    private var isReceiverRegistered = false

    private val volumeReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context?, intent: Intent?) {
            if (intent?.action == VOLUME_CHANGED_ACTION) {
                refreshVolume()
            }
        }
    }

    fun startListening() {
        if (!isReceiverRegistered) {
            val filter = IntentFilter(VOLUME_CHANGED_ACTION)
            context.registerReceiver(volumeReceiver, filter)
            isReceiverRegistered = true
        }
        refreshVolume()
    }

    fun stopListening() {
        if (isReceiverRegistered) {
            try {
                context.unregisterReceiver(volumeReceiver)
            } catch (e: Exception) {
                Log.w(TAG, "Error unregistering volume receiver", e)
            }
            isReceiverRegistered = false
        }
    }

    fun updateOutputDevice(deviceName: String?, isConnected: Boolean) {
        val displayName = when {
            deviceName.isNullOrBlank() -> "No Device Selected"
            else -> deviceName
        }
        _uiState.update {
            it.copy(
                activeOutputDeviceName = displayName,
                isOutputConnected = isConnected
            )
        }
    }

    fun refreshVolume() {
        val am = audioManager ?: return
        val current = am.getStreamVolume(AudioManager.STREAM_MUSIC)
        val max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(1)
        val percent = (current.toFloat() / max.toFloat()).coerceIn(0f, 1f)
        val isMuted = current == 0

        _uiState.update {
            it.copy(
                volumePercent = percent,
                isMuted = isMuted
            )
        }
    }

    fun setVolume(percent: Float) {
        val am = audioManager ?: return
        val clampedPercent = percent.coerceIn(0f, 1f)
        val max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val targetIndex = (clampedPercent * max).toInt().coerceIn(0, max)

        try {
            am.setStreamVolume(AudioManager.STREAM_MUSIC, targetIndex, 0)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to set volume index $targetIndex", e)
        }

        _uiState.update {
            it.copy(
                volumePercent = clampedPercent,
                isMuted = targetIndex == 0
            )
        }
    }

    fun play() {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY)
        _uiState.update { it.copy(playbackStatus = PlaybackStatus.PLAYING) }
    }

    fun pause() {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PAUSE)
        _uiState.update { it.copy(playbackStatus = PlaybackStatus.PAUSED) }
    }

    fun togglePlayPause() {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
        _uiState.update {
            val newStatus = if (it.playbackStatus == PlaybackStatus.PLAYING) {
                PlaybackStatus.PAUSED
            } else {
                PlaybackStatus.PLAYING
            }
            it.copy(playbackStatus = newStatus)
        }
    }

    fun next() {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_NEXT)
    }

    fun previous() {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
    }

    fun playZaraZaraPreset() {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(ZARA_ZARA_SEARCH_URI)).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        // Try targeting YouTube Music directly if installed
        val packageManager = context.packageManager
        val ytMusicIntent = Intent(Intent.ACTION_VIEW, Uri.parse(ZARA_ZARA_SEARCH_URI)).apply {
            setPackage(YOUTUBE_MUSIC_PACKAGE)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        try {
            if (ytMusicIntent.resolveActivity(packageManager) != null) {
                context.startActivity(ytMusicIntent)
            } else {
                context.startActivity(intent)
            }
            _uiState.update {
                it.copy(
                    playbackStatus = PlaybackStatus.PLAYING,
                    currentTrackTitle = "Zara Zara",
                    currentTrackArtist = "Rehnaa Hai Terre Dil Mein"
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error opening Zara Zara preset", e)
            _uiState.update {
                it.copy(userNotice = "Could not launch music player for preset.")
            }
        }
    }

    private fun dispatchMediaKey(keyCode: Int) {
        val am = audioManager ?: return
        val eventTime = SystemClock.uptimeMillis()
        try {
            val down = KeyEvent(eventTime, eventTime, KeyEvent.ACTION_DOWN, keyCode, 0)
            val up = KeyEvent(eventTime, eventTime, KeyEvent.ACTION_UP, keyCode, 0)
            am.dispatchMediaKeyEvent(down)
            am.dispatchMediaKeyEvent(up)
            Log.d(TAG, "Dispatched media key code: $keyCode")
        } catch (e: Exception) {
            Log.e(TAG, "Error dispatching media key code $keyCode", e)
        }
    }
}
