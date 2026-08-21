package com.animus.smartroom.core.port

import kotlinx.coroutines.flow.StateFlow

/**
 * Pure JVM representation of Voice input state.
 */
sealed class VoicePortState {
    object Idle : VoicePortState()
    data class Listening(val rmsDb: Float = 0f) : VoicePortState()
    data class Recognizing(val partialText: String? = null) : VoicePortState()
    data class Success(val recognizedText: String) : VoicePortState()
    data class Error(val message: String) : VoicePortState()
    object PermissionDenied : VoicePortState()
    object Unavailable : VoicePortState()
}

/**
 * Pure JVM port for voice input interaction.
 * Implemented on Android by AndroidSpeechRecognitionAdapter.
 */
interface VoiceInputPort {
    val state: StateFlow<VoicePortState>
    fun isAvailable(): Boolean
    fun startListening()
    fun stopListening()
    fun cancel()
    fun destroy()
}
