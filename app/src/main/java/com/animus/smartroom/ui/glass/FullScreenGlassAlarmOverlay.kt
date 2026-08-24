package com.animus.smartroom.ui.glass

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AlarmOff
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.routine.model.RoutineState
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun FullScreenGlassAlarmOverlay(
    activeRoutine: RoutineState?,
    onStopAlarm: () -> Unit,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "AlarmPulse")

    // Pulsing aura animation for urgent wake feedback
    val alarmPulseScale by infiniteTransition.animateFloat(
        initialValue = 1.0f,
        targetValue = 1.25f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "AlarmPulseScale"
    )

    val alarmGlowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = 0.75f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "AlarmGlowAlpha"
    )

    val alarmTimeStr = remember(activeRoutine?.scheduledWakeTime) {
        val wakeTime = activeRoutine?.scheduledWakeTime
        if (wakeTime != null && wakeTime > 0) {
            SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date(wakeTime))
        } else {
            SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date())
        }
    }

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color(0xFF03050C).copy(alpha = 0.92f))
            .statusBarsPadding()
            .navigationBarsPadding()
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        // Ambient background radiant wake glow
        Box(
            modifier = Modifier
                .size(340.dp)
                .scale(alarmPulseScale)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Color(0xFFF59E0B).copy(alpha = alarmGlowAlpha * 0.45f),
                            Color(0xFFEF4444).copy(alpha = alarmGlowAlpha * 0.2f),
                            Color.Transparent
                        )
                    )
                )
        )

        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            // Header: Alarm indicator badge
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier
                    .clip(GlassTokens.CornerRadiusFull)
                    .background(Color(0xFFEF4444).copy(alpha = 0.18f))
                    .border(1.dp, Color(0xFFEF4444).copy(alpha = 0.6f), GlassTokens.CornerRadiusFull)
                    .padding(horizontal = 14.dp, vertical = 6.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.NotificationsActive,
                    contentDescription = "Alarm Active",
                    tint = Color(0xFFEF4444),
                    modifier = Modifier.size(16.dp)
                )
                Text(
                    text = "WAKE ROUTINE ACTIVE",
                    color = Color.White,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
            }

            // Center Hero: Time & Routine Name
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = alarmTimeStr,
                    color = Color.White,
                    fontSize = 62.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 2.sp
                )
                Text(
                    text = "Morning Wake Alarm",
                    color = Color.White.copy(alpha = 0.85f),
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = "Smart room routine is waking the room environment.",
                    color = Color.White.copy(alpha = 0.5f),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Normal
                )
            }

            // Bottom Action: Massive STOP ALARM button
            Box(
                modifier = Modifier
                    .fillMaxWidth(0.92f)
                    .height(68.dp)
                    .clip(RoundedCornerShape(22.dp))
                    .background(
                        Brush.verticalGradient(
                            colors = listOf(
                                Color(0xFFEF4444).copy(alpha = 0.85f),
                                Color(0xFFB91C1C).copy(alpha = 0.95f)
                            )
                        )
                    )
                    .border(
                        width = 1.5.dp,
                        brush = Brush.linearGradient(
                            colors = listOf(
                                Color.White.copy(alpha = 0.7f),
                                Color(0xFFEF4444)
                            )
                        ),
                        shape = RoundedCornerShape(22.dp)
                    )
                    .clickable { onStopAlarm() },
                contentAlignment = Alignment.Center
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.AlarmOff,
                        contentDescription = "Stop Alarm",
                        tint = Color.White,
                        modifier = Modifier.size(26.dp)
                    )
                    Text(
                        text = "STOP ALARM",
                        color = Color.White,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Black,
                        letterSpacing = 1.5.sp
                    )
                }
            }
        }
    }
}
