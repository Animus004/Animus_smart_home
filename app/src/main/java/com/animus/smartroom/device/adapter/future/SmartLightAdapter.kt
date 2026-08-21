package com.animus.smartroom.device.adapter.future

import com.animus.smartroom.device.adapter.DeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

/**
 * Future extension contract for Smart Lights.
 * No hardware-specific implementation is provided until physical hardware is acquired.
 */
interface SmartLightAdapter : DeviceAdapter {
    suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult
    suspend fun setBrightness(device: RoomDevice, percentage: Int): DeviceCommandResult
    suspend fun setColor(device: RoomDevice, hexColor: String): DeviceCommandResult
    suspend fun setColorTemperature(device: RoomDevice, kelvin: Int): DeviceCommandResult

    override suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        if (!device.supportsCapability(capability)) {
            return DeviceCommandResult(
                success = false,
                message = "${device.displayName} does not support capability ${capability.name}."
            )
        }

        return when (capability) {
            DeviceCapability.Power -> {
                val isOn = when (value) {
                    is Boolean -> value
                    is String -> value.equals("on", ignoreCase = true) || value.equals("true", ignoreCase = true)
                    else -> true
                }
                setPower(device, isOn)
            }
            DeviceCapability.Brightness -> {
                val brightness = when (value) {
                    is Number -> value.toInt()
                    is String -> value.toIntOrNull()
                    else -> null
                }
                if (brightness == null || brightness !in 0..100) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid brightness value: '$value'. Expected 0..100."
                    )
                } else {
                    setBrightness(device, brightness)
                }
            }
            DeviceCapability.Color -> setColor(device, value?.toString() ?: "#FFFFFF")
            DeviceCapability.ColorTemperature -> {
                val kelvin = when (value) {
                    is Number -> value.toInt()
                    is String -> value.toIntOrNull()
                    else -> null
                }
                if (kelvin == null || kelvin !in 1000..10000) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid color temperature: '$value'. Expected 1000..10000K."
                    )
                } else {
                    setColorTemperature(device, kelvin)
                }
            }
            else -> DeviceCommandResult(
                success = false,
                message = "Capability ${capability.name} is not handled by SmartLightAdapter."
            )
        }
    }
}
