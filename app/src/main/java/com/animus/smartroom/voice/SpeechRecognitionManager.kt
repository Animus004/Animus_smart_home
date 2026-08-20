package com.animus.smartroom.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

class SpeechRecognitionManager(
    private val context: Context,
    private val onResultDispatched: (String) -> Unit
) {

    companion object {
        private const val TAG = "SpeechRecognitionMgr"
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var speechRecognizer: SpeechRecognizer? = null

    private val _state = MutableStateFlow<VoiceInputState>(VoiceInputState.Idle)
    val state: StateFlow<VoiceInputState> = _state.asStateFlow()

    fun isAvailable(): Boolean {
        return try {
            SpeechRecognizer.isRecognitionAvailable(context)
        } catch (e: Exception) {
            Log.w(TAG, "Speech recognition availability check failed", e)
            false
        }
    }

    fun startListening() {
        mainHandler.post {
            if (!isAvailable()) {
                Log.w(TAG, "SpeechRecognizer is NOT available on this device.")
                _state.value = VoiceInputState.Unavailable
                return@post
            }

            // Cleanup any existing instance
            cleanupRecognizer()

            try {
                speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
                    setRecognitionListener(createListener())
                }

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                }

                _state.value = VoiceInputState.Listening(rmsDb = 0f)
                speechRecognizer?.startListening(intent)
                Log.i(TAG, "Started speech recognition listener.")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start speech recognition", e)
                _state.value = VoiceInputState.Error("Failed to initialize speech recognition: ${e.localizedMessage}")
            }
        }
    }

    fun stopListening() {
        mainHandler.post {
            try {
                speechRecognizer?.stopListening()
                _state.value = VoiceInputState.Recognizing()
            } catch (e: Exception) {
                Log.w(TAG, "Error while stopping speech recognition", e)
            }
        }
    }

    fun cancel() {
        mainHandler.post {
            cleanupRecognizer()
            _state.value = VoiceInputState.Idle
        }
    }

    fun destroy() {
        mainHandler.post {
            cleanupRecognizer()
            _state.value = VoiceInputState.Idle
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

    private fun createListener(): RecognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            Log.d(TAG, "onReadyForSpeech")
            _state.value = VoiceInputState.Listening(rmsDb = 0f)
        }

        override fun onBeginningOfSpeech() {
            Log.d(TAG, "onBeginningOfSpeech")
            _state.value = VoiceInputState.Listening(rmsDb = 0f)
        }

        override fun onRmsChanged(rmsdB: Float) {
            if (_state.value is VoiceInputState.Listening) {
                _state.value = VoiceInputState.Listening(rmsDb = rmsdB)
            }
        }

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            Log.d(TAG, "onEndOfSpeech")
            _state.value = VoiceInputState.Recognizing()
        }

        override fun onError(errorCode: Int) {
            Log.w(TAG, "Speech recognition error code: $errorCode")
            val errorState = when (errorCode) {
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> VoiceInputState.PermissionDenied
                SpeechRecognizer.ERROR_NO_MATCH,
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> VoiceInputState.Error("I couldn't hear anything. Try again.")
                SpeechRecognizer.ERROR_NETWORK,
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> VoiceInputState.Error("Network connection error.")
                SpeechRecognizer.ERROR_AUDIO -> VoiceInputState.Error("Microphone audio error.")
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> VoiceInputState.Error("Microphone is currently busy.")
                else -> VoiceInputState.Error("Speech recognition error ($errorCode).")
            }
            _state.value = errorState
            cleanupRecognizer()
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val recognized = matches?.firstOrNull()?.trim()

            if (!recognized.isNullOrBlank()) {
                Log.i(TAG, "Speech recognized successfully: '$recognized'")
                _state.value = VoiceInputState.Success(recognized)
                onResultDispatched(recognized)
            } else {
                Log.w(TAG, "Speech results were empty.")
                _state.value = VoiceInputState.Error("I couldn't hear anything. Try again.")
            }
            cleanupRecognizer()
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val partial = matches?.firstOrNull()?.trim()
            if (!partial.isNullOrBlank()) {
                Log.d(TAG, "Partial speech: '$partial'")
                _state.value = VoiceInputState.Recognizing(partialText = partial)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}
