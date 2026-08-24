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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun AutomationsPortalPanel(
    scheduledActions: List<ScheduledDeviceAction>,
    activeRoutine: RoutineState?,
    onCancelScheduledTimer: () -> Unit,
    onCancelRoutine: () -> Unit,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    val timeFmt = SimpleDateFormat("hh:mm a", Locale.getDefault())

    Card(
        modifier = modifier
            .fillMaxWidth()
            .fillMaxHeight(0.85f),
        shape = GlassTokens.CornerRadiusLarge,
        colors = CardDefaults.cardColors(containerColor = GlassTokens.GlassSurfaceHover),
        border = GlassTokens.glassBorder(GlassTokens.AccentYellow)
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
                            .background(GlassTokens.AccentYellow.copy(alpha = 0.15f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Schedule,
                            contentDescription = "Automations",
                            tint = GlassTokens.AccentYellow,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Column {
                        Text(
                            text = "Automations & Schedules",
                            color = Color.White,
                            fontSize = 17.sp,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "Deterministic Action Timers & Routines",
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
                // Active Routine Section
                if (activeRoutine != null && activeRoutine.isActive) {
                    val wakeTimeStr = activeRoutine.scheduledWakeTime?.let { timeFmt.format(Date(it)) } ?: "Not set"
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(GlassTokens.CornerRadiusMedium)
                                .background(GlassTokens.AccentPurple.copy(alpha = 0.15f))
                                .border(1.dp, GlassTokens.AccentPurple.copy(alpha = 0.45f), GlassTokens.CornerRadiusMedium)
                                .padding(16.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Bedtime,
                                    contentDescription = "Active Routine",
                                    tint = GlassTokens.AccentPurple,
                                    modifier = Modifier.size(28.dp)
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "Active Sleep Routine",
                                        color = Color.White,
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold
                                    )
                                    Text(
                                        text = "Target Wake: $wakeTimeStr",
                                        color = Color.White.copy(alpha = 0.7f),
                                        fontSize = 12.sp
                                    )
                                }
                                TextButton(onClick = onCancelRoutine) {
                                    Text("Cancel", color = GlassTokens.AccentRed, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                }

                // Scheduled Device Actions
                val pendingActions = scheduledActions.filter { it.isPending }
                if (pendingActions.isEmpty() && (activeRoutine == null || !activeRoutine.isActive)) {
                    item {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 40.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "No active scheduled timers or automations.",
                                color = Color.White.copy(alpha = 0.45f),
                                fontSize = 13.sp
                            )
                        }
                    }
                } else {
                    items(pendingActions) { action ->
                        val execTime = timeFmt.format(Date(action.scheduledExecutionTimeMillis))

                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(GlassTokens.CornerRadiusMedium)
                                .background(GlassTokens.GlassSurface)
                                .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
                                .padding(16.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Timer,
                                    contentDescription = "Timer",
                                    tint = GlassTokens.AccentYellow,
                                    modifier = Modifier.size(24.dp)
                                )
                                Spacer(modifier = Modifier.width(12.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "${action.targetDeviceType.name} ${action.actionType.name}",
                                        color = Color.White,
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    Text(
                                        text = "Executes at $execTime",
                                        color = GlassTokens.AccentYellow,
                                        fontSize = 12.sp
                                    )
                                }
                                TextButton(onClick = onCancelScheduledTimer) {
                                    Text("Cancel", color = GlassTokens.AccentRed)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
