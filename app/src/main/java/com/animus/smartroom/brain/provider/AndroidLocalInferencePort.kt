package com.animus.smartroom.brain.provider

import android.util.Log
import com.animus.smartroom.core.brain.port.LocalInferencePort
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

enum class LocalBrainStatus {
    DISCONNECTED,
    CONNECTING,
    AVAILABLE,
    BUSY,
    ERROR,
    OFFLINE,
    STARTING,
    WARMING_UP,
    READY,
    FAILED
}

class AndroidLocalInferencePort(
    private val client: LocalInferenceClient
) : LocalInferencePort {

    companion object {
        private const val TAG = "LocalInferencePort"
    }

    private val _status = MutableStateFlow(LocalBrainStatus.STARTING)
    val status: StateFlow<LocalBrainStatus> = _status.asStateFlow()

    private val warmupMutex = Mutex()
    private val inferenceMutex = Mutex()

    val lifecycleManager = OllamaLifecycleManager(
        client = client.ollamaClient,
        configProvider = client.configProvider
    )

    /**
     * Executes real model warmup on GPU with extended timeout.
     * Guarantees single-flight execution and transitions to READY only upon genuine HTTP 200 + valid response.
     */
    suspend fun warmUp(maxAttempts: Int = 2): Boolean {
        warmupMutex.withLock {
            if (_status.value == LocalBrainStatus.READY) {
                Log.i(TAG, "[LOCAL_LLM_READY] Warmup skipped, already in READY state.")
                return true
            }

            Log.i(TAG, "[LOCAL_LLM_STARTUP] Initiating local brain startup sequence...")
            _status.value = LocalBrainStatus.STARTING

            var attempt = 1
            try {
                while (attempt <= maxAttempts) {
                    val attemptStart = System.currentTimeMillis()
                    Log.i(TAG, "[LOCAL_LLM_WARMUP_STARTED] Attempt $attempt/$maxAttempts running real inference on Qwen...")
                    _status.value = LocalBrainStatus.WARMING_UP

                    try {
                        val result = client.warmUp("Respond with exactly: READY")
                        val durationMs = System.currentTimeMillis() - attemptStart
                        if (result.isSuccess) {
                            val responseText = result.getOrNull().orEmpty()
                            if (responseText.isNotBlank()) {
                                Log.i(TAG, "[LOCAL_LLM_WARMUP_RESPONSE_RECEIVED] HTTP status code = 200")
                                Log.i(TAG, "[LOCAL_LLM_WARMUP_SUCCESS] Completed in ${durationMs}ms: '$responseText'")
                                _status.value = LocalBrainStatus.READY
                                lifecycleManager.setState(com.animus.smartroom.core.brain.model.BrainState.READY)
                                Log.i(TAG, "[LOCAL_LLM_READY] Local LLM is warm, resident in GPU VRAM, and ready for user commands.")
                                return true
                            }
                        }
                        Log.w(TAG, "[LOCAL_LLM_WARMUP_FAILED] Warmup attempt $attempt returned empty/failure: ${result.exceptionOrNull()?.message}")
                    } catch (e: kotlinx.coroutines.CancellationException) {
                        throw e
                    } catch (e: Exception) {
                        val durationMs = System.currentTimeMillis() - attemptStart
                        Log.e(TAG, "[LOCAL_LLM_WARMUP_FAILED] Warmup attempt $attempt encountered exception after ${durationMs}ms: ${e.message}", e)
                    }

                    if (attempt < maxAttempts) {
                        Log.i(TAG, "[LOCAL_LLM_WARMUP_RETRY] Preparing retry attempt ${attempt + 1} with backoff...")
                        _status.value = LocalBrainStatus.STARTING
                        delay(1000L * attempt)
                    }
                    attempt++
                }

                _status.value = LocalBrainStatus.FAILED
                lifecycleManager.setState(com.animus.smartroom.core.brain.model.BrainState.FAILED)
                Log.e(TAG, "[LOCAL_LLM_WARMUP_FAILED] All $maxAttempts warmup attempts exhausted. State set to FAILED.")
                return false
            } finally {
                if (_status.value == LocalBrainStatus.STARTING || _status.value == LocalBrainStatus.WARMING_UP) {
                    _status.value = LocalBrainStatus.FAILED
                }
            }
        }
    }

    override suspend fun generate(prompt: String, context: List<String>): String {
        val reqId = java.util.UUID.randomUUID().toString().take(8)
        val startTime = System.currentTimeMillis()

        // Strict Gating: If not yet READY or AVAILABLE, wait for warmup to complete or trigger it
        if (_status.value != LocalBrainStatus.READY && _status.value != LocalBrainStatus.BUSY && _status.value != LocalBrainStatus.AVAILABLE) {
            Log.i(TAG, "[LOCAL_LLM_USER_REQUEST_HELD] reqId=$reqId User request held while brain is status=${_status.value}. Waiting for READY...")
            if (_status.value == LocalBrainStatus.OFFLINE || _status.value == LocalBrainStatus.DISCONNECTED || _status.value == LocalBrainStatus.FAILED || _status.value == LocalBrainStatus.ERROR) {
                val warmed = warmUp(maxAttempts = 1)
                if (!warmed && _status.value != LocalBrainStatus.READY && _status.value != LocalBrainStatus.AVAILABLE) {
                    val dur = System.currentTimeMillis() - startTime
                    Log.e(TAG, "[LOCAL_INFERENCE_DIAGNOSTIC] reqId=$reqId input='$prompt' failureStage=WARMUP_FAILED error=OLLAMA_MODEL_UNAVAILABLE durationMs=$dur")
                    throw IllegalStateException("OLLAMA_MODEL_UNAVAILABLE: Local brain warmup failed (current status=${_status.value})")
                }
            } else {
                val readyStatus = _status.filter {
                    it == LocalBrainStatus.READY || it == LocalBrainStatus.AVAILABLE ||
                    it == LocalBrainStatus.FAILED || it == LocalBrainStatus.OFFLINE ||
                    it == LocalBrainStatus.DISCONNECTED || it == LocalBrainStatus.ERROR
                }.first()
                if (readyStatus != LocalBrainStatus.READY && readyStatus != LocalBrainStatus.AVAILABLE) {
                    val dur = System.currentTimeMillis() - startTime
                    Log.e(TAG, "[LOCAL_INFERENCE_DIAGNOSTIC] reqId=$reqId input='$prompt' failureStage=GATING_REJECTED error=OLLAMA_MODEL_UNAVAILABLE durationMs=$dur")
                    throw IllegalStateException("OLLAMA_MODEL_UNAVAILABLE: Cannot generate completion: Local brain is not in READY state (current status=$readyStatus)")
                }
            }
            Log.i(TAG, "[LOCAL_LLM_USER_REQUEST_RELEASED] reqId=$reqId Gated request released. Status is now READY.")
        }

        return inferenceMutex.withLock {
            _status.value = LocalBrainStatus.BUSY
            Log.i(TAG, "[LOCAL_LLM_REQUEST_STARTED] reqId=$reqId Dispatching user prompt: '$prompt'")
            val result = client.generateCompletion(prompt, context)
            val dur = System.currentTimeMillis() - startTime
            result.fold(
                onSuccess = {
                    _status.value = LocalBrainStatus.READY
                    Log.i(TAG, "[LOCAL_INFERENCE_DIAGNOSTIC] reqId=$reqId input='$prompt' stage=INFERENCE_SUCCESS durationMs=$dur length=${it.length}")
                    it
                },
                onFailure = { err ->
                    _status.value = LocalBrainStatus.READY
                    val errorType = when (err) {
                        is OllamaLocalLlmClient.OllamaError.Timeout -> "INFERENCE_TIMEOUT"
                        is OllamaLocalLlmClient.OllamaError.NetworkUnavailable -> "OLLAMA_CONNECTION_REFUSED"
                        is OllamaLocalLlmClient.OllamaError.MalformedResponse -> "QWEN_RESPONSE_PARSE_FAILED"
                        is kotlinx.coroutines.CancellationException -> "ANDROID_REQUEST_CANCELLED"
                        else -> "INFERENCE_EXECUTION_FAILED"
                    }
                    Log.e(TAG, "[LOCAL_INFERENCE_DIAGNOSTIC] reqId=$reqId input='$prompt' failureStage=$errorType durationMs=$dur error=${err.message}", err)
                    throw err
                }
            )
        }
    }

    override fun isAvailable(): Boolean {
        val s = _status.value
        return s == LocalBrainStatus.READY || s == LocalBrainStatus.BUSY || s == LocalBrainStatus.AVAILABLE
    }

    suspend fun checkHealth() {
        _status.value = LocalBrainStatus.CONNECTING
        val isHealthy = client.ping()
        _status.value = if (isHealthy) LocalBrainStatus.READY else LocalBrainStatus.DISCONNECTED
    }

    fun setStatus(newStatus: LocalBrainStatus) {
        _status.value = newStatus
    }
}
