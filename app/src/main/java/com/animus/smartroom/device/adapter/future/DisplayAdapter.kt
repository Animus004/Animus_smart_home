package com.animus.smartroom.device.adapter.future

import com.animus.smartroom.device.adapter.DeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

/**
 * Future extension contract for Displays and Projectors.
 * No hardware-specific implementation is provided until physical hardware is acquired.
 */
interface DisplayAdapter : DeviceAdapter {
    suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult
    suspend fun selectInput(device: RoomDevice, input: String): DeviceCommandResult

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
            DeviceCapability.SelectInput -> selectInput(device, value?.toString() ?: "HDMI 1")
            else -> DeviceCommandResult(
                success = false,
                message = "Capability ${capability.name} is not handled by DisplayAdapter."
            )
        }
    }
}
