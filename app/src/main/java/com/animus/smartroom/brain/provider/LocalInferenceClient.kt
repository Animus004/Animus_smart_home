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

class LocalInferenceClient(
    private val configProvider: () -> LocalBrainConfig
) {
    private val ollamaClient = OllamaLocalLlmClient(configProvider)

    val lastInferenceDurationMs: Long
        get() = ollamaClient.lastInferenceDurationMs

    suspend fun generateCompletion(
        prompt: String,
        contextPrompts: List<String> = emptyList()
    ): Result<String> {
        return ollamaClient.generateCompletion(prompt, contextPrompts)
    }

    suspend fun warmUp(prompt: String = "Respond with exactly: READY"): Result<String> {
        return ollamaClient.generateCompletion(prompt, isWarmup = true)
    }

    suspend fun ping(): Boolean {
        return ollamaClient.ping()
    }
}
