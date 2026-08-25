package com.animus.smartroom.core.voice

enum class WakeWordState {
    IDLE,
    WAKE_LISTENING,
    WAKE_DETECTED,
    CAPTURING_COMMAND,
    PROCESSING_COMMAND,
    SPEAKING_RESPONSE,
    RETURNING_TO_WAKE_LISTENING,
    ERROR
}
