package com.animus.smartroom.ui.glass

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.animus.smartroom.bluetooth.model.BluetoothUiState
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.model.TuyaAcState
import com.animus.smartroom.media.model.MusicUiState
import com.animus.smartroom.media.model.PlaybackStatus
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import com.animus.smartroom.ui.brain.BrainStatusIndicator
import com.animus.smartroom.ui.brain.VisualBrainState
import com.animus.smartroom.voice.VoiceInputState
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun ImmersiveGlassScreen(
    visualBrainState: VisualBrainState,
    voiceState: VoiceInputState,
    isProcessing: Boolean,
    lastResultMessage: String?,
    isSuccess: Boolean?,
    operationMode: OperationMode,
    onSetOperationMode: (OperationMode) -> Unit,
    activeBrainProvider: BrainProviderType,
    onSetBrainProvider: (BrainProviderType) -> Unit,
    maskedApiKey: String?,
    onSaveApiKey: (String?) -> Unit,
    onTestApiKey: (String?, (Boolean, String) -> Unit) -> Unit,
    brainHost: String = "192.168.1.4",
    isBackendConnected: Boolean = false,
    onUpdateBrainHost: (String) -> Unit = {},
    widgetSettings: WidgetSettings,
    onToggleClock: (Boolean) -> Unit,
    onToggleWeather: (Boolean) -> Unit,
    onToggleMusic: (Boolean) -> Unit,
    onToggleTelemetry: (Boolean) -> Unit,
    isFloatingOverlayRunning: Boolean,
    onToggleFloatingOverlay: () -> Unit,
    chatHistory: List<ChatMessage>,
    onSendMessage: (String) -> Unit,
    bluetoothUiState: BluetoothUiState,
    musicUiState: MusicUiState,
    onPlayPauseClick: () -> Unit,
    onNextClick: () -> Unit,
    onPreviousClick: () -> Unit,
    onVolumeChange: (Float) -> Unit,
    onPlayPresetSong: () -> Unit,
    registeredDevices: List<RoomDevice>,
    tuyaAcState: TuyaAcState,
    isAcOperating: Boolean,
    onSetAcPower: (Boolean) -> Unit,
    onSetAcTemperature: (Int) -> Unit,
    onSetAcMode: (AcMode) -> Unit,
    onSetAcFanSpeed: (AcFanSpeed) -> Unit,
    scheduledActions: List<ScheduledDeviceAction>,
    activeRoutine: RoutineState?,
    onCancelScheduledTimer: () -> Unit,
    onCancelRoutine: () -> Unit,
    onStopAlarm: () -> Unit = {},
    onStartVoiceListening: () -> Unit,
    onStopVoiceListening: () -> Unit,
    actionFeedback: ActionFeedback? = null,
    onDismissFeedback: () -> Unit,
    roomState: com.animus.smartroom.context.model.RoomStateDto? = null,
    modifier: Modifier = Modifier
) {
    var activeTool by remember { mutableStateOf(ActiveGlassTool.NONE) }
    
    // Real-Time Clock: continuous 1-second interval ticking
    var currentTimeMs by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            currentTimeMs = System.currentTimeMillis()
            kotlinx.coroutines.delay(1000L)
        }
    }
    val timeFormat = remember { SimpleDateFormat("hh:mm a", Locale.getDefault()) }
    val dateFormat = remember { SimpleDateFormat("EEEE, d MMMM", Locale.getDefault()) }
    val currentTimeStr = timeFormat.format(Date(currentTimeMs))
    val currentDateStr = dateFormat.format(Date(currentTimeMs))

    Box(modifier = modifier.fillMaxSize()) {
        // LAYER 1: Full-Screen Reactive Ambient Lighting Canvas
        AmbientBrainLight(state = visualBrainState)

        // LAYER 2: Main Immersive Foreground
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 18.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            // TOP HEADER: Ambient intelligence status + Interactive Glass Slide Switch
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                // Left: Brain status badge & branding
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = "ANIMUS",
                        color = Color.White,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Black,
                        letterSpacing = 2.sp
                    )
                    BrainStatusIndicator(state = visualBrainState, compact = true)
                }

                // Right: Real Glass Slide Switch (LOCAL ↔ REMOTE)
                GlassSlideSwitch(
                    currentMode = operationMode,
                    onModeChanged = onSetOperationMode
                )
            }

            // OPTIONAL CANVAS WIDGET: Clock & Date (Continuous Real-Time Updates)
            if (widgetSettings.showClock) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(top = 6.dp)
                ) {
                    Text(
                        text = currentTimeStr,
                        color = Color.White.copy(alpha = 0.85f),
                        fontSize = 32.sp,
                        fontWeight = FontWeight.Light,
                        letterSpacing = 1.sp
                    )
                    Text(
                        text = currentDateStr,
                        color = Color.White.copy(alpha = 0.5f),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Normal
                    )
                }
            }

            // CENTER INTERACTION HUB: Hero Mic & Reactive Voice Feedback
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f, fill = false)
            ) {
                // Authoritative Action Feedback / Error Lifecycle Banner
                TransientFeedbackOverlay(
                    actionFeedback = actionFeedback,
                    brainState = visualBrainState,
                    onDismiss = onDismissFeedback
                )

                // Hero Mic Interaction (Interactive ONLY when READY)
                HeroMicInteraction(
                    brainState = visualBrainState,
                    voiceState = voiceState,
                    isProcessing = isProcessing,
                    onStartListening = onStartVoiceListening,
                    onStopListening = onStopVoiceListening
                )

                // Status cue subtitle strictly following VisualBrainState requirements
                val cueText = when {
                    voiceState is VoiceInputState.Listening -> "Listening to room audio..."
                    voiceState is VoiceInputState.Recognizing -> "\"${voiceState.partialText}\""
                    visualBrainState == VisualBrainState.WARMING -> "Animus is preparing."
                    visualBrainState == VisualBrainState.EXECUTING || isProcessing -> "Command executing."
                    visualBrainState == VisualBrainState.COMPLETED -> "Done."
                    visualBrainState == VisualBrainState.ERROR -> "Something needs attention."
                    else -> "Tap microphone or speak naturally"
                }

                Text(
                    text = cueText,
                    color = Color.White.copy(alpha = 0.7f),
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium
                )
            }

            // OPTIONAL ROOM CLIMATE WIDGET: Actual Room Temperature (Tuya temp_current)
            if (widgetSettings.showRoomWeather) {
                val hasLiveTelemetry = tuyaAcState.lastSeenTimestamp > 0L
                val tempDisplay = if (hasLiveTelemetry) "${tuyaAcState.ambientTemperature}°C" else "--°C"
                val tempSubtitle = if (hasLiveTelemetry) "Actual room temperature" else "Room temperature unavailable"

                Box(
                    modifier = Modifier
                        .clip(GlassTokens.CornerRadiusMedium)
                        .background(GlassTokens.GlassSurface)
                        .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
                        .clickable { activeTool = ActiveGlassTool.AC_REMOTE }
                        .padding(horizontal = 18.dp, vertical = 10.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Thermostat,
                            contentDescription = "Room Temperature",
                            tint = GlassTokens.AccentCyan,
                            modifier = Modifier.size(20.dp)
                        )
                        Column {
                            Text(
                                text = tempDisplay,
                                color = Color.White,
                                fontSize = 16.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = tempSubtitle,
                                color = Color.White.copy(alpha = 0.55f),
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Normal
                            )
                        }
                    }
                }
            } else if (widgetSettings.showQuickMusic && musicUiState.playbackStatus == PlaybackStatus.PLAYING) {
                Box(
                    modifier = Modifier
                        .clip(GlassTokens.CornerRadiusMedium)
                        .background(GlassTokens.GlassSurface)
                        .border(1.dp, GlassTokens.BorderLight, GlassTokens.CornerRadiusMedium)
                        .clickable { activeTool = ActiveGlassTool.MUSIC_CONTROLLER }
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.MusicNote,
                            contentDescription = "Music",
                            tint = GlassTokens.AccentPurple,
                            modifier = Modifier.size(16.dp)
                        )
                        Text(
                            text = musicUiState.currentTrackTitle ?: "Playing audio",
                            color = Color.White.copy(alpha = 0.9f),
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // BOTTOM GLASS APP DOCK
            GlassAppDrawer(
                activeTool = activeTool,
                onSelectTool = { activeTool = it }
            )
        }

        // LAYER 3: Modal Floating Glass Tool Panels
        AnimatedVisibility(
            visible = activeTool != ActiveGlassTool.NONE,
            enter = fadeIn() + slideInVertically(initialOffsetY = { it / 2 }),
            exit = fadeOut() + slideOutVertically(targetOffsetY = { it / 2 }),
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black.copy(alpha = 0.55f))
                .clickable { activeTool = ActiveGlassTool.NONE }
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                contentAlignment = Alignment.BottomCenter
            ) {
                when (activeTool) {
                    ActiveGlassTool.DEVICE_STATUS -> {
                        DeviceStatusPanel(
                            registeredDevices = registeredDevices,
                            tuyaAcState = tuyaAcState,
                            bluetoothUiState = bluetoothUiState,
                            roomState = roomState,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.AC_REMOTE -> {
                        GlassAcRemotePanel(
                            acState = tuyaAcState,
                            isOperating = isAcOperating,
                            onSetPower = onSetAcPower,
                            onSetTemperature = onSetAcTemperature,
                            onSetMode = onSetAcMode,
                            onSetFanSpeed = onSetAcFanSpeed,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.MUSIC_CONTROLLER -> {
                        GlassMusicControllerPanel(
                            musicState = musicUiState,
                            onPlayPauseClick = onPlayPauseClick,
                            onNextClick = onNextClick,
                            onPreviousClick = onPreviousClick,
                            onVolumeChange = onVolumeChange,
                            onPlayPresetSong = onPlayPresetSong,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.CHAT -> {
                        GlassChatPanel(
                            chatHistory = chatHistory,
                            onSendMessage = onSendMessage,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.AUTOMATIONS -> {
                        AutomationsPortalPanel(
                            scheduledActions = scheduledActions,
                            activeRoutine = activeRoutine,
                            onCancelScheduledTimer = onCancelScheduledTimer,
                            onCancelRoutine = onCancelRoutine,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.WIDGET_TOGGLE -> {
                        WidgetTogglePanel(
                            widgetSettings = widgetSettings,
                            onToggleClock = onToggleClock,
                            onToggleWeather = onToggleWeather,
                            onToggleMusic = onToggleMusic,
                            onToggleTelemetry = onToggleTelemetry,
                            onToggleFloatingOverlay = onToggleFloatingOverlay,
                            isFloatingOverlayRunning = isFloatingOverlayRunning,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.BRAIN_SWITCH -> {
                        BrainSwitchPanel(
                            currentOperationMode = operationMode,
                            onSetOperationMode = onSetOperationMode,
                            activeBrainProvider = activeBrainProvider,
                            onSetBrainProvider = onSetBrainProvider,
                            maskedApiKey = maskedApiKey,
                            onSaveApiKey = onSaveApiKey,
                            onTestApiKey = onTestApiKey,
                            brainHost = brainHost,
                            isBackendConnected = isBackendConnected,
                            onUpdateBrainHost = onUpdateBrainHost,
                            onClose = { activeTool = ActiveGlassTool.NONE }
                        )
                    }
                    ActiveGlassTool.NONE -> {}
                }
            }
        }

        // LAYER 4: Full-Screen Glass Alarm Overlay (Triggered ONLY when actively ringing)
        AnimatedVisibility(
            visible = activeRoutine != null && activeRoutine.isAlarming,
            enter = fadeIn() + slideInVertically(initialOffsetY = { -it / 3 }),
            exit = fadeOut() + slideOutVertically(targetOffsetY = { it / 3 })
        ) {
            FullScreenGlassAlarmOverlay(
                activeRoutine = activeRoutine,
                onStopAlarm = onStopAlarm
            )
        }
    }
}
