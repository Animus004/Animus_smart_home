package com.animus.smartroom.device.adapter

import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

interface DeviceAdapter {
    /**
     * Executes the requested capability on the specified device.
     */
    suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult
}
