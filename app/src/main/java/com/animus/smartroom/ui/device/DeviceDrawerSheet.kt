package com.animus.smartroom.ui.device

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.model.TuyaAcState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceDrawerSheet(
    devices: List<RoomDevice>,
    acState: TuyaAcState,
    bluetoothState: BluetoothUiState,
    onDismiss: () -> Unit,
    onOpenAcRemote: () -> Unit,
    onOpenBluetoothManager: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = Color(0xFF0F172A),
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
        dragHandle = {
            BottomSheetDefaults.DragHandle(color = Color(0xFF475569))
        }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 8.dp)
                .padding(bottom = 36.dp)
        ) {
            // Title Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "ROOM DEVICES",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.5.sp,
                        color = Color(0xFF94A3B8)
                    )
                    Text(
                        text = "Smart Room Control Center",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White
                    )
                }
                Surface(
                    color = Color(0xFF1E293B),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        text = "${devices.size} Registered",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFF38BDF8),
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 1. Air Conditioner Card
            val acDevice = devices.firstOrNull { it.type == DeviceType.AIR_CONDITIONER }
            if (acDevice != null) {
                val acSummary = if (acState.isOnline) {
                    val pwr = if (acState.power) "ON" else "OFF"
                    "Online • $pwr • ${acState.targetTemperature}°C • ${acState.mode.name}"
                } else {
                    "Offline"
                }

                DeviceItemCard(
                    icon = Icons.Default.AcUnit,
                    iconTint = Color(0xFF38BDF8),
                    title = acDevice.displayName,
                    subtitle = acSummary,
                    isOnline = acState.isOnline,
                    actionLabel = "Tap to control →",
                    onClick = {
                        onDismiss()
                        onOpenAcRemote()
                    }
                )
                Spacer(modifier = Modifier.height(14.dp))
            }

            // 2. Bluetooth Speaker Card
            val isSpeakerConnected = bluetoothState.connectionState is BluetoothDeviceState.Connected
            val speakerName = bluetoothState.selectedDevice?.displayName ?: "No Speaker Selected"
            val speakerSummary = if (isSpeakerConnected) {
                "Connected • $speakerName"
            } else {
                "Disconnected • Tap to connect"
            }

            DeviceItemCard(
                icon = Icons.Default.Speaker,
                iconTint = Color(0xFFA78BFA),
                title = speakerName,
                subtitle = speakerSummary,
                isOnline = isSpeakerConnected,
                actionLabel = "Tap to manage →",
                onClick = {
                    onDismiss()
                    onOpenBluetoothManager()
                }
            )
        }
    }
}

@Composable
private fun DeviceItemCard(
    icon: ImageVector,
    iconTint: Color,
    title: String,
    subtitle: String,
    isOnline: Boolean,
    actionLabel: String,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFF1E293B)
        ),
        border = BorderStroke(1.dp, Color(0xFF334155))
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
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(iconTint.copy(alpha = 0.15f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = title,
                        tint = iconTint,
                        modifier = Modifier.size(24.dp)
                    )
                }

                Spacer(modifier = Modifier.width(14.dp))

                Column {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = title,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color.White
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(if (isOnline) Color(0xFF10B981) else Color(0xFF64748B))
                        )
                    }
                    Spacer(modifier = Modifier.height(2.dp))
                    Text(
                        text = subtitle,
                        fontSize = 13.sp,
                        color = Color(0xFF94A3B8)
                    )
                }
            }

            Text(
                text = actionLabel,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium,
                color = Color(0xFF38BDF8)
            )
        }
    }
}
