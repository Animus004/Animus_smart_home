package com.animus.smartroom.core.device

/**
 * Result of a low-level device transport write operation.
 */
data class TransportResult(
    val success: Boolean,
    val message: String = "",
    val rawResponse: String? = null
)

/**
 * Result of a low-level device transport read operation.
 */
data class TransportStateResult(
    val success: Boolean,
    val stateProperties: Map<String, Any> = emptyMap(),
    val errorMessage: String? = null
)
