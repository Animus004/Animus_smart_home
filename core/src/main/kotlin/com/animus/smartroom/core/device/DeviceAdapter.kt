package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice

/**
 * Platform-independent core device adapter abstraction.
 */
interface DeviceAdapter {
    val deviceType: DeviceType

    suspend fun getState(device: RoomDevice): Map<String, Any>

    suspend fun execute(device: RoomDevice, command: DeviceCommand): DeviceCommandResult

    suspend fun executeCapability(device: RoomDevice, capability: DeviceCapability, value: Any? = null): DeviceCommandResult {
        val command = when (capability) {
            DeviceCapability.Power -> DeviceCommand.Power(value as? Boolean ?: value.toString().toBoolean())
            DeviceCapability.Temperature -> DeviceCommand.SetTemperature(value as? Int ?: value.toString().toIntOrNull() ?: 24)
            DeviceCapability.HvacMode -> DeviceCommand.SetMode(value?.toString() ?: "auto")
            DeviceCapability.FanSpeed -> DeviceCommand.SetFanSpeed(value?.toString() ?: "auto")
            DeviceCapability.Swing -> DeviceCommand.SetSwing(value?.toString() ?: "off")
            DeviceCapability.Connect -> DeviceCommand.Connect
            DeviceCapability.Disconnect -> DeviceCommand.Disconnect
            DeviceCapability.Pause -> DeviceCommand.Pause
            DeviceCapability.Play -> DeviceCommand.Resume
            else -> return DeviceCommandResult(false, "Unsupported capability: $capability")
        }
        return execute(device, command)
    }
}
