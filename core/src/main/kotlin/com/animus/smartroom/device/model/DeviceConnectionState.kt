package com.animus.smartroom.device.model

sealed interface DeviceConnectionState {
    object Connected : DeviceConnectionState
    object Connecting : DeviceConnectionState
    object Disconnected : DeviceConnectionState
    object Disconnecting : DeviceConnectionState
    object Available : DeviceConnectionState
    object Unavailable : DeviceConnectionState
    data class Error(val message: String) : DeviceConnectionState
}
