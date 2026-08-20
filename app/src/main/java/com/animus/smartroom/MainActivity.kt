package com.animus.smartroom

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.model.PlaybackStatus
import com.animus.smartroom.ui.theme.AccentGreen
import com.animus.smartroom.ui.theme.AnimusSmartRoomTheme

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AnimusSmartRoomTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val bluetoothUiState by viewModel.bluetoothUiState.collectAsStateWithLifecycle()
                    val musicUiState by viewModel.musicUiState.collectAsStateWithLifecycle()
                    val aiCommandState by viewModel.aiCommandState.collectAsStateWithLifecycle()

                    HomeScreen(
                        bluetoothState = bluetoothUiState,
                        musicState = musicUiState,
                        aiState = aiCommandState,
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
                        onSetDeviceAlias = { mac, alias -> viewModel.onSetDeviceAlias(mac, alias) }
                    )
                }
            }
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
    onSetDeviceAlias: (String, String?) -> Unit
) {
    val context = LocalContext.current
    var showDevicePicker by remember { mutableStateOf(false) }

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
                    fontSize = 25.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "Room Audio & Automation Center",
                    fontSize = 13.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Box(
                modifier = Modifier
                    .size(44.dp)
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
                    modifier = Modifier.size(22.dp)
                )
            }
        }

        // 1. AI Command Layer: "Ask Animus"
        AskAnimusCard(
            aiState = aiState,
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
}

@Composable
fun AskAnimusCard(
    aiState: AiCommandUiState,
    onExecuteCommand: (String) -> Unit
) {
    var textInput by remember { mutableStateOf("") }
    val suggestions = listOf("Play Zara Zara", "Volume 40", "Pause", "Next")

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
                verticalAlignment = Alignment.CenterVertically
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
                        text = "Natural language room & music control",
                        fontSize = 12.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

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
                            text = "e.g. Play Zara Zara, Volume 40...",
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
            Spacer(modifier = Modifier.height(12.dp))
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

            // AI Execution Result Banner
            AnimatedVisibility(
                visible = aiState.lastResultMessage != null || aiState.isProcessing,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Column(
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
                            text = if (aiState.isProcessing) "Processing command..." else "Animus: ${aiState.lastResultMessage ?: ""}",
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

    val cardBorder = if (isConnected) {
        BorderStroke(1.5.dp, MaterialTheme.colorScheme.primary)
    } else {
        BorderStroke(1.dp, MaterialTheme.colorScheme.outline.copy(alpha = 0.5f))
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(22.dp),
        border = cardBorder,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            // Top Row: Device icon, name, MAC, and Switch button
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    modifier = Modifier.weight(1f),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(RoundedCornerShape(14.dp))
                            .background(
                                if (isConnected) MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                                else MaterialTheme.colorScheme.surfaceVariant
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = when {
                                isConnected -> Icons.Default.BluetoothConnected
                                isConnecting || isDisconnecting -> Icons.Default.BluetoothAudio
                                else -> Icons.Default.Speaker
                            },
                            contentDescription = "Device Icon",
                            tint = if (isConnected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(24.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(14.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = selectedDevice?.displayName ?: "No Device Selected",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        if (selectedDevice?.alias != null) {
                            Text(
                                text = selectedDevice.name,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Medium,
                                color = MaterialTheme.colorScheme.primary,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        Text(
                            text = if (selectedDevice != null) "MAC: ${selectedDevice.macAddress}" else "Tap Switch to choose",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                Spacer(modifier = Modifier.width(8.dp))

                // Switch Device Pill Button
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    modifier = Modifier.clickable { onSwitchDeviceClick() }
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.SwapHoriz,
                            contentDescription = "Switch Device",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Switch",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), thickness = 0.8.dp)
            Spacer(modifier = Modifier.height(16.dp))

            // Bottom Row: Status text + Connect/Disconnect Button
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Connection Status",
                        fontSize = 11.sp,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(
                                    when {
                                        isConnected -> AccentGreen
                                        isConnecting || isDisconnecting -> Color(0xFFF59E0B)
                                        isError -> Color(0xFFEF4444)
                                        else -> Color(0xFF94A3B8)
                                    }
                                )
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = when (connectionState) {
                                is BluetoothDeviceState.Connected -> "Connected"
                                is BluetoothDeviceState.Connecting -> "Connecting..."
                                is BluetoothDeviceState.Disconnecting -> "Disconnecting..."
                                is BluetoothDeviceState.Disconnected -> if (selectedDevice != null) "Disconnected" else "No Device"
                                is BluetoothDeviceState.Error -> "Connection Issue"
                            },
                            fontSize = 14.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = when {
                                isConnected -> AccentGreen
                                isConnecting || isDisconnecting -> Color(0xFFF59E0B)
                                isError -> Color(0xFFEF4444)
                                else -> MaterialTheme.colorScheme.onSurfaceVariant
                            }
                        )
                    }
                }

                // Connect / Disconnect button
                Button(
                    onClick = onActionClick,
                    enabled = !isConnecting && !isDisconnecting && selectedDevice != null,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isConnected) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.primary,
                        contentColor = if (isConnected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onPrimary
                    ),
                    contentPadding = PaddingValues(horizontal = 18.dp, vertical = 8.dp)
                ) {
                    if (isConnecting) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(text = "Connecting", fontSize = 13.sp)
                    } else if (isDisconnecting) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = MaterialTheme.colorScheme.onSurface,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(text = "Disconnecting", fontSize = 13.sp)
                    } else {
                        Text(
                            text = if (isConnected) "Disconnect" else "Connect",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            // User Notice / Permission / Pair Warning Banner
            AnimatedVisibility(
                visible = uiState.userNotice != null || (!uiState.hasRequiredPermissions && selectedDevice == null),
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 14.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f))
                        .padding(12.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Notice",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = uiState.userNotice
                                ?: if (!uiState.hasRequiredPermissions) "Bluetooth permission is required."
                                else "Please pair your audio device in settings.",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }

                    if (!uiState.hasRequiredPermissions) {
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = onRequestPermission,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth(),
                            contentPadding = PaddingValues(6.dp)
                        ) {
                            Text("Grant Bluetooth Permissions", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                        }
                    } else if (uiState.pairedDevices.isEmpty()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = {
                                context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                            },
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth(),
                            contentPadding = PaddingValues(6.dp)
                        ) {
                            Text("Open Bluetooth Settings to Pair", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                        }
                    }
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
    val isPlaying = musicState.playbackStatus == PlaybackStatus.PLAYING

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
            // 1. Header: Title + Active Audio Output Routing Indicator
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
                            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.MusicNote,
                            contentDescription = "Music",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "Music Control",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        // Output device indicator
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = "Output: ",
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Box(
                                modifier = Modifier
                                    .size(7.dp)
                                    .clip(CircleShape)
                                    .background(if (musicState.isOutputConnected) AccentGreen else Color(0xFF94A3B8))
                            )
                            Spacer(modifier = Modifier.width(5.dp))
                            Text(
                                text = if (musicState.isOutputConnected) {
                                    musicState.activeOutputDeviceName
                                } else {
                                    "${musicState.activeOutputDeviceName} (Disconnected)"
                                },
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (musicState.isOutputConnected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }

                // Playback Status Tag
                val statusText = when (musicState.playbackStatus) {
                    PlaybackStatus.PLAYING -> "Playing"
                    PlaybackStatus.PAUSED -> "Paused"
                    PlaybackStatus.SEARCH_OPENED -> "Starting"
                    PlaybackStatus.ACTION_REQUIRED -> "Action Required"
                    PlaybackStatus.BUFFERING -> "Buffering"
                    PlaybackStatus.IDLE -> "Ready"
                }
                val statusColor = when (musicState.playbackStatus) {
                    PlaybackStatus.PLAYING -> AccentGreen
                    PlaybackStatus.PAUSED -> Color(0xFFF59E0B)
                    PlaybackStatus.SEARCH_OPENED -> MaterialTheme.colorScheme.primary
                    PlaybackStatus.ACTION_REQUIRED -> Color(0xFFF59E0B)
                    PlaybackStatus.BUFFERING -> Color(0xFFF59E0B)
                    PlaybackStatus.IDLE -> MaterialTheme.colorScheme.onSurfaceVariant
                }

                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = statusColor.copy(alpha = 0.15f)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(statusColor)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = statusText,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium,
                            color = statusColor
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            // 2. Track info (if available)
            if (musicState.currentTrackTitle != null) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.GraphicEq,
                            contentDescription = "Track",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = musicState.currentTrackTitle,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            if (musicState.currentTrackArtist != null) {
                                Text(
                                    text = musicState.currentTrackArtist,
                                    fontSize = 11.sp,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
            }

            // 3. Media Transport Controls (Previous, Play/Pause, Next)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                // Previous Track
                IconButton(
                    onClick = onPreviousClick,
                    modifier = Modifier
                        .size(46.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Icon(
                        imageVector = Icons.Default.SkipPrevious,
                        contentDescription = "Previous Track",
                        tint = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.size(24.dp)
                    )
                }

                // Play / Pause Primary Button
                IconButton(
                    onClick = onPlayPauseClick,
                    modifier = Modifier
                        .size(60.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary)
                ) {
                    Icon(
                        imageVector = if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                        contentDescription = if (isPlaying) "Pause" else "Play",
                        tint = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier.size(32.dp)
                    )
                }

                // Next Track
                IconButton(
                    onClick = onNextClick,
                    modifier = Modifier
                        .size(46.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                ) {
                    Icon(
                        imageVector = Icons.Default.SkipNext,
                        contentDescription = "Next Track",
                        tint = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.size(24.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(18.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.3f), thickness = 0.8.dp)
            Spacer(modifier = Modifier.height(16.dp))

            // 4. Volume Control Section
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                @Suppress("DEPRECATION")
                val volumeIcon = when {
                    musicState.isMuted || musicState.volumePercent == 0f -> Icons.Default.VolumeOff
                    musicState.volumePercent < 0.4f -> Icons.Default.VolumeDown
                    else -> Icons.Default.VolumeUp
                }

                Icon(
                    imageVector = volumeIcon,
                    contentDescription = "Volume",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(22.dp)
                )

                Spacer(modifier = Modifier.width(10.dp))

                Slider(
                    value = musicState.volumePercent,
                    onValueChange = onVolumeChange,
                    modifier = Modifier.weight(1f),
                    colors = SliderDefaults.colors(
                        thumbColor = MaterialTheme.colorScheme.primary,
                        activeTrackColor = MaterialTheme.colorScheme.primary,
                        inactiveTrackColor = MaterialTheme.colorScheme.surfaceVariant
                    )
                )

                Spacer(modifier = Modifier.width(10.dp))

                Text(
                    text = "${(musicState.volumePercent * 100).toInt()}%",
                    fontSize = 13.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.width(36.dp)
                )
            }

            Spacer(modifier = Modifier.height(18.dp))

            // 5. Clean Primary Preset Button: "Play Zara Zara"
            Button(
                onClick = onPlayZaraZaraClick,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary
                ),
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(14.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.PlayArrow,
                    contentDescription = "Play Zara Zara",
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Play Zara Zara",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            // Notice / Bluetooth Gating Banner
            AnimatedVisibility(
                visible = musicState.userNotice != null,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.75f),
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Notice",
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = musicState.userNotice ?: "",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
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
