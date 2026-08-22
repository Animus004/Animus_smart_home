package com.animus.smartroom.brain.provider

import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainContext
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.model.MusicActionType
import com.animus.smartroom.core.brain.port.BrainProvider
import org.json.JSONObject

class GeminiBrainProvider(
    private val apiKeyProvider: () -> String?,
    private val apiClient: GeminiApiClient = GeminiApiClient()
) : BrainProvider {

    override fun isAvailable(): Boolean {
        val key = apiKeyProvider()
        return !key.isNullOrBlank()
    }

    override suspend fun understand(input: String, context: BrainContext): BrainResponse {
        val apiKey = apiKeyProvider()?.trim()
        if (apiKey.isNullOrBlank()) {
            return BrainResponse.Failure("Gemini API key is required.")
        }

        val prompt = buildStructuredPrompt(input, context)
        val apiResult = apiClient.generateContent(apiKey, prompt)

        return apiResult.fold(
            onSuccess = { rawText ->
                parseGeminiResponse(rawText, input)
            },
            onFailure = { error ->
                BrainResponse.Failure(error.message ?: "Cloud AI communication error", error)
            }
        )
    }

    private fun buildStructuredPrompt(input: String, context: BrainContext): String {
        return """
            You are Animus Brain, a smart room assistant.
            Current context:
            - Time: ${context.currentTimeMillis}
            - Preferred Temp: ${context.userPreferences.preferredTemperatureCelsius}°C
            - Preferred Speaker: ${context.userPreferences.preferredSpeaker ?: "None"}
            - Music Playing: ${context.currentMusicSummary?.isPlaying == true}
            - Active Timers: ${context.scheduledActions.size}

            User input: "$input"

            Respond in JSON:
            {
              "spokenResponse": "Brief spoken feedback to the user",
              "action": "PLAY_MUSIC|SET_VOLUME|DEVICE_COMMAND|SCHEDULE_ACTION|CONVERSATION",
              "target": "AC|SPEAKER|MUSIC",
              "parameters": {}
            }
        """.trimIndent()
    }

    private fun parseGeminiResponse(rawJson: String, originalInput: String): BrainResponse {
        return try {
            val json = JSONObject(rawJson)
            val spoken = json.optString("spokenResponse").takeIf { it.isNotBlank() }
            val actionType = json.optString("action", "CONVERSATION")

            when (actionType) {
                "PLAY_MUSIC" -> {
                    val title = json.optJSONObject("parameters")?.optString("title") ?: originalInput
                    BrainResponse.Command(spoken, BrainAction.PlayMusic(title))
                }
                "SET_VOLUME" -> {
                    val percent = json.optJSONObject("parameters")?.optInt("percentage", 50) ?: 50
                    BrainResponse.Command(spoken, BrainAction.SetVolume(percent))
                }
                "PAUSE_MUSIC" -> {
                    BrainResponse.Command(spoken, BrainAction.MusicControl(MusicActionType.PAUSE))
                }
                "RESUME_MUSIC" -> {
                    BrainResponse.Command(spoken, BrainAction.MusicControl(MusicActionType.RESUME))
                }
                else -> {
                    BrainResponse.Conversation(spoken ?: "I understand.")
                }
            }
        } catch (e: Exception) {
            BrainResponse.Conversation(rawJson)
        }
    }
}
