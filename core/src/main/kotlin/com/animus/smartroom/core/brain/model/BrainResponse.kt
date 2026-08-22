package com.animus.smartroom.core.brain.model

sealed interface BrainResponse {

    data class Command(
        val spokenResponse: String? = null,
        val actions: List<BrainAction>
    ) : BrainResponse {
        constructor(spokenResponse: String?, action: BrainAction) : this(spokenResponse, listOf(action))
        constructor(action: BrainAction) : this(null, listOf(action))
    }

    data class Conversation(
        val spokenResponse: String
    ) : BrainResponse

    data class Clarification(
        val question: String,
        val options: List<String> = emptyList()
    ) : BrainResponse

    data class Failure(
        val reason: String,
        val cause: Throwable? = null
    ) : BrainResponse
}
