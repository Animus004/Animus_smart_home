package com.animus.smartroom.ui.glass

import java.util.UUID

enum class ActionExecutionState {
    IDLE,
    EXECUTING,
    VERIFYING,
    VERIFIED_SUCCESS,
    RECOVERING,
    ERROR_BLOCKED,
    DISMISSED
}

enum class FeedbackSeverity {
    INFO,
    SUCCESS,
    WARNING,
    ERROR
}

data class ActionFeedback(
    val requestId: String = UUID.randomUUID().toString(),
    val intent: String = "",
    val targetDevice: String? = null,
    val state: ActionExecutionState = ActionExecutionState.IDLE,
    val message: String = "",
    val severity: FeedbackSeverity = FeedbackSeverity.INFO,
    val isPersistent: Boolean = false,
    val timestamp: Long = System.currentTimeMillis()
)
