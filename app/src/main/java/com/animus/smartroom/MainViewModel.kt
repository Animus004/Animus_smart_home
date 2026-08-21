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
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.runtime.AnimusRuntime
import com.animus.smartroom.core.runtime.RuntimeState
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.model.TuyaAcState
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.provider.MusicProvider
import com.animus.smartroom.media.resolver.MusicResolutionCache
import com.animus.smartroom.media.resolver.YouTubeMusicResolver
import com.animus.smartroom.voice.SpeechRecognitionManager
import com.animus.smartroom.voice.VoiceInputState
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
    val isProcessing: Boolean = false,
    val activeProviderName: String = "Local"
)

/**
 * ViewModel for MainActivity. Acts as an observer/controller, not a runtime owner.
 *
 * All singleton dependencies (DeviceRegistry, TuyaAcAdapter, DeviceSchedulerEngine,
 * ScheduledActionStorage, RoutineEngine, MusicController, BluetoothController)
 * are consumed from [AnimusApplication] — the single authoritative dependency graph.
 *
 * Destroying this ViewModel (Activity recreation) does NOT affect:
 * - Scheduled actions (persisted in ScheduledActionStorage + AlarmManager)
 * - Routine state (managed by RoutineEngine in AnimusApplication scope)
 * - DiagnosticBus event history
 * - AnimusRuntime state
 */
class MainViewModel(application: Application) : AndroidViewModel(application) {

    // ─── Application-scoped singletons (single source of truth) ──────────────
    private val app: AnimusApplication = application as AnimusApplication
    private val bluetoothManager: BluetoothAudioDeviceManager = app.bluetoothController
    private val musicController: MusicController = app.musicController

    /** AC state backed by the application-scoped TuyaAirConditionerAdapter. */
    val acState: StateFlow<TuyaAcState> = app.tuyaAcAdapter.acState
    val tuyaAcState: StateFlow<TuyaAcState> = app.tuyaAcAdapter.acState

    /** Device registry — application-scoped, survives Activity recreation. */
    val deviceRegistry = app.deviceRegistry

    // ─── Brain & Command Router (from AnimusApplication singletons) ─────────
    private val apiKeyStorage = GeminiApiKeyStorage(application.applicationContext)
    private val geminiApiClient = GeminiApiClient()
    val brainManager: AnimusBrainManager = app.brainManager
    private val initialBrainProvider = apiKeyStorage.getSelectedProvider()

    // ─── Command Router & RuntimeControlPort ──────────────────────────────────
    private val commandRouter: CommandRouter = app.commandRouter
    val runtimeControlPort: com.animus.smartroom.core.runtime.RuntimeControlPort = app.runtimeControlPort
    val overlayPermissionPort: com.animus.smartroom.core.port.OverlayPermissionPort = app.overlayPermissionPort

    // ─── Scheduler & Routine (from AnimusApplication singletons) ─────────────
    val scheduledActionStorage = app.scheduledActionStorage
    val deviceSchedulerEngine = app.deviceSchedulerEngine
    val routineEngine = app.routineEngine
    val activeRoutine: StateFlow<com.animus.smartroom.routine.model.RoutineState?> = routineEngine.activeRoutine
    val scheduledActions: StateFlow<List<com.animus.smartroom.scheduler.model.ScheduledDeviceAction>> =
        scheduledActionStorage.actionsFlow

    // ─── Registered devices (from application-scoped registry) ───────────────
    val registeredDevices: StateFlow<List<RoomDevice>> = MutableStateFlow<List<RoomDevice>>(emptyList()).apply {
        viewModelScope.launch {
            deviceRegistry.devices.collectLatest { map ->
                value = map.values.toList()
            }
        }
    }.asStateFlow()

    // ─── Runtime state (from AnimusApplication singleton) ────────────────────
    val animusRuntime: AnimusRuntime = app.animusRuntime
    val runtimeState: StateFlow<RuntimeState> = animusRuntime.state
    val actionEvents: StateFlow<List<AnimusActionEvent>> = animusRuntime.actionEvents

    // ─── UI State ─────────────────────────────────────────────────────────────
    val bluetoothUiState: StateFlow<BluetoothUiState> = bluetoothManager.uiState
    val musicUiState: StateFlow<MusicUiState> = musicController.uiState
    val activeBrainProvider: StateFlow<BrainProviderType> = brainManager.activeProvider

    // ─── Voice (application-scoped single authoritative owner) ───────────────
    val voiceInputPort: com.animus.smartroom.core.port.VoiceInputPort = app.voiceInputPort
    val voicePortState: StateFlow<com.animus.smartroom.core.port.VoicePortState> = voiceInputPort.state

    val voiceInputState: StateFlow<VoiceInputState> = MutableStateFlow<VoiceInputState>(VoiceInputState.Idle).apply {
        viewModelScope.launch {
            voicePortState.collectLatest { portState ->
                value = when (portState) {
                    is com.animus.smartroom.core.port.VoicePortState.Idle -> VoiceInputState.Idle
                    is com.animus.smartroom.core.port.VoicePortState.Listening -> VoiceInputState.Listening(portState.rmsDb)
                    is com.animus.smartroom.core.port.VoicePortState.Recognizing -> VoiceInputState.Recognizing(portState.partialText ?: "")
                    is com.animus.smartroom.core.port.VoicePortState.Success -> VoiceInputState.Success(portState.recognizedText)
                    is com.animus.smartroom.core.port.VoicePortState.Error -> VoiceInputState.Error(portState.message)
                    is com.animus.smartroom.core.port.VoicePortState.Unavailable -> VoiceInputState.Unavailable
                    is com.animus.smartroom.core.port.VoicePortState.PermissionDenied -> VoiceInputState.PermissionDenied
                }
            }
        }
    }.asStateFlow()

    /** Legacy diagnostic events stream (for backward-compatible UI rendering). */
    val diagnosticEvents: StateFlow<List<com.animus.smartroom.diagnostics.DiagnosticEvent>> =
        com.animus.smartroom.diagnostics.DiagnosticBus.eventsFlow

    private val _maskedApiKey = MutableStateFlow(apiKeyStorage.getMaskedApiKey())
    val maskedApiKey: StateFlow<String?> = _maskedApiKey.asStateFlow()

    private val _aiCommandState = MutableStateFlow(
        AiCommandUiState(activeProviderName = initialBrainProvider.displayName)
    )
    val aiCommandState: StateFlow<AiCommandUiState> = _aiCommandState.asStateFlow()

    private val _isAcOperating = MutableStateFlow(false)
    val isAcOperating: StateFlow<Boolean> = _isAcOperating.asStateFlow()

    init {
        bluetoothManager.startListening()
        musicController.startListening()

        // Sync selected bluetooth output device with music controller and DeviceRegistry
        viewModelScope.launch {
            bluetoothUiState.collectLatest { btState ->
                val selectedDevice = btState.selectedDevice
                val isConnected = btState.connectionState is BluetoothDeviceState.Connected
                val name = selectedDevice?.displayName
                    ?: if (isConnected) (btState.connectionState as BluetoothDeviceState.Connected).deviceName else null
                musicController.updateOutputDevice(name, isConnected)

                // Sync Bluetooth devices to DeviceRegistry
                val btRoomDevices = btState.pairedDevices.map { btDev ->
                    val connState = when {
                        btDev.isConnected -> DeviceConnectionState.Connected
                        else -> DeviceConnectionState.Disconnected
                    }
                    RoomDevice(
                        id = btDev.macAddress,
                        displayName = btDev.displayName,
                        type = DeviceType.BLUETOOTH_AUDIO,
                        connectionState = connState,
                        supportedCapabilities = setOf(
                            DeviceCapability.Connect,
                            DeviceCapability.Disconnect,
                            DeviceCapability.Play,
                            DeviceCapability.Pause,
                            DeviceCapability.Next,
                            DeviceCapability.Previous,
                            DeviceCapability.Volume
                        ),
                        aliases = listOfNotNull(btDev.alias, btDev.name).distinct()
                    )
                }
                deviceRegistry.registerDevices(btRoomDevices)
            }
        }

        // Initial refresh of AC state
        viewModelScope.launch {
            val realAcId = BuildConfig.TUYA_DEVICE_ID.ifBlank { "76776532a4e57c0a2ca4" }
            app.tuyaAcAdapter.refreshState(realAcId)
        }
    }

    // ─── AC control ───────────────────────────────────────────────────────────

    fun setAcPower(on: Boolean) {
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setPower(realAc, on)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    fun setAcTemperature(celsius: Int) {
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setTemperature(realAc, celsius)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    fun setAcMode(mode: com.animus.smartroom.device.adapter.AcMode) {
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setMode(realAc, mode)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    fun setAcFanSpeed(speed: com.animus.smartroom.device.adapter.AcFanSpeed) {
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setFanSpeed(realAc, speed)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    // ─── Scheduler ────────────────────────────────────────────────────────────

    fun scheduleAcTimer(delayMinutes: Int, powerOn: Boolean) {
        viewModelScope.launch {
            val actionType = if (powerOn)
                com.animus.smartroom.scheduler.model.DeviceActionType.POWER_ON
            else
                com.animus.smartroom.scheduler.model.DeviceActionType.POWER_OFF

            val res = deviceSchedulerEngine.scheduleAction(
                targetDeviceType = DeviceType.AIR_CONDITIONER,
                actionType = actionType,
                delayMinutes = delayMinutes
            )
            val msg = when (res) {
                is com.animus.smartroom.scheduler.ActionScheduleResult.Success -> {
                    val stateDesc = if (powerOn) "turn on" else "turn off"
                    "AC scheduled to $stateDesc in $delayMinutes minute${if (delayMinutes > 1) "s" else ""}."
                }
                is com.animus.smartroom.scheduler.ActionScheduleResult.Error -> res.message
            }
            _aiCommandState.update { it.copy(lastResultMessage = msg) }
        }
    }

    fun cancelAcTimer() {
        viewModelScope.launch {
            deviceSchedulerEngine.cancelActionsForDevice(DeviceType.AIR_CONDITIONER)
            _aiCommandState.update { it.copy(lastResultMessage = "AC timer cancelled.") }
        }
    }

    // ─── Routine ──────────────────────────────────────────────────────────────

    fun cancelActiveRoutine() {
        viewModelScope.launch {
            val result = routineEngine.cancelSleep()
            _aiCommandState.update { current ->
                current.copy(
                    lastResultMessage = result.message,
                    isProcessing = false
                )
            }
        }
    }

    fun stopAlarm() {
        viewModelScope.launch {
            routineEngine.stopAlarm()
        }
    }

    // ─── Diagnostics ──────────────────────────────────────────────────────────

    fun clearDiagnostics() {
        com.animus.smartroom.diagnostics.DiagnosticBus.clear()
    }

    // ─── Brain + AI Command ───────────────────────────────────────────────────

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

    fun getGeminiApiKey(): String? = apiKeyStorage.getApiKey()

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
                    lastResultMessage = if (isMusicQuery && musicSubject.isNotBlank())
                        "Resolving $musicSubject..."
                    else
                        "Processing command with $currentProviderName..."
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

    // ─── Floating Overlay Control ─────────────────────────────────────────────

    fun canDrawOverlays(): Boolean = app.overlayPermissionPort.canDrawOverlays()

    fun isFloatingOverlayRunning(): Boolean = app.isFloatingOverlayRunning()

    fun toggleFloatingOverlay(onPermissionNeeded: () -> Unit) {
        if (!app.overlayPermissionPort.canDrawOverlays()) {
            onPermissionNeeded()
            return
        }
        if (app.isFloatingOverlayRunning()) {
            app.stopFloatingOverlay()
        } else {
            app.startFloatingOverlay()
        }
    }

    // ─── Voice ────────────────────────────────────────────────────────────────

    fun onStartVoiceListening() { voiceInputPort.startListening() }
    fun onStopVoiceListening() { voiceInputPort.stopListening() }
    fun onCancelVoiceListening() { voiceInputPort.cancel() }

    // ─── Bluetooth ────────────────────────────────────────────────────────────

    fun onConnectClicked() { bluetoothManager.connect() }
    fun onDisconnectClicked() { bluetoothManager.disconnect() }
    fun onDeviceSelected(macAddress: String) { bluetoothManager.selectDevice(macAddress) }

    fun refreshState() {
        bluetoothManager.refreshState()
        musicController.refreshVolume()
    }

    fun onPermissionsResult(granted: Boolean) {
        bluetoothManager.refreshState()
        if (granted) bluetoothManager.connect()
    }

    fun getRequiredPermissions(): Array<String> = bluetoothManager.getRequiredPermissions()
    fun hasPermissions(): Boolean = bluetoothManager.hasRequiredPermissions()

    // ─── Music ────────────────────────────────────────────────────────────────

    fun onPlayPauseClicked() { musicController.togglePlayPause() }
    fun onNextClicked() { musicController.next() }
    fun onPreviousClicked() { musicController.previous() }
    fun onVolumeChanged(percent: Float) { musicController.setVolume(percent) }

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

    fun onProviderSelected(providerId: String) { musicController.setProvider(providerId) }
    fun getAvailableProviders(): List<MusicProvider> = musicController.getAvailableProviders()

    // ─── Lifecycle ────────────────────────────────────────────────────────────

    override fun onCleared() {
        super.onCleared()
        bluetoothManager.stopListening()
        musicController.stopListening()
    }
}
