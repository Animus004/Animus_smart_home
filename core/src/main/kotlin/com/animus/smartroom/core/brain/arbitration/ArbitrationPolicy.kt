package com.animus.smartroom.core.brain.arbitration

import java.util.Locale

/**
 * Deterministic policy layer mapping user intents and routines to preferred resource owners.
 */
object ArbitrationPolicy {

    /**
     * Resolves the desired owner for an exclusive resource given a user intent or routine name.
     */
    fun resolveDesiredOwner(resource: PhysicalResource, intentOrRoutine: String): ResourceOwner {
        val normalized = intentOrRoutine.trim().uppercase(Locale.ROOT)

        return when (resource) {
            PhysicalResource.LG_SNC4R_AUDIO -> {
                when {
                    normalized.contains("MOVIE") || normalized.contains("CINEMA") || normalized.contains("FIRE_TV") -> ResourceOwner.FIRE_TV
                    normalized.contains("WORK") || normalized.contains("PC") || normalized.contains("STUDY") -> ResourceOwner.PC
                    normalized.contains("MUSIC") || normalized.contains("SONG") || normalized.contains("PLAY") -> ResourceOwner.PHONE
                    else -> ResourceOwner.PHONE
                }
            }

            PhysicalResource.PROJECTOR_HDMI_INPUT -> {
                when {
                    normalized.contains("MOVIE") || normalized.contains("FIRE_TV") -> ResourceOwner.FIRE_TV
                    normalized.contains("WORK") || normalized.contains("PC") -> ResourceOwner.PC
                    else -> ResourceOwner.FIRE_TV
                }
            }

            PhysicalResource.PROJECTOR_DISPLAY -> {
                ResourceOwner.PC // Primary controller
            }

            PhysicalResource.FIRE_TV_PLAYBACK -> {
                ResourceOwner.FIRE_TV
            }

            PhysicalResource.AC_CLIMATE -> {
                ResourceOwner.PHONE // Or central room controller
            }
        }
    }

    /**
     * Maps the owner to the specific input source string for the projector.
     */
    fun resolveProjectorInput(owner: ResourceOwner): String {
        return when (owner) {
            ResourceOwner.FIRE_TV -> "HDMI_1"
            ResourceOwner.PC -> "HDMI_2"
            else -> "HDMI_1"
        }
    }
}
