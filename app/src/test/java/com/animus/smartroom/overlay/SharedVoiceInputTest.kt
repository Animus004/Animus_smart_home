package com.animus.smartroom.overlay

import com.animus.smartroom.core.port.VoiceInputPort
import com.animus.smartroom.core.port.VoicePortState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.junit.Assert.*
import org.junit.Test

class SharedVoiceInputTest {

    class FakeVoiceInputPort : VoiceInputPort {
        private val _state = MutableStateFlow<VoicePortState>(VoicePortState.Idle)
        override val state: StateFlow<VoicePortState> = _state.asStateFlow()
        var startCount = 0
        var stopCount = 0
        var cancelCount = 0

        override fun isAvailable(): Boolean = true
        override fun startListening() {
            startCount++
            _state.value = VoicePortState.Listening(15.0f)
        }
        override fun stopListening() {
            stopCount++
            _state.value = VoicePortState.Recognizing("Set AC to 24")
        }
        override fun cancel() {
            cancelCount++
            _state.value = VoicePortState.Idle
        }
        override fun destroy() {
            _state.value = VoicePortState.Idle
        }
        fun simulateResult(text: String) {
            _state.value = VoicePortState.Success(text)
            _state.value = VoicePortState.Idle
        }
    }

    @Test
    fun `shared voice port transitions and releases microphone cleanly`() {
        val voicePort = FakeVoiceInputPort()
        assertEquals(VoicePortState.Idle, voicePort.state.value)

        // Floating overlay triggers mic
        voicePort.startListening()
        assertEquals(1, voicePort.startCount)
        assertTrue(voicePort.state.value is VoicePortState.Listening)

        // Audio stops
        voicePort.stopListening()
        assertEquals(1, voicePort.stopCount)
        assertTrue(voicePort.state.value is VoicePortState.Recognizing)

        // Result received & released
        voicePort.simulateResult("Turn off ac")
        assertEquals(VoicePortState.Idle, voicePort.state.value)
    }
}
