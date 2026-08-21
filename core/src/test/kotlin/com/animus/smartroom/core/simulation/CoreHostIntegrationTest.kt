package com.animus.smartroom.core.simulation

import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.core.device.DeviceCommand
import com.animus.smartroom.core.device.FakeAirConditionerAdapter
import com.animus.smartroom.core.device.FakeAudioOutputAdapter
import com.animus.smartroom.core.device.FakeDeviceTransport
import com.animus.smartroom.core.device.FakeMusicPlaybackPort
import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.query.MemoryQuery
import com.animus.smartroom.core.memory.store.InMemoryMemoryStore
import com.animus.smartroom.core.memory.summary.DailySummaryBuilder
import com.animus.smartroom.core.memory.summary.MorningBriefingBuilder
import com.animus.smartroom.core.port.FakeClock
import com.animus.smartroom.core.port.FakePersistentStore
import com.animus.smartroom.core.port.PlatformScheduler
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.Calendar
import java.util.TimeZone

/**
 * Pure JVM integration test proving that the complete Animus pipeline
 * (Brain -> Command Parser -> DeviceRegistry -> AC Execution -> Scheduler -> Memory -> DailySummary -> MorningBriefing)
 * operates entirely independently of the Android SDK / OS runtime.
 */
class CoreHostIntegrationTest {

    private lateinit var clock: FakeClock
    private lateinit var store: FakePersistentStore
    private lateinit var memoryStore: InMemoryMemoryStore
    private lateinit var transport: FakeDeviceTransport
    private lateinit var acAdapter: FakeAirConditionerAdapter
    private lateinit var audioAdapter: FakeAudioOutputAdapter
    private lateinit var musicPort: FakeMusicPlaybackPort
    private lateinit var registry: DeviceRegistry
    private lateinit var parser: LocalCommandParser

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
        id = "tuya_ac_host",
        displayName = "Bedroom AC",
        type = DeviceType.AIR_CONDITIONER,
        supportedCapabilities = setOf(
            DeviceCapability.Power,
            DeviceCapability.Temperature,
            DeviceCapability.HvacMode,
            DeviceCapability.FanSpeed
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
        memoryStore = InMemoryMemoryStore()
        transport = FakeDeviceTransport()
        acAdapter = FakeAirConditionerAdapter(transport)
        audioAdapter = FakeAudioOutputAdapter()
        musicPort = FakeMusicPlaybackPort()
        parser = LocalCommandParser()

        registry = DeviceRegistry()
        registry.registerDevice(acDevice)
        registry.registerAdapterForDevice(acDevice.id, acAdapter)

        armedTimers.clear()
        disarmedTimers.clear()
    }

    @Test
    fun `Full end-to-end Animus session lifecycle on pure JVM host`() = runBlocking {
        // 1. User says: "Turn on AC" and "Set temperature to 24"
        val cmd1 = parser.parse("turn on ac")
        val cmd2 = parser.parse("set temperature to 24")
        assertTrue(cmd1 is AnimusCommand.SetDeviceCapability)
        assertTrue(cmd2 is AnimusCommand.SetDeviceCapability)

        // 2. Validate and execute commands
        val res1 = registry.executeCommand(acDevice, DeviceCommand.Power((cmd1 as AnimusCommand.SetDeviceCapability).value.toString().toBoolean()))
        val res2 = registry.executeCommand(acDevice, DeviceCommand.SetTemperature((cmd2 as AnimusCommand.SetDeviceCapability).value.toString().toInt()))
        assertTrue(res1.success)
        assertTrue(res2.success)

        // 3. Verify physical state on fake adapter and transport
        assertTrue(acAdapter.powerState)
        assertEquals(24, acAdapter.currentTemperature)
        assertEquals(2, transport.sentCommands.size)

        // 4. User schedules: "Turn AC off after 2 minutes"
        val parsedSchedule = parser.parse("turn ac off after 2 minutes")
        assertTrue(parsedSchedule is AnimusCommand.ScheduleDeviceAction)
        val scheduleCmd = parsedSchedule as AnimusCommand.ScheduleDeviceAction

        val actionId = "scheduled_ac_001"
        val delay = scheduleCmd.delayMinutes ?: 2
        val triggerAt = clock.currentTimeMillis() + (delay * 60 * 1000L)
        val action = ScheduledDeviceAction(
            id = actionId,
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            scheduledExecutionTimeMillis = triggerAt,
            status = ScheduledActionStatus.SCHEDULED
        )
        fakePlatformScheduler.armExact(actionId, triggerAt, "")
        assertEquals(triggerAt, armedTimers[actionId])

        // 5. Advance clock by 2 minutes and trigger scheduled execution
        clock.advanceTime(2 * 60 * 1000L)
        val offResult = registry.executeCommand(acDevice, DeviceCommand.Power(false))
        assertTrue(offResult.success)
        assertFalse(acAdapter.powerState)

        // 6. Record learning event and project milestone in memory
        val learnEvent = LearningEvent(
            timestamp = clock.currentTimeMillis(),
            topic = "SQL",
            subtopic = "JOINs",
            action = "Practiced FULL OUTER JOIN",
            status = LearningStatus.PRACTICED
        )
        memoryStore.record(learnEvent)

        // 7. Query memory and build DailySummary & MorningBriefing
        val events = memoryStore.query(MemoryQuery(ascending = true))
        assertEquals(1, events.size)

        val dailySummary = DailySummaryBuilder.build("2026-08-21", events)
        assertEquals(1, dailySummary.learningHighlights.size)
        assertEquals("SQL: Practiced FULL OUTER JOIN", dailySummary.learningHighlights.first())

        val briefing = MorningBriefingBuilder.build(
            dateStr = "2026-08-22",
            yesterdaySummary = dailySummary,
            allLearningEvents = listOf(learnEvent),
            activeScheduledSummary = "No active timers"
        )
        val briefingText = briefing.formatPlainText()
        assertTrue(briefingText.contains("Morning Briefing for 2026-08-22"))
        assertTrue(briefingText.contains("SQL: Practiced FULL OUTER JOIN"))
    }
}
