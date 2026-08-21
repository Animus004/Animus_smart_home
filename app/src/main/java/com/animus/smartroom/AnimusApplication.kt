package com.animus.smartroom

import android.app.Application
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
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage

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

    override fun onCreate() {
        super.onCreate()
        instance = this
        Log.i(TAG, "[init] Initializing AnimusApplication singletons")

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

        scheduledActionStorage = ScheduledActionStorage(this)
        deviceSchedulerEngine = DeviceSchedulerEngine(
            context = this,
            storage = scheduledActionStorage
        )

        // Restore any pending alarms across process startup
        routineEngine.restorePersistedRoutines()
        deviceSchedulerEngine.restorePersistedActions()
    }
}
