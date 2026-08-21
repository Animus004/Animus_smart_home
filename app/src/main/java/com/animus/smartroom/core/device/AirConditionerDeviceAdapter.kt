package com.animus.smartroom.core.device

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.model.TuyaAcState

/**
 * Platform-independent Air Conditioner device adapter contract.
 */
interface AirConditionerDeviceAdapter : DeviceAdapter {
    override val deviceType: DeviceType get() = DeviceType.AIR_CONDITIONER

    suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult
    suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult
    suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult
    suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult
    suspend fun getAcState(device: RoomDevice): TuyaAcState
}
