package com.animus.smartroom.core.brain.arbitration

/**
 * Enumeration of exclusive physical resources in Animus Smart Room.
 */
enum class PhysicalResource {
    LG_SNC4R_AUDIO,
    PROJECTOR_DISPLAY,
    PROJECTOR_HDMI_INPUT,
    FIRE_TV_PLAYBACK,
    AC_CLIMATE;

    companion object {
        fun fromString(name: String?): PhysicalResource? {
            if (name == null) return null
            return entries.firstOrNull { it.name.equals(name.trim(), ignoreCase = true) }
        }
    }
}

/**
 * Resource category.
 */
enum class ResourceType {
    BLUETOOTH_AUDIO_SINK,
    DISPLAY_OUTPUT,
    HDMI_SOURCE,
    MEDIA_SESSION,
    CLIMATE_CONTROLLER
}

/**
 * Possible physical resource owners.
 */
enum class ResourceOwner {
    PHONE,
    FIRE_TV,
    PC,
    NONE,
    UNKNOWN;

    companion object {
        fun fromString(value: String?): ResourceOwner {
            if (value == null) return UNKNOWN
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) } ?: UNKNOWN
        }
    }
}

/**
 * Resource state.
 */
enum class ResourceState {
    AVAILABLE,
    OWNED,
    TRANSITIONING,
    CONFLICT,
    FAILED,
    UNKNOWN
}

/**
 * Descriptor of a physical resource's current state.
 */
data class ResourceDescriptor(
    val resourceId: PhysicalResource,
    val resourceType: ResourceType,
    val currentOwner: ResourceOwner = ResourceOwner.NONE,
    val desiredOwner: ResourceOwner? = null,
    val state: ResourceState = ResourceState.AVAILABLE,
    val lastVerifiedAtMs: Long = System.currentTimeMillis(),
    val confidence: Float = 1.0f,
    val metadata: Map<String, Any?> = emptyMap()
)

/**
 * Result of an arbitration request.
 */
data class ArbitrationResult(
    val success: Boolean,
    val resourceId: PhysicalResource,
    val requestedOwner: ResourceOwner,
    val previousOwner: ResourceOwner,
    val finalOwner: ResourceOwner,
    val state: ResourceState,
    val decision: String,
    val releaseLatencyMs: Long = 0L,
    val acquisitionLatencyMs: Long = 0L,
    val verificationLatencyMs: Long = 0L,
    val totalLatencyMs: Long = 0L,
    val reason: String? = null,
    val message: String = ""
)
