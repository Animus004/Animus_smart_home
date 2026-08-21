package com.animus.smartroom.device.adapter

import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

class BluetoothAudioDeviceAdapter(
    private val bluetoothManager: BluetoothAudioDeviceManager
) : DeviceAdapter {

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
            DeviceCapability.Connect -> {
                bluetoothManager.selectDevice(device.id)
                val isConnected = bluetoothManager.connectAndAwait()
                if (isConnected) {
                    DeviceCommandResult(
                        success = true,
                        message = "Connected to ${device.displayName}"
                    )
                } else {
                    DeviceCommandResult(
                        success = false,
                        message = "Failed to connect to ${device.displayName}"
                    )
                }
            }
            DeviceCapability.Disconnect -> {
                bluetoothManager.selectDevice(device.id)
                bluetoothManager.disconnect()
                DeviceCommandResult(
                    success = true,
                    message = "Disconnecting ${device.displayName}..."
                )
            }
            else -> {
                DeviceCommandResult(
                    success = false,
                    message = "Capability ${capability.name} is not handled by BluetoothAudioDeviceAdapter."
                )
            }
        }
    }
}
