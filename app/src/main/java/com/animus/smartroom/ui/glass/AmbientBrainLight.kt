package com.animus.smartroom.ui.glass

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import com.animus.smartroom.ui.brain.VisualBrainState

@Composable
fun AmbientBrainLight(
    state: VisualBrainState,
    modifier: Modifier = Modifier
) {
    val targetColor = when (state) {
        VisualBrainState.READY -> GlassTokens.AccentGreen
        VisualBrainState.WARMING -> GlassTokens.AccentYellow
        VisualBrainState.EXECUTING -> GlassTokens.AccentBlue
        VisualBrainState.COMPLETED -> GlassTokens.AccentCyan
        VisualBrainState.ERROR -> GlassTokens.AccentRed
    }

    val animatedColor by animateColorAsState(
        targetValue = targetColor,
        animationSpec = tween(durationMillis = 600, easing = FastOutSlowInEasing),
        label = "AmbientColorTransition"
    )

    val infiniteTransition = rememberInfiniteTransition(label = "AmbientLightLoop")

    // Breathing scale for the primary ambient orb
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = when (state) {
            VisualBrainState.EXECUTING -> 1.45f
            VisualBrainState.WARMING -> 1.25f
            VisualBrainState.COMPLETED -> 1.55f
            else -> 1.10f
        },
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = when (state) {
                    VisualBrainState.EXECUTING -> 800
                    VisualBrainState.WARMING -> 1400
                    VisualBrainState.COMPLETED -> 600
                    else -> 2800
                },
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "AmbientScale"
    )

    // Ambient glow alpha
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.12f,
        targetValue = when (state) {
            VisualBrainState.EXECUTING -> 0.38f
            VisualBrainState.COMPLETED -> 0.45f
            VisualBrainState.ERROR -> 0.30f
            else -> 0.22f
        },
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = when (state) {
                    VisualBrainState.EXECUTING -> 800
                    VisualBrainState.WARMING -> 1400
                    else -> 2800
                },
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "AmbientAlpha"
    )

    // Light movement sweep (offset animation for organic liquid light feel)
    val sweepOffset by infiniteTransition.animateFloat(
        initialValue = -50f,
        targetValue = 50f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 3600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "AmbientSweep"
    )

    Canvas(modifier = modifier.fillMaxSize()) {
        val center = Offset(size.width / 2f, size.height * 0.42f + sweepOffset)
        val radius = (size.width * 0.85f) * pulseScale

        // Deep space background gradient
        drawRect(
            brush = Brush.verticalGradient(
                colors = listOf(
                    GlassTokens.BackgroundDeep,
                    GlassTokens.BackgroundDark,
                    GlassTokens.BackgroundDeep
                )
            )
        )

        // Primary ambient radial glow
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    animatedColor.copy(alpha = pulseAlpha),
                    animatedColor.copy(alpha = pulseAlpha * 0.45f),
                    animatedColor.copy(alpha = 0f)
                ),
                center = center,
                radius = radius
            ),
            center = center,
            radius = radius
        )

        // Secondary subtle top ambient accent
        val topCenter = Offset(size.width * 0.8f, size.height * 0.15f)
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    animatedColor.copy(alpha = pulseAlpha * 0.35f),
                    Color.Transparent
                ),
                center = topCenter,
                radius = size.width * 0.5f
            ),
            center = topCenter,
            radius = size.width * 0.5f
        )
    }
}
