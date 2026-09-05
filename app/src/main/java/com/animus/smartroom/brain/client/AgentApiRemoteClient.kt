package com.animus.smartroom.brain.client

import android.util.Log
import com.animus.smartroom.brain.model.AgentInteractionResponseDto
import com.animus.smartroom.brain.model.BrainResult
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Authoritative HTTP Client connecting Android to Python Phase F backend.
 * Endpoint: POST http://<host>:8095/api/agent/interact
 */
class AgentApiRemoteClient(
    private val hostProvider: () -> String = { "192.168.1.4" },
    private val port: Int = 8095,
    private val connectTimeoutMs: Int = 5000,
    private val readTimeoutMs: Int = 135000
) {

    companion object {
        private const val TAG = "AgentApiRemoteClient"
        private const val AGENT_INTERACT_PATH = "/api/agent/interact"
    }

    val baseUrl: String
        get() = "http://${hostProvider()}:$port"

    suspend fun interact(utterance: String): BrainResult = withContext(Dispatchers.IO) {
        val trimmed = utterance.trim()
        if (trimmed.isBlank()) {
            return@withContext BrainResult.Failure("Utterance was blank")
        }

        var connection: HttpURLConnection? = null
        try {
            val url = URL("$baseUrl$AGENT_INTERACT_PATH")
            Log.i(TAG, "[interact] POST $url -> '$trimmed'")

            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                doInput = true
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Accept", "application/json")
            }

            val requestJson = JSONObject().apply {
                put("utterance", trimmed)
            }

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(requestJson.toString())
                writer.flush()
            }

            val responseCode = connection.responseCode
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val responseText = BufferedReader(InputStreamReader(connection.inputStream, Charsets.UTF_8)).use { reader ->
                    reader.readText()
                }
                Log.i(TAG, "[interact] Received HTTP 200 (${responseText.length} bytes)")

                val json = JSONObject(responseText)
                val dto = AgentInteractionResponseDto.fromJson(json)

                BrainResult.RemoteAgentSuccess(
                    agentMessage = dto.agentMessage,
                    understoodIntent = dto.understoodIntent,
                    actionTaken = dto.actionTaken,
                    followupRequired = dto.followupRequired,
                    followupQuestion = dto.followupQuestion,
                    rawResponse = responseText
                )
            } else {
                val errorBody = try {
                    BufferedReader(InputStreamReader(connection.errorStream ?: connection.inputStream, Charsets.UTF_8)).use { it.readText() }
                } catch (t: Throwable) {
                    "HTTP $responseCode"
                }
                Log.e(TAG, "[interact] Backend HTTP error $responseCode: $errorBody")
                BrainResult.Failure("Backend returned HTTP $responseCode: $errorBody")
            }
        } catch (e: Exception) {
            Log.e(TAG, "[interact] Network failure communicating with Phase F agent: ${e.message}", e)
            BrainResult.Failure("Failed to connect to Animus agent: ${e.localizedMessage}", e)
        } finally {
            try {
                connection?.disconnect()
            } catch (_: Exception) {}
        }
    }
}
