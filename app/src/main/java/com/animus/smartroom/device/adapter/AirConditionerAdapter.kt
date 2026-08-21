package com.animus.smartroom.device.adapter

import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

enum class AcMode {
    COOL, HEAT, FAN, AUTO, DRY;

    companion object {
        fun fromString(value: String): AcMode? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}

enum class AcFanSpeed {
    LOW, MEDIUM, HIGH, AUTO;

    companion object {
        fun fromString(value: String): AcFanSpeed? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}

enum class AcSwing {
    OFF, VERTICAL, HORIZONTAL, BOTH;

    companion object {
        fun fromString(value: String): AcSwing? {
            return entries.firstOrNull { it.name.equals(value.trim(), ignoreCase = true) }
        }
    }
}

/**
 * Contract for Air Conditioner device integrations.
 */
interface AirConditionerAdapter : DeviceAdapter {
    suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult
    suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult
    suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult
    suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult
    suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult

    override suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        if (!device.supportsCapability(capability)) {
            return DeviceCommandResult(
                success = false,
                message = "${device.displayName} does not support capability ${capability.name}."
            )
        }

        return when (capability) {
            DeviceCapability.Power -> {
                val isOn = when (value) {
                    is Boolean -> value
                    is String -> value.equals("on", ignoreCase = true) || value.equals("true", ignoreCase = true)
                    is Number -> value.toInt() != 0
                    else -> true
                }
                setPower(device, isOn)
            }
            DeviceCapability.Temperature -> {
                val temp = when (value) {
                    is Number -> value.toInt()
                    is String -> value.toIntOrNull()
                    else -> null
                }
                if (temp == null) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid temperature value: '$value'."
                    )
                } else if (temp !in 16..30) {
                    DeviceCommandResult(
                        success = false,
                        message = "Temperature $temp°C is out of supported range (16°C - 30°C)."
                    )
                } else {
                    setTemperature(device, temp)
                }
            }
            DeviceCapability.HvacMode -> {
                val mode = when (value) {
                    is AcMode -> value
                    is String -> AcMode.fromString(value)
                    else -> null
                }
                if (mode == null) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid AC mode: '$value'. Supported modes: COOL, HEAT, FAN, AUTO, DRY."
                    )
                } else {
                    setMode(device, mode)
                }
            }
            DeviceCapability.FanSpeed -> {
                val speed = when (value) {
                    is AcFanSpeed -> value
                    is String -> AcFanSpeed.fromString(value)
                    else -> null
                }
                if (speed == null) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid fan speed: '$value'. Supported speeds: LOW, MEDIUM, HIGH, AUTO."
                    )
                } else {
                    setFanSpeed(device, speed)
                }
            }
            DeviceCapability.Swing -> {
                val swing = when (value) {
                    is AcSwing -> value
                    is String -> AcSwing.fromString(value)
                    else -> null
                }
                if (swing == null) {
                    DeviceCommandResult(
                        success = false,
                        message = "Invalid swing setting: '$value'. Supported: OFF, VERTICAL, HORIZONTAL, BOTH."
                    )
                } else {
                    setSwing(device, swing)
                }
            }
            else -> {
                DeviceCommandResult(
                    success = false,
                    message = "Capability ${capability.name} is not handled by AirConditionerAdapter."
                )
            }
        }
    }
}

/**
 * Default production placeholder adapter when physical AC model is not yet configured.
 * Reports truthful unconfigured status rather than pretending physical execution.
 */
class UnconfiguredAirConditionerAdapter : AirConditionerAdapter {
    override suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult {
        return DeviceCommandResult(
            success = false,
            message = "${device.displayName} power control is not configured. Physical AC hardware setup is pending."
        )
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        return DeviceCommandResult(
            success = false,
            message = "${device.displayName} temperature control is not configured. Physical AC hardware setup is pending."
        )
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        return DeviceCommandResult(
            success = false,
            message = "${device.displayName} mode control is not configured. Physical AC hardware setup is pending."
        )
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        return DeviceCommandResult(
            success = false,
            message = "${device.displayName} fan speed control is not configured. Physical AC hardware setup is pending."
        )
    }

    override suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult {
        return DeviceCommandResult(
            success = false,
            message = "${device.displayName} swing control is not configured. Physical AC hardware setup is pending."
        )
    }
}
