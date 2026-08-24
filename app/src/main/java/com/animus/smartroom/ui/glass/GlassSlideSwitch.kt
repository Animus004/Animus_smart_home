package com.animus.smartroom.ui.glass

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Flight
import androidx.compose.material.icons.filled.Home
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun GlassSlideSwitch(
    currentMode: OperationMode,
    onModeChanged: (OperationMode) -> Unit,
    modifier: Modifier = Modifier
) {
    val isRemote = currentMode == OperationMode.REMOTE

    val targetOffset = if (isRemote) 1f else 0f
    val animatedProgress by animateFloatAsState(
        targetValue = targetOffset,
        animationSpec = spring(
            dampingRatio = Spring.DampingRatioMediumBouncy,
            stiffness = Spring.StiffnessLow
        ),
        label = "SwitchProgress"
    )

    val activeColor by animateColorAsState(
        targetValue = if (isRemote) GlassTokens.AccentPurple else GlassTokens.AccentGreen,
        animationSpec = tween(300),
        label = "SwitchActiveColor"
    )

    val trackBorderColor by animateColorAsState(
        targetValue = if (isRemote) GlassTokens.AccentPurple.copy(alpha = 0.5f) else GlassTokens.AccentGreen.copy(alpha = 0.45f),
        animationSpec = tween(300),
        label = "SwitchBorderColor"
    )

    val interactionSource = remember { MutableInteractionSource() }

    Box(
        modifier = modifier
            .width(174.dp)
            .height(38.dp)
            .clip(GlassTokens.CornerRadiusFull)
            .background(
                Brush.horizontalGradient(
                    colors = listOf(
                        GlassTokens.GlassSurfaceHover,
                        GlassTokens.GlassSurface
                    )
                )
            )
            .border(
                width = 1.dp,
                color = trackBorderColor,
                shape = GlassTokens.CornerRadiusFull
            )
            .clickable(
                interactionSource = interactionSource,
                indication = null
            ) {
                onModeChanged(if (isRemote) OperationMode.LOCAL_ROOM else OperationMode.REMOTE)
            }
            .padding(3.dp),
        contentAlignment = Alignment.CenterStart
    ) {
        // Sliding thumb pill
        BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
            val maxTravel = maxWidth - (maxWidth / 2)

            Box(
                modifier = Modifier
                    .offset(x = maxTravel * animatedProgress)
                    .width(maxWidth / 2)
                    .fillMaxHeight()
                    .clip(GlassTokens.CornerRadiusFull)
                    .background(
                        Brush.verticalGradient(
                            colors = listOf(
                                activeColor.copy(alpha = 0.35f),
                                activeColor.copy(alpha = 0.18f)
                            )
                        )
                    )
                    .border(
                        width = 1.dp,
                        brush = Brush.linearGradient(
                            colors = listOf(
                                activeColor.copy(alpha = 0.85f),
                                activeColor.copy(alpha = 0.3f)
                            )
                        ),
                        shape = GlassTokens.CornerRadiusFull
                    )
            )
        }

        // Two Segment Labels: LOCAL / REMOTE
        Row(
            modifier = Modifier.fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Left segment: LOCAL ROOM
            Row(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clickable(
                        interactionSource = interactionSource,
                        indication = null
                    ) {
                        if (isRemote) onModeChanged(OperationMode.LOCAL_ROOM)
                    },
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Home,
                    contentDescription = "Local Room",
                    tint = if (!isRemote) GlassTokens.AccentGreen else Color.White.copy(alpha = 0.4f),
                    modifier = Modifier.size(13.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = "LOCAL",
                    color = if (!isRemote) Color.White else Color.White.copy(alpha = 0.45f),
                    fontSize = 11.sp,
                    fontWeight = if (!isRemote) FontWeight.Bold else FontWeight.Medium,
                    letterSpacing = 0.5.sp
                )
            }

            // Right segment: REMOTE
            Row(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clickable(
                        interactionSource = interactionSource,
                        indication = null
                    ) {
                        if (!isRemote) onModeChanged(OperationMode.REMOTE)
                    },
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Flight,
                    contentDescription = "Remote Mode",
                    tint = if (isRemote) GlassTokens.AccentPurple else Color.White.copy(alpha = 0.4f),
                    modifier = Modifier.size(13.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = "REMOTE",
                    color = if (isRemote) Color.White else Color.White.copy(alpha = 0.45f),
                    fontSize = 11.sp,
                    fontWeight = if (isRemote) FontWeight.Bold else FontWeight.Medium,
                    letterSpacing = 0.5.sp
                )
            }
        }
    }
}
