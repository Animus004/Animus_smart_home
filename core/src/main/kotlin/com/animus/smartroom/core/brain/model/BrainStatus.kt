package com.animus.smartroom.core.brain.model

/**
 * Authoritative formal lifecycle state machine for the Animus Local Brain.
 */
enum class BrainState {
    OFFLINE,
    STARTING,
    SERVER_READY,
    MODEL_LOADING,
    READY,
    BUSY,
    RECOVERING,
    FAILED
}

/**
 * Structured Brain response contract preventing raw HTTP/Gin infrastructure errors
 * from leaking to the Android UI and voice synthesis pipeline.
 */
data class BrainStatusResponse(
    val success: Boolean,
    val state: BrainState,
    val message: String,
    val retryable: Boolean,
    val latencyMs: Long? = null,
    val activeModel: String? = null,
    val requestId: String? = null
)
