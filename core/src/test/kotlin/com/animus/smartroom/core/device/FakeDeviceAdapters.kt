package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.AcFanSpeed
import com.animus.smartroom.device.model.AcMode
import com.animus.smartroom.device.model.AcSwing
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.RoomDevice

class FakeAirConditionerAdapter(
    private val transport: DeviceTransport = FakeDeviceTransport()
) : AirConditionerDeviceAdapter {

    var powerState: Boolean = false
    var currentTemperature: Int = 24
    var currentMode: AcMode = AcMode.COOL
    var currentFanSpeed: AcFanSpeed = AcFanSpeed.AUTO
    var simulatePowerOnFailure: Boolean = false

    private suspend fun ensurePowered(device: RoomDevice, capabilityName: String): Pair<Boolean, Boolean> {
        if (powerState) {
            return Pair(true, false)
        }
        if (simulatePowerOnFailure) {
            return Pair(false, false)
        }
        val pResult = setPower(device, true)
        if (!pResult.success) {
            return Pair(false, false)
        }
        return Pair(true, true)
    }

    override suspend fun setPower(device: RoomDevice, on: Boolean): DeviceCommandResult {
        if (powerState == on) {
            return DeviceCommandResult(success = true, message = "${device.displayName} is already turned ${if (on) "ON" else "OFF"}.")
        }
        val result = transport.send(device, DeviceCommand.Power(on))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        powerState = on
        return DeviceCommandResult(success = true, message = "${device.displayName} is now turned ${if (on) "ON" else "OFF"}.")
    }

    override suspend fun setTemperature(device: RoomDevice, celsius: Int): DeviceCommandResult {
        if (celsius !in 16..30) {
            return DeviceCommandResult(success = false, message = "Invalid temperature: $celsius°C")
        }
        val (powered, autoPowered) = ensurePowered(device, "temperature")
        if (!powered) {
            return DeviceCommandResult(success = false, message = "AC is currently off. I couldn't power it on, so I didn't apply the temperature change.")
        }
        val result = transport.send(device, DeviceCommand.SetTemperature(celsius))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        currentTemperature = celsius
        val msg = if (autoPowered) {
            "AC was off, so I turned it on and set the temperature to $celsius°C."
        } else {
            "${device.displayName} temperature set to $celsius°C."
        }
        return DeviceCommandResult(success = true, message = msg)
    }

    override suspend fun setMode(device: RoomDevice, mode: AcMode): DeviceCommandResult {
        val (powered, autoPowered) = ensurePowered(device, "mode")
        if (!powered) {
            return DeviceCommandResult(success = false, message = "AC is currently off. I couldn't power it on, so I didn't apply the mode change.")
        }
        val result = transport.send(device, DeviceCommand.SetMode(mode.name))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        currentMode = mode
        val msg = if (autoPowered) {
            "AC was off, so I turned it on and switched to ${mode.name} mode."
        } else {
            "${device.displayName} mode set to ${mode.name}."
        }
        return DeviceCommandResult(success = true, message = msg)
    }

    override suspend fun setFanSpeed(device: RoomDevice, speed: AcFanSpeed): DeviceCommandResult {
        val (powered, autoPowered) = ensurePowered(device, "fan speed")
        if (!powered) {
            return DeviceCommandResult(success = false, message = "AC is currently off. I couldn't power it on, so I didn't apply the fan speed change.")
        }
        val result = transport.send(device, DeviceCommand.SetFanSpeed(speed.name))
        if (!result.success) {
            return DeviceCommandResult(success = false, message = result.message)
        }
        currentFanSpeed = speed
        val msg = if (autoPowered) {
            "AC was off, so I turned it on and set the fan to ${speed.name}."
        } else {
            "${device.displayName} fan speed set to ${speed.name}."
        }
        return DeviceCommandResult(success = true, message = msg)
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
}

class FakeAudioOutputAdapter : AudioOutputAdapter {
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
