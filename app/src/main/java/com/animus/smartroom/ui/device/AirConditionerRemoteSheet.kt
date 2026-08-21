package com.animus.smartroom.ui.device

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AirConditionerRemoteSheet(
    state: TuyaAcState,
    isOperating: Boolean,
    activeTimer: com.animus.smartroom.scheduler.model.ScheduledDeviceAction? = null,
    onDismiss: () -> Unit,
    onPowerToggle: (Boolean) -> Unit,
    onTemperatureChange: (Int) -> Unit,
    onModeSelect: (AcMode) -> Unit,
    onFanSpeedSelect: (AcFanSpeed) -> Unit,
    onScheduleTimer: (delayMinutes: Int, powerOn: Boolean) -> Unit = { _, _ -> },
    onCancelTimer: () -> Unit = {}
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
                .padding(bottom = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "AIR CONDITIONER",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.2.sp,
                        color = Color(0xFF94A3B8)
                    )
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(top = 2.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(if (state.isOnline) Color(0xFF10B981) else Color(0xFF64748B))
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = if (state.isOnline) "Online" else "Offline",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium,
                            color = if (state.isOnline) Color(0xFF10B981) else Color(0xFF64748B)
                        )
                    }
                }

                // Ambient Temperature Badge
                state.ambientTemperature?.let { ambient ->
                    Surface(
                        color = Color(0xFF1E293B),
                        shape = RoundedCornerShape(12.dp),
                        border = BorderStroke(1.dp, Color(0xFF334155))
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Room",
                                fontSize = 12.sp,
                                color = Color(0xFF94A3B8)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "$ambient°C",
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Large Temperature Display with Steppers
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Minus Button
                FilledIconButton(
                    onClick = {
                        val next = (state.targetTemperature - 1).coerceAtLeast(16)
                        if (next != state.targetTemperature) {
                            onTemperatureChange(next)
                        }
                    },
                    enabled = !isOperating && state.targetTemperature > 16,
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = Color(0xFF1E293B),
                        contentColor = Color.White,
                        disabledContainerColor = Color(0xFF1E293B).copy(alpha = 0.5f),
                        disabledContentColor = Color(0xFF475569)
                    ),
                    modifier = Modifier.size(54.dp),
                    shape = CircleShape
                ) {
                    Icon(
                        imageVector = Icons.Default.Remove,
                        contentDescription = "Decrease Temperature",
                        modifier = Modifier.size(26.dp)
                    )
                }

                Spacer(modifier = Modifier.width(28.dp))

                // Target Temperature Reading
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.width(130.dp)
                ) {
                    Row(verticalAlignment = Alignment.Top) {
                        Text(
                            text = "${state.targetTemperature}",
                            fontSize = 68.sp,
                            fontWeight = FontWeight.Light,
                            color = if (state.power) Color.White else Color(0xFF64748B),
                            lineHeight = 68.sp
                        )
                        Text(
                            text = "°C",
                            fontSize = 24.sp,
                            fontWeight = FontWeight.Normal,
                            color = Color(0xFF38BDF8),
                            modifier = Modifier.padding(top = 8.dp)
                        )
                    }
                    Text(
                        text = if (isOperating) "Verifying with AC..." else "Target temp",
                        fontSize = 12.sp,
                        color = if (isOperating) Color(0xFF38BDF8) else Color(0xFF94A3B8)
                    )
                }

                Spacer(modifier = Modifier.width(28.dp))

                // Plus Button
                FilledIconButton(
                    onClick = {
                        val next = (state.targetTemperature + 1).coerceAtMost(30)
                        if (next != state.targetTemperature) {
                            onTemperatureChange(next)
                        }
                    },
                    enabled = !isOperating && state.targetTemperature < 30,
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = Color(0xFF1E293B),
                        contentColor = Color.White,
                        disabledContainerColor = Color(0xFF1E293B).copy(alpha = 0.5f),
                        disabledContentColor = Color(0xFF475569)
                    ),
                    modifier = Modifier.size(54.dp),
                    shape = CircleShape
                ) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = "Increase Temperature",
                        modifier = Modifier.size(26.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Power Control Button
            Button(
                onClick = { onPowerToggle(!state.power) },
                enabled = !isOperating,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (state.power) Color(0xFF10B981).copy(alpha = 0.2f) else Color(0xFFEF4444).copy(alpha = 0.15f),
                    contentColor = if (state.power) Color(0xFF34D399) else Color(0xFFF87171)
                ),
                border = BorderStroke(
                    1.dp,
                    if (state.power) Color(0xFF10B981).copy(alpha = 0.5f) else Color(0xFFEF4444).copy(alpha = 0.3f)
                )
            ) {
                Icon(
                    imageVector = Icons.Default.PowerSettingsNew,
                    contentDescription = "Power Toggle",
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = if (state.power) "POWER ON" else "POWER OFF",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 0.8.sp
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Mode Selector
            Text(
                text = "MODE",
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp,
                color = Color(0xFF94A3B8),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 10.dp)
            )

            val modes = listOf(AcMode.AUTO, AcMode.COOL, AcMode.DRY, AcMode.FAN)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF1E293B), RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                modes.forEach { mode ->
                    val isSelected = state.mode == mode
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (isSelected) Color(0xFF38BDF8).copy(alpha = 0.25f) else Color.Transparent
                            )
                            .clickable(enabled = !isOperating) { onModeSelect(mode) }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = mode.name,
                            fontSize = 13.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                            color = if (isSelected) Color(0xFF38BDF8) else Color(0xFF64748B)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(22.dp))

            // Fan Speed Selector
            Text(
                text = "FAN SPEED",
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 1.sp,
                color = Color(0xFF94A3B8),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 10.dp)
            )

            val fanSpeeds = listOf(
                AcFanSpeed.AUTO to "AUTO",
                AcFanSpeed.LOW to "LOW",
                AcFanSpeed.MEDIUM to "MED",
                AcFanSpeed.HIGH to "HIGH"
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF1E293B), RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                fanSpeeds.forEach { (speed, label) ->
                    val isSelected = state.fanSpeed == speed
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (isSelected) Color(0xFF818CF8).copy(alpha = 0.25f) else Color.Transparent
                            )
                            .clickable(enabled = !isOperating) { onFanSpeedSelect(speed) }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = label,
                            fontSize = 13.sp,
                            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                            color = if (isSelected) Color(0xFF818CF8) else Color(0xFF64748B)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // AC Timer Section
            AcTimerSection(
                activeTimer = activeTimer,
                onScheduleTimer = onScheduleTimer,
                onCancelTimer = onCancelTimer
            )

            // Operation Progress Banner
            AnimatedVisibility(visible = isOperating) {
                Row(
                    modifier = Modifier
                        .padding(top = 20.dp)
                        .fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                        color = Color(0xFF38BDF8)
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text(
                        text = "Synchronizing with physical AC...",
                        fontSize = 12.sp,
                        color = Color(0xFF94A3B8)
                    )
                }
            }
        }
    }
}

@Composable
private fun AcTimerSection(
    activeTimer: com.animus.smartroom.scheduler.model.ScheduledDeviceAction?,
    onScheduleTimer: (delayMinutes: Int, powerOn: Boolean) -> Unit,
    onCancelTimer: () -> Unit
) {
    var timerModeIsPowerOn by remember { mutableStateOf(false) } // false = OFF timer, true = ON timer
    var showCustomDialog by remember { mutableStateOf(false) }
    var customMinutesInput by remember { mutableStateOf("") }

    val hasActiveTimer = activeTimer != null && activeTimer.isPending

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = Color(0xFF1E293B),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, if (hasActiveTimer) Color(0xFF38BDF8).copy(alpha = 0.5f) else Color(0xFF334155))
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "AC TIMER",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp,
                    color = Color(0xFF94A3B8)
                )

                if (hasActiveTimer) {
                    Surface(
                        color = Color(0xFF0284C7).copy(alpha = 0.2f),
                        shape = RoundedCornerShape(6.dp)
                    ) {
                        Text(
                            text = if (activeTimer?.actionType == com.animus.smartroom.scheduler.model.DeviceActionType.POWER_ON) "ON TIMER" else "OFF TIMER",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFF38BDF8),
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (hasActiveTimer && activeTimer != null) {
                // Live 1-Second Ticker deriving remaining time
                var remainingSecs by remember(activeTimer) {
                    mutableStateOf(activeTimer.remainingMillis() / 1000L)
                }

                LaunchedEffect(activeTimer) {
                    while (true) {
                        val rem = activeTimer.remainingMillis() / 1000L
                        remainingSecs = rem
                        if (rem <= 0L) break
                        kotlinx.coroutines.delay(1000L)
                    }
                }

                val hours = remainingSecs / 3600
                val mins = (remainingSecs % 3600) / 60
                val secs = remainingSecs % 60
                val formattedTime = String.format(java.util.Locale.ROOT, "%02d:%02d:%02d", hours, mins, secs)

                val sdf = java.text.SimpleDateFormat("hh:mm a", java.util.Locale.getDefault()).apply {
                    timeZone = java.util.TimeZone.getTimeZone(com.animus.smartroom.context.HomeLocationContext.getLocation().timeZone)
                }
                val targetTimeStr = sdf.format(java.util.Date(activeTimer.scheduledExecutionTimeMillis))

                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = if (activeTimer.actionType == com.animus.smartroom.scheduler.model.DeviceActionType.POWER_ON) "TURNS ON IN" else "TURNS OFF IN",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        color = Color(0xFF94A3B8)
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = formattedTime,
                        fontSize = 28.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 2.sp,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Scheduled for $targetTimeStr",
                        fontSize = 12.sp,
                        color = Color(0xFF64748B)
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    Button(
                        onClick = onCancelTimer,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFFEF4444).copy(alpha = 0.2f),
                            contentColor = Color(0xFFFCA5A5)
                        ),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Cancel Timer",
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(text = "CANCEL TIMER", fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    }
                }
            } else {
                // Inactive Timer - Quick preset selectors
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFF0F172A), RoundedCornerShape(10.dp))
                        .padding(3.dp),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (!timerModeIsPowerOn) Color(0xFF0284C7).copy(alpha = 0.25f) else Color.Transparent)
                            .clickable { timerModeIsPowerOn = false }
                            .padding(vertical = 8.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "TURN OFF IN",
                            fontSize = 12.sp,
                            fontWeight = if (!timerModeIsPowerOn) FontWeight.Bold else FontWeight.Medium,
                            color = if (!timerModeIsPowerOn) Color(0xFF38BDF8) else Color(0xFF64748B)
                        )
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (timerModeIsPowerOn) Color(0xFF10B981).copy(alpha = 0.25f) else Color.Transparent)
                            .clickable { timerModeIsPowerOn = true }
                            .padding(vertical = 8.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "TURN ON IN",
                            fontSize = 12.sp,
                            fontWeight = if (timerModeIsPowerOn) FontWeight.Bold else FontWeight.Medium,
                            color = if (timerModeIsPowerOn) Color(0xFF34D399) else Color(0xFF64748B)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // Quick Chips: 30m, 1h, 2h, 4h, Custom
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    val presets = listOf(30 to "30m", 60 to "1h", 120 to "2h", 240 to "4h")
                    presets.forEach { (mins, label) ->
                        Surface(
                            color = Color(0xFF0F172A),
                            shape = RoundedCornerShape(8.dp),
                            border = BorderStroke(1.dp, Color(0xFF334155)),
                            modifier = Modifier
                                .weight(1f)
                                .clickable { onScheduleTimer(mins, timerModeIsPowerOn) }
                        ) {
                            Text(
                                text = label,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = Color.White,
                                modifier = Modifier
                                    .padding(vertical = 10.dp)
                                    .wrapContentWidth(Alignment.CenterHorizontally)
                            )
                        }
                    }

                    Surface(
                        color = Color(0xFF0F172A),
                        shape = RoundedCornerShape(8.dp),
                        border = BorderStroke(1.dp, Color(0xFF38BDF8).copy(alpha = 0.4f)),
                        modifier = Modifier
                            .weight(1.2f)
                            .clickable { showCustomDialog = true }
                    ) {
                        Text(
                            text = "Custom",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFF38BDF8),
                            modifier = Modifier
                                .padding(vertical = 10.dp)
                                .wrapContentWidth(Alignment.CenterHorizontally)
                        )
                    }
                }
            }
        }
    }

    if (showCustomDialog) {
        AlertDialog(
            onDismissRequest = { showCustomDialog = false },
            title = { Text(text = "Custom AC Timer", color = Color.White) },
            text = {
                Column {
                    Text(
                        text = "Enter duration in minutes for ${if (timerModeIsPowerOn) "Power ON" else "Power OFF"}:",
                        fontSize = 14.sp,
                        color = Color(0xFF94A3B8)
                    )
                    Spacer(modifier = Modifier.height(10.dp))
                    OutlinedTextField(
                        value = customMinutesInput,
                        onValueChange = { customMinutesInput = it.filter { c -> c.isDigit() } },
                        label = { Text("Minutes (e.g. 45)") },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color(0xFF38BDF8),
                            unfocusedBorderColor = Color(0xFF475569),
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White
                        )
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val mins = customMinutesInput.toIntOrNull()
                        if (mins != null && mins > 0) {
                            onScheduleTimer(mins, timerModeIsPowerOn)
                            showCustomDialog = false
                            customMinutesInput = ""
                        }
                    }
                ) {
                    Text("SET TIMER", color = Color(0xFF38BDF8), fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showCustomDialog = false }) {
                    Text("CANCEL", color = Color(0xFF94A3B8))
                }
            },
            containerColor = Color(0xFF1E293B)
        )
    }
}
