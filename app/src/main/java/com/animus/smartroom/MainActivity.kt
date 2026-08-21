package com.animus.smartroom

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.model.PlaybackStatus
import com.animus.smartroom.ui.theme.AccentGreen
import com.animus.smartroom.ui.theme.AnimusSmartRoomTheme
import com.animus.smartroom.voice.VoiceInputState

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleCommandIntent(intent)
        setContent {
            AnimusSmartRoomTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val bluetoothUiState by viewModel.bluetoothUiState.collectAsStateWithLifecycle()
                    val musicUiState by viewModel.musicUiState.collectAsStateWithLifecycle()
                    val aiCommandState by viewModel.aiCommandState.collectAsStateWithLifecycle()
                    val voiceInputState by viewModel.voiceInputState.collectAsStateWithLifecycle()
                    val activeBrainProvider by viewModel.activeBrainProvider.collectAsStateWithLifecycle()
                    val maskedApiKey by viewModel.maskedApiKey.collectAsStateWithLifecycle()
                    val activeRoutine by viewModel.activeRoutine.collectAsStateWithLifecycle()
                    val registeredDevices by viewModel.registeredDevices.collectAsStateWithLifecycle()
                    val tuyaAcState by viewModel.tuyaAcState.collectAsStateWithLifecycle()
                    val isAcOperating by viewModel.isAcOperating.collectAsStateWithLifecycle()
                    val diagnosticEvents by viewModel.diagnosticEvents.collectAsStateWithLifecycle()
                    val scheduledActions by viewModel.scheduledActions.collectAsStateWithLifecycle()

                    val activeAcTimer = scheduledActions.firstOrNull {
                        it.targetDeviceType == com.animus.smartroom.device.model.DeviceType.AIR_CONDITIONER && it.isPending
                    }

                    HomeScreen(
                        bluetoothState = bluetoothUiState,
                        musicState = musicUiState,
                        aiState = aiCommandState,
                        voiceState = voiceInputState,
                        activeBrainProvider = activeBrainProvider,
                        maskedApiKey = maskedApiKey,
                        activeRoutine = activeRoutine,
                        registeredDevices = registeredDevices,
                        tuyaAcState = tuyaAcState,
                        isAcOperating = isAcOperating,
                        diagnosticEvents = diagnosticEvents,
                        activeAcTimer = activeAcTimer,
                        onCancelRoutine = { viewModel.cancelActiveRoutine() },
                        onStopAlarm = { viewModel.stopAlarm() },
                        onClearDiagnostics = { viewModel.clearDiagnostics() },
                        onSetAcPower = { on -> viewModel.setAcPower(on) },
                        onSetAcTemperature = { temp -> viewModel.setAcTemperature(temp) },
                        onSetAcMode = { mode -> viewModel.setAcMode(mode) },
                        onSetAcFanSpeed = { speed -> viewModel.setAcFanSpeed(speed) },
                        onScheduleAcTimer = { mins, on -> viewModel.scheduleAcTimer(mins, on) },
                        onCancelAcTimer = { viewModel.cancelAcTimer() },
                        onConnectClick = { viewModel.onConnectClicked() },
                        onDisconnectClick = { viewModel.onDisconnectClicked() },
                        onDeviceSelected = { mac -> viewModel.onDeviceSelected(mac) },
                        onPermissionsResult = { granted -> viewModel.onPermissionsResult(granted) },
                        getRequiredPermissions = { viewModel.getRequiredPermissions() },
                        hasPermissions = { viewModel.hasPermissions() },
                        onPlayPauseClick = { viewModel.onPlayPauseClicked() },
                        onNextClick = { viewModel.onNextClicked() },
                        onPreviousClick = { viewModel.onPreviousClicked() },
                        onVolumeChange = { percent -> viewModel.onVolumeChanged(percent) },
                        onPlayZaraZaraClick = { viewModel.onPlayZaraZaraClicked() },
                        onExecuteCommand = { cmd -> viewModel.onExecuteCommand(cmd) },
                        onSetDeviceAlias = { mac, alias -> viewModel.onSetDeviceAlias(mac, alias) },
                        onStartVoiceListening = { viewModel.onStartVoiceListening() },
                        onStopVoiceListening = { viewModel.onStopVoiceListening() },
                        onCancelVoiceListening = { viewModel.onCancelVoiceListening() },
                        onSetBrainProvider = { type -> viewModel.setBrainProvider(type) },
                        onSaveGeminiApiKey = { key -> viewModel.onSaveGeminiApiKey(key) },
                        onTestGeminiConnection = { key, callback -> viewModel.onTestGeminiConnection(key, callback) },
                        onToggleFloatingOverlay = { onPermissionNeeded -> viewModel.toggleFloatingOverlay(onPermissionNeeded) }
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleCommandIntent(intent)
    }

    private fun handleCommandIntent(intent: Intent?) {
        val rawCommand = intent?.getStringExtra("command")
        val b64Command = intent?.getStringExtra("command_b64")
        val command = when {
            !b64Command.isNullOrBlank() -> {
                try {
                    String(android.util.Base64.decode(b64Command, android.util.Base64.DEFAULT), Charsets.UTF_8)
                } catch (e: Exception) {
                    null
                }
            }
            !rawCommand.isNullOrBlank() -> rawCommand
            else -> null
        }

        if (!command.isNullOrBlank()) {
            android.util.Log.i("MainActivity", "[intent-cmd] Received command: '$command'")
            viewModel.onExecuteCommand(command)
        } else {
            android.util.Log.d("MainActivity", "[intent-cmd] No command extra found in intent")
        }
    }

    override fun onResume() {
        super.onResume()
        viewModel.refreshState()
    }
}

@Composable
fun HomeScreen(
    bluetoothState: BluetoothUiState,
    musicState: MusicUiState,
    aiState: AiCommandUiState,
    voiceState: VoiceInputState,
    activeBrainProvider: com.animus.smartroom.brain.model.BrainProviderType,
    maskedApiKey: String?,
    activeRoutine: com.animus.smartroom.routine.model.RoutineState? = null,
    registeredDevices: List<com.animus.smartroom.device.model.RoomDevice> = emptyList(),
    tuyaAcState: com.animus.smartroom.device.tuya.model.TuyaAcState = com.animus.smartroom.device.tuya.model.TuyaAcState(),
    isAcOperating: Boolean = false,
    diagnosticEvents: List<com.animus.smartroom.diagnostics.DiagnosticEvent> = emptyList(),
    activeAcTimer: com.animus.smartroom.scheduler.model.ScheduledDeviceAction? = null,
    onCancelRoutine: () -> Unit = {},
    onStopAlarm: () -> Unit = {},
    onClearDiagnostics: () -> Unit = {},
    onSetAcPower: (Boolean) -> Unit = {},
    onSetAcTemperature: (Int) -> Unit = {},
    onSetAcMode: (com.animus.smartroom.device.adapter.AcMode) -> Unit = {},
    onSetAcFanSpeed: (com.animus.smartroom.device.adapter.AcFanSpeed) -> Unit = {},
    onScheduleAcTimer: (delayMinutes: Int, powerOn: Boolean) -> Unit = { _, _ -> },
    onCancelAcTimer: () -> Unit = {},
    onConnectClick: () -> Unit,
    onDisconnectClick: () -> Unit,
    onDeviceSelected: (String) -> Unit,
    onPermissionsResult: (Boolean) -> Unit,
    getRequiredPermissions: () -> Array<String>,
    hasPermissions: () -> Boolean,
    onPlayPauseClick: () -> Unit,
    onNextClick: () -> Unit,
    onPreviousClick: () -> Unit,
    onVolumeChange: (Float) -> Unit,
    onPlayZaraZaraClick: () -> Unit,
    onExecuteCommand: (String) -> Unit,
    onSetDeviceAlias: (String, String?) -> Unit,
    onStartVoiceListening: () -> Unit,
    onStopVoiceListening: () -> Unit,
    onCancelVoiceListening: () -> Unit,
    onSetBrainProvider: (com.animus.smartroom.brain.model.BrainProviderType) -> Unit,
    onSaveGeminiApiKey: (String?) -> Unit,
    onTestGeminiConnection: (String?, (Boolean, String) -> Unit) -> Unit,
    onToggleFloatingOverlay: (onPermissionNeeded: () -> Unit) -> Unit = {}
) {
    val context = LocalContext.current
    var showDevicePicker by remember { mutableStateOf(false) }
    var showBrainSettings by remember { mutableStateOf(false) }
    var showDeviceDrawer by remember { mutableStateOf(false) }
    var showAcRemote by remember { mutableStateOf(false) }
    var showDiagnosticLogs by remember { mutableStateOf(false) }
    var showOverlayPermissionDialog by remember { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestMultiplePermissions()
    ) { permsMap ->
        val allGranted = permsMap.values.all { it }
        onPermissionsResult(allGranted)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 24.dp)
    ) {
        // Top Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 22.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(
                    text = "Animus Smart Room",
                    fontSize = 24.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "Room Audio & Automation Center",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                // Devices Drawer Button
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(Color(0xFF38BDF8).copy(alpha = 0.15f))
                        .clickable { showDeviceDrawer = true },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Devices,
                        contentDescription = "Room Devices",
                        tint = Color(0xFF38BDF8),
                        modifier = Modifier.size(22.dp)
                    )
                }

                Spacer(modifier = Modifier.width(6.dp))

                // Diagnostics Button
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .clickable { showDiagnosticLogs = true },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.BugReport,
                        contentDescription = "Diagnostics",
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                }

                Spacer(modifier = Modifier.width(6.dp))

                // Floating Overlay Button
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(Color(0xFFA855F7).copy(alpha = 0.15f))
                        .clickable {
                            onToggleFloatingOverlay {
                                showOverlayPermissionDialog = true
                            }
                        },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.PictureInPicture,
                        contentDescription = "Floating Control Surface",
                        tint = Color(0xFFA855F7),
                        modifier = Modifier.size(20.dp)
                    )
                }

                Spacer(modifier = Modifier.width(6.dp))

                // Brain Settings Button
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .clickable { showBrainSettings = true },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Psychology,
                        contentDescription = "Brain Settings",
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                }

                Spacer(modifier = Modifier.width(6.dp))

                // Bluetooth Settings Button
                Box(
                    modifier = Modifier
                        .size(42.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .clickable {
                            context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                        },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.SettingsBluetooth,
                        contentDescription = "Bluetooth Settings",
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }

        android.util.Log.i("HomeScreen", "[compose] activeRoutine: id=${activeRoutine?.id}, status=${activeRoutine?.status}, isActive=${activeRoutine?.isActive}")

        // Active Routine Card (if active)
        if (activeRoutine != null && activeRoutine.isActive) {
            ActiveRoutineCard(
                routine = activeRoutine,
                onCancelClick = onCancelRoutine,
                onStopAlarm = onStopAlarm
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

        // 1. Voice-First AI Command Layer: "Ask Animus"
        AskAnimusCard(
            aiState = aiState,
            voiceState = voiceState,
            onStartVoiceListening = onStartVoiceListening,
            onStopVoiceListening = onStopVoiceListening,
            onCancelVoiceListening = onCancelVoiceListening,
            onOpenBrainSettings = { showBrainSettings = true },
            onExecuteCommand = onExecuteCommand
        )

        Spacer(modifier = Modifier.height(20.dp))

        // 2. Bluetooth Audio Device Card
        AudioDeviceCard(
            uiState = bluetoothState,
            onActionClick = {
                if (!hasPermissions()) {
                    permissionLauncher.launch(getRequiredPermissions())
                } else {
                    when (bluetoothState.connectionState) {
                        is BluetoothDeviceState.Connected -> onDisconnectClick()
                        is BluetoothDeviceState.Disconnected,
                        is BluetoothDeviceState.Error -> onConnectClick()
                        is BluetoothDeviceState.Connecting,
                        is BluetoothDeviceState.Disconnecting -> { /* Disabled while in progress */ }
                    }
                }
            },
            onSwitchDeviceClick = {
                if (!hasPermissions()) {
                    permissionLauncher.launch(getRequiredPermissions())
                } else {
                    showDevicePicker = true
                }
            },
            onRequestPermission = {
                permissionLauncher.launch(getRequiredPermissions())
            }
        )

        Spacer(modifier = Modifier.height(20.dp))

        // 3. Universal Music Control Section
        MusicControlCard(
            musicState = musicState,
            onPlayPauseClick = onPlayPauseClick,
            onNextClick = onNextClick,
            onPreviousClick = onPreviousClick,
            onVolumeChange = onVolumeChange,
            onPlayZaraZaraClick = onPlayZaraZaraClick
        )
    }

    if (showDevicePicker) {
        DeviceSelectionDialog(
            devices = bluetoothState.pairedDevices,
            selectedMac = bluetoothState.selectedDevice?.macAddress,
            onSelect = { mac ->
                onDeviceSelected(mac)
                showDevicePicker = false
            },
            onSetAlias = { mac, alias ->
                onSetDeviceAlias(mac, alias)
            },
            onDismiss = { showDevicePicker = false }
        )
    }

    if (showOverlayPermissionDialog) {
        AlertDialog(
            onDismissRequest = { showOverlayPermissionDialog = false },
            title = {
                Text(
                    text = "Overlay Permission Required",
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            },
            text = {
                Text(
                    text = "Animus needs permission to appear over other apps so the floating controller can remain visible while you use YouTube Music or other apps.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontSize = 14.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showOverlayPermissionDialog = false
                        val port = com.animus.smartroom.overlay.permission.AndroidOverlayPermissionPort(context)
                        context.startActivity(port.createPermissionIntent())
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
                ) {
                    Text("ALLOW OVER OTHER APPS")
                }
            },
            dismissButton = {
                TextButton(onClick = { showOverlayPermissionDialog = false }) {
                    Text("CANCEL")
                }
            }
        )
    }

    if (showBrainSettings) {
        BrainSettingsDialog(
            currentProvider = activeBrainProvider,
            maskedApiKey = maskedApiKey,
            onSelectProvider = { type -> onSetBrainProvider(type) },
            onSaveApiKey = { key -> onSaveGeminiApiKey(key) },
            onTestConnection = onTestGeminiConnection,
            onDismiss = { showBrainSettings = false }
        )
    }

    if (showDeviceDrawer) {
        com.animus.smartroom.ui.device.DeviceDrawerSheet(
            devices = registeredDevices,
            acState = tuyaAcState,
            bluetoothState = bluetoothState,
            onDismiss = { showDeviceDrawer = false },
            onOpenAcRemote = { showAcRemote = true },
            onOpenBluetoothManager = {
                context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
            }
        )
    }

    if (showAcRemote) {
        com.animus.smartroom.ui.device.AirConditionerRemoteSheet(
            state = tuyaAcState,
            isOperating = isAcOperating,
            activeTimer = activeAcTimer,
            onDismiss = { showAcRemote = false },
            onPowerToggle = onSetAcPower,
            onTemperatureChange = onSetAcTemperature,
            onModeSelect = onSetAcMode,
            onFanSpeedSelect = onSetAcFanSpeed,
            onScheduleTimer = onScheduleAcTimer,
            onCancelTimer = onCancelAcTimer
        )
    }

    if (showDiagnosticLogs) {
        com.animus.smartroom.ui.diagnostics.DiagnosticLogSheet(
            events = diagnosticEvents,
            onDismiss = { showDiagnosticLogs = false },
            onClear = onClearDiagnostics
        )
    }
}

@Composable
fun AskAnimusCard(
    aiState: AiCommandUiState,
    voiceState: VoiceInputState,
    onStartVoiceListening: () -> Unit,
    onStopVoiceListening: () -> Unit,
    onCancelVoiceListening: () -> Unit,
    onOpenBrainSettings: () -> Unit,
    onExecuteCommand: (String) -> Unit
) {
    val context = LocalContext.current
    var showTextInput by remember { mutableStateOf(false) }
    var textInput by remember { mutableStateOf("") }
    val suggestions = listOf("Play Zara Zara", "Volume 40", "Pause", "Next")

    val micPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (isGranted) {
            onStartVoiceListening()
        }
    }

    val isListening = voiceState is VoiceInputState.Listening
    val isRecognizing = voiceState is VoiceInputState.Recognizing

    // Pulsing animation for listening state
    val infiniteTransition = rememberInfiniteTransition(label = "micPulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = if (isListening) 1.15f else 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseScale"
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = "AI",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Ask Animus",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "Speak naturally to control your room",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                    border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.3f)),
                    modifier = Modifier
                        .padding(start = 8.dp)
                        .clickable { onOpenBrainSettings() }
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Icon(
                            imageVector = if (aiState.activeProviderName.contains("Gemini")) Icons.Default.Cloud else Icons.Default.Memory,
                            contentDescription = "Brain Provider",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(13.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Brain: ${aiState.activeProviderName}",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // PRIMARY HERO INTERACTION: Voice Section
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Large Microphone Button with animated ripple/pulse
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier.padding(vertical = 6.dp)
                ) {
                    if (isListening) {
                        // Outer pulse ring
                        Box(
                            modifier = Modifier
                                .size(96.dp)
                                .scale(pulseScale)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.2f))
                        )
                    }

                    Surface(
                        shape = CircleShape,
                        color = if (isListening) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.primary.copy(alpha = 0.12f),
                        border = if (!isListening) BorderStroke(1.5.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.4f)) else null,
                        modifier = Modifier
                            .size(76.dp)
                            .clip(CircleShape)
                            .clickable {
                                val hasMicPermission = ContextCompat.checkSelfPermission(
                                    context,
                                    Manifest.permission.RECORD_AUDIO
                                ) == PackageManager.PERMISSION_GRANTED

                                if (!hasMicPermission) {
                                    micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                                } else {
                                    if (isListening) {
                                        onStopVoiceListening()
                                    } else {
                                        onStartVoiceListening()
                                    }
                                }
                            }
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = if (isListening) Icons.Default.Mic else Icons.Default.MicNone,
                                contentDescription = if (isListening) "Stop Listening" else "Tap to Speak",
                                tint = if (isListening) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(36.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // Voice status label
                Text(
                    text = when (voiceState) {
                        is VoiceInputState.Idle -> "Tap to speak"
                        is VoiceInputState.Listening -> "Listening... Tap to stop"
                        is VoiceInputState.Recognizing -> if (voiceState.partialText.isNotBlank()) "Understanding: \"${voiceState.partialText}\"" else "Understanding..."
                        is VoiceInputState.Success -> "Heard: \"${voiceState.recognizedText}\""
                        is VoiceInputState.Error -> voiceState.message
                        is VoiceInputState.PermissionDenied -> "Microphone permission required"
                        is VoiceInputState.Unavailable -> "Speech recognition not available"
                    },
                    fontSize = 14.sp,
                    fontWeight = if (isListening || isRecognizing) FontWeight.Bold else FontWeight.Medium,
                    color = when (voiceState) {
                        is VoiceInputState.Listening -> MaterialTheme.colorScheme.primary
                        is VoiceInputState.Recognizing -> MaterialTheme.colorScheme.primary
                        is VoiceInputState.Error,
                        is VoiceInputState.PermissionDenied -> MaterialTheme.colorScheme.error
                        else -> MaterialTheme.colorScheme.onSurface
                    },
                    textAlign = TextAlign.Center,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(horizontal = 16.dp)
                )

                if (voiceState is VoiceInputState.Idle) {
                    Text(
                        text = "e.g. \"Play Zara Zara\", \"Play Ramta Jogi\", \"Volume 40\"",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }

                if (voiceState is VoiceInputState.PermissionDenied) {
                    Spacer(modifier = Modifier.height(6.dp))
                    TextButton(
                        onClick = { micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO) },
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        Text("Grant Permission", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // SECONDARY ACCESSIBILITY INTERACTION: "Type instead" toggle
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center
            ) {
                TextButton(
                    onClick = { showTextInput = !showTextInput },
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                ) {
                    Icon(
                        imageVector = if (showTextInput) Icons.Default.KeyboardHide else Icons.Default.Keyboard,
                        contentDescription = "Toggle Keyboard",
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = if (showTextInput) "Hide keyboard" else "Type instead",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }

            // Collapsible Text Input Drawer & Suggestion Chips
            AnimatedVisibility(
                visible = showTextInput,
                enter = fadeIn() + expandVertically(),
                exit = fadeOut() + shrinkVertically()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 6.dp)
                ) {
                    // Text Input Row with Submit
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = textInput,
                            onValueChange = { textInput = it },
                            placeholder = {
                                Text(
                                    text = "Type command (e.g. Volume 40)...",
                                    fontSize = 13.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
                                )
                            },
                            singleLine = true,
                            shape = RoundedCornerShape(14.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = MaterialTheme.colorScheme.primary,
                                unfocusedBorderColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.4f),
                                focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f),
                                unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f)
                            ),
                            modifier = Modifier.weight(1f)
                        )

                        Spacer(modifier = Modifier.width(10.dp))

                        IconButton(
                            onClick = {
                                if (textInput.isNotBlank()) {
                                    onExecuteCommand(textInput)
                                    textInput = ""
                                }
                            },
                            modifier = Modifier
                                .size(52.dp)
                                .clip(RoundedCornerShape(14.dp))
                                .background(MaterialTheme.colorScheme.primary)
                        ) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowForward,
                                contentDescription = "Submit Command",
                                tint = MaterialTheme.colorScheme.onPrimary,
                                modifier = Modifier.size(22.dp)
                            )
                        }
                    }

                    // Quick suggestion chips
                    Spacer(modifier = Modifier.height(10.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        suggestions.forEach { suggestion ->
                            Surface(
                                shape = RoundedCornerShape(10.dp),
                                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
                                modifier = Modifier.clickable {
                                    onExecuteCommand(suggestion)
                                }
                            ) {
                                Text(
                                    text = suggestion,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Medium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
                                )
                            }
                        }
                    }
                }
            }

            // AI Execution Result Banner
            AnimatedVisibility(
                visible = aiState.lastResultMessage != null || aiState.isProcessing,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (aiState.isSuccess == true) AccentGreen.copy(alpha = 0.12f)
                    else if (aiState.isSuccess == false) Color(0xFFEF4444).copy(alpha = 0.12f)
                    else MaterialTheme.colorScheme.surfaceVariant,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 14.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = when {
                                aiState.isProcessing -> Icons.Default.HourglassEmpty
                                aiState.isSuccess == true -> Icons.Default.CheckCircle
                                else -> Icons.Default.Info
                            },
                            contentDescription = "Status",
                            tint = when {
                                aiState.isSuccess == true -> AccentGreen
                                aiState.isSuccess == false -> Color(0xFFEF4444)
                                else -> MaterialTheme.colorScheme.primary
                            },
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = if (aiState.isProcessing) "Processing command with ${aiState.activeProviderName}..." else "Animus: ${aiState.lastResultMessage ?: ""}",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = when {
                                aiState.isSuccess == true -> AccentGreen
                                aiState.isSuccess == false -> Color(0xFFEF4444)
                                else -> MaterialTheme.colorScheme.onSurface
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun BrainSettingsDialog(
    currentProvider: com.animus.smartroom.brain.model.BrainProviderType,
    maskedApiKey: String?,
    onSelectProvider: (com.animus.smartroom.brain.model.BrainProviderType) -> Unit,
    onSaveApiKey: (String?) -> Unit,
    onTestConnection: (String?, (Boolean, String) -> Unit) -> Unit,
    onDismiss: () -> Unit
) {
    var apiKeyText by remember { mutableStateOf("") }
    var isTestingConnection by remember { mutableStateOf(false) }
    var testResultBanner by remember { mutableStateOf<Pair<Boolean, String>?>(null) }
    var showKeyText by remember { mutableStateOf(false) }

    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(22.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 6.dp)
        ) {
            Column(
                modifier = Modifier
                    .padding(20.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Animus Brain Engine",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Provider Option 1: Local
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (currentProvider == com.animus.smartroom.brain.model.BrainProviderType.LOCAL)
                        MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
                    else MaterialTheme.colorScheme.surfaceVariant,
                    border = if (currentProvider == com.animus.smartroom.brain.model.BrainProviderType.LOCAL)
                        BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelectProvider(com.animus.smartroom.brain.model.BrainProviderType.LOCAL) }
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = currentProvider == com.animus.smartroom.brain.model.BrainProviderType.LOCAL,
                            onClick = { onSelectProvider(com.animus.smartroom.brain.model.BrainProviderType.LOCAL) }
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "Local — Offline",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "Fast, deterministic, 100% offline control.",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // Provider Option 2: Gemini
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (currentProvider == com.animus.smartroom.brain.model.BrainProviderType.GEMINI)
                        MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
                    else MaterialTheme.colorScheme.surfaceVariant,
                    border = if (currentProvider == com.animus.smartroom.brain.model.BrainProviderType.GEMINI)
                        BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelectProvider(com.animus.smartroom.brain.model.BrainProviderType.GEMINI) }
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = currentProvider == com.animus.smartroom.brain.model.BrainProviderType.GEMINI,
                            onClick = { onSelectProvider(com.animus.smartroom.brain.model.BrainProviderType.GEMINI) }
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "Gemini — Cloud",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "AI Natural Language & Music Search Grounding.",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }

                // Gemini API Configuration Area
                AnimatedVisibility(
                    visible = currentProvider == com.animus.smartroom.brain.model.BrainProviderType.GEMINI
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 16.dp)
                    ) {
                        Text(
                            text = "Gemini API Key",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurface
                        )

                        if (!maskedApiKey.isNullOrBlank()) {
                            Text(
                                text = "Current Key: $maskedApiKey",
                                fontSize = 12.sp,
                                color = AccentGreen,
                                modifier = Modifier.padding(vertical = 2.dp)
                            )
                        }

                        Spacer(modifier = Modifier.height(6.dp))

                        OutlinedTextField(
                            value = apiKeyText,
                            onValueChange = { apiKeyText = it },
                            label = { Text("Enter API Key (AIza...)") },
                            placeholder = { Text("Paste Google AI Studio API key") },
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp),
                            trailingIcon = {
                                IconButton(onClick = { showKeyText = !showKeyText }) {
                                    Icon(
                                        imageVector = if (showKeyText) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                        contentDescription = "Toggle Visibility",
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            },
                            modifier = Modifier.fillMaxWidth()
                        )

                        Text(
                            text = "Stored securely on device. Never logged or shared.",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 4.dp)
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            OutlinedButton(
                                onClick = {
                                    isTestingConnection = true
                                    testResultBanner = null
                                    onTestConnection(apiKeyText.ifBlank { null }) { success, message ->
                                        isTestingConnection = false
                                        testResultBanner = Pair(success, message)
                                    }
                                },
                                enabled = !isTestingConnection,
                                shape = RoundedCornerShape(10.dp),
                                modifier = Modifier.weight(1f)
                            ) {
                                if (isTestingConnection) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(14.dp),
                                        strokeWidth = 2.dp
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                }
                                Text("Test Connection", fontSize = 12.sp)
                            }

                            Button(
                                onClick = {
                                    if (apiKeyText.isNotBlank()) {
                                        onSaveApiKey(apiKeyText.trim())
                                        apiKeyText = ""
                                        testResultBanner = Pair(true, "API key saved!")
                                    }
                                },
                                enabled = apiKeyText.isNotBlank(),
                                shape = RoundedCornerShape(10.dp),
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("Save Key", fontSize = 12.sp)
                            }
                        }

                        if (!maskedApiKey.isNullOrBlank()) {
                            TextButton(
                                onClick = {
                                    onSaveApiKey(null)
                                    testResultBanner = Pair(false, "API key cleared.")
                                },
                                modifier = Modifier.align(Alignment.CenterHorizontally)
                            ) {
                                Text("Clear API Key", color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
                            }
                        }

                        testResultBanner?.let { (success, message) ->
                            Surface(
                                shape = RoundedCornerShape(10.dp),
                                color = if (success) AccentGreen.copy(alpha = 0.12f) else MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.4f),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(top = 8.dp)
                            ) {
                                Text(
                                    text = message,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium,
                                    color = if (success) AccentGreen else MaterialTheme.colorScheme.error,
                                    modifier = Modifier.padding(10.dp)
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(18.dp))

                Button(
                    onClick = onDismiss,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("Done")
                }
            }
        }
    }
}

@Composable
fun AudioDeviceCard(
    uiState: BluetoothUiState,
    onActionClick: () -> Unit,
    onSwitchDeviceClick: () -> Unit,
    onRequestPermission: () -> Unit
) {
    val context = LocalContext.current
    val connectionState = uiState.connectionState
    val isConnected = connectionState is BluetoothDeviceState.Connected
    val isConnecting = connectionState is BluetoothDeviceState.Connecting
    val isDisconnecting = connectionState is BluetoothDeviceState.Disconnecting
    val isError = connectionState is BluetoothDeviceState.Error
    val selectedDevice = uiState.selectedDevice

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(
                                if (isConnected) AccentGreen.copy(alpha = 0.15f)
                                else MaterialTheme.colorScheme.surfaceVariant
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = if (isConnected) Icons.Default.BluetoothConnected else Icons.Default.Bluetooth,
                            contentDescription = "Bluetooth",
                            tint = if (isConnected) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Audio Output",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = if (isConnected) "Connected & Output Active" else "Ready to Connect",
                            fontSize = 12.sp,
                            color = if (isConnected) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = when {
                        isConnected -> AccentGreen.copy(alpha = 0.15f)
                        isConnecting || isDisconnecting -> MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                        isError -> MaterialTheme.colorScheme.error.copy(alpha = 0.15f)
                        else -> MaterialTheme.colorScheme.surfaceVariant
                    }
                ) {
                    Text(
                        text = when (connectionState) {
                            is BluetoothDeviceState.Connected -> "Connected"
                            is BluetoothDeviceState.Connecting -> "Connecting..."
                            is BluetoothDeviceState.Disconnecting -> "Disconnecting..."
                            is BluetoothDeviceState.Disconnected -> "Disconnected"
                            is BluetoothDeviceState.Error -> "Error"
                        },
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = when {
                            isConnected -> AccentGreen
                            isConnecting || isDisconnecting -> MaterialTheme.colorScheme.primary
                            isError -> MaterialTheme.colorScheme.error
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        },
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Surface(
                shape = RoundedCornerShape(14.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSwitchDeviceClick() }
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Speaker,
                            contentDescription = "Speaker Icon",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = selectedDevice?.displayName ?: "No Device Selected",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            if (selectedDevice?.alias != null) {
                                Text(
                                    text = "Hardware: ${selectedDevice.name}",
                                    fontSize = 11.sp,
                                    color = MaterialTheme.colorScheme.primary,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                            Text(
                                text = selectedDevice?.macAddress ?: "Tap to select paired device",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "Switch",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary
                        )
                        Icon(
                            imageVector = Icons.Default.ChevronRight,
                            contentDescription = "Switch Device",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            if (isError) {
                val errorMsg = (connectionState as BluetoothDeviceState.Error).message
                Spacer(modifier = Modifier.height(10.dp))
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.ErrorOutline,
                            contentDescription = "Error",
                            tint = MaterialTheme.colorScheme.error,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = errorMsg,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Button(
                onClick = onActionClick,
                enabled = !isConnecting && !isDisconnecting && selectedDevice != null,
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isConnected) Color(0xFFEF4444) else MaterialTheme.colorScheme.primary,
                    disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant
                ),
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                if (isConnecting || isDisconnecting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (isConnecting) "Connecting..." else "Disconnecting...",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                } else {
                    Icon(
                        imageVector = if (isConnected) Icons.Default.BluetoothDisabled else Icons.Default.BluetoothConnected,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (isConnected) "Disconnect Device" else "Connect Device",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }
    }
}

@Composable
fun MusicControlCard(
    musicState: MusicUiState,
    onPlayPauseClick: () -> Unit,
    onNextClick: () -> Unit,
    onPreviousClick: () -> Unit,
    onVolumeChange: (Float) -> Unit,
    onPlayZaraZaraClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(
                                if (musicState.isOutputConnected) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
                                else MaterialTheme.colorScheme.surfaceVariant
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.MusicNote,
                            contentDescription = "Music",
                            tint = if (musicState.isOutputConnected) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Music Controller",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "Provider: ${musicState.activeProviderName}",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = if (musicState.isOutputConnected) AccentGreen.copy(alpha = 0.15f)
                    else MaterialTheme.colorScheme.surfaceVariant
                ) {
                    Text(
                        text = if (musicState.isOutputConnected) "Output Active" else "Output Muted",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = if (musicState.isOutputConnected) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Surface(
                shape = RoundedCornerShape(14.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(
                            imageVector = if (musicState.isOutputConnected) Icons.Default.VolumeUp else Icons.Default.VolumeOff,
                            contentDescription = "Output Route",
                            tint = if (musicState.isOutputConnected) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(22.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = "Routing Audio To",
                                fontSize = 11.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = musicState.activeOutputDeviceName,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (musicState.isOutputConnected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }

                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = if (musicState.isOutputConnected) AccentGreen.copy(alpha = 0.2f) else MaterialTheme.colorScheme.surfaceVariant
                    ) {
                        Text(
                            text = if (musicState.isOutputConnected) "ROUTED" else "DISCONNECTED",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (musicState.isOutputConnected) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp)
                        )
                    }
                }
            }

            if (musicState.userNotice != null) {
                Spacer(modifier = Modifier.height(10.dp))
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = if (musicState.isOutputConnected) MaterialTheme.colorScheme.primary.copy(alpha = 0.1f)
                    else MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = musicState.userNotice,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        color = if (musicState.isOutputConnected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Column(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Room Volume",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = "${(musicState.volumePercent * 100).toInt()}%",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }

                Slider(
                    value = musicState.volumePercent,
                    onValueChange = onVolumeChange,
                    valueRange = 0f..1f,
                    colors = SliderDefaults.colors(
                        thumbColor = MaterialTheme.colorScheme.primary,
                        activeTrackColor = MaterialTheme.colorScheme.primary,
                        inactiveTrackColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                    modifier = Modifier.fillMaxWidth()
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                IconButton(
                    onClick = onPreviousClick,
                    modifier = Modifier
                        .size(48.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Icon(
                        imageVector = Icons.Default.SkipPrevious,
                        contentDescription = "Previous",
                        tint = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.size(24.dp)
                    )
                }

                IconButton(
                    onClick = onPlayPauseClick,
                    modifier = Modifier
                        .size(60.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary)
                ) {
                    Icon(
                        imageVector = if (musicState.playbackStatus == PlaybackStatus.PLAYING) Icons.Default.Pause else Icons.Default.PlayArrow,
                        contentDescription = "Play/Pause",
                        tint = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier.size(32.dp)
                    )
                }

                IconButton(
                    onClick = onNextClick,
                    modifier = Modifier
                        .size(48.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Icon(
                        imageVector = Icons.Default.SkipNext,
                        contentDescription = "Next",
                        tint = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.size(24.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            OutlinedButton(
                onClick = onPlayZaraZaraClick,
                shape = RoundedCornerShape(12.dp),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.primary),
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(12.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.PlayArrow,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Play Zara Zara (Verified Direct)",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }
    }
}

@Composable
fun DeviceSelectionDialog(
    devices: List<BluetoothAudioDevice>,
    selectedMac: String?,
    onSelect: (String) -> Unit,
    onSetAlias: (String, String?) -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    var deviceForAliasEdit by remember { mutableStateOf<BluetoothAudioDevice?>(null) }

    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(22.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 6.dp)
        ) {
            Column(
                modifier = Modifier.padding(20.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Paired Audio Devices",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                if (devices.isEmpty()) {
                    Text(
                        text = "No paired Bluetooth audio devices found.",
                        fontSize = 14.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(vertical = 12.dp)
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 300.dp)
                    ) {
                        items(devices) { device ->
                            val isSelected = device.macAddress.equals(selectedMac, ignoreCase = true)

                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = if (isSelected) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else MaterialTheme.colorScheme.surfaceVariant,
                                border = if (isSelected) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                                    .clickable { onSelect(device.macAddress) }
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        modifier = Modifier.weight(1f)
                                    ) {
                                        Icon(
                                            imageVector = if (device.isConnected) Icons.Default.BluetoothConnected else Icons.Default.Speaker,
                                            contentDescription = "Device",
                                            tint = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                            modifier = Modifier.size(22.dp)
                                        )
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = device.displayName,
                                                fontSize = 15.sp,
                                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                                color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                            Text(
                                                text = if (device.alias != null) "${device.name} • ${device.macAddress}" else device.macAddress,
                                                fontSize = 11.sp,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                        }
                                    }

                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        IconButton(
                                            onClick = { deviceForAliasEdit = device },
                                            modifier = Modifier.size(32.dp)
                                        ) {
                                            Icon(
                                                imageVector = Icons.Default.Edit,
                                                contentDescription = "Edit Alias",
                                                tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.8f),
                                                modifier = Modifier.size(16.dp)
                                            )
                                        }

                                        if (device.isConnected) {
                                            Surface(
                                                shape = RoundedCornerShape(10.dp),
                                                color = AccentGreen.copy(alpha = 0.15f),
                                                modifier = Modifier.padding(start = 4.dp)
                                            ) {
                                                Text(
                                                    text = "Connected",
                                                    fontSize = 10.sp,
                                                    fontWeight = FontWeight.Medium,
                                                    color = AccentGreen,
                                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                                                )
                                            }
                                        } else if (isSelected) {
                                            Icon(
                                                imageVector = Icons.Default.Check,
                                                contentDescription = "Selected",
                                                tint = MaterialTheme.colorScheme.primary,
                                                modifier = Modifier
                                                    .padding(start = 4.dp)
                                                    .size(18.dp)
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                OutlinedButton(
                    onClick = {
                        onDismiss()
                        context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    },
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth(),
                    contentPadding = PaddingValues(10.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = "Pair New",
                        modifier = Modifier.size(16.dp),
                        tint = MaterialTheme.colorScheme.primary
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Pair New Device in Settings", fontSize = 13.sp, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
    }

    deviceForAliasEdit?.let { targetDevice ->
        AliasEditDialog(
            device = targetDevice,
            onSave = { alias ->
                onSetAlias(targetDevice.macAddress, alias)
            },
            onDismiss = { deviceForAliasEdit = null }
        )
    }
}

@Composable
fun AliasEditDialog(
    device: BluetoothAudioDevice,
    onSave: (String?) -> Unit,
    onDismiss: () -> Unit
) {
    var aliasText by remember { mutableStateOf(device.alias ?: "") }

    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(22.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            elevation = CardDefaults.cardElevation(defaultElevation = 6.dp)
        ) {
            Column(
                modifier = Modifier.padding(20.dp)
            ) {
                Text(
                    text = "Device Alias",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "${device.name} (${device.macAddress})",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Spacer(modifier = Modifier.height(16.dp))

                OutlinedTextField(
                    value = aliasText,
                    onValueChange = { aliasText = it },
                    label = { Text("Custom Name / Alias") },
                    placeholder = { Text("e.g. Bedroom Speaker, TV Soundbar") },
                    singleLine = true,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(modifier = Modifier.height(20.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (!device.alias.isNullOrBlank()) {
                        TextButton(
                            onClick = {
                                onSave(null)
                                onDismiss()
                            }
                        ) {
                            Text("Clear Alias", color = MaterialTheme.colorScheme.error)
                        }
                        Spacer(modifier = Modifier.weight(1f))
                    }
                    TextButton(onClick = onDismiss) {
                        Text("Cancel")
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = {
                            onSave(aliasText.trim().ifEmpty { null })
                            onDismiss()
                        },
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Text("Save")
                    }
                }
            }
        }
    }
}

@Composable
fun ActiveRoutineCard(
    routine: com.animus.smartroom.routine.model.RoutineState,
    onCancelClick: () -> Unit,
    onStopAlarm: () -> Unit = {}
) {
    var currentTime by remember { mutableStateOf(System.currentTimeMillis()) }

    LaunchedEffect(routine.scheduledWakeTime, routine.status) {
        while (true) {
            currentTime = System.currentTimeMillis()
            kotlinx.coroutines.delay(1000L)
        }
    }

    val remainingMillis = ((routine.scheduledWakeTime ?: currentTime) - currentTime).coerceAtLeast(0L)
    val isRinging = routine.isAlarming || (routine.status == com.animus.smartroom.routine.model.RoutineStatus.ACTIVE && routine.scheduledWakeTime != null && currentTime >= routine.scheduledWakeTime)

    if (isRinging) {
        // Unmistakable urgent alarm card
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = Color(0xFF7F1D1D)
            ),
            shape = RoundedCornerShape(20.dp),
            border = BorderStroke(2.dp, Color(0xFFEF4444))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "🔔",
                    fontSize = 38.sp
                )
                Spacer(modifier = Modifier.height(10.dp))
                Text(
                    text = "WAKE UP, BUDDY",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.2.sp,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Alarm is ringing",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    color = Color(0xFFFECACA)
                )

                Spacer(modifier = Modifier.height(20.dp))

                Button(
                    onClick = onStopAlarm,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFFDC2626),
                        contentColor = Color.White
                    ),
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    elevation = ButtonDefaults.buttonElevation(defaultElevation = 6.dp)
                ) {
                    Text(
                        text = "STOP ALARM",
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.5.sp
                    )
                }
            }
        }
    } else {
        // Active countdown card
        val remainingSeconds = (remainingMillis / 1000L) % 60
        val remainingMinutes = (remainingMillis / (1000L * 60)) % 60
        val remainingHours = (remainingMillis / (1000L * 3600))
        val countdownText = if (remainingHours > 0) {
            String.format(java.util.Locale.getDefault(), "%d:%02d:%02d", remainingHours, remainingMinutes, remainingSeconds)
        } else {
            String.format(java.util.Locale.getDefault(), "%02d:%02d", remainingMinutes, remainingSeconds)
        }

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = Color(0xFF1E293B)
            ),
            shape = RoundedCornerShape(18.dp),
            border = BorderStroke(1.dp, Color(0xFF38BDF8).copy(alpha = 0.4f))
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(18.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Text(
                        text = "😴",
                        fontSize = 26.sp
                    )
                    Spacer(modifier = Modifier.width(14.dp))
                    Column {
                        Text(
                            text = "Sleep Mode",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color.White
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = countdownText,
                                fontSize = 22.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color(0xFF38BDF8)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "remaining",
                                fontSize = 12.sp,
                                color = Color(0xFF94A3B8)
                            )
                        }
                        val wakeText = routine.scheduledWakeTime?.let {
                            val sdf = java.text.SimpleDateFormat("h:mm a", java.util.Locale.getDefault())
                            "Wake-up: ${sdf.format(java.util.Date(it))}"
                        } ?: "Status: Active"
                        Text(
                            text = wakeText,
                            fontSize = 12.sp,
                            color = Color(0xFF64748B)
                        )
                    }
                }

                Button(
                    onClick = onCancelClick,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFFEF4444).copy(alpha = 0.2f),
                        contentColor = Color(0xFFF87171)
                    ),
                    shape = RoundedCornerShape(10.dp),
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp)
                ) {
                    Text(text = "Cancel", fontSize = 13.sp, fontWeight = FontWeight.Medium)
                }
            }
        }
    }
}
