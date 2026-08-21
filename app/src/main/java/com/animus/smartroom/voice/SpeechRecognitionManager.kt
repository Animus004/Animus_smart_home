package com.animus.smartroom.voice

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.port.VoiceInputPort
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.diagnostics.DiagnosticBus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

/**
 * Single authoritative SpeechRecognitionManager implementing [VoiceInputPort].
 * Owned by AnimusApplication so both MainActivity and FloatingAnimusService share the exact same instance.
 *
 * Supports both on-device recognition (Android 13+ / API 33+) and cloud/system recognition services,
 * enabling background voice capture when MainActivity is minimized/destroyed.
 */
class SpeechRecognitionManager(
    private val context: Context,
    private var onResultDispatched: ((String) -> Unit)? = null
) : VoiceInputPort {

    companion object {
        private const val TAG = "SpeechRecognitionMgr"
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var speechRecognizer: SpeechRecognizer? = null

    private val _state = MutableStateFlow<VoicePortState>(VoicePortState.Idle)
    override val state: StateFlow<VoicePortState> = _state.asStateFlow()

    fun setOnResultDispatched(callback: (String) -> Unit) {
        this.onResultDispatched = callback
    }

    override fun isAvailable(): Boolean {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && SpeechRecognizer.isOnDeviceRecognitionAvailable(context)) {
                true
            } else {
                SpeechRecognizer.isRecognitionAvailable(context)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Speech recognition availability check failed", e)
            false
        }
    }

    override fun startListening() {
        mainHandler.post {
            if (!isAvailable()) {
                Log.w(TAG, "SpeechRecognizer is NOT available on this device.")
                _state.value = VoicePortState.Unavailable
                publishVoiceDiagnostic(ActionStage.FAILED, ActionStatus.FAILED, "SpeechRecognizer unavailable")
                return@post
            }

            cleanupRecognizer()

            try {
                // Prefer OnDeviceSpeechRecognizer on Android 13+ (API 33+) for seamless background execution
                val recognizer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && SpeechRecognizer.isOnDeviceRecognitionAvailable(context)) {
                    Log.i(TAG, "Creating OnDeviceSpeechRecognizer for low-latency background recognition")
                    SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
                } else {
                    Log.i(TAG, "Creating standard SpeechRecognizer")
                    SpeechRecognizer.createSpeechRecognizer(context)
                }

                speechRecognizer = recognizer.apply {
                    setRecognitionListener(createListener())
                }

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
                    }
                }

                _state.value = VoicePortState.Listening(rmsDb = 0f)
                speechRecognizer?.startListening(intent)
                Log.i(TAG, "Started speech recognition listener.")
                publishVoiceDiagnostic(ActionStage.RECEIVED, ActionStatus.IN_PROGRESS, "Microphone listening started")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start speech recognition", e)
                _state.value = VoicePortState.Error("Failed to initialize speech recognition: ${e.localizedMessage}")
                publishVoiceDiagnostic(ActionStage.FAILED, ActionStatus.FAILED, "Init failed: ${e.localizedMessage}")
            }
        }
    }

    override fun stopListening() {
        mainHandler.post {
            try {
                speechRecognizer?.stopListening()
                _state.value = VoicePortState.Recognizing()
            } catch (e: Exception) {
                Log.w(TAG, "Error while stopping speech recognition", e)
            }
        }
    }

    override fun cancel() {
        mainHandler.post {
            cleanupRecognizer()
            _state.value = VoicePortState.Idle
            publishVoiceDiagnostic(ActionStage.CANCELLED, ActionStatus.CANCELLED, "Voice input cancelled")
        }
    }

    override fun destroy() {
        mainHandler.post {
            cleanupRecognizer()
            _state.value = VoicePortState.Idle
        }
    }

    private fun cleanupRecognizer() {
        try {
            speechRecognizer?.cancel()
            speechRecognizer?.destroy()
        } catch (e: Exception) {
            Log.w(TAG, "Error cleaning up speech recognizer", e)
        } finally {
            speechRecognizer = null
        }
    }

    private fun publishVoiceDiagnostic(stage: ActionStage, status: ActionStatus, message: String) {
        DiagnosticBus.publish {
            create(
                source = ActionSource.USER_COMMAND,
                targetDevice = null,
                action = "VOICE_RECOGNITION",
                stage = stage,
                status = status,
                message = message
            )
        }
    }

    private fun createListener(): RecognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            Log.d(TAG, "onReadyForSpeech")
            _state.value = VoicePortState.Listening(rmsDb = 0f)
        }

        override fun onBeginningOfSpeech() {
            Log.d(TAG, "onBeginningOfSpeech")
            _state.value = VoicePortState.Listening(rmsDb = 0f)
        }

        override fun onRmsChanged(rmsdB: Float) {
            if (_state.value is VoicePortState.Listening) {
                _state.value = VoicePortState.Listening(rmsDb = rmsdB)
            }
        }

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            Log.d(TAG, "onEndOfSpeech")
            _state.value = VoicePortState.Recognizing()
            publishVoiceDiagnostic(ActionStage.PARSING, ActionStatus.IN_PROGRESS, "Processing speech audio")
        }

        override fun onError(errorCode: Int) {
            Log.w(TAG, "Speech recognition error code: $errorCode")
            val errorState = when (errorCode) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> VoicePortState.PermissionDenied
                SpeechRecognizer.ERROR_NO_MATCH,
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> VoicePortState.Error("I couldn't hear anything. Try again.")
                SpeechRecognizer.ERROR_NETWORK,
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> VoicePortState.Error("Network connection error.")
                SpeechRecognizer.ERROR_AUDIO -> VoicePortState.Error("Microphone audio error.")
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> VoicePortState.Error("Microphone is currently busy.")
                else -> VoicePortState.Error("Speech recognition error ($errorCode).")
            }
            _state.value = errorState
            publishVoiceDiagnostic(ActionStage.FAILED, ActionStatus.FAILED, "Speech recognition error code $errorCode")
            cleanupRecognizer()
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val recognized = matches?.firstOrNull()?.trim()

            if (!recognized.isNullOrBlank()) {
                Log.i(TAG, "Speech recognized successfully: '$recognized'")
                _state.value = VoicePortState.Success(recognized)
                publishVoiceDiagnostic(ActionStage.COMPLETED, ActionStatus.SUCCESS, "Recognized: '$recognized'")
                onResultDispatched?.invoke(recognized)
            } else {
                Log.w(TAG, "Speech results were empty.")
                _state.value = VoicePortState.Error("I couldn't hear anything. Try again.")
                publishVoiceDiagnostic(ActionStage.FAILED, ActionStatus.FAILED, "Empty speech results")
            }
            cleanupRecognizer()
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val partial = matches?.firstOrNull()?.trim()
            if (!partial.isNullOrBlank()) {
                Log.d(TAG, "Partial speech: '$partial'")
                _state.value = VoicePortState.Recognizing(partialText = partial)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
