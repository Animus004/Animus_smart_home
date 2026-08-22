package com.animus.smartroom.brain.provider

import android.util.Log
import com.animus.smartroom.core.brain.port.LocalInferencePort
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
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
    // Phase 5F.6 lifecycle additions
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
                        kotlinx.coroutines.delay(1000L * attempt)
                    }
                    attempt++
                }

                _status.value = LocalBrainStatus.FAILED
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
        // Strict Gating: If not yet READY or AVAILABLE, wait for warmup to complete or trigger it
        if (_status.value != LocalBrainStatus.READY && _status.value != LocalBrainStatus.BUSY && _status.value != LocalBrainStatus.AVAILABLE) {
            Log.i(TAG, "[LOCAL_LLM_USER_REQUEST_HELD] User request gated while brain is in status=${_status.value}. Waiting for READY...")
            if (_status.value == LocalBrainStatus.OFFLINE || _status.value == LocalBrainStatus.DISCONNECTED || _status.value == LocalBrainStatus.FAILED || _status.value == LocalBrainStatus.ERROR) {
                // If failed/offline, initiate warmUp in background if not already in progress
                kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
                    warmUp(maxAttempts = 1)
                }
            }
            // Wait for READY or terminal failure
            val readyStatus = _status.filter { it == LocalBrainStatus.READY || it == LocalBrainStatus.AVAILABLE || it == LocalBrainStatus.FAILED || it == LocalBrainStatus.OFFLINE || it == LocalBrainStatus.DISCONNECTED || it == LocalBrainStatus.ERROR }
                .first()
            if (readyStatus != LocalBrainStatus.READY && readyStatus != LocalBrainStatus.AVAILABLE) {
                throw IllegalStateException("Cannot generate completion: Local brain is not in READY state (current status=$readyStatus)")
            }
            Log.i(TAG, "[LOCAL_LLM_USER_REQUEST_RELEASED] Gated request released. Status is now READY.")
        }

        inferenceMutex.withLock {
            _status.value = LocalBrainStatus.BUSY
            Log.i(TAG, "[LOCAL_LLM_REQUEST_STARTED] Dispatching user prompt: '$prompt'")
            val result = client.generateCompletion(prompt, context)
            return result.fold(
                onSuccess = {
                    _status.value = LocalBrainStatus.READY
                    it
                },
                onFailure = {
                    _status.value = LocalBrainStatus.READY
                    Log.e(TAG, "LOCAL_LLM_DEBUG: Generation failed: ${it.message}", it)
                    throw it
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
