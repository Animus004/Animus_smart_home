package com.animus.smartroom.device.model

import java.util.Locale

sealed class DeviceCapability(val name: String) {
    // Power
    object Power : DeviceCapability("POWER")

    // Climate / AC
    object Temperature : DeviceCapability("TEMPERATURE")
    object HvacMode : DeviceCapability("MODE")
    object FanSpeed : DeviceCapability("FAN_SPEED")
    object Swing : DeviceCapability("SWING")

    // Audio / Media
    object Connect : DeviceCapability("CONNECT")
    object Disconnect : DeviceCapability("DISCONNECT")
    object Play : DeviceCapability("PLAY")
    object Pause : DeviceCapability("PAUSE")
    object Next : DeviceCapability("NEXT")
    object Previous : DeviceCapability("PREVIOUS")
    object Volume : DeviceCapability("VOLUME")

    // Future Expansion Contracts
    object SelectInput : DeviceCapability("SELECT_INPUT")
    object CurrentInput : DeviceCapability("CURRENT_INPUT")
    object Brightness : DeviceCapability("BRIGHTNESS")
    object Color : DeviceCapability("COLOR")
    object ColorTemperature : DeviceCapability("COLOR_TEMPERATURE")

    override fun toString(): String = name

    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is DeviceCapability) return false
        return name == other.name
    }

    override fun hashCode(): Int = name.hashCode()

    companion object {
        fun fromString(value: String): DeviceCapability? {
            return when (value.trim().uppercase(Locale.ROOT)) {
                "POWER", "POWER_STATE", "STATE" -> Power
                "TEMPERATURE", "TEMP", "SET_TEMP", "SET_TEMPERATURE" -> Temperature
                "MODE", "HVAC_MODE", "AC_MODE" -> HvacMode
                "FAN_SPEED", "FAN", "SPEED" -> FanSpeed
                "SWING", "VANE", "OSCILLATE" -> Swing
                "CONNECT", "CONNECT_DEVICE" -> Connect
                "DISCONNECT", "DISCONNECT_DEVICE" -> Disconnect
                "PLAY", "PLAY_MUSIC", "PLAYBACK" -> Play
                "PAUSE", "PAUSE_MUSIC" -> Pause
                "NEXT", "NEXT_TRACK" -> Next
                "PREVIOUS", "PREV", "PREVIOUS_TRACK" -> Previous
                "VOLUME", "SET_VOLUME", "VOL" -> Volume
                "SELECT_INPUT", "INPUT", "SWITCH_INPUT" -> SelectInput
                "CURRENT_INPUT" -> CurrentInput
                "BRIGHTNESS", "SET_BRIGHTNESS" -> Brightness
                "COLOR", "SET_COLOR" -> Color
                "COLOR_TEMPERATURE", "COLOR_TEMP" -> ColorTemperature
                else -> null
            }
        }
    }
}
