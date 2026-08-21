package com.animus.smartroom.overlay.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.*
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.SubActionItem
import com.animus.smartroom.voice.VoiceInputState
import kotlinx.coroutines.delay

private val GlassSurfaceBg = Color(0xF212141A)
private val GlassBorderColor = Color(0x3338BDF8)
private val CyanAccent = Color(0xFF38BDF8)
private val GreenAccent = Color(0xFF4ADE80)
private val AmberAccent = Color(0xFFFBBF24)
private val RedAccent = Color(0xFFF87171)

@Composable
fun FloatingControlSurface(
    state: FloatingOverlayState,
    onToggleExpand: () -> Unit,
    onMicClick: () -> Unit,
    onCancelTimer: (String) -> Unit,
    onOpenApp: () -> Unit,
    onCloseOverlay: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .wrapContentSize()
            .clip(RoundedCornerShape(20.dp))
            .background(GlassSurfaceBg)
    ) {
        if (!state.isExpanded) {
            CollapsedOverlayView(
                state = state,
                onToggleExpand = onToggleExpand,
                onMicClick = onMicClick
            )
        } else {
            ExpandedOverlayView(
                state = state,
                onToggleExpand = onToggleExpand,
                onMicClick = onMicClick,
                onCancelTimer = onCancelTimer,
                onOpenApp = onOpenApp,
                onCloseOverlay = onCloseOverlay
            )
        }
    }
}

@Composable
fun CollapsedOverlayView(
    state: FloatingOverlayState,
    onToggleExpand: () -> Unit,
    onMicClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulseAlpha"
    )

    Surface(
        shape = RoundedCornerShape(24.dp),
        color = GlassSurfaceBg,
        border = BorderStroke(1.dp, GlassBorderColor),
        modifier = modifier
            .semantics { contentDescription = "Animus Floating Surface Collapsed" }
            .clickable { onToggleExpand() }
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 4.dp)
        ) {
            // Status Dot
            val dotColor = when {
                state.voiceState is VoiceInputState.Listening -> RedAccent
                state.voiceState is VoiceInputState.Recognizing -> AmberAccent
                state.activeTimer != null -> CyanAccent
                state.activeCommandCard?.overallStatus == ActionStatus.IN_PROGRESS -> AmberAccent
                state.activeCommandCard?.overallStatus == ActionStatus.SUCCESS -> GreenAccent
                else -> CyanAccent
            }

            Box(
                modifier = Modifier
                    .size(10.dp)
                    .clip(CircleShape)
                    .background(
                        if (state.voiceState is VoiceInputState.Listening)
                            dotColor.copy(alpha = pulseAlpha)
                        else
                            dotColor
                    )
            )

            // Short status pill text
            val pillText = when {
                state.voiceState is VoiceInputState.Listening -> "Listening..."
                state.voiceState is VoiceInputState.Recognizing -> "Processing..."
                state.activeTimer != null -> "⏱ ${state.activeTimer.formattedRemaining()}"
                state.activeCommandCard != null -> {
                    val first = state.activeCommandCard.subActions.firstOrNull()
                    if (first != null) "✓ ${first.description}" else "Animus"
                }
                state.musicSummary.isPlaying && !state.musicSummary.trackTitle.isNullOrBlank() ->
                    "♪ ${state.musicSummary.trackTitle}"
                else -> "Animus"
            }

            Text(
                text = EventSanitizer.sanitizeText(pillText) ?: "Animus",
                color = Color.White,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            // Direct mic trigger button on collapsed pill
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(CyanAccent.copy(alpha = 0.2f))
                    .clickable { onMicClick() }
                    .semantics { contentDescription = "Activate Voice Command" },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Mic,
                    contentDescription = null,
                    tint = CyanAccent,
                    modifier = Modifier.size(18.dp)
                )
            }
        }
    }
}

@Composable
fun ExpandedOverlayView(
    state: FloatingOverlayState,
    onToggleExpand: () -> Unit,
    onMicClick: () -> Unit,
    onCancelTimer: (String) -> Unit,
    onOpenApp: () -> Unit,
    onCloseOverlay: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(20.dp),
        color = GlassSurfaceBg,
        border = BorderStroke(1.dp, GlassBorderColor),
        modifier = modifier
            .widthIn(min = 280.dp, max = 340.dp)
            .padding(12.dp)
            .semantics { contentDescription = "Animus Floating Surface Expanded" }
    ) {
        Column(
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            // Header Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .clip(CircleShape)
                            .background(CyanAccent)
                    )
                    Text(
                        text = "ANIMUS",
                        color = Color.White,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 1.sp
                    )
                }

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    IconButton(
                        onClick = onOpenApp,
                        modifier = Modifier
                            .size(32.dp)
                            .semantics { contentDescription = "Open Full Animus App" }
                    ) {
                        Icon(
                            imageVector = Icons.Default.OpenInNew,
                            contentDescription = null,
                            tint = CyanAccent,
                            modifier = Modifier.size(18.dp)
                        )
                    }

                    IconButton(
                        onClick = onToggleExpand,
                        modifier = Modifier
                            .size(32.dp)
                            .semantics { contentDescription = "Collapse Floating Overlay" }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = null,
                            tint = Color.White.copy(alpha = 0.7f),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            // Voice Command Banner / Prompt
            VoiceStateSection(
                voiceState = state.voiceState,
                onMicClick = onMicClick
            )

            // Correlated Command Execution Card (if available)
            if (state.activeCommandCard != null) {
                CorrelatedCommandView(card = state.activeCommandCard)
            } else if (state.recentCompletedActions.isNotEmpty()) {
                RecentActionsView(actions = state.recentCompletedActions)
            }

            // Active Scheduler Countdown Card
            if (state.activeTimer != null) {
                ActiveTimerView(
                    timer = state.activeTimer,
                    onCancel = { onCancelTimer(state.activeTimer.actionId) }
                )
            }

            // Music / Output Status Card
            if (state.musicSummary.isPlaying || state.musicSummary.outputDeviceName != null) {
                MusicSummaryView(summary = state.musicSummary)
            }

            // Bottom Actions Bar
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Button(
                    onClick = onMicClick,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = CyanAccent.copy(alpha = 0.2f),
                        contentColor = CyanAccent
                    ),
                    shape = RoundedCornerShape(12.dp),
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp),
                    modifier = Modifier.semantics { contentDescription = "Tap to Speak Voice Command" }
                ) {
                    Icon(
                        imageVector = Icons.Default.Mic,
                        contentDescription = null,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = when (state.voiceState) {
                            is VoiceInputState.Listening -> "Listening..."
                            is VoiceInputState.Recognizing -> "Thinking..."
                            else -> "Voice Command"
                        },
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }

                TextButton(
                    onClick = onOpenApp,
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                    modifier = Modifier.semantics { contentDescription = "Open Animus Main App" }
                ) {
                    Text(
                        text = "OPEN APP",
                        color = CyanAccent,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

@Composable
fun VoiceStateSection(
    voiceState: VoiceInputState,
    onMicClick: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E222D),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(
                        when (voiceState) {
                            is VoiceInputState.Listening -> RedAccent.copy(alpha = 0.25f)
                            is VoiceInputState.Recognizing -> AmberAccent.copy(alpha = 0.25f)
                            else -> CyanAccent.copy(alpha = 0.15f)
                        }
                    )
                    .clickable { onMicClick() },
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Mic,
                    contentDescription = "Microphone",
                    tint = when (voiceState) {
                        is VoiceInputState.Listening -> RedAccent
                        is VoiceInputState.Recognizing -> AmberAccent
                        else -> CyanAccent
                    },
                    modifier = Modifier.size(20.dp)
                )
            }

            Column(modifier = Modifier.weight(1f)) {
                val label = when (voiceState) {
                    is VoiceInputState.Listening -> "🎙 Listening for command..."
                    is VoiceInputState.Recognizing -> "⌛ Understanding..."
                    is VoiceInputState.Error -> "⚠ ${EventSanitizer.sanitizeText(voiceState.message)}"
                    is VoiceInputState.Unavailable -> "Mic unavailable"
                    else -> "Tap mic to speak to Animus"
                }

                Text(
                    text = label,
                    color = when (voiceState) {
                        is VoiceInputState.Error -> RedAccent
                        is VoiceInputState.Listening -> RedAccent
                        is VoiceInputState.Recognizing -> AmberAccent
                        else -> Color.White.copy(alpha = 0.85f)
                    },
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}

@Composable
fun CorrelatedCommandView(
    card: com.animus.smartroom.overlay.model.CorrelatedCommandCard
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E222D),
        border = BorderStroke(1.dp, Color(0x2238BDF8)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            if (!card.rawPrompt.isNullOrBlank()) {
                Text(
                    text = "🎙 \"${EventSanitizer.sanitizeText(card.rawPrompt)}\"",
                    color = CyanAccent,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Divider(color = Color(0x22FFFFFF), thickness = 0.5.dp)
            }

            card.subActions.forEach { sub ->
                SubActionRow(sub = sub)
            }

            // Overall Status footer if multi-action
            if (card.subActions.size > 1) {
                val overallText = when (card.overallStatus) {
                    ActionStatus.SUCCESS -> "✓ All actions completed"
                    ActionStatus.FAILED -> "⚠ Completed with partial failure"
                    ActionStatus.IN_PROGRESS -> "⚙ Executing actions..."
                    else -> "✓ Finished"
                }
                Text(
                    text = overallText,
                    color = when (card.overallStatus) {
                        ActionStatus.SUCCESS -> GreenAccent
                        ActionStatus.FAILED -> AmberAccent
                        else -> CyanAccent
                    },
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}

@Composable
fun SubActionRow(sub: SubActionItem) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            val iconTint = when (sub.status) {
                ActionStatus.SUCCESS -> GreenAccent
                ActionStatus.FAILED -> RedAccent
                ActionStatus.IN_PROGRESS -> AmberAccent
                ActionStatus.NO_CHANGE -> CyanAccent
                else -> Color.White.copy(alpha = 0.7f)
            }

            val icon = when (sub.status) {
                ActionStatus.SUCCESS -> Icons.Default.CheckCircle
                ActionStatus.FAILED -> Icons.Default.Warning
                ActionStatus.IN_PROGRESS -> Icons.Default.HourglassEmpty
                ActionStatus.NO_CHANGE -> Icons.Default.Info
                else -> Icons.Default.Check
            }

            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = iconTint,
                modifier = Modifier.size(14.dp)
            )

            Text(
                text = EventSanitizer.sanitizeText(sub.description) ?: "",
                color = Color.White.copy(alpha = 0.9f),
                fontSize = 12.sp,
                fontWeight = FontWeight.Normal,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }

        if (sub.verified) {
            Text(
                text = "Verified",
                color = GreenAccent,
                fontSize = 10.sp,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

@Composable
fun RecentActionsView(actions: List<SubActionItem>) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E222D),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text(
                text = "Recent Activity",
                color = Color.White.copy(alpha = 0.5f),
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold
            )
            actions.take(3).forEach { sub ->
                SubActionRow(sub = sub)
            }
        }
    }
}

@Composable
fun ActiveTimerView(
    timer: com.animus.smartroom.overlay.model.OverlayTimerCard,
    onCancel: () -> Unit
) {
    // Local ticker that updates every second without publishing DiagnosticBus events
    var remainingText by remember(timer) { mutableStateOf(timer.formattedRemaining()) }

    LaunchedEffect(timer) {
        while (true) {
            delay(1000L)
            remainingText = timer.formattedRemaining()
        }
    }

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E222D),
        border = BorderStroke(1.dp, CyanAccent.copy(alpha = 0.3f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.Timer,
                    contentDescription = null,
                    tint = CyanAccent,
                    modifier = Modifier.size(20.dp)
                )
                Column {
                    Text(
                        text = "⏱ AC Timer: $remainingText",
                        color = Color.White,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Action: ${timer.actionType.replace("_", " ")}",
                        color = Color.White.copy(alpha = 0.6f),
                        fontSize = 11.sp
                    )
                }
            }

            TextButton(
                onClick = onCancel,
                colors = ButtonDefaults.textButtonColors(contentColor = RedAccent),
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                modifier = Modifier.semantics { contentDescription = "Cancel Active Timer" }
            ) {
                Text(
                    text = "CANCEL",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
fun MusicSummaryView(
    summary: com.animus.smartroom.overlay.model.OverlayMusicSummary
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = Color(0xFF1E222D),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(
                imageVector = Icons.Default.MusicNote,
                contentDescription = null,
                tint = CyanAccent,
                modifier = Modifier.size(18.dp)
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = summary.trackTitle ?: "Audio Output",
                    color = Color.White,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = if (summary.outputDeviceName != null) {
                        "${summary.outputDeviceName} • ${if (summary.isConnected) "Connected" else "Disconnected"}"
                    } else {
                        "Output speaker ready"
                    },
                    color = if (summary.isConnected) GreenAccent else Color.White.copy(alpha = 0.5f),
                    fontSize = 11.sp
                )
            }
        }
    }
}
