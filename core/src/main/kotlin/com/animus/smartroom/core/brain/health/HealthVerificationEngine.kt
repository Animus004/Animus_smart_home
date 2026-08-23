package com.animus.smartroom.core.brain.health

import com.animus.smartroom.core.brain.router.CapabilityRegistry
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.ConcurrentHashMap

/**
 * Interface for probing a physical device's health and connection state.
 */
interface DeviceHealthProbe {
    val target: CapabilityRegistry.DeviceTarget
    suspend fun probe(): DeviceHealth
}

/**
 * Default simulated probe for tests and standalone mode.
 */
class DefaultDeviceHealthProbe(
    override val target: CapabilityRegistry.DeviceTarget,
    private val healthy: Boolean = true,
    private val delayMs: Long = 20L
) : DeviceHealthProbe {
    override suspend fun probe(): DeviceHealth {
        val t0 = System.currentTimeMillis()
        if (delayMs > 0) {
            kotlinx.coroutines.delay(delayMs)
        }
        val dur = System.currentTimeMillis() - t0
        return if (healthy) {
            DeviceHealth(
                device = target,
                reachable = true,
                poweredOn = true,
                connected = true,
                status = DeviceHealthStatus.HEALTHY,
                latencyMs = dur
            )
        } else {
            DeviceHealth(
                device = target,
                reachable = false,
                status = DeviceHealthStatus.UNAVAILABLE,
                latencyMs = dur,
                error = "Device unreachable"
            )
        }
    }
}

/**
 * Parallel Health Verification Engine.
 * Concurrently queries required devices for a routine, producing a unified RoomHealthState vector.
 */
class HealthVerificationEngine(
    private val registeredProbes: ConcurrentHashMap<CapabilityRegistry.DeviceTarget, DeviceHealthProbe> = ConcurrentHashMap()
) {

    fun registerProbe(probe: DeviceHealthProbe) {
        registeredProbes[probe.target] = probe
    }

    suspend fun verifyHealthParallel(
        requirements: RoutineRequirements,
        customProbes: Map<CapabilityRegistry.DeviceTarget, DeviceHealthProbe> = emptyMap(),
        perDeviceTimeoutMs: Long = 2000L
    ): RoomHealthState = coroutineScope {
        val t0 = System.currentTimeMillis()
        val targetsToCheck = requirements.requiredDevices + requirements.optionalDevices

        // Launch concurrent probes
        val deferredProbes = targetsToCheck.map { target ->
            async {
                val probe = customProbes[target]
                    ?: registeredProbes[target]
                    ?: DefaultDeviceHealthProbe(target)

                val probeT0 = System.currentTimeMillis()
                try {
                    val result = withTimeoutOrNull(perDeviceTimeoutMs) {
                        probe.probe()
                    }
                    if (result != null) {
                        result
                    } else {
                        DeviceHealth(
                            device = target,
                            reachable = false,
                            status = DeviceHealthStatus.TIMEOUT,
                            freshness = CacheFreshness.TIMEOUT,
                            latencyMs = System.currentTimeMillis() - probeT0,
                            error = "Probe timed out after ${perDeviceTimeoutMs}ms"
                        )
                    }
                } catch (e: Exception) {
                    DeviceHealth(
                        device = target,
                        reachable = false,
                        status = DeviceHealthStatus.UNAVAILABLE,
                        latencyMs = System.currentTimeMillis() - probeT0,
                        error = "Probe error: ${e.message}"
                    )
                }
            }
        }

        val results = deferredProbes.awaitAll()
        val totalDuration = System.currentTimeMillis() - t0

        val deviceStates = results.associateBy { it.device }

        // Evaluate overall health based on required vs optional devices
        var overall = DeviceHealthStatus.HEALTHY
        var hasRequiredFailure = false
        var hasOptionalFailure = false

        for (req in requirements.requiredDevices) {
            val st = deviceStates[req]
            if (st == null || st.status != DeviceHealthStatus.HEALTHY) {
                hasRequiredFailure = true
                break
            }
        }

        for (opt in requirements.optionalDevices) {
            val st = deviceStates[opt]
            if (st != null && st.status != DeviceHealthStatus.HEALTHY) {
                hasOptionalFailure = true
                break
            }
        }

        if (hasRequiredFailure) {
            overall = DeviceHealthStatus.UNAVAILABLE
        } else if (hasOptionalFailure) {
            overall = DeviceHealthStatus.DEGRADED
        }

        val summary = when (overall) {
            DeviceHealthStatus.HEALTHY -> "All ${requirements.requiredDevices.size} required devices healthy."
            DeviceHealthStatus.DEGRADED -> "Required devices healthy; some optional devices degraded."
            DeviceHealthStatus.UNAVAILABLE -> "One or more required devices are unavailable."
            else -> "Health status: $overall"
        }

        RoomHealthState(
            timestamp = System.currentTimeMillis(),
            overallHealth = overall,
            deviceStates = deviceStates,
            totalProbeLatencyMs = totalDuration,
            summary = summary
        )
    }
}
