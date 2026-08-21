package com.animus.smartroom.core.device

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.adapter.DeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.model.TuyaAcState

class FakeAirConditionerAdapter(
    private val transport: DeviceTransport = FakeDeviceTransport()
) : AirConditionerDeviceAdapter, DeviceAdapter {

    var powerState: Boolean = false
    var currentTemperature: Int = 24
    var currentMode: AcMode = AcMode.COOL
    var currentFanSpeed: AcFanSpeed = AcFanSpeed.AUTO

    override suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult {
        val result = transport.send(device, DeviceCommand.Power(on))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        powerState = on
        return DeviceCommandResult(success = true, message = "AC is now turned ${if (on) "ON" else "OFF"}.")
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        if (celsius !in 16..30) {
            return DeviceCommandResult(success = false, message = "Invalid temperature: $celsius°C")
        }
        val result = transport.send(device, DeviceCommand.SetTemperature(celsius))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        currentTemperature = celsius
        return DeviceCommandResult(success = true, message = "AC temperature set to $celsius°C.")
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        val result = transport.send(device, DeviceCommand.SetMode(mode.name))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        currentMode = mode
        return DeviceCommandResult(success = true, message = "AC mode set to ${mode.name}.")
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        val result = transport.send(device, DeviceCommand.SetFanSpeed(speed.name))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        currentFanSpeed = speed
        return DeviceCommandResult(success = true, message = "AC fan speed set to ${speed.name}.")
    }

    override suspend fun getAcState(device: RoomDevice): TuyaAcState {
        return TuyaAcState(
            power = powerState,
            targetTemperature = currentTemperature,
            mode = currentMode,
            fanSpeed = currentFanSpeed,
            isOnline = true
        )
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        return mapOf(
            "power" to powerState,
            "temperature" to currentTemperature,
            "mode" to currentMode.name,
            "fanSpeed" to currentFanSpeed.name
        )
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
            else -> DeviceCommandResult(success = false, message = "Unsupported command for AC: $command")
        }
    }

    override suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        return when (capability) {
            DeviceCapability.Power -> setPower(device, value as? Boolean ?: true)
            DeviceCapability.Temperature -> setTemperature(device, (value as? Number)?.toInt() ?: 24)
            DeviceCapability.HvacMode -> {
                val mode = AcMode.fromString(value?.toString() ?: "COOL") ?: AcMode.COOL
                setMode(device, mode)
            }
            DeviceCapability.FanSpeed -> {
                val fan = AcFanSpeed.fromString(value?.toString() ?: "AUTO") ?: AcFanSpeed.AUTO
                setFanSpeed(device, fan)
            }
            else -> DeviceCommandResult(success = false, message = "Unsupported capability $capability")
        }
    }
}

class FakeAudioOutputAdapter : AudioOutputAdapter, DeviceAdapter {
    var isConnected = false
    var connectedDevice: RoomDevice? = null

    override suspend fun connect(device: RoomDevice): DeviceCommandResult {
        isConnected = true
        connectedDevice = device
        return DeviceCommandResult(success = true, message = "Connected to ${device.displayName}")
    }

    override suspend fun disconnect(device: RoomDevice): DeviceCommandResult {
        isConnected = false
        connectedDevice = null
        return DeviceCommandResult(success = true, message = "Disconnected from ${device.displayName}")
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        return mapOf(
            "connected" to isConnected,
            "device" to (connectedDevice?.displayName ?: "")
        )
    }

    override suspend fun execute(device: RoomDevice, command: DeviceCommand): DeviceCommandResult {
        return when (command) {
            is DeviceCommand.Connect -> connect(device)
            is DeviceCommand.Disconnect -> disconnect(device)
            else -> DeviceCommandResult(success = false, message = "Unsupported command: $command")
        }
    }

    override suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        return when (capability) {
            DeviceCapability.Connect -> connect(device)
            DeviceCapability.Disconnect -> disconnect(device)
            else -> DeviceCommandResult(success = false, message = "Unsupported capability $capability")
        }
    }
}

class FakeMusicPlaybackPort : MusicPlaybackPort {
    var currentTrack: ResolvedTrack? = null
    var isPlaying: Boolean = false
    var currentVolume: Int = 50

    override suspend fun play(track: ResolvedTrack, outputDeviceId: String?): Result<Unit> {
        currentTrack = track
        isPlaying = true
        return Result.success(Unit)
    }

    override suspend fun pause(): Result<Unit> {
        isPlaying = false
        return Result.success(Unit)
    }

    override suspend fun resume(): Result<Unit> {
        isPlaying = true
        return Result.success(Unit)
    }

    override suspend fun next(): Result<Unit> = Result.success(Unit)
    override suspend fun previous(): Result<Unit> = Result.success(Unit)

    override suspend fun setVolume(percentage: Int): Result<Unit> {
        currentVolume = percentage.coerceIn(0, 100)
        return Result.success(Unit)
    }
}
