package com.animus.smartroom.core.brain.router

/**
 * Authoritative Capability Registry for Animus Smart Room.
 * Acts as the hard boundary between the LLM and the physical hardware.
 */
object CapabilityRegistry {

    enum class DeviceTarget {
        AC,
        PROJECTOR,
        FIRE_TV,
        AUDIO,
        MEDIA,
        ROUTINES;

        companion object {
            fun fromString(raw: String?): DeviceTarget? {
                if (raw.isNullOrBlank()) return null
                val s = raw.trim().uppercase()
                return when (s) {
                    "AC", "AIR_CONDITIONER", "AIRCONDITIONER", "CLIMATE" -> AC
                    "PROJECTOR", "PIXAPLAY", "DISPLAY" -> PROJECTOR
                    "FIRE_TV", "FIRETV", "FIRE_STICK", "FIRESTICK", "TV" -> FIRE_TV
                    "AUDIO", "SOUNDBAR", "SPEAKER", "BLUETOOTH_AUDIO", "LG_SNC4R", "LG" -> AUDIO
                    "MEDIA", "MUSIC", "PLAYER" -> MEDIA
                    "ROUTINE", "ROUTINES", "MODE", "SCENE" -> ROUTINES
                    else -> entries.firstOrNull { it.name == s }
                }
            }
        }
    }

    enum class ActionCapability(val target: DeviceTarget) {
        // AC Capabilities
        AC_POWER_ON(DeviceTarget.AC),
        AC_POWER_OFF(DeviceTarget.AC),
        AC_SET_TEMPERATURE(DeviceTarget.AC),
        AC_SET_MODE(DeviceTarget.AC),
        AC_SET_FAN_SPEED(DeviceTarget.AC),
        AC_GET_STATE(DeviceTarget.AC),

        // Projector Capabilities
        PROJECTOR_POWER_ON(DeviceTarget.PROJECTOR),
        PROJECTOR_POWER_OFF(DeviceTarget.PROJECTOR),
        PROJECTOR_SET_INPUT(DeviceTarget.PROJECTOR),
        PROJECTOR_GET_STATE(DeviceTarget.PROJECTOR),

        // Fire TV Capabilities
        FIRE_TV_WAKE(DeviceTarget.FIRE_TV),
        FIRE_TV_HOME(DeviceTarget.FIRE_TV),
        FIRE_TV_BACK(DeviceTarget.FIRE_TV),
        FIRE_TV_NAVIGATE(DeviceTarget.FIRE_TV),
        FIRE_TV_LAUNCH_APP(DeviceTarget.FIRE_TV),
        FIRE_TV_GET_STATE(DeviceTarget.FIRE_TV),

        // Audio Capabilities
        AUDIO_CONNECT_LG(DeviceTarget.AUDIO),
        AUDIO_DISCONNECT_LG(DeviceTarget.AUDIO),
        AUDIO_GET_STATE(DeviceTarget.AUDIO),

        // Media Capabilities
        MEDIA_PLAY(DeviceTarget.MEDIA),
        MEDIA_PAUSE(DeviceTarget.MEDIA),
        MEDIA_STOP(DeviceTarget.MEDIA),
        MEDIA_NEXT(DeviceTarget.MEDIA),
        MEDIA_PREVIOUS(DeviceTarget.MEDIA),
        MEDIA_SET_VOLUME(DeviceTarget.MEDIA),

        // Predefined Routines
        ROUTINE_MOVIE_MODE(DeviceTarget.ROUTINES),
        ROUTINE_MUSIC_MODE(DeviceTarget.ROUTINES),
        ROUTINE_WORK_MODE(DeviceTarget.ROUTINES),
        ROUTINE_GOODNIGHT_MODE(DeviceTarget.ROUTINES);

        companion object {
            fun fromString(target: DeviceTarget, action: String?): ActionCapability? {
                if (action.isNullOrBlank()) return null
                val normalizedAction = action.trim().uppercase()
                return entries.firstOrNull { it.target == target && (it.name == "${target.name}_$normalizedAction" || it.name == normalizedAction) }
            }
        }
    }

    // Allowed parameter constraints
    const val MIN_AC_TEMP = 16
    const val MAX_AC_TEMP = 30
    val ALLOWED_AC_MODES = setOf("COOL", "HEAT", "FAN", "AUTO", "DRY")
    val ALLOWED_AC_FAN_SPEEDS = setOf("AUTO", "LOW", "MEDIUM", "HIGH")
    val ALLOWED_PROJECTOR_INPUTS = setOf("HDMI_1", "HDMI_2", "ANDROID")
    val ALLOWED_FIRE_TV_NAV = setOf("UP", "DOWN", "LEFT", "RIGHT", "SELECT", "ENTER")
    val ALLOWED_FIRE_TV_APPS = mapOf(
        "YOUTUBE" to "com.amazon.firetv.youtube",
        "NETFLIX" to "com.netflix.ninja",
        "PRIME_VIDEO" to "com.amazon.avod",
        "SMART_TUBE" to "com.liskovsoft.videomanager"
    )

    fun isDeviceSupported(targetStr: String?): Boolean {
        return DeviceTarget.fromString(targetStr) != null
    }

    fun isCapabilitySupported(target: DeviceTarget, actionStr: String?): Boolean {
        return ActionCapability.fromString(target, actionStr) != null
    }
}
