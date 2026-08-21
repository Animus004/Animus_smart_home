package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice

/**
 * Platform-independent Audio Output device adapter contract.
 */
interface AudioOutputAdapter : DeviceAdapter {
    override val deviceType: DeviceType get() = DeviceType.BLUETOOTH_AUDIO

    suspend fun connect(device: RoomDevice): DeviceCommandResult
    suspend fun disconnect(device: RoomDevice): DeviceCommandResult
}
