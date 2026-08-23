package com.animus.smartroom.core.brain.router

import java.util.Locale

/**
 * Bounded conversational context resolver for pronouns and implicit targets.
 * Strict rule: Explicit user targets ALWAYS override context.
 */
class ContextResolver(
    private var lastActiveTarget: CapabilityRegistry.DeviceTarget? = null,
    private var lastRequestedTemperature: Int? = null,
    private var lastRequestedMedia: String? = null
) {

    fun updateContext(target: CapabilityRegistry.DeviceTarget?, temperature: Int? = null, mediaTitle: String? = null) {
        if (target != null) {
            lastActiveTarget = target
        }
        if (temperature != null) {
            lastRequestedTemperature = temperature
        }
        if (mediaTitle != null) {
            lastRequestedMedia = mediaTitle
        }
    }

    fun getLastTarget(): CapabilityRegistry.DeviceTarget? = lastActiveTarget
    fun getLastTemperature(): Int? = lastRequestedTemperature
    fun getLastMedia(): String? = lastRequestedMedia

    fun resolveTarget(rawInput: String, extractedTarget: String?): CapabilityRegistry.DeviceTarget? {
        // 1. Explicit user target always takes highest priority
        val explicit = CapabilityRegistry.DeviceTarget.fromString(extractedTarget)
        if (explicit != null) {
            lastActiveTarget = explicit
            return explicit
        }

        // 2. Check input text for explicit keywords
        val lower = rawInput.lowercase(Locale.ROOT)
        when {
            lower.contains("ac") || lower.contains("air conditioner") || lower.contains("temperature") || lower.contains("cooler") -> {
                lastActiveTarget = CapabilityRegistry.DeviceTarget.AC
                return CapabilityRegistry.DeviceTarget.AC
            }
            lower.contains("projector") || lower.contains("pixaplay") || lower.contains("display") || lower.contains("hdmi") -> {
                lastActiveTarget = CapabilityRegistry.DeviceTarget.PROJECTOR
                return CapabilityRegistry.DeviceTarget.PROJECTOR
            }
            lower.contains("fire tv") || lower.contains("firetv") || lower.contains("fire stick") -> {
                lastActiveTarget = CapabilityRegistry.DeviceTarget.FIRE_TV
                return CapabilityRegistry.DeviceTarget.FIRE_TV
            }
            lower.contains("soundbar") || lower.contains("speaker") || lower.contains("lg") -> {
                lastActiveTarget = CapabilityRegistry.DeviceTarget.AUDIO
                return CapabilityRegistry.DeviceTarget.AUDIO
            }
        }

        // 3. Pronoun resolution ("it", "that", "this") using bounded context
        if (lower.contains(" it") || lower.startsWith("it ") || lower.contains(" that") || lower.contains(" this")) {
            return lastActiveTarget
        }

        return null
    }

    fun clear() {
        lastActiveTarget = null
        lastRequestedTemperature = null
        lastRequestedMedia = null
    }
}
