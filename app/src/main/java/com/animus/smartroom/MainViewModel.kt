package com.animus.smartroom

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import kotlinx.coroutines.flow.StateFlow

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val bluetoothManager = BluetoothAudioDeviceManager(application.applicationContext)

    val bluetoothUiState: StateFlow<BluetoothUiState> = bluetoothManager.uiState

    init {
        bluetoothManager.startListening()
    }

    fun onConnectClicked() {
        bluetoothManager.connect()
    }

    fun onDisconnectClicked() {
        bluetoothManager.disconnect()
    }

    fun onDeviceSelected(macAddress: String) {
        bluetoothManager.selectDevice(macAddress)
    }

    fun refreshState() {
        bluetoothManager.refreshState()
    }

    fun onPermissionsResult(granted: Boolean) {
        bluetoothManager.refreshState()
        if (granted) {
            bluetoothManager.connect()
        }
    }

    fun getRequiredPermissions(): Array<String> {
        return bluetoothManager.getRequiredPermissions()
    }

    fun hasPermissions(): Boolean {
        return bluetoothManager.hasRequiredPermissions()
    }

    override fun onCleared() {
        super.onCleared()
        bluetoothManager.stopListening()
    }
}
