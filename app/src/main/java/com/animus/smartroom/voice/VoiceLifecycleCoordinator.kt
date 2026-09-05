package com.animus.smartroom.voice

import android.util.Log
import com.animus.smartroom.core.port.VoiceInputPort
import com.animus.smartroom.core.port.VoiceOutputPort
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.core.runtime.RuntimeControlPort
import com.animus.smartroom.core.voice.WakeWordEngine
import com.animus.smartroom.core.voice.WakeWordState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Authoritative lifecycle coordinator for hands-free wake word, speech recognition, and response delivery.
 *
 * Enforces:
 * 1. Single microphone owner at any given time (arbitrated hand-off between WakeWordEngine and SpeechRecognitionManager).
 * 2. Acoustic echo / self-trigger protection (disables wake detection while VoiceOutputPort is actively speaking).
 * 3. Automatic transition cycle: WAKE_LISTENING -> WAKE_DETECTED -> CAPTURING_COMMAND -> PROCESSING_COMMAND -> SPEAKING_RESPONSE -> WAKE_LISTENING.
 * 4. Zero duplicate physical execution (submits purely to RuntimeControlPort).
 */
class VoiceLifecycleCoordinator(
    private val wakeWordEngine: WakeWordEngine,
    private val speechRecognitionManager: VoiceInputPort,
    private val runtimeControlPort: RuntimeControlPort,
    private val voiceOutputPort: VoiceOutputPort? = null,
    private val configStorage: VoiceWakeWordConfigStorage? = null,
    dispatcher: kotlinx.coroutines.CoroutineDispatcher = Dispatchers.Main
) {
    companion object {
        private const val TAG = "VoiceLifecycleCoord"
        private const val DEBOUNCE_COOLDOWN_MS = 1500L
    }

    private val _currentState = MutableStateFlow(WakeWordState.IDLE)
    val currentState: StateFlow<WakeWordState> = _currentState.asStateFlow()

    private val coordinatorScope = CoroutineScope(dispatcher)
    private var activeCycleJob: Job? = null
    private val isCycleActive = AtomicBoolean(false)
    private var lastWakeTimestamp = 0L

    init {
        // Wire wake-word detection callback
        wakeWordEngine.setOnWakeWordDetected { keyword ->
            handleWakeWordDetected(keyword)
        }

        // Monitor speech recognition state changes
        coordinatorScope.launch {
            speechRecognitionManager.state.collectLatest { sttState ->
                handleSttStateChange(sttState)
            }
        }
    }

    /**
     * Start the continuous hands-free voice lifecycle if enabled by configuration.
     */
    fun startCoordinator() {
        val enabled = configStorage?.isWakeWordEnabled() ?: false
        if (!enabled) {
            Log.i(TAG, "[coordinator] Wake word disabled by configuration (Manual mode active)")
            _currentState.value = WakeWordState.IDLE
            return
        }

        Log.i(TAG, "[coordinator] Starting continuous hands-free voice coordinator")
        transitionToWakeListening()
    }

    /**
     * Stop the continuous hands-free voice lifecycle and release microphone resources.
     */
    fun stopCoordinator() {
        Log.i(TAG, "[coordinator] Stopping continuous voice coordinator")
        isCycleActive.set(false)
        activeCycleJob?.cancel()
        wakeWordEngine.stopListening()
        speechRecognitionManager.cancel()
        _currentState.value = WakeWordState.IDLE
    }

    private fun handleWakeWordDetected(keyword: String) {
        val now = System.currentTimeMillis()
        if (now - lastWakeTimestamp < DEBOUNCE_COOLDOWN_MS) {
            Log.w(TAG, "[coordinator] Wake event debounced (cooldown active)")
            return
        }

        // Echo protection: Do not trigger if Animus is speaking its own response
        if (voiceOutputPort?.isSpeaking() == true) {
            Log.w(TAG, "[coordinator] Wake word ignored: VoiceOutputPort is actively speaking (Echo protection)")
            return
        }

        if (isCycleActive.getAndSet(true)) {
            Log.w(TAG, "[coordinator] Wake word ignored: Active recognition cycle already in progress")
            return
        }

        lastWakeTimestamp = now
        Log.i(TAG, "[coordinator] WAKE_DETECTED: keyword='$keyword'")
        _currentState.value = WakeWordState.WAKE_DETECTED

        // Step 1: Release microphone from wake-word engine
        wakeWordEngine.stopListening()

        // Step 2: Hand off microphone ownership to SpeechRecognizer for command capture
        activeCycleJob = coordinatorScope.launch {
            delay(150L) // Brief inter-driver audio buffer drain
            _currentState.value = WakeWordState.CAPTURING_COMMAND
            Log.i(TAG, "[coordinator] CAPTURING_COMMAND: Handing mic to SpeechRecognitionManager")
            speechRecognitionManager.startListening()
        }
    }

    private fun handleSttStateChange(sttState: VoicePortState) {
        when (sttState) {
            is VoicePortState.Success -> {
                val utterance = sttState.recognizedText
                Log.i(TAG, "[coordinator] STT succeeded: '$utterance'")
                processUserCommand(utterance)
            }
            is VoicePortState.Error -> {
                Log.w(TAG, "[coordinator] STT error: ${sttState.message}")
                recoverToWakeListening("STT error: ${sttState.message}")
            }
            is VoicePortState.Unavailable -> {
                Log.w(TAG, "[coordinator] STT unavailable")
                recoverToWakeListening("STT unavailable")
            }
            is VoicePortState.PermissionDenied -> {
                Log.e(TAG, "[coordinator] Microphone permission denied")
                _currentState.value = WakeWordState.ERROR
                isCycleActive.set(false)
            }
            else -> {}
        }
    }

    private fun processUserCommand(utterance: String) {
        _currentState.value = WakeWordState.PROCESSING_COMMAND
        Log.i(TAG, "[coordinator] PROCESSING_COMMAND: Submitting to Phase F via RuntimeControlPort")

        coordinatorScope.launch {
            try {
                val brainResult = runtimeControlPort.submitCommand(utterance)
                Log.i(TAG, "[coordinator] Command finished with result: $brainResult")

                // Step 3: Wait for TTS response speech to complete before re-arming wake detector
                _currentState.value = WakeWordState.SPEAKING_RESPONSE
                waitForTtsCompletion()

                transitionToWakeListening()
            } catch (e: Exception) {
                Log.e(TAG, "[coordinator] Error processing command: ${e.message}", e)
                recoverToWakeListening("Execution error: ${e.localizedMessage}")
            }
        }
    }

    private suspend fun waitForTtsCompletion() {
        val maxWaitMs = 12000L
        val pollIntervalMs = 200L
        var waited = 0L

        // Give TTS engine up to 500ms to start
        delay(400L)

        while (voiceOutputPort?.isSpeaking() == true && waited < maxWaitMs) {
            delay(pollIntervalMs)
            waited += pollIntervalMs
        }
        Log.i(TAG, "[coordinator] TTS response completed (Waited ${waited}ms)")
    }

    private fun recoverToWakeListening(reason: String) {
        coordinatorScope.launch {
            Log.i(TAG, "[coordinator] Recovering to WAKE_LISTENING (Reason: $reason)")
            delay(500L)
            transitionToWakeListening()
        }
    }

    private fun transitionToWakeListening() {
        val enabled = configStorage?.isWakeWordEnabled() ?: false
        isCycleActive.set(false)

        if (!enabled) {
            _currentState.value = WakeWordState.IDLE
            Log.d(TAG, "[coordinator] Returned to IDLE (Wake word disabled)")
            return
        }

        _currentState.value = WakeWordState.RETURNING_TO_WAKE_LISTENING
        coordinatorScope.launch {
            delay(200L) // Settle audio pipeline
            _currentState.value = WakeWordState.WAKE_LISTENING
            wakeWordEngine.startListening()
            Log.i(TAG, "[coordinator] System re-armed: WAKE_LISTENING active")
        }
    }
}
