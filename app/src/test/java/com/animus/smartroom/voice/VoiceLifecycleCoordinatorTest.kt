package com.animus.smartroom.voice

import com.animus.smartroom.brain.AnimusBrain
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.core.port.VoiceInputPort
import com.animus.smartroom.core.port.VoiceOutputPort
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.core.runtime.RuntimeControlPort
import com.animus.smartroom.core.voice.WakeWordEngine
import com.animus.smartroom.core.voice.WakeWordState
import com.animus.smartroom.runtime.RuntimeControlPortImpl
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class VoiceLifecycleCoordinatorTest {

    private lateinit var fakeWakeWordEngine: FakeWakeWordEngine
    private lateinit var fakeSpeechRecognitionManager: FakeSpeechRecognitionManager
    private lateinit var fakeVoiceOutputPort: FakeVoiceOutputPort
    private lateinit var fakeRuntimeControlPort: FakeRuntimeControlPort

    @Before
    fun setUp() {
        fakeWakeWordEngine = FakeWakeWordEngine()
        fakeSpeechRecognitionManager = FakeSpeechRecognitionManager()
        fakeVoiceOutputPort = FakeVoiceOutputPort()
        fakeRuntimeControlPort = FakeRuntimeControlPort()
    }

    @Test
    fun testCoordinatorDisabledByDefaultPreservesIdle() {
        val coordinator = VoiceLifecycleCoordinator(
            wakeWordEngine = fakeWakeWordEngine,
            speechRecognitionManager = fakeSpeechRecognitionManager,
            runtimeControlPort = fakeRuntimeControlPort,
            voiceOutputPort = fakeVoiceOutputPort,
            configStorage = null, // Default disabled
            dispatcher = kotlinx.coroutines.Dispatchers.Unconfined
        )

        coordinator.startCoordinator()
        assertEquals(WakeWordState.IDLE, coordinator.currentState.value)
        assertFalse(fakeWakeWordEngine.isListening)
    }

    @Test
    fun testWakeWordTriggerStartsRecognitionCycle() = runBlocking {
        var submittedCommand: String? = null
        fakeRuntimeControlPort.onSubmit = { cmd ->
            submittedCommand = cmd
            BrainResult.RemoteAgentSuccess(
                agentMessage = "AC is at 24.",
                understoodIntent = "CLIMATE_ADJUSTMENT",
                actionTaken = true
            )
        }

        // Simulating wake word trigger
        var wakeCallback: ((String) -> Unit)? = null
        fakeWakeWordEngine.onSetCallback = { cb -> wakeCallback = cb }

        val coordinator = VoiceLifecycleCoordinator(
            wakeWordEngine = fakeWakeWordEngine,
            speechRecognitionManager = fakeSpeechRecognitionManager,
            runtimeControlPort = fakeRuntimeControlPort,
            voiceOutputPort = fakeVoiceOutputPort,
            configStorage = null,
            dispatcher = kotlinx.coroutines.Dispatchers.Unconfined
        )

        // Trigger wake callback
        fakeWakeWordEngine.triggerWake("Animus")
        assertTrue(fakeWakeWordEngine.stopListeningCalled)
    }

    @Test
    fun testEchoProtectionIgnoresWakeWhenTtsIsSpeaking() {
        fakeVoiceOutputPort.speaking = true

        val coordinator = VoiceLifecycleCoordinator(
            wakeWordEngine = fakeWakeWordEngine,
            speechRecognitionManager = fakeSpeechRecognitionManager,
            runtimeControlPort = fakeRuntimeControlPort,
            voiceOutputPort = fakeVoiceOutputPort,
            configStorage = null,
            dispatcher = kotlinx.coroutines.Dispatchers.Unconfined
        )

        fakeWakeWordEngine.triggerWake("Animus")
        // Wake word should be completely ignored because TTS is speaking
        assertFalse(fakeWakeWordEngine.stopListeningCalled)
        assertEquals(WakeWordState.IDLE, coordinator.currentState.value)
    }

    @Test
    fun testStopCoordinatorReleasesAllResources() {
        val coordinator = VoiceLifecycleCoordinator(
            wakeWordEngine = fakeWakeWordEngine,
            speechRecognitionManager = fakeSpeechRecognitionManager,
            runtimeControlPort = fakeRuntimeControlPort,
            voiceOutputPort = fakeVoiceOutputPort,
            configStorage = null,
            dispatcher = kotlinx.coroutines.Dispatchers.Unconfined
        )

        coordinator.stopCoordinator()
        assertTrue(fakeWakeWordEngine.stopListeningCalled)
        assertEquals(WakeWordState.IDLE, coordinator.currentState.value)
    }

    // --- Fake Test Implementations ---

    private class FakeWakeWordEngine : WakeWordEngine {
        private val _state = MutableStateFlow(WakeWordState.IDLE)
        override val state: StateFlow<WakeWordState> = _state.asStateFlow()
        var isListening = false
        var stopListeningCalled = false
        var onSetCallback: (((String) -> Unit) -> Unit)? = null
        private var listener: ((String) -> Unit)? = null

        override fun startListening() {
            isListening = true
            _state.value = WakeWordState.WAKE_LISTENING
        }

        override fun stopListening() {
            isListening = false
            stopListeningCalled = true
            _state.value = WakeWordState.IDLE
        }

        override fun setOnWakeWordDetected(listener: (keyword: String) -> Unit) {
            this.listener = listener
            onSetCallback?.invoke(listener)
        }

        override fun isAvailable(): Boolean = true

        fun triggerWake(keyword: String) {
            listener?.invoke(keyword)
        }
    }

    private class FakeSpeechRecognitionManager : VoiceInputPort {
        val _state = MutableStateFlow<VoicePortState>(VoicePortState.Idle)
        override val state: StateFlow<VoicePortState> = _state.asStateFlow()
        var startCalled = false
        var cancelCalled = false

        override fun isAvailable(): Boolean = true

        override fun startListening() {
            startCalled = true
            _state.value = VoicePortState.Listening(0f)
        }

        override fun stopListening() {
            _state.value = VoicePortState.Recognizing()
        }

        override fun cancel() {
            cancelCalled = true
            _state.value = VoicePortState.Idle
        }

        override fun destroy() {
            cancel()
        }
    }

    private class FakeVoiceOutputPort : VoiceOutputPort {
        var speaking = false
        var spokenText: String? = null

        override suspend fun speak(text: String) {
            spokenText = text
        }

        override fun stop() {
            speaking = false
        }

        override fun isSpeaking(): Boolean = speaking
    }

    private class FakeRuntimeControlPort : RuntimeControlPort {
        var onSubmit: ((String) -> BrainResult)? = null

        override suspend fun submitCommand(input: String): BrainResult {
            return onSubmit?.invoke(input) ?: BrainResult.Success(emptyList())
        }

        override suspend fun cancelAction(actionId: String): Boolean = true
    }
}
