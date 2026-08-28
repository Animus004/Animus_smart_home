package com.animus.smartroom.device.tuya

import android.util.Log
import com.animus.smartroom.core.device.DeviceCommand
import com.animus.smartroom.device.ac.BackendAcClient
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
import kotlinx.coroutines.flow.update
import org.json.JSONObject
import java.util.Locale

/**
 * Authoritative Thin-Client Android DeviceAdapter for Lloyd Air Conditioner.
 * Proxies all queries and mutations to the authoritative Python Phase F backend AcController.
 * Android never holds Tuya local_key or connects directly to TCP 6668.
 */
class TuyaAirConditionerAdapter(
    private val apiClient: TuyaApiClient? = null,
    val allowWriteCommands: Boolean = true,
    private val hostProvider: (() -> String)? = null,
    private val backendAcClient: BackendAcClient = BackendAcClient(hostProvider = hostProvider ?: { "192.168.1.9" })
) : AirConditionerAdapter {

    override val deviceType: com.animus.smartroom.device.model.DeviceType get() = com.animus.smartroom.device.model.DeviceType.AIR_CONDITIONER

    companion object {
        private const val TAG = "TuyaAcAdapter"

        const val MIN_TEMPERATURE = 16
        const val MAX_TEMPERATURE = 30

        const val CODE_SWITCH = "switch"
        const val CODE_TEMP_SET = "temp_set"
        const val CODE_TEMP_CURRENT = "temp_current"
        const val CODE_MODE = "mode"
        const val CODE_FAN_SPEED = "fan_speed_enum"

        val MODE_ANIMUS_TO_TUYA = mapOf(
            AcMode.COOL to "cold",
            AcMode.AUTO to "auto",
            AcMode.DRY to "wet",
            AcMode.FAN to "wind"
        )

        val MODE_TUYA_TO_ANIMUS = mapOf(
            "cold" to AcMode.COOL,
            "auto" to AcMode.AUTO,
            "wet" to AcMode.DRY,
            "wind" to AcMode.FAN
        )

        val FAN_ANIMUS_TO_TUYA = mapOf(
            AcFanSpeed.LOW to "low",
            AcFanSpeed.MEDIUM to "mid",
            AcFanSpeed.HIGH to "high",
            AcFanSpeed.AUTO to "auto"
        )

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
        DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.REQUESTED, message = "Set power = $targetStateStr")

        val result = backendAcClient.setPower(on)
        return if (result.isSuccess) {
            val json = result.getOrNull()
            updateStateFromBackendJson(json)
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.COMPLETED, message = "power=$targetStateStr verified")
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} is now turned $targetStateStr."
            )
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = "Failed to set power: $errMsg")
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} power: $errMsg"
            )
        }
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.REQUESTED, message = "Set temperature = $celsius°C")

        if (celsius < MIN_TEMPERATURE || celsius > MAX_TEMPERATURE) {
            val errMsg = "Temperature $celsius°C is outside supported range $MIN_TEMPERATURE–$MAX_TEMPERATURE°C"
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = errMsg)
            return DeviceCommandResult(
                success = false,
                message = "Invalid temperature: $celsius°C. ${device.displayName} only supports $MIN_TEMPERATURE°C to $MAX_TEMPERATURE°C."
            )
        }

        val result = backendAcClient.setTemperature(celsius)
        return if (result.isSuccess) {
            val json = result.getOrNull()
            updateStateFromBackendJson(json)
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.COMPLETED, message = "targetTemperature=$celsius°C verified")
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} temperature set to $celsius°C."
            )
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = "Failed to set temperature: $errMsg")
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} temperature: $errMsg"
            )
        }
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.REQUESTED, message = "Set mode = ${mode.name}")

        if (mode == AcMode.HEAT) {
            val errMsg = "${device.displayName} is an inverter cooling unit and does not support heating mode"
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = errMsg)
            return DeviceCommandResult(success = false, message = "$errMsg.")
        }

        val result = backendAcClient.setMode(mode.name)
        return if (result.isSuccess) {
            val json = result.getOrNull()
            updateStateFromBackendJson(json)
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.COMPLETED, message = "mode=${mode.name} verified")
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} mode set to ${mode.name}."
            )
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = "Failed to set mode: $errMsg")
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} mode: $errMsg"
            )
        }
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.REQUESTED, message = "Set fan speed = ${speed.name}")

        val result = backendAcClient.setFanSpeed(speed.name)
        return if (result.isSuccess) {
            val json = result.getOrNull()
            updateStateFromBackendJson(json)
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.COMPLETED, message = "fanSpeed=${speed.name} verified")
            DeviceCommandResult(
                success = true,
                message = "${device.displayName} fan speed set to ${speed.name}."
            )
        } else {
            val errMsg = result.exceptionOrNull()?.message ?: "Unknown error"
            DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = "Failed to set fan speed: $errMsg")
            DeviceCommandResult(
                success = false,
                message = "Failed to set ${device.displayName} fan speed: $errMsg"
            )
        }
    }

    override suspend fun setSwing(device: RoomDevice, swing: AcSwing): DeviceCommandResult {
        DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.REQUESTED, message = "Set swing = ${swing.name}")
        val errMsg = "${device.displayName} has manual louvers and does not support motorized swing control"
        DiagnosticBus.log(tag = "ac", stage = DiagnosticStage.FAILED, message = errMsg)
        return DeviceCommandResult(success = false, message = "$errMsg.")
    }

    /**
     * Queries authoritative AC state from backend.
     */
    suspend fun refreshState(deviceId: String = ""): Result<TuyaAcState> {
        val statusRes = backendAcClient.getStatus()
        return if (statusRes.isSuccess) {
            val json = statusRes.getOrNull()
            val state = updateStateFromBackendJson(json)
            Result.success(state)
        } else {
            val err = statusRes.exceptionOrNull() ?: Exception("Backend unreachable")
            _acState.update { current ->
                current.copy(isOnline = false, recoveryState = "OFFLINE")
            }
            Result.failure(err)
        }
    }

    suspend fun getAcState(device: RoomDevice): TuyaAcState {
        return refreshState(device.id).getOrElse { _acState.value }
    }

    private fun updateStateFromBackendJson(json: JSONObject?): TuyaAcState {
        if (json == null) return _acState.value

        // Check if nested in 'actual_state' or direct
        val stateObj = json.optJSONObject("actual_state") ?: json

        val power = stateObj.optBoolean("power", _acState.value.power)
        val targetTemp = stateObj.optInt("target_temperature", _acState.value.targetTemperature)
        val ambientTemp = stateObj.optInt("ambient_temperature", _acState.value.ambientTemperature)
        val modeStr = stateObj.optString("mode", _acState.value.mode.name)
        val fanStr = stateObj.optString("fan_speed", _acState.value.fanSpeed.name)
        val isOnline = stateObj.optBoolean("is_online", true)

        val mode = AcMode.fromString(modeStr) ?: AcMode.COOL
        val fanSpeed = AcFanSpeed.fromString(fanStr) ?: AcFanSpeed.AUTO

        val updated = TuyaAcState(
            power = power,
            targetTemperature = if (targetTemp in MIN_TEMPERATURE..MAX_TEMPERATURE) targetTemp else 24,
            ambientTemperature = ambientTemp,
            mode = mode,
            fanSpeed = fanSpeed,
            isOnline = isOnline,
            lastSeenTimestamp = System.currentTimeMillis(),
            recoveryState = "HEALTHY"
        )
        _acState.value = updated
        return updated
    }

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
            isOnline = true,
            lastSeenTimestamp = System.currentTimeMillis(),
            recoveryState = "HEALTHY"
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

    fun updateStateDirect(
        power: Boolean,
        targetTemp: Int,
        currentTemp: Int,
        mode: AcMode,
        fanSpeed: AcFanSpeed,
        isOnline: Boolean
    ): TuyaAcState {
        val updated = TuyaAcState(
            power = power,
            targetTemperature = if (targetTemp in MIN_TEMPERATURE..MAX_TEMPERATURE) targetTemp else 24,
            ambientTemperature = currentTemp,
            mode = mode,
            fanSpeed = fanSpeed,
            isOnline = isOnline,
            lastSeenTimestamp = System.currentTimeMillis(),
            recoveryState = if (isOnline) "HEALTHY" else "OFFLINE"
        )
        _acState.value = updated
        return updated
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        val state = getAcState(device)
        return mapOf(
            "power" to state.power,
            "targetTemperature" to state.targetTemperature,
            "ambientTemperature" to state.ambientTemperature,
            "mode" to state.mode.name,
            "fanSpeed" to state.fanSpeed.name,
            "isOnline" to state.isOnline,
            "lastSeenTimestamp" to state.lastSeenTimestamp,
            "recoveryState" to state.recoveryState
        )
    }
}
