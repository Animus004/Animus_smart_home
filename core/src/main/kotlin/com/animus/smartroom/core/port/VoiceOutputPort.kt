package com.animus.smartroom.core.port

interface VoiceOutputPort {
    suspend fun speak(text: String)
    fun stop()
}
