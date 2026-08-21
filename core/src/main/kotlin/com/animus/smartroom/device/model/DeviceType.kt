package com.animus.smartroom.device.model

enum class DeviceType {
    BLUETOOTH_AUDIO,
    AIR_CONDITIONER,
    LIGHT,
    HDMI_SWITCH,
    DISPLAY,
    PROJECTOR,
    OTHER;

    companion object {
        fun fromString(value: String): DeviceType? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}
