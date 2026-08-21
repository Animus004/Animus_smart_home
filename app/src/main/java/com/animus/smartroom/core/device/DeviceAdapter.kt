package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice

/**
 * Platform-independent core device adapter abstraction.
 */
interface DeviceAdapter {
    val deviceType: DeviceType

    suspend fun getState(device: RoomDevice): Map<String, Any>

    suspend fun execute(device: RoomDevice, command: DeviceCommand): DeviceCommandResult
}
