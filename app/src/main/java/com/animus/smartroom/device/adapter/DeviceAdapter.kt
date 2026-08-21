package com.animus.smartroom.device.adapter

import com.animus.smartroom.core.device.DeviceCommand
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

interface DeviceAdapter : com.animus.smartroom.core.device.DeviceAdapter {
    /**
     * Executes the requested capability on the specified device.
     */
    suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult

    override suspend fun execute(device: RoomDevice, command: DeviceCommand): DeviceCommandResult {
        return when (command) {
            is DeviceCommand.Power ->
                executeCapability(device, DeviceCapability.Power, command.enabled)
            is DeviceCommand.SetTemperature ->
                executeCapability(device, DeviceCapability.Temperature, command.celsius)
            is DeviceCommand.SetMode ->
                executeCapability(device, DeviceCapability.HvacMode, command.mode)
            is DeviceCommand.SetFanSpeed ->
                executeCapability(device, DeviceCapability.FanSpeed, command.speed)
            is DeviceCommand.Connect ->
                executeCapability(device, DeviceCapability.Connect, null)
            is DeviceCommand.Disconnect ->
                executeCapability(device, DeviceCapability.Disconnect, null)
            else -> DeviceCommandResult(success = false, message = "Unsupported command: $command")
        }
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        return emptyMap()
    }
}
