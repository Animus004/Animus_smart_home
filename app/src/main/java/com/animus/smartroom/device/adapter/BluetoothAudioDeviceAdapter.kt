package com.animus.smartroom.device.adapter

import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.core.device.AudioOutputAdapter
import com.animus.smartroom.core.device.DeviceCommand
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

class BluetoothAudioDeviceAdapter(
    private val bluetoothManager: BluetoothAudioDeviceManager
) : DeviceAdapter, AudioOutputAdapter {

    override suspend fun connect(device: RoomDevice): DeviceCommandResult {
        bluetoothManager.selectDevice(device.id)
        val isConnected = bluetoothManager.connectAndAwait()
        return if (isConnected) {
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

    override suspend fun disconnect(device: RoomDevice): DeviceCommandResult {
        bluetoothManager.selectDevice(device.id)
        bluetoothManager.disconnect()
        return DeviceCommandResult(
            success = true,
            message = "Disconnecting ${device.displayName}..."
        )
    }

    override suspend fun execute(device: RoomDevice, command: DeviceCommand): DeviceCommandResult {
        return when (command) {
            is DeviceCommand.Connect -> connect(device)
            is DeviceCommand.Disconnect -> disconnect(device)
            else -> DeviceCommandResult(
                success = false,
                message = "Command $command is not supported on ${device.displayName}"
            )
        }
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        val uiState = bluetoothManager.uiState.value
        val isConnected = uiState.connectionState is BluetoothDeviceState.Connected &&
                (uiState.selectedDevice?.macAddress.equals(device.id, ignoreCase = true) ||
                 (uiState.connectionState as? BluetoothDeviceState.Connected)?.macAddress.equals(device.id, ignoreCase = true))
        return mapOf(
            "connected" to isConnected,
            "deviceAddress" to device.id
        )
    }

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
            DeviceCapability.Connect -> connect(device)
            DeviceCapability.Disconnect -> disconnect(device)
            else -> {
                DeviceCommandResult(
                    success = false,
                    message = "Capability ${capability.name} is not handled by BluetoothAudioDeviceAdapter."
                )
            }
        }
    }
}
