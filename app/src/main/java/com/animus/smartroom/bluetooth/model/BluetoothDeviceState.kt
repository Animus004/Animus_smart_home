package com.animus.smartroom.bluetooth.model

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
    val connectionState: BluetoothDeviceState = BluetoothDeviceState.Disconnected,
    val isPaired: Boolean = false,
    val isBluetoothEnabled: Boolean = false,
    val hasRequiredPermissions: Boolean = false,
    val targetDeviceName: String = "LG SNC4R(79)",
    val targetDeviceMac: String = "54:15:89:DC:A5:79",
    val userNotice: String? = null
)
