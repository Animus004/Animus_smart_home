package com.animus.smartroom.core.brain.adaptive

import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.health.DeviceHealthStatus
import com.animus.smartroom.core.brain.health.RoomHealthState
import com.animus.smartroom.core.brain.health.RoutineRequirements
import com.animus.smartroom.core.brain.router.CapabilityRegistry

/**
 * Categorized physical defects detected during live routine observation.
 */
enum class StateDefectType {
    PROJECTOR_POWER_LOST,
    PROJECTOR_INPUT_ALTERED,
    FIRE_TV_ASLEEP,
    AUDIO_OWNERSHIP_LOST,
    DEVICE_UNREACHABLE,
    AC_TEMPERATURE_DRIFT,
    UNEXPECTED_MEDIA_STATE
}

enum class DivergenceSeverity {
    NONE,
    MINOR_RECOVERABLE,
    DEGRADED_PERMISSIBLE,
    CRITICAL_BLOCKING
}

data class StateDefect(
    val type: StateDefectType,
    val target: CapabilityRegistry.DeviceTarget,
    val resource: PhysicalResource? = null,
    val expectedValue: String,
    val actualValue: String,
    val repairCapability: CapabilityRegistry.ActionCapability?,
    val isCritical: Boolean = true
)

data class DivergenceReport(
    val isDiverged: Boolean,
    val severity: DivergenceSeverity,
    val defects: List<StateDefect> = emptyList(),
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Continuous Physical State Observer & Divergence Detector.
 * Compares expected room invariants against authoritative real-time physical sensor readings.
 */
object StateDivergenceDetector {

    fun detectDivergence(
        routineName: String,
        requirements: RoutineRequirements,
        healthState: RoomHealthState,
        expectedAudioOwner: ResourceOwner? = null
    ): DivergenceReport {
        val defects = mutableListOf<StateDefect>()
        val normRoutine = routineName.uppercase()

        // 1. Check reachability of all required devices
        for (reqTarget in requirements.requiredDevices) {
            val devState = healthState.deviceStates[reqTarget]
            if (devState == null || !devState.reachable || devState.status == DeviceHealthStatus.UNAVAILABLE) {
                defects.add(
                    StateDefect(
                        type = StateDefectType.DEVICE_UNREACHABLE,
                        target = reqTarget,
                        expectedValue = "REACHABLE",
                        actualValue = devState?.status?.name ?: "UNREACHABLE",
                        repairCapability = null,
                        isCritical = true
                    )
                )
            }
        }

        // 2. Routine-specific invariant verification
        if (normRoutine.contains("MOVIE") || normRoutine.contains("CINEMA")) {
            val projState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.PROJECTOR]
            val fireState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.FIRE_TV]
            val audioState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.AUDIO]

            // Check Projector Power
            if (projState != null && projState.reachable && projState.poweredOn == false) {
                defects.add(
                    StateDefect(
                        type = StateDefectType.PROJECTOR_POWER_LOST,
                        target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                        resource = PhysicalResource.PROJECTOR_DISPLAY,
                        expectedValue = "ON",
                        actualValue = "OFF",
                        repairCapability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON,
                        isCritical = true
                    )
                )
            }

            // Check Projector HDMI Source
            if (projState != null && projState.reachable && projState.poweredOn == true && projState.currentInput != null && projState.currentInput != "HDMI_1") {
                defects.add(
                    StateDefect(
                        type = StateDefectType.PROJECTOR_INPUT_ALTERED,
                        target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                        resource = PhysicalResource.PROJECTOR_HDMI_INPUT,
                        expectedValue = "HDMI_1",
                        actualValue = projState.currentInput ?: "UNKNOWN",
                        repairCapability = CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
                        isCritical = false
                    )
                )
            }

            // Check Fire TV Wake State
            if (fireState != null && fireState.reachable && fireState.poweredOn == false) {
                defects.add(
                    StateDefect(
                        type = StateDefectType.FIRE_TV_ASLEEP,
                        target = CapabilityRegistry.DeviceTarget.FIRE_TV,
                        resource = PhysicalResource.FIRE_TV_PLAYBACK,
                        expectedValue = "AWAKE",
                        actualValue = "ASLEEP",
                        repairCapability = CapabilityRegistry.ActionCapability.FIRE_TV_WAKE,
                        isCritical = true
                    )
                )
            }

            // Check LG Soundbar Ownership
            val expectedOwner = expectedAudioOwner ?: ResourceOwner.FIRE_TV
            if (audioState != null && audioState.currentOwner != null && audioState.currentOwner != expectedOwner.name) {
                defects.add(
                    StateDefect(
                        type = StateDefectType.AUDIO_OWNERSHIP_LOST,
                        target = CapabilityRegistry.DeviceTarget.AUDIO,
                        resource = PhysicalResource.LG_SNC4R_AUDIO,
                        expectedValue = expectedOwner.name,
                        actualValue = audioState.currentOwner ?: "NONE",
                        repairCapability = CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
                        isCritical = true
                    )
                )
            }
        } else if (normRoutine.contains("MUSIC") || normRoutine.contains("SONG")) {
            val audioState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.AUDIO]
            val expectedOwner = expectedAudioOwner ?: ResourceOwner.PC
            if (audioState != null && audioState.currentOwner != null && audioState.currentOwner != expectedOwner.name) {
                defects.add(
                    StateDefect(
                        type = StateDefectType.AUDIO_OWNERSHIP_LOST,
                        target = CapabilityRegistry.DeviceTarget.AUDIO,
                        resource = PhysicalResource.LG_SNC4R_AUDIO,
                        expectedValue = expectedOwner.name,
                        actualValue = audioState.currentOwner ?: "NONE",
                        repairCapability = CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
                        isCritical = true
                    )
                )
            }
        }

        val isDiverged = defects.isNotEmpty()
        val severity = when {
            defects.isEmpty() -> DivergenceSeverity.NONE
            defects.any { it.type == StateDefectType.DEVICE_UNREACHABLE && it.isCritical } -> DivergenceSeverity.CRITICAL_BLOCKING
            defects.any { it.isCritical } -> DivergenceSeverity.MINOR_RECOVERABLE
            else -> DivergenceSeverity.DEGRADED_PERMISSIBLE
        }

        return DivergenceReport(
            isDiverged = isDiverged,
            severity = severity,
            defects = defects
        )
    }
}
