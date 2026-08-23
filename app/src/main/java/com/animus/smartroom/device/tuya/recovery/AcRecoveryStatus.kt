package com.animus.smartroom.device.tuya.recovery

enum class RecoveryConfidence {
    HIGH,
    MEDIUM,
    LOW
}

/**
 * Diagnostic and telemetry status snapshot for the AC recovery lifecycle.
 */
data class AcRecoveryStatus(
    val device: String = "Bedroom AC",
    val deviceId: String = "76776532a4e57c0a2ca4",
    val state: AcRecoveryState = AcRecoveryState.IDLE,
    val provisioningMode: String = "UNKNOWN",
    val deviceDiscovered: Boolean = false,
    val cloudReachable: Boolean = false,
    val sameDeviceIdVerified: Boolean = false,
    val currentIp: String? = null,
    val attemptCount: Int = 0,
    val maxAttempts: Int = 5,
    val reason: String = "",
    val nextAction: String = "",
    val lastSeenTimestamp: Long = 0L,
    val confidence: RecoveryConfidence = RecoveryConfidence.HIGH
)
