package com.animus.smartroom.brain.model

import com.animus.smartroom.command.model.AnimusCommand

sealed interface BrainResult {
    data class Success(
        val command: AnimusCommand,
        val rawResponse: String? = null
    ) : BrainResult

    data class InvalidResponse(
        val reason: String,
        val rawResponse: String? = null
    ) : BrainResult

    data class Failure(
        val errorMessage: String,
        val cause: Throwable? = null
    ) : BrainResult

    data object Unavailable : BrainResult
}
