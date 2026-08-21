package com.animus.smartroom.overlay.service

import android.annotation.SuppressLint
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.util.DisplayMetrics
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.ComposeView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.setViewTreeLifecycleOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner
import com.animus.smartroom.AnimusApplication
import com.animus.smartroom.MainActivity
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.overlay.model.*
import com.animus.smartroom.overlay.storage.OverlayPositionStorage
import com.animus.smartroom.overlay.ui.FloatingControlSurface
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.voice.SpeechRecognitionManager
import com.animus.smartroom.voice.VoiceInputState
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlin.math.abs

/**
 * Foreground / Overlay Service responsible for displaying the Animus Floating Control Surface.
 * Uses WindowManager TYPE_APPLICATION_OVERLAY and ComposeView.
 * It is strictly a client of AnimusRuntime, DiagnosticBus 2.0, and RuntimeControlPort.
 */
class FloatingAnimusService : Service(), LifecycleOwner, SavedStateRegistryOwner {

    companion object {
        private const val TAG = "FloatingAnimusService"
        const val ACTION_START = "com.animus.smartroom.ACTION_START_FLOATING_OVERLAY"
        const val ACTION_STOP = "com.animus.smartroom.ACTION_STOP_FLOATING_OVERLAY"

        var isRunning: Boolean = false
            private set

        fun startIntent(context: Context): Intent =
            Intent(context, FloatingAnimusService::class.java).apply { action = ACTION_START }

        fun stopIntent(context: Context): Intent =
            Intent(context, FloatingAnimusService::class.java).apply { action = ACTION_STOP }
    }

    private val lifecycleRegistry = LifecycleRegistry(this)
    private val savedStateRegistryController = SavedStateRegistryController.create(this)

    override val lifecycle: Lifecycle get() = lifecycleRegistry
    override val savedStateRegistry: SavedStateRegistry get() = savedStateRegistryController.savedStateRegistry

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private var layoutParams: WindowManager.LayoutParams? = null

    private lateinit var positionStorage: OverlayPositionStorage
    private var speechRecognitionManager: SpeechRecognitionManager? = null

    private val _overlayState = MutableStateFlow(FloatingOverlayState())
    val overlayState: StateFlow<FloatingOverlayState> = _overlayState.asStateFlow()

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "[overlay] onCreate")
        isRunning = true
        savedStateRegistryController.performRestore(null)
        lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_CREATE)
        lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_START)
        lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_RESUME)

        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        positionStorage = OverlayPositionStorage(this)

        initSpeechRecognizer()
        initOverlayWindow()
        observeEventStreams()
    }

    private fun initSpeechRecognizer() {
        speechRecognitionManager = SpeechRecognitionManager(this) { spokenText ->
            Log.i(TAG, "[overlay] Voice input recognized: '$spokenText'")
            val app = application as? AnimusApplication
            app?.let {
                serviceScope.launch {
                    _overlayState.update { it.copy(isVoiceProcessing = true) }
                    it.runtimeControlPort.submitCommand(spokenText)
                    _overlayState.update { it.copy(isVoiceProcessing = false) }
                }
            }
        }

        // Observe voice states
        serviceScope.launch {
            speechRecognitionManager?.state?.collectLatest { voiceState ->
                _overlayState.update { it.copy(voiceState = voiceState) }
            }
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun initOverlayWindow() {
        val wm = windowManager ?: return

        val displayMetrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        wm.defaultDisplay.getMetrics(displayMetrics)
        val screenWidth = displayMetrics.widthPixels
        val screenHeight = displayMetrics.heightPixels

        val initialPos = positionStorage.getPosition(screenWidth, screenHeight)

        val windowType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            windowType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                    WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = initialPos.x
            y = initialPos.y
        }
        layoutParams = params

        val composeView = ComposeView(this).apply {
            setViewTreeLifecycleOwner(this@FloatingAnimusService)
            setViewTreeSavedStateRegistryOwner(this@FloatingAnimusService)
            setContent {
                val state by overlayState.collectAsState()
                FloatingControlSurface(
                    state = state,
                    onToggleExpand = { toggleExpand() },
                    onMicClick = { handleMicClick() },
                    onCancelTimer = { actionId -> cancelScheduledTimer(actionId) },
                    onOpenApp = { openMainActivity() },
                    onCloseOverlay = { stopSelf() }
                )
            }
        }

        // Add Drag and Touch listener to container
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f
        var isDragging = false

        composeView.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    isDragging = false
                    false
                }
                MotionEvent.ACTION_MOVE -> {
                    val deltaX = (event.rawX - initialTouchX).toInt()
                    val deltaY = (event.rawY - initialTouchY).toInt()
                    if (abs(deltaX) > 10 || abs(deltaY) > 10) {
                        isDragging = true
                        params.x = initialX + deltaX
                        params.y = initialY + deltaY
                        wm.updateViewLayout(composeView, params)
                    }
                    isDragging
                }
                MotionEvent.ACTION_UP -> {
                    if (isDragging) {
                        positionStorage.savePosition(
                            x = params.x,
                            y = params.y,
                            screenWidth = screenWidth,
                            screenHeight = screenHeight
                        )
                        true
                    } else {
                        false
                    }
                }
                else -> false
            }
        }

        overlayView = composeView
        try {
            wm.addView(composeView, params)
            Log.i(TAG, "[overlay] Floating window added to WindowManager at (${params.x}, ${params.y})")
        } catch (e: Exception) {
            Log.e(TAG, "[overlay] Failed to add floating view to WindowManager", e)
            stopSelf()
        }
    }

    private fun observeEventStreams() {
        val app = application as? AnimusApplication ?: return

        // 1. Observe DiagnosticBus.actionEvents for live command and recent action updates
        serviceScope.launch {
            DiagnosticBus.actionEvents.collectLatest { events ->
                processActionEvents(events)
            }
        }

        // 2. Observe ScheduledActionStorage for active timers
        serviceScope.launch {
            app.scheduledActionStorage.actionsFlow.collectLatest { actions ->
                val activeAcTimer = actions.firstOrNull {
                    it.targetDeviceType == DeviceType.AIR_CONDITIONER &&
                            (it.status == ScheduledActionStatus.SCHEDULED || it.status == ScheduledActionStatus.EXECUTING)
                }

                val timerCard = activeAcTimer?.let {
                    OverlayTimerCard(
                        actionId = it.id,
                        deviceType = it.targetDeviceType,
                        actionType = it.actionType.name,
                        targetTimestamp = it.scheduledExecutionTimeMillis
                    )
                }
                _overlayState.update { it.copy(activeTimer = timerCard) }
            }
        }

        // 3. Observe MusicController state
        serviceScope.launch {
            app.musicController.uiState.collectLatest { musicUi ->
                val summary = OverlayMusicSummary(
                    trackTitle = musicUi.currentTrackTitle,
                    outputDeviceName = musicUi.activeOutputDeviceName,
                    isConnected = musicUi.isOutputConnected,
                    isPlaying = musicUi.playbackStatus == com.animus.smartroom.media.model.PlaybackStatus.PLAYING
                )
                _overlayState.update { it.copy(musicSummary = summary) }
            }
        }
    }

    private fun processActionEvents(events: List<AnimusActionEvent>) {
        if (events.isEmpty()) return

        // Find most recent correlation group
        val latestEvent = events.last()
        val corrId = latestEvent.correlationId

        val correlatedGroup = if (!corrId.isNullOrBlank()) {
            events.filter { it.correlationId == corrId }
        } else {
            listOf(latestEvent)
        }

        val subActions = correlatedGroup.map { evt ->
            val description = formatEventDescription(evt)
            val isVerified = evt.metadata["verified"] == "true" || evt.stage == ActionStage.COMPLETED
            SubActionItem(
                id = evt.id,
                deviceType = evt.targetDevice,
                action = evt.action,
                description = description,
                status = evt.status,
                verified = isVerified
            )
        }

        val hasFailure = correlatedGroup.any { it.status == ActionStatus.FAILED }
        val allCompleted = correlatedGroup.all { it.stage == ActionStage.COMPLETED || it.stage == ActionStage.FAILED }
        val overallStatus = when {
            hasFailure -> ActionStatus.FAILED
            allCompleted -> ActionStatus.SUCCESS
            else -> ActionStatus.IN_PROGRESS
        }

        val commandCard = CorrelatedCommandCard(
            correlationId = corrId ?: latestEvent.id,
            rawPrompt = latestEvent.message,
            subActions = subActions,
            overallStatus = overallStatus,
            timestamp = latestEvent.timestamp
        )

        // Recent completed actions (last 4 terminal events)
        val completed = events.filter { it.stage == ActionStage.COMPLETED || it.stage == ActionStage.FAILED }
            .takeLast(4)
            .map { evt ->
                SubActionItem(
                    id = evt.id,
                    deviceType = evt.targetDevice,
                    action = evt.action,
                    description = formatEventDescription(evt),
                    status = evt.status,
                    verified = evt.metadata["verified"] == "true"
                )
            }

        _overlayState.update {
            it.copy(
                activeCommandCard = commandCard,
                recentCompletedActions = completed
            )
        }
    }

    private fun formatEventDescription(evt: AnimusActionEvent): String {
        return when {
            evt.targetDevice == DeviceType.AIR_CONDITIONER -> {
                when {
                    evt.action.contains("POWER_OFF", ignoreCase = true) -> "Bedroom AC → OFF"
                    evt.action.contains("POWER_ON", ignoreCase = true) -> "Bedroom AC → ON"
                    evt.action.contains("TEMPERATURE", ignoreCase = true) ->
                        "Bedroom AC → ${evt.metadata["temperature"] ?: "24"}°C"
                    else -> "Bedroom AC → ${evt.action.replace("_", " ")}"
                }
            }
            evt.targetDevice == DeviceType.BLUETOOTH_AUDIO -> {
                val track = evt.metadata["track"] ?: "Music"
                val dev = evt.metadata["outputDevice"] ?: "Speaker"
                "♪ $track → $dev"
            }
            else -> evt.message ?: evt.action
        }
    }

    private fun toggleExpand() {
        _overlayState.update { it.copy(isExpanded = !it.isExpanded) }
    }

    private fun handleMicClick() {
        val currentVoiceState = _overlayState.value.voiceState
        if (currentVoiceState is VoiceInputState.Listening) {
            speechRecognitionManager?.stopListening()
        } else {
            speechRecognitionManager?.startListening()
        }
    }

    private fun cancelScheduledTimer(actionId: String) {
        val app = application as? AnimusApplication ?: return
        serviceScope.launch {
            app.runtimeControlPort.cancelAction(actionId)
        }
    }

    private fun openMainActivity() {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        startActivity(intent)
        // Collapse overlay when navigating to main activity
        _overlayState.update { it.copy(isExpanded = false) }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                Log.i(TAG, "[overlay] Explicit stop requested")
                stopSelf()
                return START_NOT_STICKY
            }
            else -> {
                Log.i(TAG, "[overlay] Floating service running")
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "[overlay] onDestroy")
        isRunning = false
        lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_PAUSE)
        lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_STOP)
        lifecycleRegistry.handleLifecycleEvent(Lifecycle.Event.ON_DESTROY)

        speechRecognitionManager?.destroy()
        speechRecognitionManager = null

        overlayView?.let { view ->
            try {
                windowManager?.removeView(view)
                Log.i(TAG, "[overlay] Floating view removed from WindowManager")
            } catch (e: Exception) {
                Log.w(TAG, "[overlay] Error removing view on destroy", e)
            }
        }
        overlayView = null
        serviceScope.cancel()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
