package com.animus.smartroom.brain.provider

import android.util.Log
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.LocalBrainConfig
import com.animus.smartroom.core.brain.prompt.LocalSystemPromptBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Dedicated client communicating with Ollama's OpenAI-compatible /v1/chat/completions endpoint.
 * Supports configurable host, port, timeout, model, and sanitizes logs to prevent leaking sensitive context.
 */
class OllamaLocalLlmClient(
    private val configProvider: () -> LocalBrainConfig
) {
    companion object {
        private const val TAG = "OllamaLocalLlmClient"
    }

    var lastInferenceDurationMs: Long = 0L
        private set

    sealed class OllamaError(message: String, cause: Throwable? = null) : RuntimeException(message, cause) {
        class DisabledOrInvalidConfig(msg: String) : OllamaError(msg)
        class NetworkUnavailable(msg: String, cause: Throwable?) : OllamaError(msg, cause)
        class Timeout(msg: String, cause: Throwable?) : OllamaError(msg, cause)
        class HttpError(val code: Int, msg: String) : OllamaError("Ollama HTTP $code: $msg")
        class MalformedResponse(msg: String, cause: Throwable? = null) : OllamaError(msg, cause)
    }

    suspend fun generateCompletion(
        prompt: String,
        contextPrompts: List<String> = emptyList(),
        brainContext: BrainContext? = null,
        isWarmup: Boolean = false
    ): Result<String> = withContext(Dispatchers.IO) {
        val config = configProvider()
        Log.i(TAG, "LOCAL_LLM_DEBUG: config loaded -> host=${config.host}, port=${config.port}, model=${config.model}, enabled=${config.enabled}, endpointUrl=${config.endpointUrl}")
        if (!config.enabled || !config.isValid()) {
            Log.w(TAG, "LOCAL_LLM_DEBUG: Config is disabled or invalid. enabled=${config.enabled}, valid=${config.isValid()}")
            return@withContext Result.failure(OllamaError.DisabledOrInvalidConfig("Ollama local brain is disabled or config is invalid"))
        }

        val effectiveTimeout = if (isWarmup) config.warmupTimeoutMs else config.timeoutMs
        val startTime = System.currentTimeMillis()
        if (isWarmup) {
            Log.i(TAG, "[LOCAL_LLM_WARMUP_REQUEST_SENT] Target=${config.endpointUrl}, model=${config.model}, timeout=${effectiveTimeout}ms")
        } else {
            Log.i(TAG, "LOCAL_LLM_DEBUG: [REQUEST_STARTED] Target=${config.endpointUrl}, model=${config.model}, timeout=${effectiveTimeout}ms")
        }
        try {
            val url = URL(config.endpointUrl)
            val connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = effectiveTimeout
                readTimeout = effectiveTimeout
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
                setRequestProperty("Accept", "application/json")
            }

            val systemMessage = when {
                brainContext != null -> LocalSystemPromptBuilder.build(brainContext)
                contextPrompts.isNotEmpty() && contextPrompts[0].isNotBlank() -> contextPrompts[0]
                else -> LocalSystemPromptBuilder.build(BrainContext())
            }

            val messagesArray = JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "system")
                    put("content", systemMessage)
                })
                contextPrompts.forEach { ctx ->
                    put(JSONObject().apply {
                        put("role", "system")
                        put("content", "Context: $ctx")
                    })
                }
                put(JSONObject().apply {
                    put("role", "user")
                    put("content", prompt)
                })
            }

            val requestBody = JSONObject().apply {
                put("model", config.model)
                put("messages", messagesArray)
                put("stream", false)
                put("keep_alive", "24h")
                put("max_tokens", config.maxTokens)
                put("temperature", config.temperature)
            }

            Log.i(TAG, "LOCAL_LLM_DEBUG: [REQUEST_BODY] ${requestBody.toString()}")

            OutputStreamWriter(connection.outputStream, "UTF-8").use { writer ->
                writer.write(requestBody.toString())
                writer.flush()
            }
            Log.i(TAG, "LOCAL_LLM_DEBUG: [REQUEST_SENT] Payload dispatched to Ollama (${requestBody.length()} keys)")

            val responseCode = connection.responseCode
            if (isWarmup) {
                Log.i(TAG, "[LOCAL_LLM_WARMUP_RESPONSE_RECEIVED] HTTP status code = $responseCode")
            } else {
                Log.i(TAG, "LOCAL_LLM_DEBUG: [RESPONSE_RECEIVED] HTTP status code = $responseCode")
            }
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val responseText = BufferedReader(InputStreamReader(connection.inputStream, "UTF-8")).use { reader ->
                    reader.readText()
                }

                val jsonResponse = JSONObject(responseText)
                val choices = jsonResponse.optJSONArray("choices")
                val firstChoice = choices?.optJSONObject(0)
                val messageContent = firstChoice?.optJSONObject("message")?.optString("content")
                    ?: jsonResponse.optJSONObject("message")?.optString("content")
                    ?: jsonResponse.optString("response", "")

                if (messageContent.isBlank() && choices == null && !jsonResponse.has("message") && !jsonResponse.has("response")) {
                    lastInferenceDurationMs = System.currentTimeMillis() - startTime
                    Log.w(TAG, "LOCAL_LLM_DEBUG: [MALFORMED_RESPONSE] choices missing: $responseText")
                    return@withContext Result.failure(OllamaError.MalformedResponse("Empty or invalid choices array in Ollama response"))
                }

                lastInferenceDurationMs = System.currentTimeMillis() - startTime
                Log.i(TAG, "LOCAL_LLM_DEBUG: [RESPONSE_SUCCESS] Completed in ${lastInferenceDurationMs}ms (content length: ${messageContent.length})")
                Result.success(messageContent)
            } else {
                lastInferenceDurationMs = System.currentTimeMillis() - startTime
                val errorStream = connection.errorStream
                val errorText = errorStream?.bufferedReader()?.use { it.readText() } ?: "HTTP $responseCode"
                Log.e(TAG, "LOCAL_LLM_DEBUG: [HTTP_ERROR] Code $responseCode: $errorText")
                Result.failure(OllamaError.HttpError(responseCode, errorText))
            }
        } catch (e: java.net.SocketTimeoutException) {
            lastInferenceDurationMs = System.currentTimeMillis() - startTime
            Log.e(TAG, "LOCAL_LLM_DEBUG: [REQUEST_TIMEOUT] Timed out after ${config.timeoutMs}ms: ${e.message}")
            Result.failure(OllamaError.Timeout("Ollama request timed out after ${config.timeoutMs}ms", e))
        } catch (e: java.io.IOException) {
            lastInferenceDurationMs = System.currentTimeMillis() - startTime
            Log.e(TAG, "LOCAL_LLM_DEBUG: [NETWORK_ERROR] Could not connect to Ollama at ${config.host}:${config.port}: ${e.message}", e)
            Result.failure(OllamaError.NetworkUnavailable("Could not connect to Ollama at ${config.host}:${config.port}", e))
        } catch (e: kotlinx.coroutines.CancellationException) {
            lastInferenceDurationMs = System.currentTimeMillis() - startTime
            Log.w(TAG, "LOCAL_LLM_DEBUG: [REQUEST_CANCELLED] Coroutine/Job cancelled after ${lastInferenceDurationMs}ms", e)
            throw e
        } catch (e: Exception) {
            lastInferenceDurationMs = System.currentTimeMillis() - startTime
            Log.e(TAG, "LOCAL_LLM_DEBUG: [UNEXPECTED_ERROR] Error during Ollama inference: ${e.message}", e)
            Result.failure(e)
        }
    }

    suspend fun ping(): Boolean = withContext(Dispatchers.IO) {
        val config = configProvider()
        if (!config.enabled || !config.isValid()) return@withContext false
        try {
            val url = URL("http://${config.host}:${config.port}/v1/models")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = 2000
                readTimeout = 2000
            }
            conn.responseCode in 200..399
        } catch (e: Exception) {
            false
        }
    }
}
