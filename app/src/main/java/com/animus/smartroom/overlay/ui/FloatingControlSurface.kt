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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.model.SubActionItem

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
    if (state.visibility == FloatingOverlayVisibility.HIDDEN) {
        // Render nothing / 0 size when hidden
        Spacer(modifier = Modifier.size(0.dp))
        return
    }

    Box(
        modifier = modifier
            .wrapContentSize()
            .clip(RoundedCornerShape(20.dp))
            .background(GlassSurfaceBg)
    ) {
        when {
            state.visibility == FloatingOverlayVisibility.COLLAPSED -> {
                CollapsedOverlayView(
                    state = state,
                    onToggleExpand = onToggleExpand,
                    onMicClick = onMicClick
                )
            }
            state.visibility == FloatingOverlayVisibility.MUSIC_PERSISTENT && !state.isExpanded -> {
                MusicCollapsedOverlayView(
                    state = state,
                    onToggleExpand = onToggleExpand,
                    onMicClick = onMicClick
                )
            }
            else -> {
                // EXPANDED or MUSIC_PERSISTENT with expanded true or LISTENING
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
                state.voiceState is VoicePortState.Listening -> RedAccent
                state.voiceState is VoicePortState.Recognizing -> AmberAccent
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
                        if (state.voiceState is VoicePortState.Listening)
                            dotColor.copy(alpha = pulseAlpha)
                        else
                            dotColor
                    )
            )

            // Short status pill text
            val pillText = when {
                state.voiceState is VoicePortState.Listening -> "Listening..."
                state.voiceState is VoicePortState.Recognizing -> "Processing..."
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
fun MusicCollapsedOverlayView(
    state: FloatingOverlayState,
    onToggleExpand: () -> Unit,
    onMicClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(24.dp),
        color = GlassSurfaceBg,
        border = BorderStroke(1.dp, CyanAccent.copy(alpha = 0.6f)),
        modifier = modifier
            .semantics { contentDescription = "Animus Music Floating Pill" }
            .clickable { onToggleExpand() }
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        ) {
            Icon(
                imageVector = Icons.Default.MusicNote,
                contentDescription = null,
                tint = CyanAccent,
                modifier = Modifier.size(16.dp)
            )

            val track = state.musicSummary.trackTitle ?: "Music"
            val dev = state.musicSummary.outputDeviceName ?: "Speaker"
            val text = "$track • $dev"

            Text(
                text = EventSanitizer.sanitizeText(text) ?: "Music",
                color = Color.White,
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )

            Box(
                modifier = Modifier
                    .size(30.dp)
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
                    modifier = Modifier.size(16.dp)
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
            // Drag Handle & Header Row
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Visual drag pill handle
                Box(
                    modifier = Modifier
                        .size(width = 36.dp, height = 4.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(Color.White.copy(alpha = 0.3f))
                )
                Spacer(modifier = Modifier.height(6.dp))

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
            }

            // Voice Interaction Bar
            VoiceInputSection(
                voiceState = state.voiceState,
                isVoiceProcessing = state.isVoiceProcessing,
                onMicClick = onMicClick
            )

            // Active Correlated Command Card
            state.activeCommandCard?.let { card ->
                CorrelatedCommandCardView(card = card)
            }

            // Active Scheduled Timer Card
            state.activeTimer?.let { timer ->
                OverlayTimerCardView(
                    timer = timer,
                    onCancel = { onCancelTimer(timer.actionId) }
                )
            }

            // Music Summary Card
            if (state.musicSummary.isPlaying || !state.musicSummary.trackTitle.isNullOrBlank()) {
                MusicSummaryCardView(summary = state.musicSummary)
            }
        }
    }
}

@Composable
fun VoiceInputSection(
    voiceState: VoicePortState,
    isVoiceProcessing: Boolean,
    onMicClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0x221E293B),
        border = BorderStroke(1.dp, GlassBorderColor.copy(alpha = 0.3f)),
        modifier = modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 10.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                val promptText = when (voiceState) {
                    is VoicePortState.Listening -> "Listening for command..."
                    is VoicePortState.Recognizing -> voiceState.partialText ?: "Processing speech..."
                    is VoicePortState.Success -> "“${voiceState.recognizedText}”"
                    is VoicePortState.Error -> voiceState.message
                    else -> if (isVoiceProcessing) "Executing command..." else "Tap mic to speak"
                }

                Text(
                    text = EventSanitizer.sanitizeText(promptText) ?: "",
                    color = when (voiceState) {
                        is VoicePortState.Listening -> CyanAccent
                        is VoicePortState.Error -> RedAccent
                        else -> Color.White.copy(alpha = 0.8f)
                    },
                    fontSize = 12.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }

            IconButton(
                onClick = onMicClick,
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(
                        if (voiceState is VoicePortState.Listening) RedAccent.copy(alpha = 0.25f)
                        else CyanAccent.copy(alpha = 0.2f)
                    )
                    .semantics { contentDescription = "Activate Voice Command" }
            ) {
                Icon(
                    imageVector = if (voiceState is VoicePortState.Listening) Icons.Default.MicOff else Icons.Default.Mic,
                    contentDescription = null,
                    tint = if (voiceState is VoicePortState.Listening) RedAccent else CyanAccent,
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}

@Composable
fun CorrelatedCommandCardView(
    card: com.animus.smartroom.overlay.model.CorrelatedCommandCard,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0x330F172A),
        border = BorderStroke(1.dp, GlassBorderColor.copy(alpha = 0.5f)),
        modifier = modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "COMMAND RESULT",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = CyanAccent,
                    letterSpacing = 0.5.sp
                )

                val statusText = when (card.overallStatus) {
                    ActionStatus.SUCCESS -> "VERIFIED"
                    ActionStatus.FAILED -> "FAILED"
                    ActionStatus.IN_PROGRESS -> "RUNNING"
                    else -> "PENDING"
                }

                val statusColor = when (card.overallStatus) {
                    ActionStatus.SUCCESS -> GreenAccent
                    ActionStatus.FAILED -> RedAccent
                    else -> AmberAccent
                }

                Text(
                    text = statusText,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = statusColor
                )
            }

            // Sub-Actions List
            card.subActions.forEach { sub ->
                SubActionRow(subAction = sub)
            }
        }
    }
}

@Composable
fun SubActionRow(
    subAction: SubActionItem,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        val (icon, color) = when (subAction.status) {
            ActionStatus.SUCCESS -> Icons.Default.CheckCircle to GreenAccent
            ActionStatus.FAILED -> Icons.Default.Error to RedAccent
            ActionStatus.NO_CHANGE -> Icons.Default.CheckCircle to GreenAccent
            else -> Icons.Default.HourglassEmpty to AmberAccent
        }

        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = color,
            modifier = Modifier.size(14.dp)
        )

        Text(
            text = EventSanitizer.sanitizeText(subAction.description) ?: "",
            color = Color.White,
            fontSize = 12.sp,
            modifier = Modifier.weight(1f),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )

        if (subAction.verified) {
            Text(
                text = "✓ Verified",
                color = GreenAccent,
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium
            )
        }
    }
}

@Composable
fun OverlayTimerCardView(
    timer: com.animus.smartroom.overlay.model.OverlayTimerCard,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0x330F172A),
        border = BorderStroke(1.dp, CyanAccent.copy(alpha = 0.4f)),
        modifier = modifier.fillMaxWidth()
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
                    modifier = Modifier.size(18.dp)
                )

                Column {
                    Text(
                        text = "AC TIMER",
                        fontSize = 10.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color.White.copy(alpha = 0.7f),
                        letterSpacing = 0.5.sp
                    )
                    Text(
                        text = timer.formattedRemaining(),
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = CyanAccent
                    )
                }
            }

            Button(
                onClick = onCancel,
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = RedAccent.copy(alpha = 0.2f),
                    contentColor = RedAccent
                ),
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                modifier = Modifier
                    .height(28.dp)
                    .semantics { contentDescription = "Cancel Active Timer" }
            ) {
                Text(
                    text = "CANCEL",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
fun MusicSummaryCardView(
    summary: com.animus.smartroom.overlay.model.OverlayMusicSummary,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = Color(0x330F172A),
        border = BorderStroke(1.dp, GlassBorderColor.copy(alpha = 0.4f)),
        modifier = modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Icon(
                imageVector = Icons.Default.MusicNote,
                contentDescription = null,
                tint = CyanAccent,
                modifier = Modifier.size(20.dp)
            )

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = EventSanitizer.sanitizeText(summary.trackTitle ?: "No Music") ?: "No Music",
                    color = Color.White,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                val outputText = if (summary.isConnected) {
                    "${summary.outputDeviceName ?: "Speaker"} • Connected"
                } else if (!summary.outputDeviceName.isNullOrBlank()) {
                    "⚠ ${summary.outputDeviceName} disconnected"
                } else {
                    "No speaker"
                }

                Text(
                    text = EventSanitizer.sanitizeText(outputText) ?: "",
                    color = if (summary.isConnected) GreenAccent else AmberAccent,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }
}
