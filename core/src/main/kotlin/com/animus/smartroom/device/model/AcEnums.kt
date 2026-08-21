package com.animus.smartroom.device.model

enum class AcMode {
    COOL, HEAT, FAN, AUTO, DRY;

    companion object {
        fun fromString(value: String): AcMode? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}

enum class AcFanSpeed {
    LOW, MEDIUM, HIGH, AUTO;

    companion object {
        fun fromString(value: String): AcFanSpeed? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}

enum class AcSwing {
    OFF, VERTICAL, HORIZONTAL, BOTH;

    companion object {
        fun fromString(value: String): AcSwing? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}
