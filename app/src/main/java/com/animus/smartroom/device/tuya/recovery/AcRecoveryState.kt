package com.animus.smartroom.device.tuya.recovery

/**
 * Represents the distinct lifecycle states of the AC Wi-Fi recovery subsystem.
 */
enum class AcRecoveryState {
    /** Controller is idle; AC is operating normally or hasn't been probed. */
    IDLE,

    /** AC has been detected as offline / unreachable. */
    OFFLINE,

    /** Waiting for physical user action (e.g., IR remote button or power cycle). */
    WAITING_FOR_USER,

    /** Fast blinking Wi-Fi LED / EZ SmartConfig mode detected or reported. */
    FAST_BLINK_DETECTED,

    /** Slow blinking Wi-Fi LED / AP hotspot mode detected or reported. */
    SLOW_BLINK_DETECTED,

    /** Listening on local network (UDP 6667 / 6666) for device re-announcement. */
    DISCOVERING,

    /** Provisioning or association payload in progress. */
    PROVISIONING,

    /** Device associated; waiting for IP / cloud routing stabilization. */
    WAITING_FOR_NETWORK,

    /** Polling live Tuya cloud / local status to verify readback and telemetry. */
    VERIFYING,

    /** AC has successfully reconnected and verified with identical device ID. */
    RECOVERED,

    /** Recovery attempts exceeded bounded limit without successful verification. */
    FAILED,

    /** Recovery requires physical reset or remote button press. */
    MANUAL_INTERVENTION_REQUIRED
}
