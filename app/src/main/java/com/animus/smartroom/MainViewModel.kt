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
import com.animus.smartroom.command.model.AnimusCommand
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
import kotlinx.coroutines.async
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
    private val voiceOutputAdapter: com.animus.smartroom.voice.AndroidVoiceOutputAdapter = app.voiceOutputAdapter

    /** AC state backed by the application-scoped TuyaAirConditionerAdapter. */
    val acState: StateFlow<TuyaAcState> = app.tuyaAcAdapter.acState
    val tuyaAcState: StateFlow<TuyaAcState> = app.tuyaAcAdapter.acState

    /** Device registry — application-scoped, survives Activity recreation. */
    val deviceRegistry = app.deviceRegistry

    // ─── Brain & Command Router (from AnimusApplication singletons) ─────────
    private val apiKeyStorage = GeminiApiKeyStorage(application.applicationContext)
    private val geminiApiClient = GeminiApiClient()
    val brainManager: AnimusBrainManager = app.brainManager
    val geminiKnowledgeBridge = com.animus.smartroom.brain.knowledge.GeminiKnowledgeBridge()
    private val initialBrainProvider = apiKeyStorage.getSelectedProvider()

    // ─── Visual Brain State (Authoritative lifecycle visualizer) ─────────────
    private val _visualBrainState = MutableStateFlow(com.animus.smartroom.ui.brain.VisualBrainState.WARMING)
    val visualBrainState: StateFlow<com.animus.smartroom.ui.brain.VisualBrainState> = _visualBrainState.asStateFlow()

    // ─── Phase D: Operation Mode & Glass Customization State ─────────────────
    private val _operationMode = MutableStateFlow(com.animus.smartroom.ui.glass.OperationMode.LOCAL_ROOM)
    val operationMode: StateFlow<com.animus.smartroom.ui.glass.OperationMode> = _operationMode.asStateFlow()

    private val _widgetSettings = MutableStateFlow(com.animus.smartroom.ui.glass.WidgetSettings())
    val widgetSettings: StateFlow<com.animus.smartroom.ui.glass.WidgetSettings> = _widgetSettings.asStateFlow()

    private val _chatHistory = MutableStateFlow<List<com.animus.smartroom.ui.glass.ChatMessage>>(emptyList())
    val chatHistory: StateFlow<List<com.animus.smartroom.ui.glass.ChatMessage>> = _chatHistory.asStateFlow()

    fun setOperationMode(mode: com.animus.smartroom.ui.glass.OperationMode) {
        Log.i("MainViewModel", "[OPERATION_MODE] Switched to: $mode")
        _operationMode.value = mode
    }

    fun toggleWidgetClock(show: Boolean) {
        _widgetSettings.update { it.copy(showClock = show) }
    }

    fun toggleWidgetWeather(show: Boolean) {
        _widgetSettings.update { it.copy(showRoomWeather = show) }
    }

    fun toggleWidgetMusic(show: Boolean) {
        _widgetSettings.update { it.copy(showQuickMusic = show) }
    }

    fun toggleWidgetTelemetry(show: Boolean) {
        _widgetSettings.update { it.copy(showDeviceTelemetry = show) }
    }

    fun sendChatMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isBlank()) return
        _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = true, text = trimmed) }
        onExecuteCommand(trimmed)
    }

    fun clearAiFeedback() {
        _aiCommandState.update { it.copy(lastResultMessage = null, isSuccess = null) }
    }

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

    private val pcAlarmClient = com.animus.smartroom.routine.alarm.PcAlarmClient()

    private val _activeRequestId = MutableStateFlow<String?>(null)
    val activeRequestId: StateFlow<String?> = _activeRequestId.asStateFlow()

    private val _actionFeedbackState = MutableStateFlow<com.animus.smartroom.ui.glass.ActionFeedback?>(null)
    val actionFeedbackState: StateFlow<com.animus.smartroom.ui.glass.ActionFeedback?> = _actionFeedbackState.asStateFlow()

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

        // Sync Visual Brain State from LocalInferencePort when idle (do not overwrite active command execution or physical error states)
        viewModelScope.launch {
            app.localInferencePort.status.collectLatest { portStatus ->
                val hasActiveExecutionError = _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED
                val isPersistentError = _visualBrainState.value == com.animus.smartroom.ui.brain.VisualBrainState.ERROR && hasActiveExecutionError
                val isExecutingOrCompleted = _visualBrainState.value == com.animus.smartroom.ui.brain.VisualBrainState.EXECUTING ||
                        _visualBrainState.value == com.animus.smartroom.ui.brain.VisualBrainState.COMPLETED
                if (!_aiCommandState.value.isProcessing &&
                    !isExecutingOrCompleted &&
                    !isPersistentError) {
                    _visualBrainState.value = when (portStatus) {
                        com.animus.smartroom.brain.provider.LocalBrainStatus.STARTING,
                        com.animus.smartroom.brain.provider.LocalBrainStatus.WARMING_UP,
                        com.animus.smartroom.brain.provider.LocalBrainStatus.CONNECTING -> com.animus.smartroom.ui.brain.VisualBrainState.WARMING
                        com.animus.smartroom.brain.provider.LocalBrainStatus.READY,
                        com.animus.smartroom.brain.provider.LocalBrainStatus.AVAILABLE -> com.animus.smartroom.ui.brain.VisualBrainState.READY
                        com.animus.smartroom.brain.provider.LocalBrainStatus.BUSY -> com.animus.smartroom.ui.brain.VisualBrainState.EXECUTING
                        com.animus.smartroom.brain.provider.LocalBrainStatus.ERROR,
                        com.animus.smartroom.brain.provider.LocalBrainStatus.OFFLINE,
                        com.animus.smartroom.brain.provider.LocalBrainStatus.DISCONNECTED,
                        com.animus.smartroom.brain.provider.LocalBrainStatus.FAILED -> com.animus.smartroom.ui.brain.VisualBrainState.ERROR
                    }
                }
            }
        }

        // Local Brain health watchdog: automatically recovers when Ollama daemon boots
        viewModelScope.launch {
            while (true) {
                kotlinx.coroutines.delay(6000L)
                if (!app.localInferencePort.isAvailable() && !_aiCommandState.value.isProcessing) {
                    try {
                        (app.localInferencePort as? com.animus.smartroom.brain.provider.AndroidLocalInferencePort)?.checkHealth()
                    } catch (_: Exception) {}
                }
            }
        }

        // Observe Tuya AC state changes to self-clear stale errors upon physical recovery
        viewModelScope.launch {
            tuyaAcState.collectLatest { state ->
                val currentFb = _actionFeedbackState.value
                if (currentFb != null && (currentFb.targetDevice == "AC" || currentFb.intent.contains("AC", ignoreCase = true))) {
                    if (currentFb.state == com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED && state.recoveryState == "HEALTHY") {
                        val reqId = currentFb.requestId
                        _actionFeedbackState.value = currentFb.copy(
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                            message = "AC ${if (state.power) "ON · ${state.targetTemperature}°C (${state.mode.name})" else "OFF"} · verified",
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                        )
                        viewModelScope.launch {
                            kotlinx.coroutines.delay(3000L)
                            if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                _actionFeedbackState.value = null
                            }
                        }
                    }
                }
            }
        }
    }

    // ─── AC control ───────────────────────────────────────────────────────────

    fun setAcPower(on: Boolean) {
        val reqId = java.util.UUID.randomUUID().toString()
        _activeRequestId.value = reqId
        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
            requestId = reqId,
            intent = if (on) "TURN_ON_AC" else "TURN_OFF_AC",
            targetDevice = "AC",
            state = com.animus.smartroom.ui.glass.ActionExecutionState.EXECUTING,
            message = if (on) "Turning on AC..." else "Turning off AC...",
            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO
        )
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setPower(realAc, on)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                    if (_activeRequestId.value == reqId) {
                        if (result.success) {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = if (on) "TURN_ON_AC" else "TURN_OFF_AC",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                                message = if (on) "AC ON · verified" else "AC OFF · verified",
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                            )
                            viewModelScope.launch {
                                kotlinx.coroutines.delay(3000L)
                                if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                    _actionFeedbackState.value = null
                                }
                            }
                        } else {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = if (on) "TURN_ON_AC" else "TURN_OFF_AC",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                                message = result.message,
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                                isPersistent = false
                            )
                        }
                    }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    fun setAcTemperature(celsius: Int) {
        val reqId = java.util.UUID.randomUUID().toString()
        _activeRequestId.value = reqId
        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
            requestId = reqId,
            intent = "SET_AC_TEMPERATURE",
            targetDevice = "AC",
            state = com.animus.smartroom.ui.glass.ActionExecutionState.EXECUTING,
            message = "Setting AC to $celsius°C...",
            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO
        )
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setTemperature(realAc, celsius)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                    if (_activeRequestId.value == reqId) {
                        if (result.success) {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = "SET_AC_TEMPERATURE",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                                message = "AC set to $celsius°C · verified",
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                            )
                            viewModelScope.launch {
                                kotlinx.coroutines.delay(3000L)
                                if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                    _actionFeedbackState.value = null
                                }
                            }
                        } else {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = "SET_AC_TEMPERATURE",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                                message = result.message,
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                                isPersistent = false
                            )
                        }
                    }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    fun setAcMode(mode: com.animus.smartroom.device.adapter.AcMode) {
        val reqId = java.util.UUID.randomUUID().toString()
        _activeRequestId.value = reqId
        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
            requestId = reqId,
            intent = "SET_AC_MODE",
            targetDevice = "AC",
            state = com.animus.smartroom.ui.glass.ActionExecutionState.EXECUTING,
            message = "Setting AC mode to ${mode.name}...",
            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO
        )
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setMode(realAc, mode)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                    if (_activeRequestId.value == reqId) {
                        if (result.success) {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = "SET_AC_MODE",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                                message = "AC mode ${mode.name} · verified",
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                            )
                            viewModelScope.launch {
                                kotlinx.coroutines.delay(3000L)
                                if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                    _actionFeedbackState.value = null
                                }
                            }
                        } else {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = "SET_AC_MODE",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                                message = result.message,
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                                isPersistent = false
                            )
                        }
                    }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    fun setAcFanSpeed(speed: com.animus.smartroom.device.adapter.AcFanSpeed) {
        val reqId = java.util.UUID.randomUUID().toString()
        _activeRequestId.value = reqId
        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
            requestId = reqId,
            intent = "SET_AC_FAN_SPEED",
            targetDevice = "AC",
            state = com.animus.smartroom.ui.glass.ActionExecutionState.EXECUTING,
            message = "Setting AC fan to ${speed.name}...",
            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO
        )
        viewModelScope.launch {
            _isAcOperating.value = true
            try {
                val realAc = deviceRegistry.getDevicesByType(DeviceType.AIR_CONDITIONER).firstOrNull()
                if (realAc != null) {
                    val result = app.tuyaAcAdapter.setFanSpeed(realAc, speed)
                    _aiCommandState.update { it.copy(lastResultMessage = result.message) }
                    if (_activeRequestId.value == reqId) {
                        if (result.success) {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = "SET_AC_FAN_SPEED",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                                message = "AC fan ${speed.name} · verified",
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                            )
                            viewModelScope.launch {
                                kotlinx.coroutines.delay(3000L)
                                if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                    _actionFeedbackState.value = null
                                }
                            }
                        } else {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = "SET_AC_FAN_SPEED",
                                targetDevice = "AC",
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                                message = result.message,
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                                isPersistent = false
                            )
                        }
                    }
                }
            } finally {
                _isAcOperating.value = false
            }
        }
    }

    // ─── Scheduler ────────────────────────────────────────────────────────────

    fun scheduleAcTimer(delayMinutes: Int, powerOn: Boolean) {
        viewModelScope.launch {
            val res = deviceSchedulerEngine.scheduleAction(
                targetDeviceType = DeviceType.AIR_CONDITIONER,
                actionType = if (powerOn) com.animus.smartroom.scheduler.model.DeviceActionType.POWER_ON else com.animus.smartroom.scheduler.model.DeviceActionType.POWER_OFF,
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
        val reqId = java.util.UUID.randomUUID().toString()
        _activeRequestId.value = reqId
        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
            requestId = reqId,
            intent = "STOP_ALARM",
            state = com.animus.smartroom.ui.glass.ActionExecutionState.EXECUTING,
            message = "Stopping all alarms...",
            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO
        )
        viewModelScope.launch {
            val androidStopJob = async {
                try {
                    routineEngine.stopAlarm()
                    true
                } catch (e: Exception) {
                    false
                }
            }
            val pcStopJob = async {
                try {
                    pcAlarmClient.stopPcAlarm() is com.animus.smartroom.routine.alarm.PcAlarmResult.Success
                } catch (e: Exception) {
                    false
                }
            }
            val androidStopped = androidStopJob.await()
            val pcStopped = pcStopJob.await()

            val statusMsg = when {
                androidStopped && pcStopped -> "All alarms stopped"
                androidStopped && !pcStopped -> "Android alarm stopped · PC alarm unavailable"
                !androidStopped && pcStopped -> "PC alarm stopped"
                else -> "Alarm stop completed"
            }
            if (_activeRequestId.value == reqId) {
                _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                    requestId = reqId,
                    intent = "STOP_ALARM",
                    state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                    message = statusMsg,
                    severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                )
                viewModelScope.launch {
                    kotlinx.coroutines.delay(3000L)
                    if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                        _actionFeedbackState.value = null
                    }
                }
            }
        }
    }

    fun triggerTestAlarm() {
        viewModelScope.launch {
            val storage = com.animus.smartroom.routine.storage.RoutineStorage(getApplication())
            val routine = com.animus.smartroom.routine.model.RoutineState(
                id = "morning_wake_alarm",
                type = com.animus.smartroom.routine.model.RoutineType.SLEEP,
                status = com.animus.smartroom.routine.model.RoutineStatus.ALARMING,
                scheduledWakeTime = System.currentTimeMillis()
            )
            storage.saveActiveRoutine(routine)
            com.animus.smartroom.routine.alarm.AlarmSoundPlayer.startAlarm(getApplication())
            launch {
                pcAlarmClient.startPcAlarm()
            }
        }
    }

    fun dismissActionFeedback() {
        _actionFeedbackState.value = null
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

        val reqId = java.util.UUID.randomUUID().toString()
        _activeRequestId.value = reqId
        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
            requestId = reqId,
            intent = trimmed,
            state = com.animus.smartroom.ui.glass.ActionExecutionState.EXECUTING,
            message = "Executing: '$trimmed'...",
            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO
        )

        viewModelScope.launch {
            _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.EXECUTING
            val currentProviderName = brainManager.activeProvider.value.displayName
            Log.i("MainViewModel", "[LOCAL_QWEN] User command: '$trimmed' (Provider: $currentProviderName)")

            // Remote Mode Safety Check: Guard room-only actuators (Projector, Fire TV, Soundbar BT) when away from room
            if (_operationMode.value == com.animus.smartroom.ui.glass.OperationMode.REMOTE) {
                val lower = trimmed.lowercase(java.util.Locale.ROOT)
                val isRoomOnlyActuatorCommand = lower.startsWith("turn on projector") || lower.startsWith("turn off projector") ||
                        lower.contains("movie mode") || lower.startsWith("watch ") ||
                        lower.startsWith("switch audio") || lower.startsWith("transfer audio") ||
                        lower.startsWith("connect soundbar") || lower.startsWith("disconnect soundbar")

                if (isRoomOnlyActuatorCommand) {
                    val msg = "Room actuators (Projector, Fire TV, Soundbar) are disabled in Remote Mode. AC, Music & Gemini remain active."
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = msg,
                            isSuccess = false
                        )
                    }
                    _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = msg) }
                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.ERROR
                    if (_activeRequestId.value == reqId) {
                        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                            requestId = reqId,
                            intent = trimmed,
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                            message = msg,
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                            isPersistent = false
                        )
                    }
                    return@launch
                }
            }

            // Check if query requires fresh external knowledge lookup
            if (geminiKnowledgeBridge.isFreshKnowledgeQuery(trimmed)) {
                _aiCommandState.update {
                    it.copy(
                        isProcessing = true,
                        lastInputText = trimmed,
                        activeProviderName = "Gemini Knowledge Bridge",
                        lastResultMessage = "Looking up streaming availability..."
                    )
                }

                val apiKey = apiKeyStorage.getApiKey()
                val knowledgeResult = geminiKnowledgeBridge.queryKnowledge(trimmed, apiKey)

                if (knowledgeResult.isSuccess) {
                    val formattedMsg = buildString {
                        append(knowledgeResult.summary)
                        if (knowledgeResult.mediaServices.isNotEmpty()) {
                            val availableList = knowledgeResult.mediaServices.filter { it.isAvailable }
                            if (availableList.isNotEmpty()) {
                                append("\n\nAvailable on: ")
                                append(availableList.joinToString(", ") { it.serviceName })
                            }
                        }
                    }
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = formattedMsg,
                            isSuccess = true
                        )
                    }
                    _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = formattedMsg) }
                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.COMPLETED
                    if (_activeRequestId.value == reqId) {
                        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                            requestId = reqId,
                            intent = trimmed,
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                            message = formattedMsg,
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                        )
                        viewModelScope.launch {
                            kotlinx.coroutines.delay(3000L)
                            if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                _actionFeedbackState.value = null
                            }
                        }
                    }
                    viewModelScope.launch {
                        kotlinx.coroutines.delay(2500)
                        if (_visualBrainState.value == com.animus.smartroom.ui.brain.VisualBrainState.COMPLETED) {
                            _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.READY
                        }
                    }
                } else {
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = knowledgeResult.summary,
                            isSuccess = false
                        )
                    }
                    _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = knowledgeResult.summary) }
                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.ERROR
                    if (_activeRequestId.value == reqId) {
                        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                            requestId = reqId,
                            intent = trimmed,
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                            message = knowledgeResult.summary,
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                            isPersistent = false
                        )
                    }
                }
                return@launch
            }

            // Ordinary deterministic command flow
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

            val brainResult = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                brainManager.interpret(trimmed)
            }
            Log.i("MainViewModel", "[DETERMINISTIC_BRAIN] Brain interpreted result: $brainResult")

            when (brainResult) {
                is BrainResult.Success -> {
                    val isUnderstandingFailure = brainResult.commands.all { it is AnimusCommand.UnknownCommand }
                    if (isUnderstandingFailure) {
                        val reply = "I couldn't understand that command."
                        Log.i("MainViewModel", "[COMMAND_UNDERSTANDING_FAILURE] '$trimmed' not understood -> conversational fallback")
                        _aiCommandState.update {
                            it.copy(
                                isProcessing = false,
                                lastResultMessage = reply,
                                isSuccess = false
                            )
                        }
                        _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = reply) }
                        if (_activeRequestId.value == reqId) {
                            _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                requestId = reqId,
                                intent = trimmed,
                                state = com.animus.smartroom.ui.glass.ActionExecutionState.IDLE,
                                message = reply,
                                severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO,
                                isPersistent = false
                            )
                            viewModelScope.launch {
                                kotlinx.coroutines.delay(3000L)
                                if (_activeRequestId.value == reqId && _actionFeedbackState.value?.message == reply) {
                                    _actionFeedbackState.value = null
                                }
                            }
                        }
                        // Conversational failure: Visual Brain stays READY (no fake hardware error)
                        _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.READY
                    } else {
                        val result = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                            commandRouter.execute(brainResult.commands)
                        }
                        Log.i("MainViewModel", "[PHYSICAL_EXECUTION] Execution result: success=${result.success}, message='${result.message}'")
                        _aiCommandState.update {
                            it.copy(
                                isProcessing = false,
                                lastResultMessage = result.message,
                                isSuccess = result.success
                            )
                        }
                        _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = result.message) }
                        if (_activeRequestId.value == reqId) {
                            if (result.success) {
                                _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                    requestId = reqId,
                                    intent = trimmed,
                                    state = com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS,
                                    message = result.message,
                                    severity = com.animus.smartroom.ui.glass.FeedbackSeverity.SUCCESS
                                )
                                viewModelScope.launch {
                                    kotlinx.coroutines.delay(3000L)
                                    if (_activeRequestId.value == reqId && _actionFeedbackState.value?.state == com.animus.smartroom.ui.glass.ActionExecutionState.VERIFIED_SUCCESS) {
                                        _actionFeedbackState.value = null
                                    }
                                }
                            } else {
                                _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                                    requestId = reqId,
                                    intent = trimmed,
                                    state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                                    message = result.message,
                                    severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                                    isPersistent = true
                                )
                                voiceOutputAdapter.speak(result.message)
                            }
                        }
                        if (result.success) {
                            _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.COMPLETED
                            viewModelScope.launch {
                                kotlinx.coroutines.delay(2500)
                                if (_visualBrainState.value == com.animus.smartroom.ui.brain.VisualBrainState.COMPLETED) {
                                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.READY
                                }
                            }
                        } else {
                            _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.ERROR
                        }
                    }
                }
                is BrainResult.InvalidResponse -> {
                    Log.w("MainViewModel", "[brain] Invalid brain response: ${brainResult.reason}")
                    val reply = "I couldn't understand that command."
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = reply,
                            isSuccess = false
                        )
                    }
                    _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = reply) }
                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.READY
                    if (_activeRequestId.value == reqId) {
                        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                            requestId = reqId,
                            intent = trimmed,
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.IDLE,
                            message = reply,
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.INFO,
                            isPersistent = false
                        )
                        viewModelScope.launch {
                            kotlinx.coroutines.delay(3000L)
                            if (_activeRequestId.value == reqId && _actionFeedbackState.value?.message == reply) {
                                _actionFeedbackState.value = null
                            }
                        }
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
                    _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = brainResult.errorMessage) }
                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.ERROR
                    if (_activeRequestId.value == reqId) {
                        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                            requestId = reqId,
                            intent = trimmed,
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                            message = brainResult.errorMessage,
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                            isPersistent = false
                        )
                    }
                }
                is BrainResult.Unavailable -> {
                    Log.w("MainViewModel", "[brain] Brain is unavailable")
                    val msg = "Brain provider is unavailable."
                    _aiCommandState.update {
                        it.copy(
                            isProcessing = false,
                            lastResultMessage = msg,
                            isSuccess = false
                        )
                    }
                    _chatHistory.update { it + com.animus.smartroom.ui.glass.ChatMessage(isUser = false, text = msg) }
                    _visualBrainState.value = com.animus.smartroom.ui.brain.VisualBrainState.ERROR
                    if (_activeRequestId.value == reqId) {
                        _actionFeedbackState.value = com.animus.smartroom.ui.glass.ActionFeedback(
                            requestId = reqId,
                            intent = trimmed,
                            state = com.animus.smartroom.ui.glass.ActionExecutionState.ERROR_BLOCKED,
                            message = msg,
                            severity = com.animus.smartroom.ui.glass.FeedbackSeverity.ERROR,
                            isPersistent = false
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
