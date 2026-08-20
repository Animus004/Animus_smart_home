package com.animus.smartroom

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.GeminiApiClient
import com.animus.smartroom.brain.provider.GeminiApiKeyStorage
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.provider.MusicProvider
import com.animus.smartroom.voice.SpeechRecognitionManager
import com.animus.smartroom.voice.VoiceInputState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

import com.animus.smartroom.media.resolver.MusicResolutionCache
import com.animus.smartroom.media.resolver.YouTubeMusicResolver

data class AiCommandUiState(
    val lastInputText: String = "",
    val lastResultMessage: String? = null,
    val isSuccess: Boolean? = null,
    val isProcessing: Boolean = false,
    val activeProviderName: String = "Local"
)

class MainViewModel(application: Application) : AndroidViewModel(application) {

    private val bluetoothManager = BluetoothAudioDeviceManager(application.applicationContext)
    private val musicController = MusicController(application.applicationContext)

    private val apiKeyStorage = GeminiApiKeyStorage(application.applicationContext)
    private val geminiApiClient = GeminiApiClient()

    private val localBrain = LocalAnimusBrain()
    private val cloudBrain = CloudAnimusBrain(
        apiKeyProvider = { apiKeyStorage.getApiKey() },
        apiClient = geminiApiClient
    )

    private val initialBrainProvider = apiKeyStorage.getSelectedProvider()
    private val brainManager = AnimusBrainManager(
        localBrain = localBrain,
        cloudBrain = cloudBrain,
        initialProvider = initialBrainProvider,
        onProviderChanged = { apiKeyStorage.saveSelectedProvider(it) }
    )

    private val musicResolutionCache = MusicResolutionCache.create(application.applicationContext)
    private val musicResolver = YouTubeMusicResolver(
        apiKeyProvider = { BuildConfig.YOUTUBE_API_KEY.ifBlank { null } },
        cache = musicResolutionCache
    )

    private val commandRouter = CommandRouter(
        bluetoothManager = bluetoothManager,
        musicController = musicController,
        musicResolver = musicResolver
    )

    private val speechRecognitionManager = SpeechRecognitionManager(application.applicationContext) { spokenText ->
        onExecuteCommand(spokenText)
    }

    val bluetoothUiState: StateFlow<BluetoothUiState> = bluetoothManager.uiState
    val musicUiState: StateFlow<MusicUiState> = musicController.uiState
    val activeBrainProvider: StateFlow<BrainProviderType> = brainManager.activeProvider
    val voiceInputState: StateFlow<VoiceInputState> = speechRecognitionManager.state

    private val _maskedApiKey = MutableStateFlow(apiKeyStorage.getMaskedApiKey())
    val maskedApiKey: StateFlow<String?> = _maskedApiKey.asStateFlow()

    private val _aiCommandState = MutableStateFlow(
        AiCommandUiState(activeProviderName = initialBrainProvider.displayName)
    )
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

    fun setBrainProvider(type: BrainProviderType) {
        brainManager.setProvider(type)
        apiKeyStorage.saveSelectedProvider(type)
        _aiCommandState.update { it.copy(activeProviderName = type.displayName) }
    }

    fun onSaveGeminiApiKey(key: String?) {
        apiKeyStorage.saveApiKey(key)
        if (!key.isNullOrBlank()) {
            setBrainProvider(BrainProviderType.GEMINI)
        }
        _maskedApiKey.value = apiKeyStorage.getMaskedApiKey()
    }

    fun getGeminiApiKey(): String? {
        return apiKeyStorage.getApiKey()
    }

    fun onTestGeminiConnection(apiKey: String?, onResult: (Boolean, String) -> Unit) {
        viewModelScope.launch {
            val key = apiKey?.trim()?.ifBlank { null } ?: apiKeyStorage.getApiKey()
            if (key.isNullOrBlank()) {
                onResult(false, "API key cannot be empty.")
                return@launch
            }
            val result = geminiApiClient.testConnection(key)
            result.fold(
                onSuccess = { onResult(true, "Gemini connection successful!") },
                onFailure = { error -> onResult(false, error.message ?: "Connection failed.") }
            )
        }
    }

    // AI Command Layer operations
    fun onExecuteCommand(rawInput: String) {
        val trimmed = rawInput.trim()
        if (trimmed.isBlank()) return

        viewModelScope.launch {
            val currentProviderName = brainManager.activeProvider.value.displayName
            Log.i("MainViewModel", "[music-resolver] User command: '$trimmed' (Provider: $currentProviderName)")
            val isMusicQuery = trimmed.startsWith("play", ignoreCase = true)
            val musicSubject = if (isMusicQuery) trimmed.substring(4).trim() else ""

            _aiCommandState.update {
                it.copy(
                    isProcessing = true,
                    lastInputText = trimmed,
                    activeProviderName = currentProviderName,
                    lastResultMessage = if (isMusicQuery && musicSubject.isNotBlank()) "Resolving $musicSubject..." else "Processing command with $currentProviderName..."
                )
            }

            val brainResult = brainManager.interpret(trimmed)
            Log.i("MainViewModel", "[brain] Brain interpreted result: $brainResult")

            when (brainResult) {
                is BrainResult.Success -> {
                    val result = commandRouter.execute(brainResult.commands)
                    Log.i("MainViewModel", "[playback] Execution result: success=${result.success}, message='${result.message}'")
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = result.message,
                            isSuccess = result.success
                        )
                    }
                }
                is BrainResult.InvalidResponse -> {
                    Log.w("MainViewModel", "[brain] Invalid brain response: ${brainResult.reason}")
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = "Brain Error: ${brainResult.reason}",
                            isSuccess = false
                        )
                    }
                }
                is BrainResult.Failure -> {
                    Log.e("MainViewModel", "[brain] Brain failure: ${brainResult.errorMessage}", brainResult.cause)
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = brainResult.errorMessage,
                            isSuccess = false
                        )
                    }
                }
                is BrainResult.Unavailable -> {
                    Log.w("MainViewModel", "[brain] Brain is unavailable")
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = "Brain provider is unavailable.",
                            isSuccess = false
                        )
                    }
                }
            }
        }
    }

    fun clearCommandResult() {
        _aiCommandState.update { it.copy(lastResultMessage = null, isSuccess = null) }
    }

    // Voice interaction methods
    fun onStartVoiceListening() {
        speechRecognitionManager.startListening()
    }

    fun onStopVoiceListening() {
        speechRecognitionManager.stopListening()
    }

    fun onCancelVoiceListening() {
        speechRecognitionManager.cancel()
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
        speechRecognitionManager.destroy()
    }
}
