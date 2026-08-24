package com.animus.smartroom.brain.knowledge

import android.util.Log
import com.animus.smartroom.brain.provider.GeminiApiClient
import com.animus.smartroom.brain.provider.GeminiModelConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

data class MediaServiceOption(
    val serviceName: String,
    val isAvailable: Boolean,
    val confidence: String = "HIGH",
    val notes: String? = null
)

data class FreshKnowledgeResult(
    val isSuccess: Boolean,
    val query: String,
    val summary: String,
    val mediaServices: List<MediaServiceOption> = emptyList(),
    val errorMessage: String? = null
)

class GeminiKnowledgeBridge(
    private val modelId: String = GeminiModelConfig.DEFAULT_GEMINI_MODEL
) {
    companion object {
        private const val TAG = "GeminiKnowledgeBridge"
        private const val BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

        val KNOWLEDGE_TRIGGERS = listOf(
            "where can i watch",
            "where can we watch",
            "where to watch",
            "is it available on",
            "is available on",
            "available on",
            "where is",
            "where to stream",
            "stream on",
            "streaming on",
            "what is the latest",
            "latest information",
            "tell me about the movie",
            "who directed",
            "available on netflix",
            "available on prime",
            "available on youtube",
            "available on hotstar"
        )
    }

    /**
     * Deterministic check: determines if the user's natural language input requires fresh external knowledge.
     * Ordinary commands (e.g. "set ac to 24", "play kesariya", "turn on projector") return false.
     */
    fun isFreshKnowledgeQuery(text: String): Boolean {
        val lower = text.trim().lowercase(Locale.ROOT)
        // Hard exclusions for ordinary deterministic commands
        if (lower.startsWith("set ac") || lower.startsWith("turn on") || lower.startsWith("turn off") ||
            lower.startsWith("set volume") || lower.startsWith("sleep for") || lower.startsWith("cancel") ||
            lower.startsWith("play ") && !lower.contains("where") && !lower.contains("available")
        ) {
            return false
        }

        return KNOWLEDGE_TRIGGERS.any { lower.contains(it) }
    }

    /**
     * Queries Gemini for structured fresh data / streaming availability.
     * Guarantees:
     * 1. Qwen handles the initial intent classification locally.
     * 2. Gemini only provides external facts, never hardware commands.
     * 3. Privacy: No user profiling, no image uploads, API keys masked in all logs.
     */
    suspend fun queryKnowledge(
        query: String,
        apiKey: String?
    ): FreshKnowledgeResult = withContext(Dispatchers.IO) {
        val sanitizedQuery = query.trim()
        Log.i(TAG, "[LOCAL_QWEN] Fresh knowledge classification triggered for query: '$sanitizedQuery'")

        if (apiKey.isNullOrBlank()) {
            Log.w(TAG, "[GEMINI_LOOKUP] Gemini API key not configured. Graceful fallback active.")
            return@withContext FreshKnowledgeResult(
                isSuccess = false,
                query = sanitizedQuery,
                summary = "External knowledge service is unavailable (API key not configured).",
                errorMessage = "API_KEY_NOT_CONFIGURED"
            )
        }

        val keyFingerprint = GeminiApiClient.computeKeyFingerprint(apiKey)
        Log.i(TAG, "[GEMINI_LOOKUP] Dispatching external knowledge request (key: ...$keyFingerprint)...")

        val systemPrompt = """
You are the Animus Smart Room Fresh Knowledge Provider.
Your task is to provide accurate, up-to-date streaming availability and factual information about movies, shows, or media.

Output Requirements:
Return a strictly valid JSON object:
{
  "summary": "<concise 1-2 sentence spoken summary for the user>",
  "services": [
    {
      "name": "Netflix|Amazon Prime Video|Apple TV|YouTube|Hotstar|JioCinema",
      "available": true|false,
      "confidence": "HIGH|MEDIUM|LOW",
      "notes": "<optional brief note, e.g. Rent/Buy or Included with subscription>"
    }
  ]
}
Never output markdown formatting, code blocks, or raw hardware commands.
"""

        try {
            val endpoint = "$BASE_URL/$modelId:generateContent?key=${apiKey.trim()}"
            val url = URL(endpoint)
            val connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 8000
                readTimeout = 12000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=UTF-8")
            }

            val requestBody = JSONObject().apply {
                put("systemInstruction", JSONObject().apply {
                    put("parts", JSONArray().apply {
                        put(JSONObject().apply { put("text", systemPrompt) })
                    })
                })
                put("contents", JSONArray().apply {
                    put(JSONObject().apply {
                        put("role", "user")
                        put("parts", JSONArray().apply {
                            put(JSONObject().apply { put("text", sanitizedQuery) })
                        })
                    })
                })
                put("generationConfig", JSONObject().apply {
                    put("temperature", 0.1)
                    put("responseMimeType", "application/json")
                })
            }

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(requestBody.toString())
                writer.flush()
            }

            val responseCode = connection.responseCode
            if (responseCode != HttpURLConnection.HTTP_OK) {
                val errorStream = connection.errorStream?.let { InputStreamReader(it, Charsets.UTF_8) }
                val errorText = errorStream?.let { BufferedReader(it).readText() } ?: "HTTP $responseCode"
                val maskedError = GeminiApiClient.maskKeyInText(errorText, apiKey)
                Log.e(TAG, "[GEMINI_LOOKUP] Request failed: $maskedError")
                return@withContext FreshKnowledgeResult(
                    isSuccess = false,
                    query = sanitizedQuery,
                    summary = "Unable to fetch live information right now.",
                    errorMessage = "HTTP_$responseCode"
                )
            }

            val responseText = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).readText()
            val jsonResponse = JSONObject(responseText)
            val candidates = jsonResponse.optJSONArray("candidates")
            val firstCandidate = candidates?.optJSONObject(0)
            val contentObj = firstCandidate?.optJSONObject("content")
            val parts = contentObj?.optJSONArray("parts")
            val rawOutput = parts?.optJSONObject(0)?.optString("text") ?: ""

            Log.i(TAG, "[DETERMINISTIC_BRAIN] Parsing structured knowledge result...")
            val parsedResult = parseKnowledgeJson(rawOutput, sanitizedQuery)
            Log.i(TAG, "[PHYSICAL_EXECUTION] Fresh knowledge resolved: '${parsedResult.summary}'")
            parsedResult

        } catch (e: Exception) {
            val maskedMsg = GeminiApiClient.maskKeyInText(e.message ?: "Unknown error", apiKey)
            Log.e(TAG, "[GEMINI_LOOKUP] Network/API error: $maskedMsg", e)
            FreshKnowledgeResult(
                isSuccess = false,
                query = sanitizedQuery,
                summary = "Failed to connect to knowledge service.",
                errorMessage = e.javaClass.simpleName
            )
        }
    }

    private fun parseKnowledgeJson(rawJson: String, query: String): FreshKnowledgeResult {
        return try {
            val clean = rawJson.trim().removePrefix("```json").removePrefix("```").removeSuffix("```").trim()
            val obj = JSONObject(clean)
            val summary = obj.optString("summary", "Information resolved.")
            val servicesList = mutableListOf<MediaServiceOption>()

            val servicesArray = obj.optJSONArray("services")
            if (servicesArray != null) {
                for (i in 0 until servicesArray.length()) {
                    val s = servicesArray.optJSONObject(i) ?: continue
                    servicesList.add(
                        MediaServiceOption(
                            serviceName = s.optString("name", "Unknown"),
                            isAvailable = s.optBoolean("available", false),
                            confidence = s.optString("confidence", "HIGH"),
                            notes = s.optString("notes").takeIf { it.isNotBlank() }
                        )
                    )
                }
            }

            FreshKnowledgeResult(
                isSuccess = true,
                query = query,
                summary = summary,
                mediaServices = servicesList
            )
        } catch (e: Exception) {
            Log.w(TAG, "[DETERMINISTIC_BRAIN] Could not parse JSON, returning raw text: $rawJson")
            FreshKnowledgeResult(
                isSuccess = true,
                query = query,
                summary = rawJson.ifBlank { "Information fetched." }
            )
        }
    }
}
