package com.animus.smartroom.device.adapter

import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

/**
 * In-memory test-only AC adapter for unit tests.
 */
class MockAirConditionerAdapter : AirConditionerAdapter {
    var powerState: Boolean = false
    var currentTemperature: Int = 24
    var currentMode: AcMode = AcMode.COOL
    var currentFanSpeed: AcFanSpeed = AcFanSpeed.AUTO
    var currentSwing: AcSwing = AcSwing.OFF

    override suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult {
        powerState = on
        val stateStr = if (on) "ON" else "OFF"
        return DeviceCommandResult(
            success = true,
            message = "${device.displayName} turned $stateStr."
        )
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        currentTemperature = celsius
        return DeviceCommandResult(
            success = true,
            message = "${device.displayName} temperature set to $celsius°C."
        )
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        currentMode = mode
        return DeviceCommandResult(
            success = true,
            message = "${device.displayName} mode set to $mode."
        )
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        currentFanSpeed = speed
        return DeviceCommandResult(
            success = true,
            message = "${device.displayName} fan speed set to $speed."
        )
    }

    override suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult {
        currentSwing = swing
        return DeviceCommandResult(
            success = true,
            message = "${device.displayName} swing set to $swing."
        )
    }
}
