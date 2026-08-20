package com.animus.smartroom

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.command.parser.CommandParser
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.provider.MusicProvider
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AiCommandUiState(
    val lastInputText: String = "",
    val lastResultMessage: String? = null,
    val isSuccess: Boolean? = null,
    val isProcessing: Boolean = false
)

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val bluetoothManager = BluetoothAudioDeviceManager(application.applicationContext)
    private val musicController = MusicController(application.applicationContext)

    private val commandParser: CommandParser = LocalCommandParser()
    private val commandRouter = CommandRouter(bluetoothManager, musicController)

    val bluetoothUiState: StateFlow<BluetoothUiState> = bluetoothManager.uiState
    val musicUiState: StateFlow<MusicUiState> = musicController.uiState

    private val _aiCommandState = MutableStateFlow(AiCommandUiState())
    val aiCommandState: StateFlow<AiCommandUiState> = _aiCommandState.asStateFlow()

    init {
        bluetoothManager.startListening()
        musicController.startListening()

        // Sync selected bluetooth output device with music controller
        viewModelScope.launch {
            bluetoothUiState.collectLatest { btState ->
                val selectedDevice = btState.selectedDevice
                val isConnected = btState.connectionState is BluetoothDeviceState.Connected
                val name = selectedDevice?.displayName ?: if (isConnected) (btState.connectionState as BluetoothDeviceState.Connected).deviceName else null
                musicController.updateOutputDevice(name, isConnected)
            }
        }
    }

    fun onSetDeviceAlias(macAddress: String, alias: String?) {
        bluetoothManager.setDeviceAlias(macAddress, alias)
    }

    // AI Command Layer operations
    fun onExecuteCommand(rawInput: String) {
        val trimmed = rawInput.trim()
        if (trimmed.isBlank()) return

        viewModelScope.launch {
            Log.i("MainViewModel", "[ai] User entered command: '$trimmed'")
            _aiCommandState.update { it.copy(isProcessing = true, lastInputText = trimmed) }

            val parsedCommand = commandParser.parse(trimmed)
            Log.i("MainViewModel", "[ai] Parsed command: ${parsedCommand::class.simpleName}")

            val result = commandRouter.execute(parsedCommand)
            Log.i("MainViewModel", "[ai] Execution result: success=${result.success}, message='${result.message}'")

            _aiCommandState.update {
                it.copy(
                    isProcessing = false,
                    lastResultMessage = result.message,
                    isSuccess = result.success
                )
            }
        }
    }

    fun clearCommandResult() {
        _aiCommandState.update { it.copy(lastResultMessage = null, isSuccess = null) }
    }

    // Bluetooth operations
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
        musicController.refreshVolume()
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

    // Media & Music operations
    fun onPlayPauseClicked() {
        musicController.togglePlayPause()
    }

    fun onNextClicked() {
        musicController.next()
    }

    fun onPreviousClicked() {
        musicController.previous()
    }

    fun onVolumeChanged(percent: Float) {
        musicController.setVolume(percent)
    }

    fun onPlayZaraZaraClicked() {
        val btState = bluetoothUiState.value
        val isConnected = btState.connectionState is BluetoothDeviceState.Connected
        val targetName = btState.selectedDevice?.name ?: "LG SNC4R"

        Log.d("MusicController", "[bluetooth] Checking output device before preset: target=$targetName, isConnected=$isConnected")

        if (!isConnected) {
            val notice = "Connect $targetName to play room audio"
            Log.w("MusicController", "[music] BLOCKED preset: Target '$targetName' is NOT connected")
            musicController.setNotice(notice)
            return
        }

        Log.i("MusicController", "[music] ALLOWED preset: Target '$targetName' is connected. Playing Zara Zara via provider.")
        musicController.playZaraZaraPreset(targetName)
    }

    fun onProviderSelected(providerId: String) {
        musicController.setProvider(providerId)
    }

    fun getAvailableProviders(): List<MusicProvider> {
        return musicController.getAvailableProviders()
    }

    override fun onCleared() {
        super.onCleared()
        bluetoothManager.stopListening()
        musicController.stopListening()
    }
}
