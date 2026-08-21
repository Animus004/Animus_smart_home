package com.animus.smartroom.core.simulation

import com.animus.smartroom.core.device.DeviceCommand
import com.animus.smartroom.core.device.FakeAirConditionerAdapter
import com.animus.smartroom.core.device.FakeAudioOutputAdapter
import com.animus.smartroom.core.device.FakeDeviceTransport
import com.animus.smartroom.core.device.FakeMusicPlaybackPort
import com.animus.smartroom.core.device.ResolvedTrack
import com.animus.smartroom.core.port.FakeClock
import com.animus.smartroom.core.port.FakePersistentStore
import com.animus.smartroom.core.port.PlatformScheduler
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.scheduler.ActionScheduleResult
import com.animus.smartroom.scheduler.DeviceSchedulerEngine
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.Calendar
import java.util.TimeZone

/**
 * Pure JVM simulation proving that Animus Core contracts (DeviceRegistry, SchedulerEngine,
 * DeviceAdapter, DeviceTransport, MusicPlaybackPort, Clock, PersistentStore, PlatformScheduler)
 * execute completely independently of the Android SDK / OS runtime.
 */
class FakeCoreHostSimulationTest {

    private lateinit var clock: FakeClock
    private lateinit var store: FakePersistentStore
    private lateinit var storage: ScheduledActionStorage
    private lateinit var transport: FakeDeviceTransport
    private lateinit var acAdapter: FakeAirConditionerAdapter
    private lateinit var audioAdapter: FakeAudioOutputAdapter
    private lateinit var musicPort: FakeMusicPlaybackPort
    private lateinit var registry: DeviceRegistry
    private lateinit var schedulerEngine: DeviceSchedulerEngine

    private val armedTimers = mutableMapOf<String, Long>()
    private val disarmedTimers = mutableListOf<String>()

    private val fakePlatformScheduler = object : PlatformScheduler {
        override fun armExact(actionId: String, triggerAtMillis: Long, metadataJson: String) {
            armedTimers[actionId] = triggerAtMillis
        }

        override fun disarm(actionId: String) {
            disarmedTimers.add(actionId)
            armedTimers.remove(actionId)
        }
    }

    private val acDevice = RoomDevice(
        id = "tuya_ac_001",
        displayName = "Bedroom AC",
        type = DeviceType.AIR_CONDITIONER,
        supportedCapabilities = setOf(
            DeviceCapability.Power,
            DeviceCapability.Temperature,
            DeviceCapability.HvacMode,
            DeviceCapability.FanSpeed
        )
    )

    private val soundbarDevice = RoomDevice(
        id = "soundbar_001",
        displayName = "LG Soundbar",
        type = DeviceType.BLUETOOTH_AUDIO,
        supportedCapabilities = setOf(
            DeviceCapability.Connect,
            DeviceCapability.Disconnect
        )
    )

    @Before
    fun setup() {
        val cal = Calendar.getInstance(TimeZone.getTimeZone("Asia/Kolkata")).apply {
            set(2026, Calendar.AUGUST, 21, 20, 0, 0)
            set(Calendar.MILLISECOND, 0)
        }

        clock = FakeClock(currentTime = cal.timeInMillis, timeZone = "Asia/Kolkata")
        store = FakePersistentStore()
        storage = ScheduledActionStorage(store = store)
        transport = FakeDeviceTransport()
        acAdapter = FakeAirConditionerAdapter(transport)
        audioAdapter = FakeAudioOutputAdapter()
        musicPort = FakeMusicPlaybackPort()

        registry = DeviceRegistry()
        registry.registerDevice(acDevice)
        registry.registerDevice(soundbarDevice)
        registry.registerAdapterForDevice(acDevice.id, acAdapter)
        registry.registerAdapterForDevice(soundbarDevice.id, audioAdapter)

        schedulerEngine = DeviceSchedulerEngine(
            storage = storage,
            clock = clock,
            platformScheduler = fakePlatformScheduler
        )

        armedTimers.clear()
        disarmedTimers.clear()
    }

    @Test
    fun `Simulate scenario Turn AC off after 2 minutes on future host`() = runBlocking {
        // 1. Schedule AC power off in 2 minutes
        val scheduleResult = schedulerEngine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            delayMinutes = 2
        )
        assertTrue(scheduleResult is ActionScheduleResult.Success)
        val action = (scheduleResult as ActionScheduleResult.Success).action

        val expectedTrigger = clock.currentTimeMillis() + (2 * 60 * 1000L)
        assertEquals(expectedTrigger, action.scheduledExecutionTimeMillis)
        assertEquals(expectedTrigger, armedTimers[action.id])
        assertEquals(ScheduledActionStatus.SCHEDULED, action.status)

        // 2. Query remaining time
        val query1 = schedulerEngine.queryRemainingTime(DeviceType.AIR_CONDITIONER)
        assertEquals("Your AC is scheduled to turn off in 2 minutes.", query1)

        // 3. Fast-forward clock by 2 minutes
        clock.advanceTime(2 * 60 * 1000L)

        // 4. Host triggers execution
        storage.updateStatus(action.id, ScheduledActionStatus.EXECUTING)
        val cmdRes = registry.executeCommand(acDevice, DeviceCommand.Power(false))
        assertTrue(cmdRes.success)
        assertFalse(acAdapter.powerState)

        storage.updateStatus(action.id, ScheduledActionStatus.COMPLETED)
        val finalAction = storage.getAction(action.id)
        assertEquals(ScheduledActionStatus.COMPLETED, finalAction?.status)
    }

    @Test
    fun `Simulate scenario Set AC to 24 degrees on future host`() = runBlocking {
        val result = registry.executeCommand(acDevice, DeviceCommand.SetTemperature(24))
        assertTrue(result.success)
        assertEquals(24, acAdapter.currentTemperature)
        assertEquals("AC temperature set to 24°C.", result.message)

        // Verify transport received low-level write
        assertEquals(1, transport.sentCommands.size)
        assertEquals(DeviceCommand.SetTemperature(24), transport.sentCommands.first().second)
    }

    @Test
    fun `Simulate scenario Play Zara Zara on future host`() = runBlocking {
        val track = ResolvedTrack(title = "Zara Zara", artist = "Bombay Jayashri", videoId = "IWjbBSMsQJg")
        val result = musicPort.play(track, soundbarDevice.displayName)

        assertTrue(result.isSuccess)
        assertTrue(musicPort.isPlaying)
        assertEquals("Zara Zara", musicPort.currentTrack?.title)
        assertEquals("IWjbBSMsQJg", musicPort.currentTrack?.videoId)
    }
}
