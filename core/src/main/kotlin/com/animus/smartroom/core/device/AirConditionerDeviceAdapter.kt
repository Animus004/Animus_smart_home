package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.AcFanSpeed
import com.animus.smartroom.device.model.AcMode
import com.animus.smartroom.device.model.AcSwing
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice

/**
 * Platform-independent Air Conditioner device adapter contract.
 */
interface AirConditionerDeviceAdapter : DeviceAdapter {
    override val deviceType: DeviceType get() = DeviceType.AIR_CONDITIONER

    suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult
    suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult
    suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult
    suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult
    suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult = DeviceCommandResult(true, "Swing set")
}
