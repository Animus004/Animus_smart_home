package com.animus.smartroom.routine.model

enum class RoutineType {
    SLEEP
}

enum class RoutineStatus {
    SCHEDULED,
    ACTIVE,
    ALARMING,
    COMPLETED,
    CANCELLED,
    FAILED
}

data class EnvironmentSnapshot(
    val isSpeakerConnected: Boolean = false,
    val speakerName: String? = null,
    val mediaVolume: Float = 0.5f,
    val isMusicPlaying: Boolean = false,
    val acPower: Boolean? = null,
    val acTargetTemperature: Int? = null,
    val acMode: String? = null,
    val acFanSpeed: String? = null
)

data class RoutineState(
    val id: String,
    val type: RoutineType = RoutineType.SLEEP,
    val createdAt: Long = System.currentTimeMillis(),
    val scheduledWakeTime: Long? = null,
    val status: RoutineStatus = RoutineStatus.ACTIVE,
    val failureReason: String? = null,
    val initialSnapshot: EnvironmentSnapshot? = null
) {
    val isActive: Boolean
        get() = status == RoutineStatus.ACTIVE || status == RoutineStatus.SCHEDULED || status == RoutineStatus.ALARMING

    val isAlarming: Boolean
        get() = status == RoutineStatus.ALARMING
}
