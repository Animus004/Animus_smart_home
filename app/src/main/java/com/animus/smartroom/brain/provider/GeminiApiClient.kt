package com.animus.smartroom.brain.provider

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.atomic.AtomicInteger

class GeminiApiClient(
    val modelId: String = GeminiModelConfig.DEFAULT_GEMINI_MODEL
) {

    companion object {
        private const val TAG = "GeminiApiClient"
        private val testRequestCounter = AtomicInteger(0)
        private val generateRequestCounter = AtomicInteger(0)

        const val SYSTEM_INSTRUCTION = """
You are the Animus Smart Room command interpreter.
Convert the user's natural-language request into a structured JSON response containing an ordered array of supported Animus commands in the "commands" property.

Supported Command Schemas:
- {"command": "PLAY_MUSIC", "title": "<song_title>", "artist": "<artist_optional>", "playbackUrl": null}
- {"command": "PAUSE_MUSIC"}
- {"command": "RESUME_MUSIC"}
- {"command": "NEXT_TRACK"}
- {"command": "PREVIOUS_TRACK"}
- {"command": "SET_VOLUME", "value": <0..100>}
- {"command": "CONNECT_BLUETOOTH_DEVICE", "target": "<device_name_or_alias_optional>"}
- {"command": "DISCONNECT_BLUETOOTH_DEVICE"}
- {"command": "SWITCH_BLUETOOTH_DEVICE", "target": "<device_name_or_alias>"}
- {"command": "SET_DEVICE", "target": "AC", "capability": "POWER", "value": true|false}
- {"command": "SET_DEVICE", "target": "AC", "capability": "TEMPERATURE", "value": <16..30>}
- {"command": "SET_DEVICE", "target": "AC", "capability": "MODE", "value": "COOL|AUTO|DRY|FAN"}
- {"command": "SET_DEVICE", "target": "AC", "capability": "FAN_SPEED", "value": "LOW|MEDIUM|HIGH|AUTO"}
- {"command": "SLEEP_MODE", "durationMinutes": <minutes|null>, "wakeTime": "<HH:mm>|null"}
- {"command": "CANCEL_SLEEP"}
- {"command": "SCHEDULE_DEVICE_ACTION", "target": "AC", "action": "POWER_OFF|POWER_ON|SET_TEMPERATURE", "delayMinutes": <minutes|null>, "scheduledTime": "<time_string|null>", "recurrence": "DAILY|null"}
- {"command": "CANCEL_SCHEDULED_ACTION", "target": "AC"}
- {"command": "QUERY_SCHEDULED_ACTION", "target": "AC"}
- {"command": "UNKNOWN", "rawText": "<user_input>"}

Scheduled & Delayed Device Action Rules:
- When the user requests a delayed or scheduled device operation (e.g. "Turn the AC off after 2 hours", "Turn AC on in 30 minutes", "Turn off AC at 11 PM", "Turn AC off every night at 11 PM"):
  - Relative delay: {"command": "SCHEDULE_DEVICE_ACTION", "target": "AC", "action": "POWER_OFF"|"POWER_ON", "delayMinutes": <minutes>, "scheduledTime": null, "recurrence": null}
  - Absolute time: {"command": "SCHEDULE_DEVICE_ACTION", "target": "AC", "action": "POWER_OFF"|"POWER_ON", "delayMinutes": null, "scheduledTime": "<time>", "recurrence": null}
  - Recurring: {"command": "SCHEDULE_DEVICE_ACTION", "target": "AC", "action": "POWER_OFF"|"POWER_ON", "delayMinutes": null, "scheduledTime": "<time>", "recurrence": "DAILY"}
- When the user asks to cancel an AC timer (e.g. "Cancel my AC timer", "Stop AC timer", "Delete the AC schedule"):
  {"command": "CANCEL_SCHEDULED_ACTION", "target": "AC"}
- When the user asks about remaining time on an AC timer (e.g. "How much time is left on the AC timer?", "When is my AC turning off?", "Check AC timer"):
  {"command": "QUERY_SCHEDULED_ACTION", "target": "AC"}

Sleep Mode & Routine Rules:
- When the user requests to sleep, nap, or rest:
  - If a duration is specified (e.g. "I want to sleep for 45 minutes", "Sleep for 30 mins", "Need to sleep for an hour"):
    {"command": "SLEEP_MODE", "durationMinutes": <minutes>, "wakeTime": null}
  - If an absolute wake time is specified (e.g. "Wake me up at 4 PM", "Sleep until 16:00"):
    {"command": "SLEEP_MODE", "durationMinutes": null, "wakeTime": "<HH:mm>"}
  - If neither duration nor wake time is specified (e.g. "I am tired and want to sleep", "I need to sleep", "Make me comfortable and sleep"):
    {"command": "SLEEP_MODE", "durationMinutes": null, "wakeTime": null}
  - If the user responds with just a duration/time to a follow-up (e.g. "30 minutes", "2 minutes", "until 4 PM"):
    {"command": "SLEEP_MODE", "durationMinutes": 30, "wakeTime": null}
- When the user cancels sleep (e.g. "Cancel sleep mode", "Cancel my sleep timer", "Don't wake me up"):
  {"command": "CANCEL_SLEEP"}

Multi-Command & Sequential Rules:
- When the user requests multiple actions in a single sentence (e.g. 2, 3, or 4+ actions separated by commas, "and", or sequence):
  Parse EVERY action into its corresponding command object and include ALL of them in the "commands" array in the exact order requested.
- Example: "Play Zara Zara, set volume to 30%, and set the AC to 24 degrees"
  -> {"commands": [{"command": "PLAY_MUSIC", "title": "Zara Zara", "artist": null, "playbackUrl": null}, {"command": "SET_VOLUME", "value": 30}, {"command": "SET_DEVICE", "target": "AC", "capability": "TEMPERATURE", "value": 24}]}
- For AC actions, always use target="AC".
- For PLAY_MUSIC, accurately extract song title and artist. Do not split song titles containing "and" (e.g., "Play Romeo and Juliet").

Output Requirements:
- Return raw JSON strictly matching: {"commands": [ ... ]}
- Never output markdown formatting, backticks, or explanatory text.
- Never output Android intents or raw hardware codes.
"""

        fun computeKeyFingerprint(key: String): String {
            return try {
                val digest = MessageDigest.getInstance("SHA-256")
                val hash = digest.digest(key.trim().toByteArray(Charsets.UTF_8))
                hash.take(4).joinToString("") { "%02X".format(it) }
            } catch (e: Exception) {
                "UNKNOWN"
            }
        }

        fun maskKeyInText(text: String, apiKey: String?): String {
            if (apiKey.isNullOrBlank()) return text
            val trimmed = apiKey.trim()
            return if (trimmed.length > 6) {
                text.replace(trimmed, "API_KEY_MASKED[${computeKeyFingerprint(trimmed)}]")
            } else {
                text
            }
        }
    }

    suspend fun generateContent(apiKey: String, userInput: String): Result<String> = withContext(Dispatchers.IO) {
        val trimmedKey = apiKey.trim()
        if (trimmedKey.isBlank()) {
            return@withContext Result.failure(IllegalArgumentException("Gemini API key cannot be empty."))
        }

        val reqId = generateRequestCounter.incrementAndGet()
        val keyFp = computeKeyFingerprint(trimmedKey)
        val endpoint = GeminiModelConfig.getGenerateContentUrl(modelId)
        val endpointPath = "/v1beta/models/$modelId:generateContent"
        Log.i(TAG, "Gemini GenerateContent request #$reqId [model='$modelId', keyFp='$keyFp', endpoint='$endpointPath']")

        val requestJson = JSONObject().apply {
            put("system_instruction", JSONObject().apply {
                put("parts", JSONArray().apply {
                    put(JSONObject().apply { put("text", SYSTEM_INSTRUCTION.trimIndent()) })
                })
            })

            put("contents", JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "user")
                    put("parts", JSONArray().apply {
                        put(JSONObject().apply { put("text", userInput) })
                    })
                })
            })

            put("generationConfig", JSONObject().apply {
                put("temperature", 0.1)
                put("topP", 0.95)
                put("response_mime_type", "application/json")
            })
        }

        executeWithRetry(
            apiKey = trimmedKey,
            endpoint = endpoint,
            endpointPath = endpointPath,
            requestPayload = requestJson.toString(),
            tag = "generateContent #$reqId"
        ).mapCatching { responseText ->
            val jsonResponse = JSONObject(responseText)
            val candidates = jsonResponse.optJSONArray("candidates")
            if (candidates != null && candidates.length() > 0) {
                val candidate = candidates.getJSONObject(0)
                val content = candidate.optJSONObject("content")
                val parts = content?.optJSONArray("parts")
                if (parts != null && parts.length() > 0) {
                    for (i in 0 until parts.length()) {
                        val part = parts.getJSONObject(i)
                        val text = part.optString("text", "").trim()
                        if (text.isNotBlank()) {
                            return@mapCatching text
                        }
                    }
                }
            }
            throw IllegalStateException("Empty candidate text in Gemini response.")
        }
    }

    /**
     * Isolated, lightweight connection test.
     * Uses minimal payload WITHOUT search grounding or heavy schemas to guarantee clean quota validation.
     * Guaranteed exactly 1 request per user tap (unless transient retry triggers on 503/429).
     */
    suspend fun testConnection(apiKey: String): Result<String> = withContext(Dispatchers.IO) {
        val trimmedKey = apiKey.trim()
        if (trimmedKey.isBlank()) {
            return@withContext Result.failure(IllegalArgumentException("Gemini API key cannot be empty."))
        }

        val reqId = testRequestCounter.incrementAndGet()
        val keyFp = computeKeyFingerprint(trimmedKey)
        val endpoint = GeminiModelConfig.getGenerateContentUrl(modelId)
        val endpointPath = "/v1beta/models/$modelId:generateContent"
        Log.i(TAG, "Gemini Test Connection request #$reqId [model='$modelId', keyFp='$keyFp', endpoint='$endpointPath']")

        // Minimal payload to test authentication and model endpoint as specified in Step 8
        val testPayload = JSONObject().apply {
            put("contents", JSONArray().apply {
                put(JSONObject().apply {
                    put("role", "user")
                    put("parts", JSONArray().apply {
                        put(JSONObject().apply { put("text", "Return JSON: {\"status\":\"ok\"}") })
                    })
                })
            })
            put("generationConfig", JSONObject().apply {
                put("temperature", 0.1)
                put("response_mime_type", "application/json")
            })
        }

        executeWithRetry(
            apiKey = trimmedKey,
            endpoint = endpoint,
            endpointPath = endpointPath,
            requestPayload = testPayload.toString(),
            tag = "testConnection #$reqId"
        ).map {
            "Gemini connection successful! (Model: $modelId, Key FP: $keyFp)"
        }
    }

    private suspend fun executeWithRetry(
        apiKey: String,
        endpoint: String,
        endpointPath: String,
        requestPayload: String,
        tag: String
    ): Result<String> {
        val maxAttempts = 2
        var lastException: Exception? = null

        for (attempt in 1..maxAttempts) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL(endpoint)
                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("x-goog-api-key", apiKey)
                    connectTimeout = 8000
                    readTimeout = 12000
                    doOutput = true
                    doInput = true
                }

                OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(requestPayload)
                    writer.flush()
                }

                val responseCode = connection.responseCode
                val retryAfter = connection.getHeaderField("Retry-After")
                val requestId = connection.getHeaderField("x-goog-request-id") ?: connection.getHeaderField("x-request-id")

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val responseText = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                    return Result.success(responseText)
                } else {
                    val errorStream = connection.errorStream
                    val rawErrorBody = if (errorStream != null) {
                        BufferedReader(InputStreamReader(errorStream, Charsets.UTF_8)).use { it.readText() }
                    } else {
                        "HTTP $responseCode: ${connection.responseMessage}"
                    }

                    val isRetried = attempt > 1
                    val parsedError = parseDetailedGoogleError(
                        code = responseCode,
                        rawBody = rawErrorBody,
                        model = modelId,
                        endpointPath = endpointPath,
                        retryAfter = retryAfter,
                        requestId = requestId,
                        wasRetried = isRetried
                    )
                    Log.w(TAG, "[$tag Attempt $attempt/$maxAttempts] Failed: $parsedError")

                    // Transient retry on 429 / 503 only once
                    if ((responseCode == 429 || responseCode == 503) && attempt < maxAttempts) {
                        val backoffMs = if (!retryAfter.isNullOrBlank()) {
                            (retryAfter.toLongOrNull() ?: 1L).coerceIn(1L, 3L) * 1000L
                        } else {
                            1000L
                        }
                        Log.i(TAG, "[$tag] Transient HTTP $responseCode received. Retrying in ${backoffMs}ms...")
                        delay(backoffMs)
                        continue
                    }

                    return Result.failure(RuntimeException(parsedError))
                }
            } catch (e: Exception) {
                val safeMsg = maskKeyInText(e.message ?: "Unknown connection error", apiKey)
                Log.e(TAG, "[$tag Attempt $attempt/$maxAttempts] Exception: $safeMsg", e)
                lastException = RuntimeException(safeMsg, e)
                if (attempt < maxAttempts) {
                    delay(1000L)
                }
            } finally {
                connection?.disconnect()
            }
        }

        return Result.failure(lastException ?: RuntimeException("Network request failed after retries."))
    }

    fun parseDetailedGoogleError(
        code: Int,
        rawBody: String,
        model: String = modelId,
        endpointPath: String = "/v1beta/models/$model:generateContent",
        retryAfter: String? = null,
        requestId: String? = null,
        wasRetried: Boolean = false
    ): String {
        return try {
            val json = JSONObject(rawBody)
            val errorObj = json.optJSONObject("error")
            val status = errorObj?.optString("status", "") ?: ""
            val message = errorObj?.optString("message", "") ?: ""
            val detailsArray = errorObj?.optJSONArray("details")

            var detailReason = ""
            if (detailsArray != null && detailsArray.length() > 0) {
                val detailsList = mutableListOf<String>()
                for (i in 0 until detailsArray.length()) {
                    val detail = detailsArray.optJSONObject(i) ?: continue
                    val reason = detail.optString("reason", "")
                    if (reason.isNotBlank()) detailsList.add(reason)
                    val metadata = detail.optJSONObject("metadata")
                    if (metadata != null && metadata.length() > 0) {
                        val quotaLimit = metadata.optString("quota_limit", "")
                        if (quotaLimit.isNotBlank()) detailsList.add("limit: $quotaLimit")
                    }
                }
                if (detailsList.isNotEmpty()) {
                    detailReason = " [Details: ${detailsList.joinToString(", ")}]"
                }
            }

            val retryInfo = if (!retryAfter.isNullOrBlank()) " | Retry-After: $retryAfter" else ""
            val reqIdInfo = if (!requestId.isNullOrBlank()) " | RequestId: $requestId" else ""
            val retriedInfo = if (wasRetried) " (retried)" else ""

            when (code) {
                429 -> {
                    if (status.contains("RESOURCE_EXHAUSTED", ignoreCase = true) || message.contains("quota", ignoreCase = true)) {
                        "HTTP 429 (RESOURCE_EXHAUSTED)$retriedInfo: Google quota/rate limit reached for model '$model'$detailReason. $message$retryInfo$reqIdInfo"
                    } else {
                        "HTTP 429: Gemini service rate limited$retriedInfo. $message$detailReason$retryInfo$reqIdInfo"
                    }
                }
                503 -> "HTTP 503: Gemini service temporarily overloaded$retriedInfo. Spikes are temporary. $message$retryInfo$reqIdInfo"
                404 -> "HTTP 404: Gemini model '$model' not found at '$endpointPath'. Verify model ID."
                400, 401, 403 -> "HTTP $code: Authentication/Permission error ($status). $message"
                else -> "HTTP $code: Gemini API error ($status). $message$detailReason$retryInfo$reqIdInfo"
            }
        } catch (e: Exception) {
            "HTTP $code: $rawBody"
        }
    }
}

