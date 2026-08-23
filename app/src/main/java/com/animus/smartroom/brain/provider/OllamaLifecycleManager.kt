package com.animus.smartroom.brain.provider

import android.util.Log
import com.animus.smartroom.core.brain.model.BrainState
import com.animus.smartroom.core.brain.model.LocalBrainConfig
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicLong
import kotlin.random.Random

/**
 * Authoritative lifecycle manager, single-flight readiness coordinator,
 * and request gate for Ollama local LLM execution.
 */
class OllamaLifecycleManager(
    private val client: OllamaLocalLlmClient,
    private val configProvider: () -> LocalBrainConfig
) {
    companion object {
        private const val TAG = "OllamaLifecycleManager"
        private val requestCounter = AtomicLong(1000)
    }

    private val _state = MutableStateFlow(BrainState.OFFLINE)
    val state: StateFlow<BrainState> = _state.asStateFlow()

    private val startupMutex = Mutex()
    private val inferenceMutex = Mutex()
    private var inFlightWarmup: CompletableDeferred<Boolean>? = null

    /**
     * Guarantees server and model are ready using single-flight synchronization.
     * Multiple concurrent callers await the same warmup operation without launching duplicate requests.
     */
    suspend fun ensureReady(): Boolean = withContext(Dispatchers.IO) {
        if (_state.value == BrainState.READY || _state.value == BrainState.BUSY) {
            return@withContext true
        }

        var deferredToAwait: CompletableDeferred<Boolean>? = null
        startupMutex.withLock {
            if (_state.value == BrainState.READY || _state.value == BrainState.BUSY) {
                return@withContext true
            }

            if (inFlightWarmup != null) {
                deferredToAwait = inFlightWarmup
            } else {
                val deferred = CompletableDeferred<Boolean>()
                inFlightWarmup = deferred
                deferredToAwait = null
            }
        }

        if (deferredToAwait != null) {
            Log.i(TAG, "[OLLAMA_SINGLE_FLIGHT] Request joined existing in-flight startup/warmup sequence...")
            return@withContext deferredToAwait!!.await()
        }

        val config = configProvider()
        Log.i(TAG, "[OLLAMA_LIFECYCLE_START] Initiating single-flight startup for model='${config.model}' at ${config.endpointUrl}...")
        _state.value = BrainState.STARTING

        var success = false
        try {
            // Step 1: Check server ping / reachable
            val isServerUp = client.ping()
            if (!isServerUp) {
                Log.w(TAG, "[OLLAMA_SERVER_OFFLINE] Ollama server is unreachable. Attempting connection / warmup...")
            }
            _state.value = BrainState.SERVER_READY

            // Step 2: Model Loading into VRAM
            _state.value = BrainState.MODEL_LOADING
            val t0 = System.currentTimeMillis()
            val warmupResult = client.warmUp("Respond with exactly: READY")
            val dur = System.currentTimeMillis() - t0

            if (warmupResult.isSuccess && warmupResult.getOrNull()?.isNotBlank() == true) {
                Log.i(TAG, "[OLLAMA_MODEL_READY] Model '${config.model}' warm and resident in VRAM in ${dur}ms.")
                _state.value = BrainState.READY
                success = true
            } else {
                val err = warmupResult.exceptionOrNull()
                Log.e(TAG, "[OLLAMA_WARMUP_FAILED] Warmup failed after ${dur}ms: ${err?.message}")
                _state.value = BrainState.FAILED
                success = false
            }
        } catch (e: Exception) {
            Log.e(TAG, "[OLLAMA_LIFECYCLE_ERROR] Exception during startup: ${e.message}", e)
            _state.value = BrainState.FAILED
            success = false
        } finally {
            startupMutex.withLock {
                inFlightWarmup?.complete(success)
                inFlightWarmup = null
            }
        }
        return@withContext success
    }

    /**
     * Executes inference through the bounded Request Gate with 409 Conflict recovery.
     */
    suspend fun executeInference(
        prompt: String,
        contextPrompts: List<String> = emptyList()
    ): Result<String> = withContext(Dispatchers.IO) {
        val reqId = "REQ-${requestCounter.incrementAndGet()}"
        Log.i(TAG, "[$reqId] RECEIVED: prompt='$prompt'")

        // 1. Ensure Readiness
        if (!ensureReady()) {
            Log.e(TAG, "[$reqId] FAILED: Local Brain could not transition to READY (state=${_state.value})")
            return@withContext Result.failure(IllegalStateException("Local brain unavailable (state=${_state.value})"))
        }

        // 2. Request Gate (Inference Serialization)
        inferenceMutex.withLock {
            _state.value = BrainState.BUSY
            Log.i(TAG, "[$reqId] INFERENCE_START")
            val t0 = System.currentTimeMillis()

            var attempt = 1
            val maxAttempts = 3
            var lastException: Throwable? = null

            while (attempt <= maxAttempts) {
                try {
                    val result = client.generateCompletion(prompt, contextPrompts)
                    val dur = System.currentTimeMillis() - t0
                    if (result.isSuccess) {
                        Log.i(TAG, "[$reqId] INFERENCE_SUCCESS (attempt $attempt, ${dur}ms)")
                        _state.value = BrainState.READY
                        return@withContext result
                    }

                    val ex = result.exceptionOrNull()
                    lastException = ex

                    // Classify transient vs permanent error
                    if (ex is OllamaLocalLlmClient.OllamaError.HttpError && ex.code == 409) {
                        Log.w(TAG, "[$reqId] TRANSIENT_409: Model busy/loading collision on attempt $attempt. Backing off...")
                        _state.value = BrainState.MODEL_LOADING
                        val backoffMs = (500L * attempt) + Random.nextLong(100, 400)
                        delay(backoffMs)
                    } else if (ex is OllamaLocalLlmClient.OllamaError.Timeout || ex is OllamaLocalLlmClient.OllamaError.NetworkUnavailable) {
                        Log.w(TAG, "[$reqId] TRANSIENT_NETWORK: Connection hiccup on attempt $attempt. Backing off...")
                        _state.value = BrainState.RECOVERING
                        val backoffMs = (800L * attempt) + Random.nextLong(100, 300)
                        delay(backoffMs)
                    } else {
                        // Permanent error (e.g. malformed or invalid config)
                        Log.e(TAG, "[$reqId] PERMANENT_ERROR: ${ex?.message}")
                        _state.value = BrainState.READY
                        return@withContext result
                    }
                } catch (e: Exception) {
                    lastException = e
                    Log.e(TAG, "[$reqId] ATTEMPT_${attempt}_EXCEPTION: ${e.message}", e)
                    delay(500L * attempt)
                }
                attempt++
            }

            _state.value = BrainState.READY
            Log.e(TAG, "[$reqId] EXHAUSTED: All $maxAttempts attempts failed. Reason=${lastException?.message}")
            return@withContext Result.failure(lastException ?: RuntimeException("Inference failed after $maxAttempts attempts"))
        }
    }

    /**
     * Triggers watchdog recovery.
     */
    suspend fun recover(): Boolean = withContext(Dispatchers.IO) {
        Log.w(TAG, "[OLLAMA_WATCHDOG_RECOVER] Triggering full Ollama recovery...")
        _state.value = BrainState.RECOVERING
        return@withContext ensureReady()
    }

    fun setState(newState: BrainState) {
        _state.value = newState
    }
}
