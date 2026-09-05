package com.animus.smartroom.ui.glass

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.model.TuyaAcState

data class DeviceTelemetryCardData(
    val name: String,
    val domain: String,
    val icon: ImageVector,
    val isOnline: Boolean,
    val statusText: String,
    val details: String
)

@Composable
fun DeviceStatusPanel(
    registeredDevices: List<RoomDevice>,
    tuyaAcState: TuyaAcState,
    bluetoothUiState: BluetoothUiState,
    roomState: com.animus.smartroom.context.model.RoomStateDto? = null,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    val soundbarConnected = roomState?.soundbar?.isConnected == true ||
            bluetoothUiState.selectedDevice?.isConnected == true ||
            bluetoothUiState.pairedDevices.any { it.isConnected }
    val acPowerText = if (roomState?.ac != null) {
        if (roomState.ac.power) "ON (${roomState.ac.targetTemperature}°C, ${roomState.ac.hvacMode})" else "OFF"
    } else if (tuyaAcState.power) {
        "ON (${tuyaAcState.targetTemperature}°C, ${tuyaAcState.mode.name})"
    } else {
        "OFF"
    }

    val projectorOnline = roomState?.projector?.isConnected ?: true
    val projectorStatusText = if (roomState?.projector != null) {
        if (roomState.projector.isPowerOn) "ON (${roomState.projector.inputSource})" else "STANDBY (${roomState.projector.powerState})"
    } else {
        "HDMI 1 (192.168.1.10:5555)"
    }
    val projectorDetails = if (roomState?.projector != null) {
        "Source: ${roomState.projector.inputSource} • Signal: ${if (roomState.projector.hasSignal) "ACTIVE" else "IDLE"}"
    } else {
        "Resolution: 1080p • State: Active Surface"
    }

    val fireTvStatusText = if (roomState?.fireTv != null) {
        if (roomState.fireTv.isPowerOn) "${roomState.fireTv.currentApp} (${roomState.fireTv.playbackState})" else "SLEEP"
    } else {
        "READY (192.168.1.5:5555)"
    }
    val fireTvDetails = if (roomState?.fireTv != null) {
        "App: ${roomState.fireTv.currentApp} • Soundbar: ${if (roomState.fireTv.soundbarConnected) "ATTACHED" else "DETACHED"}"
    } else {
        "OS: Fire OS 7.7.1.6 • Media: YouTube / Netflix / Prime"
    }

    val soundbarOwner = roomState?.soundbar?.connectedDevice ?: "Fire TV / PC"
    val soundbarStatusText = if (roomState?.soundbar != null) {
        if (roomState.soundbar.isConnected) "CONNECTED ($soundbarOwner)" else "STANDBY / YIELDED"
    } else if (soundbarConnected) {
        "CONNECTED"
    } else {
        "STANDBY / YIELDED"
    }

    val pcStatusText = if (roomState?.pc != null) {
        if (roomState.pc.isOnline) "ONLINE (Vol: ${roomState.pc.volume}%)" else "OFFLINE"
    } else {
        "ONLINE (Port 8095)"
    }

    val telemetryList = listOf(
        DeviceTelemetryCardData(
            name = "Bedroom Air Conditioner",
            domain = "Tuya Cloud / Climate",
            icon = Icons.Default.AcUnit,
            isOnline = roomState?.ac?.isOnline ?: tuyaAcState.isOnline,
            statusText = acPowerText,
            details = if (roomState?.ac != null) "Target: ${roomState.ac.targetTemperature}°C (Ambient: ${roomState.ac.ambientTemperature}°C)" else "Target: ${tuyaAcState.targetTemperature}°C • Fan: ${tuyaAcState.fanSpeed.name}"
        ),
        DeviceTelemetryCardData(
            name = "LG SNC4R Soundbar",
            domain = "Bluetooth A2DP Audio",
            icon = Icons.Default.Speaker,
            isOnline = soundbarConnected,
            statusText = soundbarStatusText,
            details = "Active Owner: $soundbarOwner • Route: ${roomState?.environment?.activeAudioRoute ?: "AUTO"}"
        ),
        DeviceTelemetryCardData(
            name = "Amazon Fire TV Stick",
            domain = "ADB / Media Surface",
            icon = Icons.Default.Tv,
            isOnline = roomState?.fireTv?.isOnline ?: true,
            statusText = fireTvStatusText,
            details = fireTvDetails
        ),
        DeviceTelemetryCardData(
            name = "Smart Projector",
            domain = "ADB / Display Output",
            icon = Icons.Default.Videocam,
            isOnline = projectorOnline,
            statusText = projectorStatusText,
            details = projectorDetails
        ),
        DeviceTelemetryCardData(
            name = "Animus PC Smart Daemon",
            domain = "Local HTTP Service",
            icon = Icons.Default.Computer,
            isOnline = roomState?.pc?.isOnline ?: true,
            statusText = pcStatusText,
            details = if (roomState?.pc != null) "Endpoint: ${roomState.pc.activeEndpoint} • Mute: ${roomState.pc.isMuted}" else "Music Engine: MPV / ytmusicapi • Auth: OAuth"
        ),
        DeviceTelemetryCardData(
            name = "Ollama Inference Engine",
            domain = "Local Neural LLM",
            icon = Icons.Default.Psychology,
            isOnline = true,
            statusText = "READY (Qwen 2.5 / 3 4B)",
            details = "Latency: ~350ms • Execution: GPU Accelerated"
        )
    )

    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(0.85f),
        shape = GlassTokens.CornerRadiusLarge,
        colors = CardDefaults.cardColors(containerColor = GlassTokens.GlassSurfaceHover),
        border = GlassTokens.glassBorder(GlassTokens.AccentBlue)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(GlassTokens.CornerRadiusSmall)
                            .background(GlassTokens.AccentBlue.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Sensors,
                            contentDescription = "Device Status",
                            tint = GlassTokens.AccentBlue,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Column {
                        Text(
                            text = "Device Health & Telemetry",
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Authoritative Room Hardware Matrix",
                            color = Color.White.copy(alpha = 0.6f),
                            fontSize = 11.5.sp
                        )
                    }
                }

                IconButton(onClick = onClose) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close",
                        tint = Color.White.copy(alpha = 0.7f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.fillMaxSize()
            ) {
                items(telemetryList) { item ->
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(GlassTokens.CornerRadiusMedium)
                            .background(GlassTokens.GlassSurface)
                            .border(
                                width = 1.dp,
                                brush = Brush.linearGradient(
                                    listOf(
                                        if (item.isOnline) GlassTokens.AccentGreen.copy(alpha = 0.35f) else GlassTokens.AccentRed.copy(alpha = 0.35f),
                                        Color.White.copy(alpha = 0.05f)
                                    )
                                ),
                                shape = GlassTokens.CornerRadiusMedium
                            )
                            .padding(14.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(42.dp)
                                    .clip(GlassTokens.CornerRadiusSmall)
                                    .background(
                                        if (item.isOnline) GlassTokens.AccentGreen.copy(alpha = 0.12f)
                                        else GlassTokens.AccentRed.copy(alpha = 0.12f)
                                    ),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = item.icon,
                                    contentDescription = item.name,
                                    tint = if (item.isOnline) GlassTokens.AccentGreen else GlassTokens.AccentRed,
                                    modifier = Modifier.size(22.dp)
                                )
                            }

                            Spacer(modifier = Modifier.width(12.dp))

                            Column(modifier = Modifier.weight(1f)) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Text(
                                        text = item.name,
                                        color = Color.White,
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    Text(
                                        text = item.statusText,
                                        color = if (item.isOnline) GlassTokens.AccentGreen else GlassTokens.AccentRed,
                                        fontSize = 11.5.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                                Spacer(modifier = Modifier.height(2.dp))
                                Text(
                                    text = item.details,
                                    color = Color.White.copy(alpha = 0.65f),
                                    fontSize = 11.5.sp
                                )
                                Spacer(modifier = Modifier.height(1.dp))
                                Text(
                                    text = item.domain,
                                    color = GlassTokens.AccentBlue.copy(alpha = 0.85f),
                                    fontSize = 10.sp
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
