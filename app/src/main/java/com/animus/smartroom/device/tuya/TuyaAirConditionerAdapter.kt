package com.animus.smartroom.device.tuya

import android.util.Log
import com.animus.smartroom.core.device.AirConditionerDeviceAdapter
import com.animus.smartroom.core.device.DeviceCommand
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
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

class TuyaAirConditionerAdapter(
    private val apiClient: TuyaApiClient,
    val allowWriteCommands: Boolean = false
) : AirConditionerAdapter, AirConditionerDeviceAdapter {

    override val deviceType: com.animus.smartroom.device.model.DeviceType get() = com.animus.smartroom.device.model.DeviceType.AIR_CONDITIONER

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
        val targetStateStr = if (on) "ON" else "OFF"
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.REQUESTED,
            message = "Set power = $targetStateStr"
        )
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.VALIDATING,
            message = "Power action $targetStateStr is valid"
        )

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_SWITCH,
            "value" to on
        )

        if (!allowWriteCommands) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.EXECUTING,
                message = "[read-only-guard] Simulated setPower($on) for ${device.displayName}"
            )
            _acState.value = _acState.value.copy(power = on)
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.COMPLETED,
                message = "power=$targetStateStr (Simulated)"
            )
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} power set to $targetStateStr (Verified mapping: $tuyaCommand)"
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.EXECUTING,
            message = "Sending power command ($targetStateStr)"
        )
        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))

        return if (result.isSuccess) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.DEVICE_RESPONSE,
                message = "Tuya command accepted"
            )
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.VERIFYING,
                message = "Reading AC state"
            )

            // Read back state from Tuya with retry to handle propagation latency
            val currentState = verifyReadbackWithRetry(device.id, { it.power == on })

            if (currentState.power == on) {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.COMPLETED,
                    message = "power=$targetStateStr verified"
                )
                DeviceCommandResult(
                    success = true,
                    message = "${device.displayName} is now turned $targetStateStr."
                )
            } else {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.FAILED,
                    message = "Command accepted but readback did not match requested power state ($targetStateStr)"
                )
                DeviceCommandResult(
                    success = false,
                    message = "Command accepted but ${device.displayName} readback power was not $targetStateStr."
                )
            }
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = "Failed to set power: $errMsg"
            )
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} power: $errMsg"
            )
        }
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.REQUESTED,
            message = "Set temperature = $celsius°C"
        )

        if (celsius < MIN_TEMPERATURE || celsius > MAX_TEMPERATURE) {
            val errMsg = "Temperature $celsius°C is outside supported range $MIN_TEMPERATURE–$MAX_TEMPERATURE°C"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = errMsg
            )
            return DeviceCommandResult(
                success = false,
                message = "Invalid temperature: $celsius°C. ${device.displayName} only supports $MIN_TEMPERATURE°C to $MAX_TEMPERATURE°C."
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.VALIDATING,
            message = "Temperature $celsius°C within $MIN_TEMPERATURE–$MAX_TEMPERATURE°C"
        )

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_TEMP_SET,
            "value" to celsius
        )

        if (!allowWriteCommands) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.EXECUTING,
                message = "[read-only-guard] Simulated setTemperature($celsius°C) for ${device.displayName}"
            )
            _acState.value = _acState.value.copy(targetTemperature = celsius)
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.COMPLETED,
                message = "targetTemperature=$celsius°C (Simulated)"
            )
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} temperature set to $celsius°C (Verified mapping: $tuyaCommand)"
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.EXECUTING,
            message = "Sending semantic temperature command ($celsius°C)"
        )
        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))

        return if (result.isSuccess) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.DEVICE_RESPONSE,
                message = "Tuya command accepted"
            )
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.VERIFYING,
                message = "Reading AC state"
            )

            // Read back state from Tuya with retry to confirm live synchronization
            val currentState = verifyReadbackWithRetry(device.id, { it.targetTemperature == celsius })

            if (currentState.targetTemperature == celsius) {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.COMPLETED,
                    message = "targetTemperature=$celsius°C verified"
                )
                DeviceCommandResult(
                    success = true,
                    message = "${device.displayName} temperature set to $celsius°C."
                )
            } else {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.FAILED,
                    message = "Command accepted but readback temperature (${currentState.targetTemperature}°C) did not match requested $celsius°C"
                )
                DeviceCommandResult(
                    success = false,
                    message = "Command accepted but readback temperature was ${currentState.targetTemperature}°C instead of $celsius°C."
                )
            }
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = "Failed to set temperature: $errMsg"
            )
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} temperature: $errMsg"
            )
        }
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.REQUESTED,
            message = "Set mode = ${mode.name}"
        )

        if (mode == AcMode.HEAT) {
            val errMsg = "${device.displayName} is an inverter cooling unit and does not support heating mode"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = errMsg
            )
            return DeviceCommandResult(
                success = false,
                message = "$errMsg."
            )
        }

        val tuyaCode = MODE_ANIMUS_TO_TUYA[mode] ?: run {
            val errMsg = "${device.displayName} does not support mode '${mode.name}'"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = errMsg
            )
            return DeviceCommandResult(
                success = false,
                message = "$errMsg."
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.VALIDATING,
            message = "Mode ${mode.name} mapped to Tuya code '$tuyaCode'"
        )

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_MODE,
            "value" to tuyaCode
        )

        if (!allowWriteCommands) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.EXECUTING,
                message = "[read-only-guard] Simulated setMode(${mode.name}) for ${device.displayName}"
            )
            _acState.value = _acState.value.copy(mode = mode)
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.COMPLETED,
                message = "mode=${mode.name} (Simulated)"
            )
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} mode set to ${mode.name} (Verified mapping: $tuyaCommand)"
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.EXECUTING,
            message = "Sending mode command (${mode.name})"
        )
        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))

        return if (result.isSuccess) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.DEVICE_RESPONSE,
                message = "Tuya command accepted"
            )
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.VERIFYING,
                message = "Reading AC state"
            )

            // Read back state from Tuya with retry to confirm live synchronization
            val currentState = verifyReadbackWithRetry(device.id, { it.mode == mode })

            if (currentState.mode == mode) {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.COMPLETED,
                    message = "mode=${mode.name} verified"
                )
                DeviceCommandResult(
                    success = true,
                    message = "${device.displayName} mode set to ${mode.name}."
                )
            } else {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.FAILED,
                    message = "Command accepted but readback mode (${currentState.mode.name}) did not match requested ${mode.name}"
                )
                DeviceCommandResult(
                    success = false,
                    message = "Command accepted but readback mode was ${currentState.mode.name}."
                )
            }
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = "Failed to set mode: $errMsg"
            )
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} mode: $errMsg"
            )
        }
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.REQUESTED,
            message = "Set fan speed = ${speed.name}"
        )

        val tuyaCode = FAN_ANIMUS_TO_TUYA[speed] ?: run {
            val errMsg = "${device.displayName} does not support fan speed '${speed.name}'"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = errMsg
            )
            return DeviceCommandResult(
                success = false,
                message = "$errMsg."
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.VALIDATING,
            message = "Fan speed ${speed.name} mapped to Tuya code '$tuyaCode'"
        )

        val tuyaCommand = mapOf<String, Any>(
            "code" to CODE_FAN_SPEED,
            "value" to tuyaCode
        )

        if (!allowWriteCommands) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.EXECUTING,
                message = "[read-only-guard] Simulated setFanSpeed(${speed.name}) for ${device.displayName}"
            )
            _acState.value = _acState.value.copy(fanSpeed = speed)
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.COMPLETED,
                message = "fanSpeed=${speed.name} (Simulated)"
            )
            return DeviceCommandResult(
                success = true,
                message = "${device.displayName} fan speed set to ${speed.name} (Verified mapping: $tuyaCommand)"
            )
        }

        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.EXECUTING,
            message = "Sending fan speed command (${speed.name})"
        )
        val result = apiClient.sendCommands(device.id, listOf(tuyaCommand))

        return if (result.isSuccess) {
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.DEVICE_RESPONSE,
                message = "Tuya command accepted"
            )
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.VERIFYING,
                message = "Reading AC state"
            )

            // Read back state from Tuya with retry to confirm live synchronization
            val currentState = verifyReadbackWithRetry(device.id, { it.fanSpeed == speed })

            if (currentState.fanSpeed == speed) {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.COMPLETED,
                    message = "fanSpeed=${speed.name} verified"
                )
                DeviceCommandResult(
                    success = true,
                    message = "${device.displayName} fan speed set to ${speed.name}."
                )
            } else {
                DiagnosticBus.log(
                    tag = "ac",
                    stage = DiagnosticStage.FAILED,
                    message = "Command accepted but readback fan speed (${currentState.fanSpeed.name}) did not match requested ${speed.name}"
                )
                DeviceCommandResult(
                    success = false,
                    message = "Command accepted but readback fan speed was ${currentState.fanSpeed.name}."
                )
            }
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(
                tag = "ac",
                stage = DiagnosticStage.FAILED,
                message = "Failed to set fan speed: $errMsg"
            )
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} fan speed: $errMsg"
            )
        }
    }

    override suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult {
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.REQUESTED,
            message = "Set swing = ${swing.name}"
        )
        val errMsg = "${device.displayName} has manual louvers and does not support motorized swing control"
        DiagnosticBus.log(
            tag = "ac",
            stage = DiagnosticStage.FAILED,
            message = errMsg
        )
        return DeviceCommandResult(
            success = false,
            message = "$errMsg."
        )
    }

    suspend fun verifyReadbackWithRetry(
        deviceId: String,
        predicate: (TuyaAcState) -> Boolean,
        maxRetries: Int = 3,
        initialDelayMs: Long = 400L,
        retryDelayMs: Long = 500L
    ): TuyaAcState {
        kotlinx.coroutines.delay(initialDelayMs)
        for (i in 0 until maxRetries) {
            val refreshed = refreshState(deviceId)
            val currentState = refreshed.getOrNull() ?: _acState.value
            if (predicate(currentState)) {
                return currentState
            }
            if (i < maxRetries - 1) {
                kotlinx.coroutines.delay(retryDelayMs)
            }
        }
        return _acState.value
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

    override suspend fun getAcState(device: RoomDevice): TuyaAcState {
        return refreshState(device.id).getOrElse { _acState.value }
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

    override suspend fun execute(device: RoomDevice, command: DeviceCommand): DeviceCommandResult {
        return when (command) {
            is DeviceCommand.Power -> setPower(device, command.enabled)
            is DeviceCommand.SetTemperature -> setTemperature(device, command.celsius)
            is DeviceCommand.SetMode -> {
                val modeEnum = AcMode.fromString(command.mode) ?: AcMode.COOL
                setMode(device, modeEnum)
            }
            is DeviceCommand.SetFanSpeed -> {
                val fanEnum = AcFanSpeed.fromString(command.speed) ?: AcFanSpeed.AUTO
                setFanSpeed(device, fanEnum)
            }
            is DeviceCommand.SetSwing -> {
                val swingEnum = AcSwing.fromString(command.swing) ?: AcSwing.OFF
                setSwing(device, swingEnum)
            }
            else -> DeviceCommandResult(success = false, message = "Unsupported command for AC: $command")
        }
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        val state = getAcState(device)
        return mapOf(
            "power" to state.power,
            "targetTemperature" to state.targetTemperature,
            "ambientTemperature" to state.ambientTemperature,
            "mode" to state.mode.name,
            "fanSpeed" to state.fanSpeed.name,
            "isOnline" to state.isOnline
        )
    }
}
