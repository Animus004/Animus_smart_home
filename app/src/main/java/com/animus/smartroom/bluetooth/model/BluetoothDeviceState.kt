package com.animus.smartroom.bluetooth.model

data class BluetoothAudioDevice(
    val name: String,
    val macAddress: String,
    val isBonded: Boolean = true,
    val isConnected: Boolean = false,
    val isAudioDevice: Boolean = true
)

sealed interface BluetoothDeviceState {
    data object Disconnected : BluetoothDeviceState
    data object Connecting : BluetoothDeviceState
    data class Connected(
        val deviceName: String,
        val macAddress: String
    ) : BluetoothDeviceState
    data class Error(
        val message: String
    ) : BluetoothDeviceState
}

data class BluetoothUiState(
    val pairedDevices: List<BluetoothAudioDevice> = emptyList(),
    val selectedDevice: BluetoothAudioDevice? = null,
    val connectionState: BluetoothDeviceState = BluetoothDeviceState.Disconnected,
    val isBluetoothEnabled: Boolean = false,
    val hasRequiredPermissions: Boolean = false,
    val userNotice: String? = null
)
