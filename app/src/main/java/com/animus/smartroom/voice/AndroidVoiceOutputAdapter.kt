package com.animus.smartroom.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.util.Log
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.Locale

/**
 * Clean Android implementation of [VoiceOutputPort].
 * Uses Android's native TextToSpeech engine to synthesize spoken responses.
 */
class AndroidVoiceOutputAdapter(
    private val context: Context? = null
) : VoiceOutputPort, TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "VoiceOutputAdapter"
    }

    private var tts: TextToSpeech? = null
    private var isTtsReady: Boolean = false

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
            Log.i(TAG, "SPOKEN_RESPONSE_INITIALIZED: TTS ready=$isTtsReady")
        } else {
            Log.w(TAG, "SPOKEN_RESPONSE_INITIALIZATION_FAILED: Status code $status")
            isTtsReady = false
        }
    }

    override suspend fun speak(text: String) {
        if (text.isBlank()) return
        Log.i(TAG, "SPOKEN_RESPONSE_STARTED: '$text'")
        withContext(Dispatchers.Main) {
            try {
                if (isTtsReady && tts != null) {
                    tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "Animus_TTS_${System.currentTimeMillis()}")
                    Log.i(TAG, "SPOKEN_RESPONSE_COMPLETED: Dispatched to native TTS engine")
                } else {
                    Log.i(TAG, "SPOKEN_RESPONSE_FALLBACK (TTS not ready): '$text'")
                }
            } catch (e: Exception) {
                Log.e(TAG, "SPOKEN_RESPONSE_FAILED: ${e.message}", e)
            }
        }
    }

    override fun stop() {
        Log.d(TAG, "SPOKEN_RESPONSE_STOPPED")
        try {
            tts?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping TTS: ${e.message}")
        }
    }
}
