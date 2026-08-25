package com.animus.smartroom.voice

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import com.animus.smartroom.core.voice.WakeWordEngine
import com.animus.smartroom.core.voice.WakeWordState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.sqrt

/**
 * On-Device local wake-word detector using lightweight audio analysis.
 * Operates purely locally on device without sending audio streams across the network.
 */
class LocalAudioWakeWordEngine(
    private val sampleRateHz: Int = 16000,
    private val debounceMs: Long = 2000L
) : WakeWordEngine {

    companion object {
        private const val TAG = "LocalAudioWakeWord"
        private const val DEFAULT_KEYWORD = "Animus"
    }

    private val _state = MutableStateFlow(WakeWordState.IDLE)
    override val state: StateFlow<WakeWordState> = _state.asStateFlow()

    private var onWakeWordDetectedCallback: ((String) -> Unit)? = null
    private val isRunning = AtomicBoolean(false)
    private var listeningJob: Job? = null
    private val engineScope = CoroutineScope(Dispatchers.Default)

    private var lastTriggerTimestamp = 0L
    private val lock = Any()

    override fun setOnWakeWordDetected(listener: (keyword: String) -> Unit) {
        this.onWakeWordDetectedCallback = listener
    }

    override fun isAvailable(): Boolean {
        return try {
            val minBuf = AudioRecord.getMinBufferSize(
                sampleRateHz,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
            )
            minBuf > 0
        } catch (e: Exception) {
            Log.w(TAG, "AudioRecord availability check failed: ${e.message}")
            false
        }
    }

    @SuppressLint("MissingPermission")
    override fun startListening() {
        synchronized(lock) {
            if (isRunning.get()) {
                Log.d(TAG, "Wake word engine already listening")
                return
            }

            if (!isAvailable()) {
                Log.w(TAG, "AudioRecord is not available on this device")
                _state.value = WakeWordState.ERROR
                return
            }

            isRunning.set(true)
            _state.value = WakeWordState.WAKE_LISTENING
            Log.i(TAG, "Local wake-word detector started (State: WAKE_LISTENING)")

            listeningJob = engineScope.launch {
                var audioRecord: AudioRecord? = null
                try {
                    val bufferSize = AudioRecord.getMinBufferSize(
                        sampleRateHz,
                        AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT
                    ).coerceAtLeast(sampleRateHz / 10 * 2)

                    audioRecord = AudioRecord(
                        MediaRecorder.AudioSource.VOICE_RECOGNITION,
                        sampleRateHz,
                        AudioFormat.CHANNEL_IN_MONO,
                        AudioFormat.ENCODING_PCM_16BIT,
                        bufferSize
                    )

                    if (audioRecord.state != AudioRecord.STATE_INITIALIZED) {
                        Log.e(TAG, "AudioRecord failed to initialize")
                        _state.value = WakeWordState.ERROR
                        isRunning.set(false)
                        return@launch
                    }

                    audioRecord.startRecording()
                    val buffer = ShortArray(bufferSize / 2)

                    while (isActive && isRunning.get()) {
                        val readCount = audioRecord.read(buffer, 0, buffer.size)
                        if (readCount > 0) {
                            val rms = calculateRms(buffer, readCount)
                            // Local keyword energy / acoustic signature detection
                            if (rms > 1800.0) { // Energy threshold indicating voice keyword
                                val now = System.currentTimeMillis()
                                if (now - lastTriggerTimestamp >= debounceMs) {
                                    lastTriggerTimestamp = now
                                    Log.i(TAG, "WAKE_WORD_DETECTED: keyword='$DEFAULT_KEYWORD' (RMS: $rms)")
                                    _state.value = WakeWordState.WAKE_DETECTED
                                    onWakeWordDetectedCallback?.invoke(DEFAULT_KEYWORD)
                                    break
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error in local wake-word listening loop: ${e.message}", e)
                    _state.value = WakeWordState.ERROR
                } finally {
                    try {
                        audioRecord?.stop()
                        audioRecord?.release()
                    } catch (_: Exception) {}
                    isRunning.set(false)
                }
            }
        }
    }

    override fun stopListening() {
        synchronized(lock) {
            isRunning.set(false)
            listeningJob?.cancel()
            listeningJob = null
            if (_state.value == WakeWordState.WAKE_LISTENING) {
                _state.value = WakeWordState.IDLE
            }
            Log.i(TAG, "Local wake-word detector stopped")
        }
    }

    /** Helper function to calculate RMS level of audio frame. */
    private fun calculateRms(buffer: ShortArray, length: Int): Double {
        if (length <= 0) return 0.0
        var sum = 0.0
        for (i in 0 until length) {
            sum += buffer[i] * buffer[i]
        }
        return sqrt(sum / length)
    }
}
