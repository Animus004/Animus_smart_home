package com.animus.smartroom.ui.glass

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.tuya.model.TuyaAcState

@Composable
fun GlassAcRemotePanel(
    acState: TuyaAcState,
    isOperating: Boolean,
    onSetPower: (Boolean) -> Unit,
    onSetTemperature: (Int) -> Unit,
    onSetMode: (AcMode) -> Unit,
    onSetFanSpeed: (AcFanSpeed) -> Unit,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    var showPairingDialog by remember { mutableStateOf(false) }

    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(0.85f),
        shape = GlassTokens.CornerRadiusLarge,
        colors = CardDefaults.cardColors(containerColor = GlassTokens.GlassSurfaceHover),
        border = GlassTokens.glassBorder(GlassTokens.AccentCyan)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
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
                            .background(GlassTokens.AccentCyan.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.AcUnit,
                            contentDescription = "AC Remote",
                            tint = GlassTokens.AccentCyan,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Column {
                        Text(
                            text = "Smart Climate Control",
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Tuya Cloud Climate Node",
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

            Spacer(modifier = Modifier.height(20.dp))

            // Main Temperature Hero & Stepper
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(GlassTokens.CornerRadiusMedium)
                    .background(GlassTokens.GlassSurface)
                    .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
                    .padding(20.dp),
                contentAlignment = Alignment.Center
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    // Decrement button (-)
                    Box(
                        modifier = Modifier
                            .size(48.dp)
                            .clip(CircleShape)
                            .background(GlassTokens.GlassSurfaceHover)
                            .border(1.dp, GlassTokens.BorderLight, CircleShape)
                            .clickable(enabled = acState.targetTemperature > 16 && !isOperating) {
                                onSetTemperature(acState.targetTemperature - 1)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Remove,
                            contentDescription = "Decrease Temperature",
                            tint = if (acState.targetTemperature > 16) GlassTokens.AccentCyan else Color.White.copy(alpha = 0.2f),
                            modifier = Modifier.size(24.dp)
                        )
                    }

                    // Temperature Big Display
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = "${acState.targetTemperature}°C",
                            color = if (acState.power) GlassTokens.AccentCyan else Color.White.copy(alpha = 0.4f),
                            fontSize = 44.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = if (acState.power) "SETPOINT ACTIVE" else "UNIT OFF",
                            color = if (acState.power) GlassTokens.AccentGreen else Color.White.copy(alpha = 0.4f),
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            letterSpacing = 1.sp
                        )
                    }

                    // Increment button (+)
                    Box(
                        modifier = Modifier
                            .size(48.dp)
                            .clip(CircleShape)
                            .background(GlassTokens.GlassSurfaceHover)
                            .border(1.dp, GlassTokens.BorderLight, CircleShape)
                            .clickable(enabled = acState.targetTemperature < 30 && !isOperating) {
                                onSetTemperature(acState.targetTemperature + 1)
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Add,
                            contentDescription = "Increase Temperature",
                            tint = if (acState.targetTemperature < 30) GlassTokens.AccentCyan else Color.White.copy(alpha = 0.2f),
                            modifier = Modifier.size(24.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Power Switch Button
            Button(
                onClick = { onSetPower(!acState.power) },
                enabled = !isOperating,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (acState.power) GlassTokens.AccentGreen.copy(alpha = 0.25f) else GlassTokens.AccentRed.copy(alpha = 0.25f),
                    contentColor = if (acState.power) GlassTokens.AccentGreen else GlassTokens.AccentRed
                ),
                shape = GlassTokens.CornerRadiusMedium,
                border = BorderStroke(
                    1.dp,
                    if (acState.power) GlassTokens.AccentGreen.copy(alpha = 0.5f) else GlassTokens.AccentRed.copy(alpha = 0.5f)
                ),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.PowerSettingsNew,
                    contentDescription = "Power",
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = if (acState.power) "AC IS POWERED ON" else "AC IS POWERED OFF",
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Modes Section
            Text(
                text = "OPERATING MODE",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.align(Alignment.Start)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf(AcMode.COOL, AcMode.AUTO, AcMode.DRY, AcMode.FAN).forEach { mode ->
                    val isSelected = acState.mode == mode
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(GlassTokens.CornerRadiusSmall)
                            .background(
                                if (isSelected) GlassTokens.AccentCyan.copy(alpha = 0.25f)
                                else GlassTokens.GlassSurface
                            )
                            .border(
                                1.dp,
                                if (isSelected) GlassTokens.AccentCyan else GlassTokens.BorderLight,
                                GlassTokens.CornerRadiusSmall
                            )
                            .clickable(enabled = !isOperating) { onSetMode(mode) }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = mode.name,
                            color = if (isSelected) GlassTokens.AccentCyan else Color.White.copy(alpha = 0.7f),
                            fontSize = 11.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Fan Speed Section
            Text(
                text = "FAN SPEED",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.align(Alignment.Start)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf(AcFanSpeed.LOW, AcFanSpeed.MEDIUM, AcFanSpeed.HIGH, AcFanSpeed.AUTO).forEach { speed ->
                    val isSelected = acState.fanSpeed == speed
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(GlassTokens.CornerRadiusSmall)
                            .background(
                                if (isSelected) GlassTokens.AccentBlue.copy(alpha = 0.25f)
                                else GlassTokens.GlassSurface
                            )
                            .border(
                                1.dp,
                                if (isSelected) GlassTokens.AccentBlue else GlassTokens.BorderLight,
                                GlassTokens.CornerRadiusSmall
                            )
                            .clickable(enabled = !isOperating) { onSetFanSpeed(speed) }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = speed.name,
                            color = if (isSelected) GlassTokens.AccentBlue else Color.White.copy(alpha = 0.7f),
                            fontSize = 11.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // Device Pairing Extension Entry Point
            OutlinedButton(
                onClick = { showPairingDialog = true },
                shape = GlassTokens.CornerRadiusMedium,
                border = GlassTokens.glassBorder(GlassTokens.AccentPurple),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = GlassTokens.AccentPurple),
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(imageVector = Icons.Default.AddLink, contentDescription = "Pair Device", modifier = Modifier.size(18.dp))
                Spacer(modifier = Modifier.width(8.dp))
                Text("Pair New Smart Room Device", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }

    if (showPairingDialog) {
        AlertDialog(
            onDismissRequest = { showPairingDialog = false },
            title = { Text("Device Pairing & Provisioning", color = Color.White) },
            text = {
                Text(
                    "Extensible device provisioning architecture. Automatically discovers Tuya Wi-Fi endpoints, Bluetooth A2DP audio peripherals, and ADB media nodes on your local subnet (192.168.1.0/24).",
                    color = Color.White.copy(alpha = 0.8f),
                    fontSize = 13.sp
                )
            },
            confirmButton = {
                TextButton(onClick = { showPairingDialog = false }) {
                    Text("OK", color = GlassTokens.AccentCyan)
                }
            },
            containerColor = GlassTokens.BackgroundSurface
        )
    }
}
