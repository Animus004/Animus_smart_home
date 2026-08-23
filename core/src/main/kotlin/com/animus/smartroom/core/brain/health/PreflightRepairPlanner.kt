package com.animus.smartroom.core.brain.health

import com.animus.smartroom.core.brain.arbitration.ArbitrationPolicy
import com.animus.smartroom.core.brain.arbitration.PhysicalResource
import com.animus.smartroom.core.brain.arbitration.ResourceOwner
import com.animus.smartroom.core.brain.router.CapabilityRegistry

/**
 * Pre-flight decision outcome.
 */
enum class PreflightDecision {
    PROCEED,
    REPAIR_THEN_PROCEED,
    PROCEED_WITH_DEGRADED_MODE,
    BLOCK_REQUIRES_USER_ACTION,
    FAIL_TERMINAL
}

/**
 * Deterministic pre-flight plan containing defect repairs and verification checkpoints.
 */
data class PreflightPlan(
    val routine: String,
    val decision: PreflightDecision,
    val repairs: List<CapabilityRegistry.ActionCapability> = emptyList(),
    val requiredArbitrations: Map<PhysicalResource, ResourceOwner> = emptyMap(),
    val verificationCheckpoints: List<String> = emptyList(),
    val reason: String? = null
)

/**
 * Deterministic defect analyzer and pre-flight repair planner.
 */
object PreflightRepairPlanner {

    fun planPreflight(
        requirements: RoutineRequirements,
        healthState: RoomHealthState
    ): PreflightPlan {
        val routine = requirements.routineOrIntent
        val repairs = mutableListOf<CapabilityRegistry.ActionCapability>()
        val arbitrations = mutableMapOf<PhysicalResource, ResourceOwner>()
        val verification = mutableListOf<String>()

        // 1. If any critical required device is unreachable / timeout, block
        for (req in requirements.requiredDevices) {
            val devState = healthState.deviceStates[req]
            if (devState == null || !devState.reachable || devState.status == DeviceHealthStatus.TIMEOUT) {
                return PreflightPlan(
                    routine = routine,
                    decision = PreflightDecision.BLOCK_REQUIRES_USER_ACTION,
                    reason = "Required device $req is unreachable or timed out."
                )
            }
        }

        // 2. Routine-specific defect checks and repair generation
        when {
            routine.contains("MOVIE") || routine.contains("CINEMA") -> {
                val projState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.PROJECTOR]
                val fireState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.FIRE_TV]
                val audioState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.AUDIO]

                // Projector power defect
                if (projState?.poweredOn != true) {
                    repairs.add(CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON)
                }
                verification.add("PROJECTOR_POWERED_ON")

                // Projector input defect
                if (projState?.currentInput != "HDMI_1") {
                    repairs.add(CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT)
                }
                verification.add("PROJECTOR_INPUT_HDMI_1")

                // Fire TV wake defect
                if (fireState?.poweredOn != true) {
                    repairs.add(CapabilityRegistry.ActionCapability.FIRE_TV_WAKE)
                }
                verification.add("FIRE_TV_AWAKE")

                // Audio Arbitration: Movie mode requires Fire TV to own LG soundbar
                val desiredAudioOwner = ArbitrationPolicy.resolveDesiredOwner(PhysicalResource.LG_SNC4R_AUDIO, "MOVIE_MODE")
                if (audioState?.currentOwner != desiredAudioOwner.name) {
                    arbitrations[PhysicalResource.LG_SNC4R_AUDIO] = desiredAudioOwner
                    repairs.add(CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG)
                }
                verification.add("AUDIO_OWNED_BY_FIRE_TV")
            }

            routine.contains("MUSIC") || routine.contains("SONG") -> {
                val audioState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.AUDIO]
                val desiredAudioOwner = ArbitrationPolicy.resolveDesiredOwner(PhysicalResource.LG_SNC4R_AUDIO, "MUSIC_MODE")
                if (audioState?.currentOwner != desiredAudioOwner.name) {
                    arbitrations[PhysicalResource.LG_SNC4R_AUDIO] = desiredAudioOwner
                    repairs.add(CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG)
                }
                verification.add("AUDIO_OWNED_BY_PHONE")
                repairs.add(CapabilityRegistry.ActionCapability.MEDIA_PLAY)
                verification.add("MEDIA_PLAYBACK_ACTIVE")
            }

            routine.contains("WORK") -> {
                val acState = healthState.deviceStates[CapabilityRegistry.DeviceTarget.AC]
                if (acState?.poweredOn != true) {
                    repairs.add(CapabilityRegistry.ActionCapability.AC_POWER_ON)
                }
                repairs.add(CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE)
                verification.add("AC_COMFORT_TEMP")
            }

            routine.contains("GOODNIGHT") -> {
                repairs.add(CapabilityRegistry.ActionCapability.MEDIA_STOP)
                repairs.add(CapabilityRegistry.ActionCapability.PROJECTOR_POWER_OFF)
                repairs.add(CapabilityRegistry.ActionCapability.AUDIO_DISCONNECT_LG)
                repairs.add(CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE)
                verification.add("ALL_DEVICES_OFF_OR_SLEEP")
            }

            else -> {
                // Direct device commands
                for (cap in requirements.requiredCapabilities) {
                    repairs.add(cap)
                    verification.add("${cap.name}_VERIFIED")
                }
            }
        }

        val decision = if (repairs.isEmpty()) {
            PreflightDecision.PROCEED
        } else if (healthState.overallHealth == DeviceHealthStatus.DEGRADED) {
            PreflightDecision.PROCEED_WITH_DEGRADED_MODE
        } else {
            PreflightDecision.REPAIR_THEN_PROCEED
        }

        return PreflightPlan(
            routine = routine,
            decision = decision,
            repairs = repairs,
            requiredArbitrations = arbitrations,
            verificationCheckpoints = verification
        )
    }
}
