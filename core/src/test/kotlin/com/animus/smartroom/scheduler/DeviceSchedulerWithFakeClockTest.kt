package com.animus.smartroom.scheduler

import com.animus.smartroom.core.port.FakeClock
import com.animus.smartroom.core.port.FakePersistentStore
import com.animus.smartroom.core.port.PlatformScheduler
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.storage.ScheduledActionStorage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.Calendar
import java.util.TimeZone

class DeviceSchedulerWithFakeClockTest {

    private lateinit var fakeClock: FakeClock
    private lateinit var fakeStore: FakePersistentStore
    private lateinit var storage: ScheduledActionStorage
    private lateinit var engine: DeviceSchedulerEngine
    private val armedActions = mutableMapOf<String, Long>()
    private val disarmedActions = mutableListOf<String>()

    private val fakePlatformScheduler = object : PlatformScheduler {
        override fun armExact(actionId: String, triggerAtMillis: Long, metadataJson: String) {
            armedActions[actionId] = triggerAtMillis
        }

        override fun disarm(actionId: String) {
            disarmedActions.add(actionId)
            armedActions.remove(actionId)
        }
    }

    @Before
    fun setup() {
        // Set fake clock to 2026-08-21 14:00:00 Asia/Kolkata
        val tz = TimeZone.getTimeZone("Asia/Kolkata")
        val cal = Calendar.getInstance(tz).apply {
            set(Calendar.YEAR, 2026)
            set(Calendar.MONTH, Calendar.AUGUST)
            set(Calendar.DAY_OF_MONTH, 21)
            set(Calendar.HOUR_OF_DAY, 14)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }

        fakeClock = FakeClock(currentTime = cal.timeInMillis, timeZone = "Asia/Kolkata")
        fakeStore = FakePersistentStore()
        storage = ScheduledActionStorage(store = fakeStore)
        engine = DeviceSchedulerEngine(
            storage = storage,
            clock = fakeClock,
            platformScheduler = fakePlatformScheduler
        )
        armedActions.clear()
        disarmedActions.clear()
    }

    @Test
    fun `scheduleAction with 30 minute delay arms platform scheduler with exact timestamp`() {
        val result = engine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            delayMinutes = 30
        )

        assertTrue(result is ActionScheduleResult.Success)
        val action = (result as ActionScheduleResult.Success).action
        val expectedTrigger = fakeClock.currentTimeMillis() + (30 * 60 * 1000L)

        assertEquals(expectedTrigger, action.scheduledExecutionTimeMillis)
        assertEquals(expectedTrigger, armedActions[action.id])
        assertEquals(ScheduledActionStatus.SCHEDULED, action.status)

        // Query remaining time
        val query1 = engine.queryRemainingTime(DeviceType.AIR_CONDITIONER)
        assertEquals("Your AC is scheduled to turn off in 30 minutes.", query1)

        // Advance fake clock by 10 minutes
        fakeClock.advanceTime(10 * 60 * 1000L)
        val query2 = engine.queryRemainingTime(DeviceType.AIR_CONDITIONER)
        assertEquals("Your AC is scheduled to turn off in 20 minutes.", query2)
    }

    @Test
    fun `scheduleAction cancels superseded active timer for same device`() {
        val res1 = engine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            delayMinutes = 60
        )
        val action1 = (res1 as ActionScheduleResult.Success).action
        assertTrue(armedActions.containsKey(action1.id))

        // Schedule new timer for 15 minutes
        val res2 = engine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_ON,
            delayMinutes = 15
        )
        val action2 = (res2 as ActionScheduleResult.Success).action

        assertTrue(disarmedActions.contains(action1.id))
        assertTrue(armedActions.containsKey(action2.id))
        assertEquals(ScheduledActionStatus.CANCELLED, storage.getAction(action1.id)?.status)
        assertEquals(ScheduledActionStatus.SCHEDULED, storage.getAction(action2.id)?.status)
    }

    @Test
    fun `cancelAction disarms platform scheduler and updates storage`() {
        val res = engine.scheduleAction(
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            delayMinutes = 45
        )
        val action = (res as ActionScheduleResult.Success).action

        val cancelled = engine.cancelAction(action.id)
        assertTrue(cancelled)
        assertTrue(disarmedActions.contains(action.id))
        assertEquals(ScheduledActionStatus.CANCELLED, storage.getAction(action.id)?.status)
    }
}
