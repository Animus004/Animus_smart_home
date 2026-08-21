package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.RoomDevice

/**
 * Platform-independent transport contract separating domain operations from device protocols.
 */
interface DeviceTransport {
    suspend fun send(device: RoomDevice, command: DeviceCommand): TransportResult
    suspend fun readState(device: RoomDevice): TransportStateResult
}
