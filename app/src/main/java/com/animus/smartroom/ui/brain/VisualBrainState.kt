package com.animus.smartroom.ui.brain

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

enum class VisualBrainState(
    val color: Color,
    val label: String,
    val symbol: String
) {
    READY(Color(0xFF22C55E), "READY", "🟢"),          // 🟢 GREEN
    WARMING(Color(0xFFEAB308), "WARMING", "🟡"),      // 🟡 YELLOW
    EXECUTING(Color(0xFF3B82F6), "EXECUTING", "🔵"),  // 🔵 BLUE
    COMPLETED(Color(0xFF06B6D4), "COMPLETED", "🔷"),  // 🔷 CYAN
    ERROR(Color(0xFFEF4444), "ERROR", "🔴")           // 🔴 RED
}

@Composable
fun BrainStatusIndicator(
    state: VisualBrainState,
    modifier: Modifier = Modifier,
    compact: Boolean = false
) {
    val animatedColor by animateColorAsState(
        targetValue = state.color,
        animationSpec = tween(durationMillis = 400),
        label = "BrainColorAnimation"
    )

    val infiniteTransition = rememberInfiniteTransition(label = "BrainPulseTransition")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = if (state == VisualBrainState.EXECUTING || state == VisualBrainState.WARMING) 1.25f else 1.05f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (state == VisualBrainState.EXECUTING) 700 else 1200,
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "PulseScale"
    )

    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = if (state == VisualBrainState.EXECUTING) 0.85f else 0.55f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (state == VisualBrainState.EXECUTING) 700 else 1200,
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "PulseAlpha"
    )

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(
                Brush.horizontalGradient(
                    colors = listOf(
                        animatedColor.copy(alpha = 0.14f),
                        animatedColor.copy(alpha = 0.06f)
                    )
                )
            )
            .border(
                width = 1.dp,
                color = animatedColor.copy(alpha = 0.45f),
                shape = RoundedCornerShape(20.dp)
            )
            .padding(
                horizontal = if (compact) 10.dp else 14.dp,
                vertical = if (compact) 5.dp else 7.dp
            ),
        contentAlignment = Alignment.Center
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(7.dp)
        ) {
            // Pulsing status dot
            Box(
                modifier = Modifier
                    .size(if (compact) 8.dp else 10.dp)
                    .scale(pulseScale)
                    .clip(CircleShape)
                    .background(animatedColor.copy(alpha = pulseAlpha))
            )

            // Inner solid dot
            Box(
                modifier = Modifier
                    .size(if (compact) 6.dp else 7.dp)
                    .clip(CircleShape)
                    .background(animatedColor)
            )

            Text(
                text = state.label,
                color = animatedColor,
                fontSize = if (compact) 11.sp else 12.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.5.sp
            )
        }
    }
}
