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
import com.animus.smartroom.ui.theme.AnimusSmartRoomTheme
import com.animus.smartroom.ui.theme.CardBackground
import com.animus.smartroom.ui.theme.PrimaryBlue
import com.animus.smartroom.ui.theme.SurfaceDark

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
                    val uiState by viewModel.bluetoothUiState.collectAsStateWithLifecycle()
                    HomeScreen(
                        uiState = uiState,
                        onConnectClick = { viewModel.onConnectClicked() },
                        onDisconnectClick = { viewModel.onDisconnectClicked() },
                        onDeviceSelected = { mac -> viewModel.onDeviceSelected(mac) },
                        onPermissionsResult = { granted -> viewModel.onPermissionsResult(granted) },
                        getRequiredPermissions = { viewModel.getRequiredPermissions() },
                        hasPermissions = { viewModel.hasPermissions() }
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
    uiState: BluetoothUiState,
    onConnectClick: () -> Unit,
    onDisconnectClick: () -> Unit,
    onDeviceSelected: (String) -> Unit,
    onPermissionsResult: (Boolean) -> Unit,
    getRequiredPermissions: () -> Array<String>,
    hasPermissions: () -> Boolean
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
        // App Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(bottom = 24.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(
                    text = "Animus Smart Room",
                    fontSize = 26.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
                Text(
                    text = "Room Audio & Automation Center",
                    fontSize = 13.sp,
                    color = Color(0xFF9E9E9E)
                )
            }

            Box(
                modifier = Modifier
                    .size(42.dp)
                    .clip(CircleShape)
                    .background(SurfaceDark)
                    .clickable {
                        context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                    },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.SettingsBluetooth,
                    contentDescription = "Bluetooth Settings",
                    tint = PrimaryBlue,
                    modifier = Modifier.size(22.dp)
                )
            }
        }

        // Bluetooth Audio Device Card
        AudioDeviceCard(
            uiState = uiState,
            onActionClick = {
                if (!hasPermissions()) {
                    permissionLauncher.launch(getRequiredPermissions())
                } else {
                    when (uiState.connectionState) {
                        is BluetoothDeviceState.Connected -> onDisconnectClick()
                        is BluetoothDeviceState.Disconnected,
                        is BluetoothDeviceState.Error -> onConnectClick()
                        is BluetoothDeviceState.Connecting -> { /* Disabled while connecting */ }
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

        // Music Section (UI Placeholder)
        MusicSection()
    }

    if (showDevicePicker) {
        DeviceSelectionDialog(
            devices = uiState.pairedDevices,
            selectedMac = uiState.selectedDevice?.macAddress,
            onSelect = { mac ->
                onDeviceSelected(mac)
                showDevicePicker = false
            },
            onDismiss = { showDevicePicker = false }
        )
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
    val isError = connectionState is BluetoothDeviceState.Error
    val selectedDevice = uiState.selectedDevice

    val cardBorder = if (isConnected) {
        BorderStroke(1.5.dp, PrimaryBlue)
    } else {
        BorderStroke(1.dp, Color(0xFF333333))
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        border = cardBorder,
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 6.dp)
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            // Header with Icon, Device info, and Switch button
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
                            .clip(RoundedCornerShape(12.dp))
                            .background(
                                if (isConnected) PrimaryBlue.copy(alpha = 0.18f) else Color(0xFF202020)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = when {
                                isConnected -> Icons.Default.BluetoothConnected
                                isConnecting -> Icons.Default.BluetoothAudio
                                else -> Icons.Default.Speaker
                            },
                            contentDescription = "Device Icon",
                            tint = if (isConnected) PrimaryBlue else Color(0xFFAAAAAA),
                            modifier = Modifier.size(26.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(14.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = selectedDevice?.name ?: "No Device Selected",
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = if (selectedDevice != null) "MAC: ${selectedDevice.macAddress}" else "Tap to choose device",
                            fontSize = 12.sp,
                            color = Color(0xFF888888),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                Spacer(modifier = Modifier.width(8.dp))

                // Switch Device button
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFF252525),
                    modifier = Modifier.clickable { onSwitchDeviceClick() }
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.SwapHoriz,
                            contentDescription = "Switch Device",
                            tint = PrimaryBlue,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Switch",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Medium,
                            color = PrimaryBlue
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(18.dp))
            HorizontalDivider(color = Color(0xFF383838), thickness = 0.8.dp)
            Spacer(modifier = Modifier.height(16.dp))

            // Real status details row
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Connection Status",
                        fontSize = 12.sp,
                        color = Color(0xFF888888)
                    )
                    Spacer(modifier = Modifier.height(2.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(
                                    when {
                                        isConnected -> Color(0xFF00E676)
                                        isConnecting -> Color(0xFFFFD600)
                                        isError -> Color(0xFFFF5252)
                                        else -> Color(0xFF757575)
                                    }
                                )
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = when (connectionState) {
                                is BluetoothDeviceState.Connected -> "Connected"
                                is BluetoothDeviceState.Connecting -> "Connecting..."
                                is BluetoothDeviceState.Disconnected -> if (selectedDevice != null) "Disconnected" else "No Device"
                                is BluetoothDeviceState.Error -> "Connection Issue"
                            },
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = when {
                                isConnected -> Color(0xFF00E676)
                                isConnecting -> Color(0xFFFFD600)
                                isError -> Color(0xFFFF5252)
                                else -> Color(0xFFCCCCCC)
                            }
                        )
                    }
                }

                // Connect / Disconnect button
                Button(
                    onClick = onActionClick,
                    enabled = !isConnecting && selectedDevice != null,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isConnected) Color(0xFF333333) else PrimaryBlue,
                        disabledContainerColor = PrimaryBlue.copy(alpha = 0.5f)
                    ),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 10.dp)
                ) {
                    if (isConnecting) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(text = "Connecting", fontSize = 14.sp, color = Color.White)
                    } else {
                        Text(
                            text = if (isConnected) "Disconnect" else "Connect",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                }
            }

            // User Notice / Error or Unpaired Guidance Banner
            AnimatedVisibility(
                visible = uiState.userNotice != null || (!uiState.hasRequiredPermissions && selectedDevice == null),
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 14.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(Color(0xFF241C1C))
                        .padding(12.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Notice",
                            tint = Color(0xFFFF8A80),
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = uiState.userNotice
                                ?: if (!uiState.hasRequiredPermissions) "Bluetooth permission required."
                                else "Please pair your audio device in Bluetooth settings.",
                            fontSize = 12.sp,
                            color = Color(0xFFFFCDD2)
                        )
                    }

                    if (!uiState.hasRequiredPermissions) {
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = onRequestPermission,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth(),
                            contentPadding = PaddingValues(8.dp)
                        ) {
                            Text("Grant Bluetooth Permissions", fontSize = 12.sp, color = PrimaryBlue)
                        }
                    } else if (uiState.pairedDevices.isEmpty()) {
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(
                            onClick = {
                                context.startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS))
                            },
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth(),
                            contentPadding = PaddingValues(8.dp)
                        ) {
                            Text("Open Bluetooth Settings to Pair", fontSize = 12.sp, color = PrimaryBlue)
                        }
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
    onDismiss: () -> Unit
) {
    val context = LocalContext.current

    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E1E1E)),
            elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
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
                        color = Color.White
                    )
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = Color.Gray
                        )
                    }
                }

                Spacer(modifier = Modifier.height(14.dp))

                if (devices.isEmpty()) {
                    Text(
                        text = "No paired Bluetooth audio devices found.",
                        fontSize = 14.sp,
                        color = Color(0xFF888888),
                        modifier = Modifier.padding(vertical = 12.dp)
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(max = 280.dp)
                    ) {
                        items(devices) { device ->
                            val isSelected = device.macAddress.equals(selectedMac, ignoreCase = true)

                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = if (isSelected) PrimaryBlue.copy(alpha = 0.15f) else Color(0xFF282828),
                                border = if (isSelected) BorderStroke(1.dp, PrimaryBlue) else null,
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
                                            tint = if (isSelected) PrimaryBlue else Color(0xFFAAAAAA),
                                            modifier = Modifier.size(22.dp)
                                        )
                                        Spacer(modifier = Modifier.width(12.dp))
                                        Column {
                                            Text(
                                                text = device.name,
                                                fontSize = 15.sp,
                                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                                                color = if (isSelected) PrimaryBlue else Color.White,
                                                maxLines = 1,
                                                overflow = TextOverflow.Ellipsis
                                            )
                                            Text(
                                                text = device.macAddress,
                                                fontSize = 11.sp,
                                                color = Color(0xFF888888)
                                            )
                                        }
                                    }

                                    if (device.isConnected) {
                                        Surface(
                                            shape = RoundedCornerShape(10.dp),
                                            color = Color(0xFF1E3A2F),
                                            modifier = Modifier.padding(start = 8.dp)
                                        ) {
                                            Text(
                                                text = "Connected",
                                                fontSize = 10.sp,
                                                color = Color(0xFF69F0AE),
                                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                                            )
                                        }
                                    } else if (isSelected) {
                                        Icon(
                                            imageVector = Icons.Default.Check,
                                            contentDescription = "Selected",
                                            tint = PrimaryBlue,
                                            modifier = Modifier.size(18.dp)
                                        )
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
                        tint = PrimaryBlue
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Pair New Device in Settings", fontSize = 13.sp, color = PrimaryBlue)
                }
            }
        }
    }
}

@Composable
fun MusicSection() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color(0xFF202020)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.MusicNote,
                            contentDescription = "Music",
                            tint = Color.White,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(14.dp))
                    Column {
                        Text(
                            text = "Music Presets",
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            text = "Smart Room Quick Audio",
                            fontSize = 12.sp,
                            color = Color(0xFF888888)
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = Color(0xFF282828)
                ) {
                    Text(
                        text = "Preset",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFFB0B0B0),
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(18.dp))

            Button(
                onClick = { /* Music playback placeholder */ },
                colors = ButtonDefaults.buttonColors(containerColor = PrimaryBlue),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(14.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.PlayArrow,
                    contentDescription = "Play",
                    tint = Color.White,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Play Zara Zara",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = Color.White
                )
            }
        }
    }
}
