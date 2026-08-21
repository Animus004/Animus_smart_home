package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.RoomDevice

/**
 * Deterministic test implementation of [DeviceTransport].
 */
class FakeDeviceTransport : DeviceTransport {

    val sentCommands = mutableListOf<Pair<RoomDevice, DeviceCommand>>()
    var mockState: Map<String, Any> = emptyMap()
    var shouldFailSend = false
    var shouldFailRead = false

    override suspend fun send(device: RoomDevice, command: DeviceCommand): TransportResult {
        if (shouldFailSend) {
            return TransportResult(success = false, message = "Simulated transport error")
        }
        sentCommands.add(device to command)
        return TransportResult(success = true, message = "Transport write success")
    }

    override suspend fun readState(device: RoomDevice): TransportStateResult {
        if (shouldFailRead) {
            return TransportStateResult(success = false, errorMessage = "Simulated read error")
        }
        return TransportStateResult(success = true, stateProperties = mockState)
    }
}
