package com.animus.smartroom.voice

sealed interface VoiceInputState {
    data object Idle : VoiceInputState
    data class Listening(val rmsDb: Float = 0f) : VoiceInputState
    data class Recognizing(val partialText: String = "") : VoiceInputState
    data class Success(val recognizedText: String) : VoiceInputState
    data class Error(val message: String) : VoiceInputState
    data object Unavailable : VoiceInputState
    data object PermissionDenied : VoiceInputState
}
