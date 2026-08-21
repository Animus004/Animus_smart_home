package com.animus.smartroom.device.adapter.future

import com.animus.smartroom.device.adapter.DeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

/**
 * Future extension contract for HDMI Switch devices.
 * No hardware-specific implementation is provided until physical hardware is acquired.
 */
interface HdmiSwitchAdapter : DeviceAdapter {
    suspend fun selectInput(device: RoomDevice, port: Int): DeviceCommandResult
    suspend fun getCurrentInput(device: RoomDevice): DeviceCommandResult

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
            DeviceCapability.SelectInput -> {
                val port = when (value) {
                    is Number -> value.toInt()
                    is String -> value.toIntOrNull()
                    else -> null
                }
                if (port == null || port < 1) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid HDMI input port: '$value'."
                    )
                } else {
                    selectInput(device, port)
                }
            }
            DeviceCapability.CurrentInput -> getCurrentInput(device)
            else -> DeviceCommandResult(
                success = false,
                message = "Capability ${capability.name} is not handled by HdmiSwitchAdapter."
            )
        }
    }
}
