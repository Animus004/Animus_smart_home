package com.animus.smartroom.ui.glass

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.HourglassTop
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.ui.brain.VisualBrainState

@Composable
fun TransientFeedbackOverlay(
    actionFeedback: ActionFeedback?,
    brainState: VisualBrainState = VisualBrainState.READY,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    val isVisible = actionFeedback != null && actionFeedback.message.isNotBlank()

    AnimatedVisibility(
        visible = isVisible,
        enter = fadeIn() + slideInVertically(initialOffsetY = { -30 }),
        exit = fadeOut() + slideOutVertically(targetOffsetY = { -30 }),
        modifier = modifier
    ) {
        if (actionFeedback != null) {
            val accentColor = when (actionFeedback.state) {
                ActionExecutionState.VERIFIED_SUCCESS -> GlassTokens.AccentCyan
                ActionExecutionState.ERROR_BLOCKED -> GlassTokens.AccentRed
                ActionExecutionState.RECOVERING -> GlassTokens.AccentYellow
                ActionExecutionState.EXECUTING,
                ActionExecutionState.VERIFYING -> GlassTokens.AccentBlue
                else -> when (actionFeedback.severity) {
                    FeedbackSeverity.SUCCESS -> GlassTokens.AccentCyan
                    FeedbackSeverity.ERROR -> GlassTokens.AccentRed
                    FeedbackSeverity.WARNING -> GlassTokens.AccentYellow
                    FeedbackSeverity.INFO -> GlassTokens.AccentGreen
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth(0.92f)
                    .shadow(elevation = 12.dp, shape = GlassTokens.CornerRadiusMedium, ambientColor = accentColor, spotColor = accentColor)
                    .clip(GlassTokens.CornerRadiusMedium)
                    .background(
                        Brush.verticalGradient(
                            colors = listOf(
                                GlassTokens.GlassSurfaceHover.copy(alpha = 0.92f),
                                GlassTokens.GlassSurface.copy(alpha = 0.88f)
                            )
                        )
                    )
                    .border(
                        width = 1.dp,
                        brush = Brush.linearGradient(
                            colors = listOf(
                                accentColor.copy(alpha = 0.80f),
                                accentColor.copy(alpha = 0.20f)
                            )
                        ),
                        shape = GlassTokens.CornerRadiusMedium
                    )
                    .clickable { onDismiss() }
                    .padding(horizontal = 16.dp, vertical = 12.dp),
                contentAlignment = Alignment.Center
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Icon(
                        imageVector = when (actionFeedback.state) {
                            ActionExecutionState.VERIFIED_SUCCESS -> Icons.Default.CheckCircle
                            ActionExecutionState.ERROR_BLOCKED -> Icons.Default.ErrorOutline
                            ActionExecutionState.RECOVERING -> Icons.Default.HourglassTop
                            ActionExecutionState.EXECUTING,
                            ActionExecutionState.VERIFYING -> Icons.Default.Sync
                            else -> when (actionFeedback.severity) {
                                FeedbackSeverity.SUCCESS -> Icons.Default.CheckCircle
                                FeedbackSeverity.ERROR -> Icons.Default.ErrorOutline
                                FeedbackSeverity.WARNING -> Icons.Default.HourglassTop
                                FeedbackSeverity.INFO -> Icons.Default.Info
                            }
                        },
                        contentDescription = "Feedback Status",
                        tint = accentColor,
                        modifier = Modifier.size(22.dp)
                    )

                    Text(
                        text = actionFeedback.message,
                        color = Color.White.copy(alpha = 0.95f),
                        fontSize = 13.5.sp,
                        fontWeight = FontWeight.Medium,
                        lineHeight = 19.sp,
                        textAlign = TextAlign.Start,
                        modifier = Modifier.weight(1f, fill = false)
                    )
                }
            }
        }
    }
}
