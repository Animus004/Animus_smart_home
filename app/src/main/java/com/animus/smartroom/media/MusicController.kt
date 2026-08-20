package com.animus.smartroom.media

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.KeyEvent
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.model.PlaybackStatus
import com.animus.smartroom.media.provider.GenericMusicProvider
import com.animus.smartroom.media.provider.MusicProvider
import com.animus.smartroom.media.provider.ProviderResult
import com.animus.smartroom.media.provider.YouTubeMusicProvider
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

        // Preset track definitions
        private const val ZARA_ZARA_TITLE = "Zara Zara"
        private const val ZARA_ZARA_ARTIST = "Bombay Jayashri"

        // Adaptive inspection intervals after launch (ms)
        private val METADATA_INSPECTION_INTERVALS_MS = listOf(1000L, 2200L, 3500L)
    }

    private val audioManager: AudioManager? =
        context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager

    private val mediaSessionManager: MediaSessionManager? =
        context.getSystemService(Context.MEDIA_SESSION_SERVICE) as? MediaSessionManager

    // Provider layer
    private val providers: Map<String, MusicProvider> = mapOf(
        YouTubeMusicProvider.PROVIDER_ID to YouTubeMusicProvider(context),
        GenericMusicProvider.PROVIDER_ID to GenericMusicProvider(context)
    )

    private var activeProvider: MusicProvider =
        providers[YouTubeMusicProvider.PROVIDER_ID] ?: GenericMusicProvider(context)

    private val _uiState = MutableStateFlow(
        MusicUiState(
            activeProviderId = activeProvider.providerId,
            activeProviderName = activeProvider.displayName
        )
    )
    val uiState: StateFlow<MusicUiState> = _uiState.asStateFlow()

    private var isReceiverRegistered = false
    private val mainHandler = Handler(Looper.getMainLooper())
    private var pendingInspectionRunnables = mutableListOf<Runnable>()

    private val volumeReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context?, intent: Intent?) {
            if (intent?.action == VOLUME_CHANGED_ACTION) {
                Log.d(TAG, "[media] System volume change broadcast received")
                refreshVolume()
            }
        }
    }

    fun startListening() {
        Log.d(TAG, "[media] startListening called")
        if (!isReceiverRegistered) {
            val filter = IntentFilter(VOLUME_CHANGED_ACTION)
            context.registerReceiver(volumeReceiver, filter)
            isReceiverRegistered = true
        }
        refreshVolume()
    }

    fun stopListening() {
        Log.d(TAG, "[media] stopListening called")
        cancelPendingInspectionAttempts()
        if (isReceiverRegistered) {
            try {
                context.unregisterReceiver(volumeReceiver)
            } catch (e: Exception) {
                Log.w(TAG, "[media] Error unregistering volume receiver", e)
            }
            isReceiverRegistered = false
        }
    }

    fun setProvider(providerId: String) {
        val provider = providers[providerId] ?: return
        activeProvider = provider
        Log.i(TAG, "[provider] Active music provider changed to: ${provider.displayName} ($providerId)")
        _uiState.update {
            it.copy(
                activeProviderId = provider.providerId,
                activeProviderName = provider.displayName
            )
        }
    }

    fun getAvailableProviders(): List<MusicProvider> = providers.values.toList()

    fun updateOutputDevice(deviceName: String?, isConnected: Boolean) {
        val displayName = when {
            deviceName.isNullOrBlank() -> "No Device Selected"
            else -> deviceName
        }
        Log.d(TAG, "[output] Output device updated: $displayName (connected=$isConnected)")

        if (!isConnected) {
            cancelPendingInspectionAttempts()
            Log.d(TAG, "[output] Bluetooth output disconnected. Cancelled all pending media inspections.")
        }

        _uiState.update {
            it.copy(
                activeOutputDeviceName = displayName,
                isOutputConnected = isConnected
            )
        }
    }

    fun setNotice(notice: String?) {
        _uiState.update { it.copy(userNotice = notice) }
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

        Log.d(TAG, "[media] Setting volume: ${(clampedPercent * 100).toInt()}% (index=$targetIndex/$max)")
        try {
            am.setStreamVolume(AudioManager.STREAM_MUSIC, targetIndex, 0)
        } catch (e: Exception) {
            Log.e(TAG, "[media] Failed to set volume index $targetIndex", e)
        }

        _uiState.update {
            it.copy(
                volumePercent = clampedPercent,
                isMuted = targetIndex == 0
            )
        }
    }

    fun play() {
        if (!_uiState.value.isOutputConnected) {
            Log.w(TAG, "[media] play() blocked: No Bluetooth audio output connected")
            setNotice("Connect ${_uiState.value.activeOutputDeviceName} to play audio")
            return
        }
        Log.d(TAG, "[media] play() requested by user")
        if (!tryMediaSessionPlay()) {
            dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY)
        }
        _uiState.update { it.copy(playbackStatus = PlaybackStatus.PLAYING, userNotice = null) }
    }

    fun pause() {
        Log.d(TAG, "[media] pause() requested by user")
        if (!tryMediaSessionPause()) {
            dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PAUSE)
        }
        _uiState.update { it.copy(playbackStatus = PlaybackStatus.PAUSED) }
    }

    fun togglePlayPause() {
        if (!_uiState.value.isOutputConnected) {
            Log.w(TAG, "[media] togglePlayPause() blocked: No Bluetooth audio output connected")
            setNotice("Connect ${_uiState.value.activeOutputDeviceName} to play audio")
            return
        }
        Log.d(TAG, "[media] togglePlayPause() requested by user")
        val currentStatus = _uiState.value.playbackStatus
        if (currentStatus == PlaybackStatus.PLAYING) {
            pause()
        } else {
            play()
        }
    }

    fun next() {
        Log.d(TAG, "[media] next() requested by user")
        if (!tryMediaSessionNext()) {
            dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_NEXT)
        }
    }

    fun previous() {
        Log.d(TAG, "[media] previous() requested by user")
        if (!tryMediaSessionPrevious()) {
            dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
        }
    }

    /**
     * Executes the "Play Zara Zara" preset via the Universal MusicProvider architecture.
     */
    fun playZaraZaraPreset(activeDeviceName: String) {
        playTrackPreset(
            title = ZARA_ZARA_TITLE,
            artist = ZARA_ZARA_ARTIST,
            activeDeviceName = activeDeviceName
        )
    }

    /**
     * Universal entry point for playing a track preset through the active MusicProvider.
     */
    fun playTrackPreset(title: String, artist: String?, activeDeviceName: String, directVideoId: String? = null) {
        val isConnected = _uiState.value.isOutputConnected
        Log.i(TAG, "[ai] Command received: PLAY_MUSIC (title='$title', artist='$artist', directVideoId='$directVideoId')")
        Log.i(TAG, "[music] Forwarding to provider: '${activeProvider.displayName}', Target Bluetooth Output: '$activeDeviceName'")

        if (!isConnected) {
            Log.w(TAG, "[music] BLOCKED: Selected Bluetooth device '$activeDeviceName' is NOT connected")
            _uiState.update {
                it.copy(userNotice = "Connect $activeDeviceName to play room audio")
            }
            return
        }

        Log.i(TAG, "[music] ALLOWED: Bluetooth device '$activeDeviceName' is connected.")
        cancelPendingInspectionAttempts()

        val result = if (!directVideoId.isNullOrBlank()) {
            Log.i(TAG, "[music] Direct video ID provided ($directVideoId). Launching direct playback.")
            (activeProvider as? YouTubeMusicProvider)?.playDirectTrack(directVideoId, title, artist)
                ?: activeProvider.searchAndPlay(title, artist)
        } else {
            activeProvider.searchAndPlay(title, artist)
        }
        Log.i(TAG, "[provider] Provider ${activeProvider.displayName} returned: ${result::class.simpleName}")

        when (result) {
            is ProviderResult.DirectPlaybackStarted -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.PLAYING,
                        currentTrackTitle = title,
                        currentTrackArtist = artist,
                        isPresetReady = false,
                        userNotice = null
                    )
                }
            }

            is ProviderResult.DirectPlayIntentLaunched -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.SEARCH_OPENED,
                        currentTrackTitle = title,
                        currentTrackArtist = artist,
                        isPresetReady = false,
                        userNotice = "Starting $title in ${activeProvider.displayName}..."
                    )
                }
                scheduleSafeSessionInspection(title, artist)
            }

            is ProviderResult.PlaybackConfirmed -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.PLAYING,
                        currentTrackTitle = title,
                        currentTrackArtist = artist,
                        isPresetReady = false,
                        userNotice = null
                    )
                }
            }

            is ProviderResult.SearchOpenedRequiresUserPlay -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.SEARCH_OPENED,
                        currentTrackTitle = title,
                        currentTrackArtist = artist,
                        isPresetReady = true,
                        userNotice = "$title is ready in ${activeProvider.displayName} — Tap Play in ${activeProvider.displayName}"
                    )
                }
                scheduleSafeSessionInspection(title, artist)
            }

            is ProviderResult.AppNotInstalled -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.ACTION_REQUIRED,
                        currentTrackTitle = title,
                        currentTrackArtist = artist,
                        isPresetReady = false,
                        userNotice = "${activeProvider.displayName} is not installed"
                    )
                }
            }

            is ProviderResult.AppInstalledButIntentUnresolvable -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.ACTION_REQUIRED,
                        currentTrackTitle = title,
                        currentTrackArtist = artist,
                        isPresetReady = false,
                        userNotice = "${activeProvider.displayName} is installed, but playback intent could not be resolved"
                    )
                }
            }

            is ProviderResult.Failed -> {
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.ACTION_REQUIRED,
                        isPresetReady = false,
                        userNotice = "Could not open ${activeProvider.displayName}: ${result.reason}"
                    )
                }
            }
        }
    }

    private fun scheduleSafeSessionInspection(expectedTitle: String, expectedArtist: String?) {
        cancelPendingInspectionAttempts()
        Log.d(TAG, "[session] Scheduling metadata inspection sequence across ${METADATA_INSPECTION_INTERVALS_MS}ms")

        var attemptCount = 0
        for (delayMs in METADATA_INSPECTION_INTERVALS_MS) {
            attemptCount++
            val currentAttempt = attemptCount
            val runnable = Runnable {
                if (!_uiState.value.isOutputConnected) {
                    Log.w(TAG, "[output] Session inspection #$currentAttempt aborted: Bluetooth output is not connected.")
                    return@Runnable
                }

                evaluateActiveSessionForTrack(currentAttempt, expectedTitle, expectedArtist)
            }
            pendingInspectionRunnables.add(runnable)
            mainHandler.postDelayed(runnable, delayMs)
        }
    }

    private fun evaluateActiveSessionForTrack(attemptIndex: Int, expectedTitle: String, expectedArtist: String?) {
        val controller = findActiveMediaController()
        if (controller == null) {
            Log.d(TAG, "[session] Attempt #$attemptIndex: No inspectable MediaController available.")
            Log.d(TAG, "[session] Refusing blind media-key dispatch to prevent resuming unrelated track.")
            return
        }

        val packageName = controller.packageName
        val metadata = controller.metadata
        val playbackState = controller.playbackState?.state

        val currentTitle = metadata?.getString(MediaMetadata.METADATA_KEY_TITLE) ?: ""
        val currentArtist = metadata?.getString(MediaMetadata.METADATA_KEY_ARTIST) ?: ""

        Log.d(TAG, "[session] Active package: $packageName")
        Log.d(TAG, "[session] Current title: $currentTitle")
        Log.d(TAG, "[session] Current artist: $currentArtist")
        Log.d(TAG, "[session] Playback state: $playbackState")

        val titleMatches = currentTitle.contains(expectedTitle, ignoreCase = true)
        val artistMatches = expectedArtist.isNullOrBlank() || currentArtist.contains(expectedArtist, ignoreCase = true) ||
                currentArtist.contains("Jayashri", ignoreCase = true) ||
                currentArtist.contains("Harris Jayaraj", ignoreCase = true)

        if (titleMatches && (artistMatches || currentArtist.isBlank())) {
            Log.i(TAG, "[music] Requested track '$expectedTitle' already active in session; PLAY allowed")
            try {
                controller.transportControls.play()
                _uiState.update {
                    it.copy(
                        playbackStatus = PlaybackStatus.PLAYING,
                        isPresetReady = false,
                        userNotice = null
                    )
                }
                cancelPendingInspectionAttempts()
            } catch (e: Exception) {
                Log.w(TAG, "[session] Error calling play() on matching session", e)
            }
        } else {
            Log.w(TAG, "[music] Refusing PLAY because active track does not match requested track (Current: '$currentTitle' by '$currentArtist')")
        }
    }

    private fun cancelPendingInspectionAttempts() {
        if (pendingInspectionRunnables.isNotEmpty()) {
            Log.d(TAG, "[session] Cancelling ${pendingInspectionRunnables.size} pending inspection attempts")
            for (r in pendingInspectionRunnables) {
                mainHandler.removeCallbacks(r)
            }
            pendingInspectionRunnables.clear()
        }
    }

    private fun tryMediaSessionPlay(): Boolean {
        val controller = findActiveMediaController() ?: return false
        return try {
            val packageName = controller.packageName
            Log.d(TAG, "[session] Found active MediaController for package: $packageName")
            controller.transportControls.play()
            Log.i(TAG, "[session] Invoked transportControls.play() on $packageName")
            true
        } catch (e: Exception) {
            Log.w(TAG, "[session] Error calling transportControls.play() on controller", e)
            false
        }
    }

    private fun tryMediaSessionPause(): Boolean {
        val controller = findActiveMediaController() ?: return false
        return try {
            controller.transportControls.pause()
            Log.i(TAG, "[session] Invoked transportControls.pause() on ${controller.packageName}")
            true
        } catch (e: Exception) {
            Log.w(TAG, "[session] Error calling transportControls.pause() on controller", e)
            false
        }
    }

    private fun tryMediaSessionNext(): Boolean {
        val controller = findActiveMediaController() ?: return false
        return try {
            controller.transportControls.skipToNext()
            Log.i(TAG, "[session] Invoked transportControls.skipToNext() on ${controller.packageName}")
            true
        } catch (e: Exception) {
            Log.w(TAG, "[session] Error calling transportControls.skipToNext()", e)
            false
        }
    }

    private fun tryMediaSessionPrevious(): Boolean {
        val controller = findActiveMediaController() ?: return false
        return try {
            controller.transportControls.skipToPrevious()
            Log.i(TAG, "[session] Invoked transportControls.skipToPrevious() on ${controller.packageName}")
            true
        } catch (e: Exception) {
            Log.w(TAG, "[session] Error calling transportControls.skipToPrevious()", e)
            false
        }
    }

    private fun findActiveMediaController(): MediaController? {
        val manager = mediaSessionManager ?: return null
        return try {
            val activeSessions = manager.getActiveSessions(null)
            if (activeSessions.isNullOrEmpty()) {
                Log.d(TAG, "[session] No active MediaSessions returned from MediaSessionManager")
                null
            } else {
                Log.d(TAG, "[session] Active MediaSessions found: ${activeSessions.map { it.packageName }}")
                // Prefer YouTube Music session if active, otherwise the first active session
                activeSessions.firstOrNull { it.packageName == YouTubeMusicProvider.PACKAGE_NAME }
                    ?: activeSessions.firstOrNull()
            }
        } catch (se: SecurityException) {
            Log.d(TAG, "[session] MediaSessionManager.getActiveSessions requires NotificationListener permission.")
            null
        } catch (e: Exception) {
            Log.w(TAG, "[session] Exception querying active MediaSessions", e)
            null
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
            Log.d(TAG, "[media] Dispatched media key code: $keyCode")
        } catch (e: Exception) {
            Log.e(TAG, "[media] Error dispatching media key code $keyCode", e)
        }
    }
}
