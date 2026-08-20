package com.animus.smartroom.brain.provider

import android.util.Log
import com.animus.smartroom.brain.AnimusBrain
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult

class CloudAnimusBrain(
    private val apiKeyProvider: () -> String? = { null },
    private val apiClient: GeminiApiClient = GeminiApiClient()
) : AnimusBrain {

    companion object {
        private const val TAG = "CloudAnimusBrain"
    }

    override val providerType: BrainProviderType = BrainProviderType.GEMINI

    override suspend fun interpret(input: String): BrainResult {
        val apiKey = apiKeyProvider()?.trim()
        if (apiKey.isNullOrBlank()) {
            Log.w(TAG, "[interpret] Gemini API key is missing.")
            return BrainResult.Failure("Gemini API key is required. Tap Brain badge to configure.")
        }

        Log.i(TAG, "[interpret] Querying Gemini Cloud Brain for input: '$input'")

        val apiResult = apiClient.generateContent(apiKey, input)

        return apiResult.fold(
            onSuccess = { rawJson ->
                Log.d(TAG, "[interpret] Received raw response from Gemini: $rawJson")
                when (val validation = BrainCommandValidator.parseAndValidateJson(rawJson)) {
                    is BrainValidationResult.Valid -> {
                        Log.i(TAG, "[interpret] Validated command from Gemini: ${validation.command::class.simpleName}")
                        BrainResult.Success(validation.command, rawResponse = rawJson)
                    }
                    is BrainValidationResult.Invalid -> {
                        Log.w(TAG, "[interpret] Gemini response failed validation: ${validation.reason}")
                        BrainResult.InvalidResponse(validation.reason, rawResponse = rawJson)
                    }
                }
            },
            onFailure = { error ->
                Log.e(TAG, "[interpret] Gemini API call failed: ${error.message}", error)
                BrainResult.Failure(error.message ?: "Cloud AI communication failure", error)
            }
        )
    }

    fun parseCloudResponse(jsonResponse: String): BrainResult {
        return when (val validation = BrainCommandValidator.parseAndValidateJson(jsonResponse)) {
            is BrainValidationResult.Valid -> BrainResult.Success(validation.command, rawResponse = jsonResponse)
            is BrainValidationResult.Invalid -> BrainResult.InvalidResponse(validation.reason, rawResponse = jsonResponse)
        }
    }
}
