package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.RoomDevice

/**
 * Placeholder / contract for future LocalTuya direct LAN protocol transport.
 */
class LocalTuyaDeviceTransport(
    val localKeyProvider: (deviceId: String) -> String? = { null },
    val ipAddressProvider: (deviceId: String) -> String? = { null }
) : DeviceTransport {

    override suspend fun send(device: RoomDevice, command: DeviceCommand): TransportResult {
        // Future LocalTuya LAN UDP/TCP socket implementation
        return TransportResult(
            success = false,
            message = "LocalTuya transport not yet active. Use TuyaCloudDeviceTransport."
        )
    }

    override suspend fun readState(device: RoomDevice): TransportStateResult {
        // Future LocalTuya LAN status read
        return TransportStateResult(
            success = false,
            errorMessage = "LocalTuya transport not yet active. Use TuyaCloudDeviceTransport."
        )
    }
}
