package com.animus.smartroom.ui.glass

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.animus.smartroom.ui.brain.VisualBrainState
import com.animus.smartroom.voice.VoiceInputState

@Composable
fun HeroMicInteraction(
    brainState: VisualBrainState,
    voiceState: VoiceInputState,
    isProcessing: Boolean,
    onStartListening: () -> Unit,
    onStopListening: () -> Unit,
    modifier: Modifier = Modifier
) {
    val isReady = brainState == VisualBrainState.READY && !isProcessing
    val isListening = voiceState is VoiceInputState.Listening || voiceState is VoiceInputState.Recognizing

    val stateColor = when (brainState) {
        VisualBrainState.READY -> GlassTokens.AccentGreen
        VisualBrainState.WARMING -> GlassTokens.AccentYellow
        VisualBrainState.EXECUTING -> GlassTokens.AccentBlue
        VisualBrainState.COMPLETED -> GlassTokens.AccentCyan
        VisualBrainState.ERROR -> GlassTokens.AccentRed
    }

    val animatedColor by animateColorAsState(
        targetValue = stateColor,
        animationSpec = tween(durationMillis = 400),
        label = "HeroColor"
    )

    val infiniteTransition = rememberInfiniteTransition(label = "HeroMicPulse")

    // Outer ripple animation
    val outerRippleScale by infiniteTransition.animateFloat(
        initialValue = 1.0f,
        targetValue = if (isListening) 1.55f else if (brainState == VisualBrainState.EXECUTING || isProcessing) 1.35f else 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (isListening) 650 else if (brainState == VisualBrainState.EXECUTING || isProcessing) 800 else 2400,
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "OuterRipple"
    )

    // Inner ripple animation
    val innerRippleScale by infiniteTransition.animateFloat(
        initialValue = 0.95f,
        targetValue = if (isListening) 1.25f else 1.06f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = if (isListening) 650 else 2400,
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "InnerRipple"
    )

    // Continuous orbital rotation for executing state
    val continuousRotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 3000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "OrbitalRotation"
    )

    Box(
        modifier = modifier.size(200.dp),
        contentAlignment = Alignment.Center
    ) {
        // Outer glow ripple ring
        Box(
            modifier = Modifier
                .size(175.dp)
                .scale(outerRippleScale)
                .clip(CircleShape)
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            animatedColor.copy(alpha = if (isListening) 0.35f else 0.12f),
                            Color.Transparent
                        )
                    )
                )
        )

        // Middle reactive ring (rotates during executing state)
        Box(
            modifier = Modifier
                .size(145.dp)
                .scale(innerRippleScale)
                .rotate(if (brainState == VisualBrainState.EXECUTING || isProcessing) continuousRotation else 0f)
                .clip(CircleShape)
                .border(
                    width = if (brainState == VisualBrainState.EXECUTING || isProcessing) 2.dp else 1.5.dp,
                    brush = if (brainState == VisualBrainState.EXECUTING || isProcessing) {
                        Brush.sweepGradient(
                            colors = listOf(
                                animatedColor,
                                animatedColor.copy(alpha = 0.1f),
                                animatedColor
                            )
                        )
                    } else {
                        Brush.linearGradient(
                            colors = listOf(
                                animatedColor.copy(alpha = if (isListening) 0.65f else 0.25f),
                                animatedColor.copy(alpha = 0.08f)
                            )
                        )
                    },
                    shape = CircleShape
                )
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            animatedColor.copy(alpha = if (isListening) 0.22f else 0.08f),
                            Color.Transparent
                        )
                    )
                )
        )

        // Primary central glass core
        // CRITICAL INVARIANT: Interactive ONLY when VisualBrainState == READY
        val coreModifier = Modifier
            .size(118.dp)
            .clip(CircleShape)
            .background(
                Brush.verticalGradient(
                    colors = listOf(
                        GlassTokens.GlassSurfaceHover,
                        GlassTokens.GlassSurface
                    )
                )
            )
            .border(
                width = 1.5.dp,
                brush = Brush.linearGradient(
                    colors = listOf(
                        animatedColor.copy(alpha = 0.85f),
                        animatedColor.copy(alpha = 0.25f)
                    )
                ),
                shape = CircleShape
            )

        val finalCoreModifier = if (isReady) {
            coreModifier.clickable {
                if (isListening) {
                    onStopListening()
                } else {
                    onStartListening()
                }
            }
        } else {
            // Disabled when not READY
            coreModifier
        }

        Box(
            modifier = finalCoreModifier,
            contentAlignment = Alignment.Center
        ) {
            when (brainState) {
                VisualBrainState.READY -> {
                    Icon(
                        imageVector = if (isListening) Icons.Default.Stop else Icons.Default.Mic,
                        contentDescription = if (isListening) "Stop Listening" else "Start Voice Command",
                        tint = animatedColor,
                        modifier = Modifier.size(46.dp)
                    )
                }
                VisualBrainState.WARMING -> {
                    // Radiant amber energy core
                    Icon(
                        imageVector = Icons.Default.HourglassEmpty,
                        contentDescription = "Animus is preparing",
                        tint = animatedColor,
                        modifier = Modifier.size(42.dp)
                    )
                }
                VisualBrainState.EXECUTING -> {
                    // Flowing blue command execution core
                    Icon(
                        imageVector = Icons.Default.Sync,
                        contentDescription = "Command executing",
                        tint = animatedColor,
                        modifier = Modifier
                            .size(44.dp)
                            .rotate(continuousRotation)
                    )
                }
                VisualBrainState.COMPLETED -> {
                    // Cyan confirmation burst
                    Icon(
                        imageVector = Icons.Default.Check,
                        contentDescription = "Operation completed",
                        tint = animatedColor,
                        modifier = Modifier.size(48.dp)
                    )
                }
                VisualBrainState.ERROR -> {
                    // Red warning / attention core
                    Icon(
                        imageVector = Icons.Default.PriorityHigh,
                        contentDescription = "Attention required",
                        tint = animatedColor,
                        modifier = Modifier.size(44.dp)
                    )
                }
            }
        }
    }
}
