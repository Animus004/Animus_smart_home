package com.animus.smartroom.brain.model

import com.animus.smartroom.command.model.AnimusCommand

sealed interface BrainResult {
    data class Success(
        val commands: List<AnimusCommand>,
        val rawResponse: String? = null
    ) : BrainResult {
        // Convenience constructor for single-command results
        constructor(command: AnimusCommand, rawResponse: String? = null) : this(
            commands = listOf(command),
            rawResponse = rawResponse
        )

        // Backward compatibility accessor for single-command consumers
        val command: AnimusCommand
            get() = commands.firstOrNull() ?: AnimusCommand.UnknownCommand("")
    }

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
