package com.animus.smartroom.core.device

/**
 * Platform-independent command hierarchy for hardware and media devices.
 */
sealed class DeviceCommand {
    data class Power(val enabled: Boolean) : DeviceCommand()
    data class SetTemperature(val celsius: Int) : DeviceCommand()
    data class SetMode(val mode: String) : DeviceCommand()
    data class SetFanSpeed(val speed: String) : DeviceCommand()
    data class SetSwing(val swing: String) : DeviceCommand()
    object Connect : DeviceCommand()
    object Disconnect : DeviceCommand()
    object Pause : DeviceCommand()
    object Resume : DeviceCommand()
}
