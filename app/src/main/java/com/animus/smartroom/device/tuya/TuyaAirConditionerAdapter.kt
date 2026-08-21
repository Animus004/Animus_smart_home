package com.animus.smartroom.device.tuya

import android.util.Log
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.adapter.AcSwing
import com.animus.smartroom.device.adapter.AirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.device.tuya.model.TuyaAcState
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

class TuyaAirConditionerAdapter(
    private val apiClient: TuyaApiClient,
    val allowWriteCommands: Boolean = false
) : AirConditionerAdapter {

    companion object {
        private const val TAG = "TuyaAcAdapter"

        const val MIN_TEMPERATURE = 16
        const val MAX_TEMPERATURE = 30

        // Exact verified Tuya codes for this AC
        const val CODE_SWITCH = "switch"
        const val CODE_TEMP_SET = "temp_set"
        const val CODE_TEMP_CURRENT = "temp_current"
        const val CODE_MODE = "mode"
        const val CODE_FAN_SPEED = "fan_speed_enum"

        // Mode translations: Animus -> Tuya
        val MODE_ANIMUS_TO_TUYA = mapOf(
            AcMode.COOL to "cold",
            AcMode.AUTO to "auto",
            AcMode.DRY to "wet",
            AcMode.FAN to "wind"
        )

        // Mode translations: Tuya -> Animus
        val MODE_TUYA_TO_ANIMUS = mapOf(
            "cold" to AcMode.COOL,
            "auto" to AcMode.AUTO,
            "wet" to AcMode.DRY,
            "wind" to AcMode.FAN
        )

        // Fan Speed translations: Animus -> Tuya
        val FAN_ANIMUS_TO_TUYA = mapOf(
            AcFanSpeed.LOW to "low",
            AcFanSpeed.MEDIUM to "mid",
            AcFanSpeed.HIGH to "high",
            AcFanSpeed.AUTO to "auto"
        )

        // Fan Speed translations: Tuya -> Animus
        val FAN_TUYA_TO_ANIMUS = mapOf(
            "low" to AcFanSpeed.LOW,
            "mid" to AcFanSpeed.MEDIUM,
            "high" to AcFanSpeed.HIGH,
            "auto" to AcFanSpeed.AUTO
        )
    }

    private val _acState = MutableStateFlow(TuyaAcState())
    val acState: StateFlow<TuyaAcState> = _acState.asStateFlow()

    override suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        Log.d(TAG, "[execute] Device='${device.displayName}', Capability='${capability.name}', Value='$value'")

        return when (capability) {
            is DeviceCapability.Power -> {
                val on = when (value) {
                    is Boolean -> value
                    is String -> value.equals("true", ignoreCase = true) || value.equals("on", ignoreCase = true)
                    else -> true
                }
                setPower(device, on)
            }

            is DeviceCapability.Temperature -> {
                val temp = when (value) {
                    is Number -> value.toInt()
                    is String -> value.toIntOrNull() ?: 24
                    else -> 24
                }
                setTemperature(device, temp)
            }

            is DeviceCapability.HvacMode -> {
                val mode = when (value) {
                    is AcMode -> value
                    is String -> AcMode.fromString(value) ?: AcMode.AUTO
                    else -> AcMode.AUTO
                }
                setMode(device, mode)
            }

            is DeviceCapability.FanSpeed -> {
                val speed = when (value) {
                    is AcFanSpeed -> value
                    is String -> AcFanSpeed.fromString(value) ?: AcFanSpeed.AUTO
                    else -> AcFanSpeed.AUTO
                }
                setFanSpeed(device, speed)
            }

            is DeviceCapability.Swing -> {
                val swing = when (value) {
                    is AcSwing -> value
                    is String -> AcSwing.fromString(value) ?: AcSwing.OFF
                    else -> AcSwing.OFF
                }
                setSwing(device, swing)
            }

            else -> {
                DeviceCommandResult(
                    success = false,
                    message = "${device.displayName} does not support capability '${capability.name}'."
                )
            }
        }
    }

    override suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult {
        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_SWITCH,
            "value" to on
        )

        if (!allowWriteCommands) {
            Log.i(TAG, "[read-only-guard] Simulated setPower($on) for ${device.displayName}")
            _acState.value = _acState.value.copy(power = on)
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} power set to ${if (on) "ON" else "OFF"} (Verified mapping: $tuyaCommand)"
            )
        }

        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))
        return if (result.isSuccess) {
            _acState.value = _acState.value.copy(power = on)
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} is now ${if (on) "ON" else "OFF"}."
            )
        } else {
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} power: ${result.exceptionOrNull()?.message}"
            )
        }
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        if (celsius < MIN_TEMPERATURE || celsius > MAX_TEMPERATURE) {
            return DeviceCommandResult(
                success = false,
                message = "Invalid temperature: $celsius°C. ${device.displayName} only supports $MIN_TEMPERATURE°C to $MAX_TEMPERATURE°C."
            )
        }

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_TEMP_SET,
            "value" to celsius
        )

        if (!allowWriteCommands) {
            Log.i(TAG, "[read-only-guard] Simulated setTemperature($celsius°C) for ${device.displayName}")
            _acState.value = _acState.value.copy(targetTemperature = celsius)
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} temperature set to $celsius°C (Verified mapping: $tuyaCommand)"
            )
        }

        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))
        return if (result.isSuccess) {
            _acState.value = _acState.value.copy(targetTemperature = celsius)
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} set to $celsius°C."
            )
        } else {
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} temperature: ${result.exceptionOrNull()?.message}"
            )
        }
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        if (mode == AcMode.HEAT) {
            return DeviceCommandResult(
                success = false,
                message = "${device.displayName} is an inverter cooling unit and does not support heating mode."
            )
        }

        val tuyaCode = MODE_ANIMUS_TO_TUYA[mode] ?: run {
            return DeviceCommandResult(
                success = false,
                message = "${device.displayName} does not support mode '${mode.name}'."
            )
        }

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_MODE,
            "value" to tuyaCode
        )

        if (!allowWriteCommands) {
            Log.i(TAG, "[read-only-guard] Simulated setMode($mode -> $tuyaCode) for ${device.displayName}")
            _acState.value = _acState.value.copy(mode = mode)
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} mode set to ${mode.name} (Verified mapping: $tuyaCommand)"
            )
        }

        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))
        return if (result.isSuccess) {
            _acState.value = _acState.value.copy(mode = mode)
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} mode set to ${mode.name}."
            )
        } else {
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} mode: ${result.exceptionOrNull()?.message}"
            )
        }
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        val tuyaCode = FAN_ANIMUS_TO_TUYA[speed] ?: run {
            return DeviceCommandResult(
                success = false,
                message = "${device.displayName} does not support fan speed '${speed.name}'."
            )
        }

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_FAN_SPEED,
            "value" to tuyaCode
        )

        if (!allowWriteCommands) {
            Log.i(TAG, "[read-only-guard] Simulated setFanSpeed($speed -> $tuyaCode) for ${device.displayName}")
            _acState.value = _acState.value.copy(fanSpeed = speed)
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} fan set to ${speed.name} (Verified mapping: $tuyaCommand)"
            )
        }

        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))
        return if (result.isSuccess) {
            _acState.value = _acState.value.copy(fanSpeed = speed)
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} fan set to ${speed.name}."
            )
        } else {
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} fan speed: ${result.exceptionOrNull()?.message}"
            )
        }
    }

    override suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult {
        return DeviceCommandResult(
            success = false,
            message = "${device.displayName} has manual louvers and does not support motorized swing control."
        )
    }

    /**
     * Queries the live status from Tuya Cloud and updates the semantic Animus state.
     */
    suspend fun refreshState(deviceId: String): Result<TuyaAcState> {
        val statusResult = apiClient.fetchStatus(deviceId)
        return statusResult.mapCatching { items ->
            applyTuyaStatus(items)
        }
    }

    /**
     * Translates raw Tuya status items into Animus semantic state.
     */
    fun applyTuyaStatus(items: List<TuyaDeviceStatusItem>): TuyaAcState {
        var power = _acState.value.power
        var targetTemp = _acState.value.targetTemperature
        var ambientTemp = _acState.value.ambientTemperature
        var mode = _acState.value.mode
        var fanSpeed = _acState.value.fanSpeed

        for (item in items) {
            when (item.code) {
                CODE_SWITCH -> {
                    power = when (val v = item.value) {
                        is Boolean -> v
                        is String -> v.toBoolean()
                        else -> power
                    }
                }
                CODE_TEMP_SET -> {
                    targetTemp = when (val v = item.value) {
                        is Number -> v.toInt()
                        is String -> v.toIntOrNull() ?: targetTemp
                        else -> targetTemp
                    }
                }
                CODE_TEMP_CURRENT -> {
                    ambientTemp = when (val v = item.value) {
                        is Number -> v.toInt()
                        is String -> v.toIntOrNull() ?: ambientTemp
                        else -> ambientTemp
                    }
                }
                CODE_MODE -> {
                    val modeStr = item.value?.toString()?.lowercase(Locale.ROOT)
                    if (modeStr != null && MODE_TUYA_TO_ANIMUS.containsKey(modeStr)) {
                        mode = MODE_TUYA_TO_ANIMUS.getValue(modeStr)
                    }
                }
                CODE_FAN_SPEED -> {
                    val fanStr = item.value?.toString()?.lowercase(Locale.ROOT)
                    if (fanStr != null && FAN_TUYA_TO_ANIMUS.containsKey(fanStr)) {
                        fanSpeed = FAN_TUYA_TO_ANIMUS.getValue(fanStr)
                    }
                }
            }
        }

        val updated = TuyaAcState(
            power = power,
            targetTemperature = targetTemp,
            ambientTemperature = ambientTemp,
            mode = mode,
            fanSpeed = fanSpeed,
            isOnline = true
        )
        _acState.value = updated
        return updated
    }
}
