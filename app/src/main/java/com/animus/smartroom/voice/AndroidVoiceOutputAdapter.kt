package com.animus.smartroom.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Clean Android implementation of [VoiceOutputPort].
 * Uses Android's native TextToSpeech engine to synthesize spoken responses.
 * Implements [isSpeaking] tracking to provide acoustic echo / self-trigger protection for wake word.
 */
class AndroidVoiceOutputAdapter(
    private val context: Context? = null
) : VoiceOutputPort, TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "VoiceOutputAdapter"
    }

    private var tts: TextToSpeech? = null
    private var isTtsReady: Boolean = false
    private val _isSpeaking = AtomicBoolean(false)

    init {
        if (context != null) {
            try {
                tts = TextToSpeech(context.applicationContext, this)
            } catch (e: Exception) {
                Log.w(TAG, "Failed to initialize TextToSpeech: ${e.message}")
            }
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.US)
            isTtsReady = result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    _isSpeaking.set(true)
                    Log.d(TAG, "[TTS] Started speaking: $utteranceId")
                }

                override fun onDone(utteranceId: String?) {
                    _isSpeaking.set(false)
                    Log.d(TAG, "[TTS] Finished speaking: $utteranceId")
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    _isSpeaking.set(false)
                    Log.w(TAG, "[TTS] Error speaking: $utteranceId")
                }

                override fun onError(utteranceId: String?, errorCode: Int) {
                    _isSpeaking.set(false)
                    Log.w(TAG, "[TTS] Error speaking ($errorCode): $utteranceId")
                }
            })
            Log.i(TAG, "SPOKEN_RESPONSE_INITIALIZED: TTS ready=$isTtsReady")
        } else {
            Log.w(TAG, "SPOKEN_RESPONSE_INITIALIZATION_FAILED: Status code $status")
            isTtsReady = false
        }
    }

    override fun isSpeaking(): Boolean {
        return _isSpeaking.get()
    }

    override suspend fun speak(text: String) {
        if (text.isBlank()) return
        Log.i(TAG, "SPOKEN_RESPONSE_STARTED: '$text'")
        withContext(Dispatchers.Main) {
            try {
                if (isTtsReady && tts != null) {
                    _isSpeaking.set(true)
                    tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "Animus_TTS_${System.currentTimeMillis()}")
                    Log.i(TAG, "SPOKEN_RESPONSE_COMPLETED: Dispatched to native TTS engine")
                } else {
                    Log.i(TAG, "SPOKEN_RESPONSE_FALLBACK (TTS not ready): '$text'")
                }
            } catch (e: Exception) {
                _isSpeaking.set(false)
                Log.e(TAG, "SPOKEN_RESPONSE_FAILED: ${e.message}", e)
            }
        }
    }

    override fun stop() {
        Log.d(TAG, "SPOKEN_RESPONSE_STOPPED")
        _isSpeaking.set(false)
        try {
            tts?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping TTS: ${e.message}")
        }
    }
}

