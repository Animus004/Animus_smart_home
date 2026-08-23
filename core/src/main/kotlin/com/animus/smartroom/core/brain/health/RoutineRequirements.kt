package com.animus.smartroom.core.brain.health

import com.animus.smartroom.core.brain.router.CapabilityRegistry
import java.util.Locale

/**
 * Routine pre-flight requirements specification.
 * Filters health checks so only devices relevant to the requested routine or command are queried.
 */
data class RoutineRequirements(
    val routineOrIntent: String,
    val requiredDevices: Set<CapabilityRegistry.DeviceTarget>,
    val optionalDevices: Set<CapabilityRegistry.DeviceTarget> = emptySet(),
    val requiredCapabilities: Set<CapabilityRegistry.ActionCapability> = emptySet()
) {
    companion object {
        fun forIntent(intentOrRoutine: String, targetDevice: CapabilityRegistry.DeviceTarget? = null): RoutineRequirements {
            val norm = intentOrRoutine.trim().uppercase(Locale.ROOT)

            return when {
                norm.contains("MOVIE") || norm.contains("CINEMA") -> RoutineRequirements(
                    routineOrIntent = "MOVIE_MODE",
                    requiredDevices = setOf(
                        CapabilityRegistry.DeviceTarget.PROJECTOR,
                        CapabilityRegistry.DeviceTarget.FIRE_TV,
                        CapabilityRegistry.DeviceTarget.AUDIO
                    ),
                    optionalDevices = setOf(CapabilityRegistry.DeviceTarget.AC),
                    requiredCapabilities = setOf(
                        CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON,
                        CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
                        CapabilityRegistry.ActionCapability.FIRE_TV_WAKE,
                        CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG
                    )
                )

                norm.contains("MUSIC") || norm.contains("SONG") || norm.contains("MEDIA") -> RoutineRequirements(
                    routineOrIntent = "MUSIC_MODE",
                    requiredDevices = setOf(
                        CapabilityRegistry.DeviceTarget.AUDIO,
                        CapabilityRegistry.DeviceTarget.MEDIA
                    ),
                    optionalDevices = emptySet(),
                    requiredCapabilities = setOf(
                        CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
                        CapabilityRegistry.ActionCapability.MEDIA_PLAY
                    )
                )

                norm.contains("WORK") || norm.contains("STUDY") || norm.contains("FOCUS") -> RoutineRequirements(
                    routineOrIntent = "WORK_MODE",
                    requiredDevices = setOf(CapabilityRegistry.DeviceTarget.AC),
                    optionalDevices = setOf(CapabilityRegistry.DeviceTarget.AUDIO),
                    requiredCapabilities = setOf(CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE)
                )

                norm.contains("GOODNIGHT") || norm.contains("SLEEP") || norm.contains("ALL_OFF") -> RoutineRequirements(
                    routineOrIntent = "GOODNIGHT_MODE",
                    requiredDevices = setOf(
                        CapabilityRegistry.DeviceTarget.MEDIA,
                        CapabilityRegistry.DeviceTarget.PROJECTOR,
                        CapabilityRegistry.DeviceTarget.AUDIO,
                        CapabilityRegistry.DeviceTarget.AC
                    ),
                    optionalDevices = emptySet()
                )

                targetDevice != null -> RoutineRequirements(
                    routineOrIntent = intentOrRoutine,
                    requiredDevices = setOf(targetDevice),
                    optionalDevices = emptySet()
                )

                else -> RoutineRequirements(
                    routineOrIntent = intentOrRoutine,
                    requiredDevices = setOf(CapabilityRegistry.DeviceTarget.AC),
                    optionalDevices = emptySet()
                )
            }
        }
    }
}
