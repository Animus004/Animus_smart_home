package com.animus.smartroom.core.brain.health

import com.animus.smartroom.core.brain.router.CapabilityRegistry

/**
 * Health status of an individual device or room subsystem.
 */
enum class DeviceHealthStatus {
    HEALTHY,
    DEGRADED,
    UNAVAILABLE,
    TIMEOUT,
    UNKNOWN
}

/**
 * Cache freshness classification.
 */
enum class CacheFreshness {
    KNOWN_CURRENT,
    KNOWN_RECENT,
    STALE,
    TIMEOUT,
    UNKNOWN
}

/**
 * Health descriptor for a single device target.
 */
data class DeviceHealth(
    val device: CapabilityRegistry.DeviceTarget,
    val reachable: Boolean = true,
    val poweredOn: Boolean? = null,
    val connected: Boolean? = null,
    val currentInput: String? = null,
    val currentOwner: String? = null,
    val relevantCapabilityState: Map<String, Any?> = emptyMap(),
    val status: DeviceHealthStatus = DeviceHealthStatus.HEALTHY,
    val freshness: CacheFreshness = CacheFreshness.KNOWN_CURRENT,
    val latencyMs: Long = 0L,
    val error: String? = null
)

/**
 * Aggregated room health state vector across all devices.
 */
data class RoomHealthState(
    val timestamp: Long = System.currentTimeMillis(),
    val overallHealth: DeviceHealthStatus = DeviceHealthStatus.HEALTHY,
    val deviceStates: Map<CapabilityRegistry.DeviceTarget, DeviceHealth> = emptyMap(),
    val arbitrationStates: Map<String, String> = emptyMap(),
    val totalProbeLatencyMs: Long = 0L,
    val summary: String = "All systems healthy."
) {
    fun isDeviceHealthy(target: CapabilityRegistry.DeviceTarget): Boolean {
        val st = deviceStates[target] ?: return false
        return st.status == DeviceHealthStatus.HEALTHY && st.reachable
    }

    fun isDeviceAvailable(target: CapabilityRegistry.DeviceTarget): Boolean {
        val st = deviceStates[target] ?: return false
        return st.status != DeviceHealthStatus.UNAVAILABLE && st.status != DeviceHealthStatus.TIMEOUT
    }
}
