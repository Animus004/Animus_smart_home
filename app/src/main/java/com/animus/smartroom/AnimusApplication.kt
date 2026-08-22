package com.animus.smartroom

import android.app.Application
import android.content.Intent
import android.os.Build
import android.util.Log
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.device.adapter.BluetoothAudioDeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaCloudApiClient
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.routine.RoutineEngine
import com.animus.smartroom.routine.scheduler.RoutineScheduler
import com.animus.smartroom.routine.storage.RoutineStorage
import com.animus.smartroom.notification.AndroidNotificationAdapter
import com.animus.smartroom.runtime.AnimusRuntimeImpl
import com.animus.smartroom.runtime.AnimusRuntimeService
import com.animus.smartroom.runtime.RuntimeControlPortImpl
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import com.animus.smartroom.core.runtime.AnimusRuntime
import com.animus.smartroom.core.runtime.RuntimeControlPort
import com.animus.smartroom.core.port.OverlayPermissionPort
import com.animus.smartroom.overlay.permission.AndroidOverlayPermissionPort
import com.animus.smartroom.overlay.service.FloatingAnimusService
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.GeminiApiClient
import com.animus.smartroom.brain.provider.GeminiApiKeyStorage
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.media.resolver.MusicResolutionCache
import com.animus.smartroom.media.resolver.YouTubeMusicResolver
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class AnimusApplication : Application() {

    companion object {
        private const val TAG = "AnimusApplication"
        lateinit var instance: AnimusApplication
            private set
    }

    lateinit var bluetoothController: BluetoothAudioDeviceManager
        private set

    lateinit var musicController: MusicController
        private set

    lateinit var tuyaApiClient: TuyaCloudApiClient
        private set

    lateinit var tuyaAcAdapter: TuyaAirConditionerAdapter
        private set

    lateinit var deviceRegistry: DeviceRegistry
        private set

    lateinit var routineStorage: RoutineStorage
        private set

    lateinit var routineScheduler: RoutineScheduler
        private set

    lateinit var routineEngine: RoutineEngine
        private set

    lateinit var scheduledActionStorage: ScheduledActionStorage
        private set

    lateinit var deviceSchedulerEngine: DeviceSchedulerEngine
        private set

    lateinit var memoryStore: com.animus.smartroom.core.memory.store.MemoryStore
        private set

    lateinit var animusRuntime: AnimusRuntime
        private set

    lateinit var runtimeControlPort: RuntimeControlPort
        private set

    lateinit var overlayPermissionPort: OverlayPermissionPort
        private set

    lateinit var brainManager: AnimusBrainManager
        private set

    lateinit var commandRouter: CommandRouter
        private set

    lateinit var voiceInputPort: com.animus.smartroom.core.port.VoiceInputPort
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        Log.i(TAG, "[init] Initializing AnimusApplication singletons")

        com.animus.smartroom.diagnostics.DiagnosticBus.logSink = { tag, stage, message ->
            when (stage) {
                com.animus.smartroom.diagnostics.DiagnosticStage.FAILED -> Log.e(tag, "[${stage.name}] $message")
                else -> Log.i(tag, "[${stage.name}] $message")
            }
        }

        bluetoothController = BluetoothAudioDeviceManager(this)
        musicController = MusicController(this)

        tuyaApiClient = TuyaCloudApiClient(
            accessIdProvider = { BuildConfig.TUYA_ACCESS_ID },
            accessSecretProvider = { BuildConfig.TUYA_ACCESS_SECRET },
            endpointProvider = { BuildConfig.TUYA_REGION_ENDPOINT.ifBlank { "https://openapi.tuyain.com" } }
        )

        tuyaAcAdapter = TuyaAirConditionerAdapter(
            apiClient = tuyaApiClient,
            allowWriteCommands = true
        )

        deviceRegistry = DeviceRegistry().apply {
            registerAdapterForType(DeviceType.BLUETOOTH_AUDIO, BluetoothAudioDeviceAdapter(bluetoothController))
            registerAdapterForType(DeviceType.AIR_CONDITIONER, tuyaAcAdapter)

            val realAcId = BuildConfig.TUYA_DEVICE_ID.ifBlank { "76776532a4e57c0a2ca4" }
            registerDevice(
                RoomDevice(
                    id = realAcId,
                    displayName = "Bedroom AC",
                    type = DeviceType.AIR_CONDITIONER,
                    connectionState = DeviceConnectionState.Connected,
                    supportedCapabilities = setOf(
                        DeviceCapability.Power,
                        DeviceCapability.Temperature,
                        DeviceCapability.HvacMode,
                        DeviceCapability.FanSpeed
                    ),
                    aliases = listOf("ac", "air conditioner", "cooler", "room ac")
                )
            )

            registerDevice(
                RoomDevice(
                    id = "bt_speaker_primary",
                    displayName = "Bluetooth Speaker",
                    type = DeviceType.BLUETOOTH_AUDIO,
                    connectionState = DeviceConnectionState.Disconnected,
                    supportedCapabilities = setOf(
                        DeviceCapability.Connect,
                        DeviceCapability.Disconnect,
                        DeviceCapability.Play,
                        DeviceCapability.Volume
                    ),
                    aliases = listOf("speaker", "soundbar", "bluetooth speaker", "audio")
                )
            )
        }

        routineStorage = RoutineStorage(this)
        routineScheduler = RoutineScheduler(this)
        routineEngine = RoutineEngine(
            context = this,
            deviceRegistry = deviceRegistry,
            bluetoothManager = bluetoothController,
            musicController = musicController,
            musicResolver = null
        )

        val scheduledActionStore = com.animus.smartroom.core.port.AndroidPersistentStore(this, ScheduledActionStorage.PREFS_NAME)
        scheduledActionStorage = ScheduledActionStorage(scheduledActionStore)
        deviceSchedulerEngine = DeviceSchedulerEngine(
            storage = scheduledActionStorage,
            clock = com.animus.smartroom.core.port.AndroidClock(),
            platformScheduler = com.animus.smartroom.core.port.AndroidAlarmManagerScheduler(this)
        )

        memoryStore = com.animus.smartroom.core.memory.store.AndroidMemoryStore(
            persistentStore = com.animus.smartroom.core.port.AndroidPersistentStore(this)
        )

        val apiKeyStorage = GeminiApiKeyStorage(this)
        val localBrainConfigStorage = com.animus.smartroom.brain.provider.LocalBrainConfigStorage(this)
        val localInferenceClient = com.animus.smartroom.brain.provider.LocalInferenceClient { localBrainConfigStorage.getConfig() }
        val localInferencePort = com.animus.smartroom.brain.provider.AndroidLocalInferencePort(localInferenceClient)
        // Automatically start real warmup in background on IO dispatcher
        kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.IO).launch {
            localInferencePort.warmUp()
        }
        val localBrainProvider = com.animus.smartroom.brain.provider.LocalBrainProvider(inferencePort = localInferencePort)

        val voiceOutput = com.animus.smartroom.voice.AndroidVoiceOutputAdapter(this)
        val geminiApiClient = GeminiApiClient()
        val localBrain = LocalAnimusBrain(localBrainProvider = localBrainProvider, voiceOutputPort = voiceOutput)
        val cloudBrain = CloudAnimusBrain(
            apiKeyProvider = { apiKeyStorage.getApiKey() },
            apiClient = geminiApiClient
        )
        brainManager = AnimusBrainManager(
            localBrain = localBrain,
            cloudBrain = cloudBrain,
            initialProvider = apiKeyStorage.getSelectedProvider(),
            onProviderChanged = { apiKeyStorage.saveSelectedProvider(it) }
        )

        val musicResolutionCache = MusicResolutionCache.create(this)
        val musicResolver = YouTubeMusicResolver(
            apiKeyProvider = { BuildConfig.YOUTUBE_API_KEY.ifBlank { null } },
            cache = musicResolutionCache
        )

        commandRouter = CommandRouter(
            bluetoothManager = bluetoothController,
            musicController = musicController,
            musicResolver = musicResolver,
            deviceRegistry = deviceRegistry,
            routineEngine = routineEngine,
            deviceSchedulerEngine = deviceSchedulerEngine
        )

        runtimeControlPort = RuntimeControlPortImpl(
            brainManager = brainManager,
            commandRouter = commandRouter,
            deviceSchedulerEngine = deviceSchedulerEngine
        )

        overlayPermissionPort = AndroidOverlayPermissionPort(this)

        animusRuntime = AnimusRuntimeImpl()

        voiceInputPort = com.animus.smartroom.voice.SpeechRecognitionManager(this) { spokenText ->
            Log.i(TAG, "[voice] Global voice input recognized: '$spokenText'")
            kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.Dispatchers.Main).launch {
                runtimeControlPort.submitCommand(spokenText)
            }
        }

        // Create notification channel early so service can use it immediately
        AndroidNotificationAdapter.createNotificationChannel(this)

        // Restore any pending alarms across process startup
        routineEngine.restorePersistedRoutines()
        deviceSchedulerEngine.restorePersistedActions()
    }

    /**
     * Start the AnimusRuntimeService foreground service on demand.
     * Call when Animus needs persistent background capability beyond AlarmManager.
     * Safe to call multiple times — service handles idempotency.
     */
    fun startRuntime() {
        Log.i(TAG, "[runtime] Starting AnimusRuntimeService")
        val intent = AnimusRuntimeService.startIntent(this)
        startForegroundService(intent)
    }

    /**
     * Stop the AnimusRuntimeService. The runtime state in AnimusRuntimeImpl
     * will persist until the next startRuntime() call.
     */
    fun stopRuntime() {
        Log.i(TAG, "[runtime] Stopping AnimusRuntimeService")
        val intent = AnimusRuntimeService.stopIntent(this)
        startService(intent)
    }

    /**
     * Start the FloatingAnimusService if permission is granted.
     * Returns true if service launch attempted, false if permission missing.
     */
    fun startFloatingOverlay(): Boolean {
        if (!overlayPermissionPort.canDrawOverlays()) {
            Log.w(TAG, "[overlay] Cannot start floating overlay: SYSTEM_ALERT_WINDOW permission missing")
            return false
        }
        Log.i(TAG, "[overlay] Starting FloatingAnimusService")
        val intent = FloatingAnimusService.startIntent(this)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        return true
    }

    /**
     * Stop the FloatingAnimusService and remove overlay window.
     */
    fun stopFloatingOverlay() {
        Log.i(TAG, "[overlay] Stopping FloatingAnimusService")
        val intent = FloatingAnimusService.stopIntent(this)
        startService(intent)
    }

    /**
     * Check whether the floating overlay service is currently running.
     */
    fun isFloatingOverlayRunning(): Boolean = FloatingAnimusService.isRunning
}
