package com.animus.smartroom.scheduler

import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.util.Calendar
import java.util.TimeZone

class DeviceSchedulerEngineTest {

    private lateinit var storage: ScheduledActionStorage
    private lateinit var engine: DeviceSchedulerEngine

    @Before
    fun setUp() {
        storage = ScheduledActionStorage(com.animus.smartroom.core.port.FakePersistentStore())
        storage.clear()
        engine = DeviceSchedulerEngine(storage = storage, clock = com.animus.smartroom.core.port.AndroidClock())
    }

    // 1. Relative Delay Parsing Tests
    @Test
    fun testRelativeDelayParsing_30minutes() {
        val now = 1000000000000L
        val result = DeviceSchedulerEngine.parseExecutionTime(30, null, now)
        assertNotNull(result)
        assertEquals(now + 30 * 60 * 1000L, result)
    }

    @Test
    fun testRelativeDelayParsing_2hours() {
        val now = 1000000000000L
        val result = DeviceSchedulerEngine.parseExecutionTime(120, null, now)
        assertNotNull(result)
        assertEquals(now + 120 * 60 * 1000L, result)
    }

    // 2. Absolute Time Parsing in Asia/Kolkata
    @Test
    fun testAbsoluteTimeParsing_futureToday() {
        val tz = TimeZone.getTimeZone("Asia/Kolkata")
        val cal = Calendar.getInstance(tz).apply {
            set(Calendar.HOUR_OF_DAY, 10)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val now = cal.timeInMillis

        // Schedule at 11:00 PM (23:00) today
        val result = DeviceSchedulerEngine.parseExecutionTime(null, "11 PM", now, "Asia/Kolkata")
        assertNotNull(result)

        val targetCal = Calendar.getInstance(tz).apply { timeInMillis = result!! }
        assertEquals(23, targetCal.get(Calendar.HOUR_OF_DAY))
        assertEquals(0, targetCal.get(Calendar.MINUTE))
        assertEquals(cal.get(Calendar.DAY_OF_YEAR), targetCal.get(Calendar.DAY_OF_YEAR))
    }

    @Test
    fun testAbsoluteTimeParsing_pastTimeRollsToTomorrow() {
        val tz = TimeZone.getTimeZone("Asia/Kolkata")
        val cal = Calendar.getInstance(tz).apply {
            set(Calendar.HOUR_OF_DAY, 15)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val now = cal.timeInMillis

        // Schedule at 6:00 AM (past time for today)
        val result = DeviceSchedulerEngine.parseExecutionTime(null, "6 AM", now, "Asia/Kolkata")
        assertNotNull(result)

        val targetCal = Calendar.getInstance(tz).apply { timeInMillis = result!! }
        assertEquals(6, targetCal.get(Calendar.HOUR_OF_DAY))
        assertEquals(0, targetCal.get(Calendar.MINUTE))
        assertEquals(cal.get(Calendar.DAY_OF_YEAR) + 1, targetCal.get(Calendar.DAY_OF_YEAR))
    }

    // 3. Scheduling & Storage State
    @Test
    fun testScheduleAction_success() {
        val res = engine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            delayMinutes = 60
        )

        assertTrue(res is ActionScheduleResult.Success)
        val action = (res as ActionScheduleResult.Success).action
        assertEquals(DeviceType.AIR_CONDITIONER, action.targetDeviceType)
        assertEquals(DeviceActionType.POWER_OFF, action.actionType)
        assertEquals(ScheduledActionStatus.SCHEDULED, action.status)

        val saved = storage.getAction(action.id)
        assertNotNull(saved)
        assertEquals(action.id, saved?.id)
    }

    // 4. Cancellation Behavior
    @Test
    fun testCancelAction() {
        val res = engine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            delayMinutes = 45
        ) as ActionScheduleResult.Success

        assertTrue(engine.cancelAction(res.action.id))
        val updated = storage.getAction(res.action.id)
        assertEquals(ScheduledActionStatus.CANCELLED, updated?.status)
        assertFalse(updated!!.isPending)
    }

    @Test
    fun testCancelActionsForDevice() {
        engine.scheduleAction(DeviceType.AIR_CONDITIONER, DeviceActionType.POWER_OFF, delayMinutes = 30)
        val cancelled = engine.cancelActionsForDevice(DeviceType.AIR_CONDITIONER)
        assertEquals(1, cancelled)
        assertTrue(storage.getActiveActions().isEmpty())
    }

    // 5. Query Remaining Time
    @Test
    fun testQueryRemainingTime_activeTimer() {
        val futureTime = System.currentTimeMillis() + (102 * 60 * 1000L) // 1h 42m
        val action = ScheduledDeviceAction(
            id = "test-1",
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            scheduledExecutionTimeMillis = futureTime
        )
        storage.saveAction(action)

        val queryResponse = engine.queryRemainingTime(DeviceType.AIR_CONDITIONER)
        assertTrue(queryResponse.contains("1 hour 42 minutes"))
    }

    @Test
    fun testQueryRemainingTime_noActiveTimer() {
        val queryResponse = engine.queryRemainingTime(DeviceType.AIR_CONDITIONER)
        assertEquals("You don't have an active AC timer.", queryResponse)
    }

    // 6. LocalCommandParser Regex Integration Tests
    @Test
    fun testLocalParser_acTimerDelay() {
        val parser = LocalCommandParser()

        val cmd1 = parser.parse("Turn AC off after 2 hours")
        assertTrue(cmd1 is AnimusCommand.ScheduleDeviceAction)
        val s1 = cmd1 as AnimusCommand.ScheduleDeviceAction
        assertEquals("AC", s1.target)
        assertEquals("POWER_OFF", s1.action)
        assertEquals(120, s1.delayMinutes)

        val cmd2 = parser.parse("Turn the AC on in 30 minutes")
        assertTrue(cmd2 is AnimusCommand.ScheduleDeviceAction)
        val s2 = cmd2 as AnimusCommand.ScheduleDeviceAction
        assertEquals("POWER_ON", s2.action)
        assertEquals(30, s2.delayMinutes)

        val cmd3 = parser.parse("Turn AC off at 11 PM")
        assertTrue(cmd3 is AnimusCommand.ScheduleDeviceAction)
        val s3 = cmd3 as AnimusCommand.ScheduleDeviceAction
        assertEquals("11 PM", s3.scheduledTime)

        val cmd4 = parser.parse("Turn AC off every night at 11 PM")
        assertTrue(cmd4 is AnimusCommand.ScheduleDeviceAction)
        val s4 = cmd4 as AnimusCommand.ScheduleDeviceAction
        assertEquals("DAILY", s4.recurrence)

        val cmd5 = parser.parse("Cancel my AC timer")
        assertTrue(cmd5 is AnimusCommand.CancelScheduledAction)

        val cmd6 = parser.parse("How much time is left on the AC timer?")
        assertTrue(cmd6 is AnimusCommand.QueryScheduledAction)
    }

    // 7. BrainCommandValidator JSON Integration Tests
    @Test
    fun testBrainValidator_scheduleDeviceAction() {
        val json = """
            {
              "command": "SCHEDULE_DEVICE_ACTION",
              "target": "AC",
              "action": "POWER_OFF",
              "delayMinutes": 120
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is com.animus.smartroom.brain.validator.BrainValidationResult.Valid)
        val cmd = (validation as com.animus.smartroom.brain.validator.BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.ScheduleDeviceAction)
        assertEquals(120, (cmd as AnimusCommand.ScheduleDeviceAction).delayMinutes)
    }

    // 8. CommandRouter End-to-End Scheduling
    @Test
    fun testCommandRouter_scheduleAndQuery() = runBlocking {
        val router = CommandRouter(deviceSchedulerEngine = engine)

        val scheduleCmd = AnimusCommand.ScheduleDeviceAction(
            target = "AC",
            action = "POWER_OFF",
            delayMinutes = 90
        )
        val scheduleRes = router.execute(scheduleCmd)
        assertTrue(scheduleRes.success)
        assertTrue(scheduleRes.message.contains("90 minutes"))

        val queryCmd = AnimusCommand.QueryScheduledAction(target = "AC")
        val queryRes = router.execute(queryCmd)
        assertTrue(queryRes.success)
        assertTrue(queryRes.message.contains("1 hour 30 minutes"))

        val cancelCmd = AnimusCommand.CancelScheduledAction(target = "AC")
        val cancelRes = router.execute(cancelCmd)
        assertTrue(cancelRes.success)
        assertTrue(cancelRes.message.contains("Cancelled active timer"))
    }
}
