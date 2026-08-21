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
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.overlay.OverlayEventAction
import com.animus.smartroom.core.overlay.OverlayEventPolicy
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.overlay.model.CorrelatedCommandCard
import com.animus.smartroom.overlay.model.FloatingOverlayState
import com.animus.smartroom.overlay.model.FloatingOverlayVisibility
import com.animus.smartroom.overlay.model.OverlayMusicSummary
import com.animus.smartroom.overlay.model.OverlayTimerCard
import com.animus.smartroom.overlay.model.SubActionItem
import com.animus.smartroom.overlay.storage.OverlayPositionStorage
import com.animus.smartroom.overlay.ui.FloatingControlSurface
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlin.math.abs

/**
 * Floating overlay service that hosts [FloatingControlSurface] in the WindowManager.
 *
 * Implements:
 * 1. Explicit visibility state machine: HIDDEN, COLLAPSED, EXPANDED, MUSIC_PERSISTENT, LISTENING.
 * 2. Auto-collapse after 8s of inactivity, auto-hide after 45s of inactivity (unless in MUSIC_PERSISTENT or active timer).
 * 3. Event-driven wakeup via [OverlayEventPolicy].
 * 4. Music persistent companion mode for YouTube Music foreground execution.
 * 5. Uses shared application [AnimusApplication.voiceInputPort] for background speech recognition.
 */
class FloatingAnimusService : Service(), LifecycleOwner, SavedStateRegistryOwner {

    companion object {
        private const val TAG = "FloatingAnimusService"

        const val ACTION_START = "com.animus.smartroom.action.START_FLOATING_OVERLAY"
        const val ACTION_STOP = "com.animus.smartroom.action.STOP_FLOATING_OVERLAY"

        const val AUTO_COLLAPSE_DELAY_MS = 8_000L
        const val AUTO_HIDE_DELAY_MS = 45_000L

        @Volatile
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

    private val _overlayState = MutableStateFlow(FloatingOverlayState())
    val overlayState: StateFlow<FloatingOverlayState> = _overlayState.asStateFlow()

    private var autoCollapseJob: Job? = null
    private var autoHideJob: Job? = null

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

        initVoiceObserver()
        initOverlayWindow()
        observeEventStreams()
        startInactivityTimers()
    }

    private fun initVoiceObserver() {
        val app = application as? AnimusApplication ?: return
        serviceScope.launch {
            app.voiceInputPort.state.collectLatest { voiceState ->
                _overlayState.update { current ->
                    val newVisibility = when (voiceState) {
                        is VoicePortState.Listening,
                        is VoicePortState.Recognizing -> FloatingOverlayVisibility.LISTENING
                        is VoicePortState.Success -> FloatingOverlayVisibility.EXPANDED
                        is VoicePortState.Error -> {
                            if (current.isMusicPersistent) FloatingOverlayVisibility.MUSIC_PERSISTENT
                            else FloatingOverlayVisibility.COLLAPSED
                        }
                        is VoicePortState.Idle -> {
                            if (current.visibility == FloatingOverlayVisibility.LISTENING) {
                                if (current.isMusicPersistent) FloatingOverlayVisibility.MUSIC_PERSISTENT
                                else FloatingOverlayVisibility.COLLAPSED
                            } else {
                                current.visibility
                            }
                        }
                        else -> current.visibility
                    }

                    current.copy(
                        voiceState = voiceState,
                        visibility = newVisibility,
                        lastMeaningfulEventTimestamp = System.currentTimeMillis()
                    )
                }
                resetInactivityTimers()
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

        // 1. Observe DiagnosticBus.actionEvents
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
                        targetTimestamp = it.scheduledExecutionTimeMillis,
                        formattedTargetTime = ""
                    )
                }

                _overlayState.update { it.copy(activeTimer = timerCard) }
                if (timerCard != null && _overlayState.value.visibility == FloatingOverlayVisibility.HIDDEN) {
                    _overlayState.update { it.copy(visibility = FloatingOverlayVisibility.COLLAPSED) }
                }
            }
        }

        // 3. Observe MusicUiState for persistent music mode
        serviceScope.launch {
            app.musicController.uiState.collectLatest { musicUi ->
                val isPlaying = musicUi.playbackStatus == com.animus.smartroom.media.model.PlaybackStatus.PLAYING
                val summary = OverlayMusicSummary(
                    trackTitle = musicUi.currentTrackTitle,
                    outputDeviceName = musicUi.activeOutputDeviceName,
                    isConnected = musicUi.isOutputConnected,
                    isPlaying = isPlaying
                )

                _overlayState.update { current ->
                    val newVisibility = when {
                        isPlaying && current.visibility == FloatingOverlayVisibility.HIDDEN -> FloatingOverlayVisibility.MUSIC_PERSISTENT
                        isPlaying && current.visibility == FloatingOverlayVisibility.COLLAPSED -> FloatingOverlayVisibility.MUSIC_PERSISTENT
                        !isPlaying && current.visibility == FloatingOverlayVisibility.MUSIC_PERSISTENT -> FloatingOverlayVisibility.COLLAPSED
                        else -> current.visibility
                    }

                    current.copy(
                        musicSummary = summary,
                        visibility = newVisibility,
                        lastMeaningfulEventTimestamp = System.currentTimeMillis()
                    )
                }
                resetInactivityTimers()
            }
        }

        // 4. Observe Bluetooth connection state
        serviceScope.launch {
            app.bluetoothController.uiState.collectLatest { btUi ->
                val isConnected = btUi.connectionState is BluetoothDeviceState.Connected
                val devName = btUi.selectedDevice?.displayName
                    ?: if (isConnected) (btUi.connectionState as BluetoothDeviceState.Connected).deviceName else null

                _overlayState.update { current ->
                    current.copy(
                        musicSummary = current.musicSummary.copy(
                            outputDeviceName = devName ?: current.musicSummary.outputDeviceName,
                            isConnected = isConnected
                        )
                    )
                }
            }
        }
    }

    private fun processActionEvents(events: List<AnimusActionEvent>) {
        if (events.isEmpty()) return

        val latestEvent = events.last()
        val isMusicPlaying = _overlayState.value.musicSummary.isPlaying
        val eventAction = OverlayEventPolicy.evaluate(latestEvent, isMusicPlaying)

        if (eventAction == OverlayEventAction.IGNORE) return

        // Multi-command grouping by correlation ID
        val corrId = latestEvent.correlationId
        val relatedEvents = if (corrId != null) {
            events.filter { it.correlationId == corrId }
        } else {
            listOf(latestEvent)
        }

        val subActions = relatedEvents
            .distinctBy { "${it.targetDevice}_${it.action}" }
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

        val hasFailure = subActions.any { it.status == ActionStatus.FAILED }
        val allCompleted = subActions.all {
            it.status == ActionStatus.SUCCESS || it.status == ActionStatus.NO_CHANGE || it.status == ActionStatus.FAILED
        }

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

        _overlayState.update { current ->
            val targetVisibility = when (eventAction) {
                OverlayEventAction.SURFACE_IMMEDIATELY,
                OverlayEventAction.SURFACE_TIMER_COMPLETION -> FloatingOverlayVisibility.EXPANDED
                OverlayEventAction.SURFACE_MUSIC_PERSISTENT -> FloatingOverlayVisibility.MUSIC_PERSISTENT
                OverlayEventAction.SHOW_ONLY_IF_VISIBLE -> current.visibility
                OverlayEventAction.IGNORE -> current.visibility
            }

            current.copy(
                activeCommandCard = commandCard,
                recentCompletedActions = completed,
                visibility = if (current.visibility == FloatingOverlayVisibility.HIDDEN && eventAction != OverlayEventAction.SHOW_ONLY_IF_VISIBLE)
                    targetVisibility else current.visibility,
                isExpanded = (targetVisibility == FloatingOverlayVisibility.EXPANDED),
                lastMeaningfulEventTimestamp = System.currentTimeMillis()
            )
        }

        resetInactivityTimers()
    }

    private fun startInactivityTimers() {
        resetInactivityTimers()
    }

    private fun resetInactivityTimers() {
        autoCollapseJob?.cancel()
        autoHideJob?.cancel()

        // 1. Auto-collapse after 8s if in EXPANDED state
        autoCollapseJob = serviceScope.launch {
            delay(AUTO_COLLAPSE_DELAY_MS)
            _overlayState.update { current ->
                if (current.visibility == FloatingOverlayVisibility.EXPANDED || current.isExpanded) {
                    val nextVis = if (current.musicSummary.isPlaying)
                        FloatingOverlayVisibility.MUSIC_PERSISTENT
                    else
                        FloatingOverlayVisibility.COLLAPSED
                    current.copy(visibility = nextVis, isExpanded = false)
                } else {
                    current
                }
            }
        }

        // 2. Auto-hide after 45s of total inactivity (unless in MUSIC_PERSISTENT or active timer)
        autoHideJob = serviceScope.launch {
            delay(AUTO_HIDE_DELAY_MS)
            _overlayState.update { current ->
                val canHide = !current.musicSummary.isPlaying &&
                        current.activeTimer == null &&
                        current.voiceState is VoicePortState.Idle

                if (canHide && current.visibility != FloatingOverlayVisibility.HIDDEN) {
                    current.copy(visibility = FloatingOverlayVisibility.HIDDEN, isExpanded = false)
                } else {
                    current
                }
            }
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
        _overlayState.update { current ->
            val nextExpanded = !current.isExpanded
            val nextVis = if (nextExpanded) FloatingOverlayVisibility.EXPANDED
            else if (current.musicSummary.isPlaying) FloatingOverlayVisibility.MUSIC_PERSISTENT
            else FloatingOverlayVisibility.COLLAPSED

            current.copy(isExpanded = nextExpanded, visibility = nextVis)
        }
        resetInactivityTimers()
    }

    private fun handleMicClick() {
        val app = application as? AnimusApplication ?: return
        val currentVoiceState = _overlayState.value.voiceState
        if (currentVoiceState is VoicePortState.Listening) {
            app.voiceInputPort.stopListening()
        } else {
            _overlayState.update { it.copy(visibility = FloatingOverlayVisibility.LISTENING) }
            app.voiceInputPort.startListening()
        }
        resetInactivityTimers()
    }

    private fun cancelScheduledTimer(actionId: String) {
        val app = application as? AnimusApplication ?: return
        serviceScope.launch {
            app.runtimeControlPort.cancelAction(actionId)
        }
        resetInactivityTimers()
    }

    private fun openMainActivity() {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        startActivity(intent)
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
                _overlayState.update { it.copy(visibility = FloatingOverlayVisibility.COLLAPSED) }
                resetInactivityTimers()
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
