package com.animus.smartroom.core.voice

import kotlinx.coroutines.flow.StateFlow

/**
 * Authoritative interface for on-device, local wake-word detection engines.
 * Operates purely locally without streaming audio to the backend.
 */
interface WakeWordEngine {
    val state: StateFlow<WakeWordState>
    fun startListening()
    fun stopListening()
    fun setOnWakeWordDetected(listener: (keyword: String) -> Unit)
    fun isAvailable(): Boolean
}
