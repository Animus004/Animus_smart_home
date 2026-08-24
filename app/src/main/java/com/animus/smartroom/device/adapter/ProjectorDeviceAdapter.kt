package com.animus.smartroom.device.adapter

import android.util.Log
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.media.provider.PcLocalMusicProvider

/**
 * Authoritative DeviceAdapter for Smart Projector (Zebronics ADB control via PC daemon).
 * Performs physical readback verification for power and input commands.
 */
class ProjectorDeviceAdapter(
    private val pcLocalMusicProvider: PcLocalMusicProvider = PcLocalMusicProvider()
) : DeviceAdapter {

    override val deviceType: DeviceType = DeviceType.PROJECTOR

    companion object {
        private const val TAG = "ProjectorDeviceAdapter"
    }

    override suspend fun executeCapability(
        device: RoomDevice,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        Log.i(TAG, "[PROJECTOR_EXECUTE] Capability=${capability.name}, Value=$value for ${device.displayName}")

        return when (capability) {
            DeviceCapability.Power -> {
                val turnOn = when (value) {
                    is Boolean -> value
                    is String -> value.equals("on", ignoreCase = true) || value.equals("true", ignoreCase = true)
                    else -> true
                }
                executePower(device, turnOn)
            }
            DeviceCapability.SelectInput -> {
                val input = value?.toString()?.trim()?.uppercase()?.replace(" ", "_") ?: "HDMI_1"
                executeSelectInput(device, input)
            }
            else -> {
                DeviceCommandResult(
                    success = false,
                    message = "Projector does not support capability: ${capability.name}"
                )
            }
        }
    }

    private fun executePower(device: RoomDevice, turnOn: Boolean): DeviceCommandResult {
        val (dispatchOk, dispatchMsg) = pcLocalMusicProvider.setProjectorPower(turnOn)
        if (turnOn) {
            // Fresh readback verification from PC daemon telemetry
            val status = pcLocalMusicProvider.getProjectorStatus()
            val powerState = status?.optString("power_state")
            val isVerifiedOn = powerState.equals("ON", ignoreCase = true)
            Log.i(TAG, "[PROJECTOR_VERIFY_POWER_ON] DispatchOk=$dispatchOk, StatusPowerState=$powerState, Verified=$isVerifiedOn")

            return if (isVerifiedOn) {
                DeviceCommandResult(
                    success = true,
                    message = "Projector is now ON."
                )
            } else {
                DeviceCommandResult(
                    success = false,
                    message = "Projector did not turn on."
                )
            }
        } else {
            Log.i(TAG, "[PROJECTOR_POWER_OFF] DispatchOk=$dispatchOk, Msg=$dispatchMsg")
            return if (dispatchOk) {
                DeviceCommandResult(
                    success = true,
                    message = "Projector is now OFF."
                )
            } else {
                DeviceCommandResult(
                    success = false,
                    message = if (dispatchMsg.isNotBlank()) dispatchMsg else "Could not turn off projector."
                )
            }
        }
    }

    private fun executeSelectInput(device: RoomDevice, input: String): DeviceCommandResult {
        val (ok, msg) = pcLocalMusicProvider.setProjectorSource(input)
        Log.i(TAG, "[PROJECTOR_SELECT_INPUT] Input=$input, Ok=$ok, Msg=$msg")
        return DeviceCommandResult(
            success = ok,
            message = if (ok) "Projector set to $input." else msg
        )
    }

    override suspend fun getState(device: RoomDevice): Map<String, Any> {
        val status = pcLocalMusicProvider.getProjectorStatus() ?: return emptyMap()
        val result = mutableMapOf<String, Any>()
        if (status.has("power_state")) {
            result["power_state"] = status.getString("power_state")
        }
        if (status.has("source")) {
            result["source"] = status.getString("source")
        }
        if (status.has("connected")) {
            result["connected"] = status.getBoolean("connected")
        }
        return result
    }
}
