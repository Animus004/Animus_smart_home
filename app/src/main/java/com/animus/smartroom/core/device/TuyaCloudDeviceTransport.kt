package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.client.TuyaApiClient

/**
 * Tuya Cloud implementation of [DeviceTransport] wrapping [TuyaApiClient].
 */
class TuyaCloudDeviceTransport(
    private val apiClient: TuyaApiClient
) : DeviceTransport {

    override suspend fun send(device: RoomDevice, command: DeviceCommand): TransportResult {
        val commandsList = mutableListOf<Map<String, Any>>()

        when (command) {
            is DeviceCommand.Power -> {
                commandsList.add(mapOf("code" to "switch", "value" to command.enabled))
            }
            is DeviceCommand.SetTemperature -> {
                commandsList.add(mapOf("code" to "temp_set", "value" to command.celsius))
            }
            is DeviceCommand.SetMode -> {
                commandsList.add(mapOf("code" to "mode", "value" to command.mode))
            }
            is DeviceCommand.SetFanSpeed -> {
                commandsList.add(mapOf("code" to "fan_speed_enum", "value" to command.speed))
            }
            else -> {
                return TransportResult(success = false, message = "Unsupported command type for Tuya: $command")
            }
        }

        val result = apiClient.sendCommands(device.id, commandsList)
        return if (result.isSuccess && result.getOrNull() == true) {
            TransportResult(success = true, message = "Tuya command accepted")
        } else {
            TransportResult(
                success = false,
                message = result.exceptionOrNull()?.message ?: "Tuya write failed"
            )
        }
    }

    override suspend fun readState(device: RoomDevice): TransportStateResult {
        val result = apiClient.fetchStatus(device.id)
        return if (result.isSuccess) {
            val statusItems = result.getOrNull() ?: emptyList()
            val stateMap = mutableMapOf<String, Any>()
            statusItems.forEach { item ->
                item.value?.let { v -> stateMap[item.code] = v }
            }
            TransportStateResult(success = true, stateProperties = stateMap)
        } else {
            TransportStateResult(
                success = false,
                errorMessage = result.exceptionOrNull()?.message ?: "Failed to read Tuya device status"
            )
        }
    }
}
