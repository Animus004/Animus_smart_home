package com.animus.smartroom.routine

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.adapter.MockAirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.scheduler.RoutineScheduler
import com.animus.smartroom.routine.scheduler.ScheduleResult
import com.animus.smartroom.routine.sleep.SleepModeRoutine
import com.animus.smartroom.routine.storage.RoutineStorage
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class SleepModeRoutineExecutionTest {

    private lateinit var deviceRegistry: DeviceRegistry
    private lateinit var mockAcAdapter: MockAirConditionerAdapter
    private lateinit var fakeStorage: FakeRoutineStorage
    private lateinit var fakeScheduler: FakeRoutineScheduler
    private lateinit var sleepModeRoutine: SleepModeRoutine

    private class FakeRoutineStorage : RoutineStorage(null) {
        var savedRoutine: RoutineState? = null

        override fun saveActiveRoutine(routine: RoutineState?) {
            savedRoutine = routine
        }

        override fun getActiveRoutine(): RoutineState? {
            return savedRoutine
        }

        override fun clearActiveRoutine() {
            savedRoutine = null
        }
    }

    private class FakeRoutineScheduler : RoutineScheduler(null) {
        var scheduledTriggerMillis: Long? = null
        var isCancelled: Boolean = false

        override fun canScheduleExactAlarms(): Boolean = true

        override fun scheduleWake(routineId: String, triggerAtMillis: Long): ScheduleResult {
            scheduledTriggerMillis = triggerAtMillis
            isCancelled = false
            return ScheduleResult.Success(triggerAtMillis)
        }

        override fun cancelWake(routineId: String) {
            isCancelled = true
        }
    }

    @Before
    fun setUp() {
        deviceRegistry = DeviceRegistry()
        mockAcAdapter = MockAirConditionerAdapter()
        deviceRegistry.registerAdapterForType(DeviceType.AIR_CONDITIONER, mockAcAdapter)
        deviceRegistry.registerDevice(
            RoomDevice(
                id = "test_ac_001",
                displayName = "Bedroom AC",
                type = DeviceType.AIR_CONDITIONER,
                connectionState = DeviceConnectionState.Connected,
                supportedCapabilities = setOf(
                    DeviceCapability.Power,
                    DeviceCapability.Temperature,
                    DeviceCapability.HvacMode,
                    DeviceCapability.FanSpeed
                ),
                aliases = listOf("AC", "Air Conditioner")
            )
        )

        fakeStorage = FakeRoutineStorage()
        fakeScheduler = FakeRoutineScheduler()

        sleepModeRoutine = SleepModeRoutine(
            deviceRegistry = deviceRegistry,
            bluetoothManager = null,
            musicController = null,
            musicResolver = null,
            routineScheduler = fakeScheduler,
            routineStorage = fakeStorage
        )
    }

    @Test
    fun testSleepModeClarificationWhenNoDurationProvided() = runBlocking {
        val result = sleepModeRoutine.enter(durationMinutes = null, wakeTime = null)
        assertTrue(result.success)
        assertEquals(SleepModeRoutine.CLARIFICATION_PROMPT, result.message)
        assertFalse("AC should not turn on during clarification", mockAcAdapter.powerState)
        assertNull("No alarm should be scheduled on clarification", fakeScheduler.scheduledTriggerMillis)
    }

    @Test
    fun testSleepModeExecutionWithDuration() = runBlocking {
        val result = sleepModeRoutine.enter(durationMinutes = 30, wakeTime = null)
        assertTrue(result.success)
        assertTrue(result.message.contains("Sleep Mode activated"))

        // Verify AC configuration
        assertTrue("AC power should be ON", mockAcAdapter.powerState)
        assertEquals("AC mode should be AUTO", AcMode.AUTO, mockAcAdapter.currentMode)
        assertEquals("AC temperature should be 24°C", 24, mockAcAdapter.currentTemperature)
        assertEquals("AC fan speed should be AUTO", AcFanSpeed.AUTO, mockAcAdapter.currentFanSpeed)

        // Verify scheduler & storage
        assertNotNull(fakeScheduler.scheduledTriggerMillis)
        assertNotNull(fakeStorage.savedRoutine)
        assertEquals(RoutineStatus.ACTIVE, fakeStorage.savedRoutine?.status)
    }

    @Test
    fun testWakeTimeCalculation() {
        val now = System.currentTimeMillis()
        val wake30 = sleepModeRoutine.calculateWakeTimeMillis(30, null)
        assertNotNull(wake30)
        assertTrue(wake30!! >= now + (30 * 60 * 1000L) - 1000L)
        assertTrue(wake30 <= now + (30 * 60 * 1000L) + 1000L)
    }

    @Test
    fun testCancelSleepModeWhenActive() = runBlocking {
        sleepModeRoutine.enter(durationMinutes = 15, wakeTime = null)
        val cancelResult = sleepModeRoutine.cancel()
        assertTrue(cancelResult.success)
        assertEquals("Sleep timer cancelled.", cancelResult.message)
        assertTrue(fakeScheduler.isCancelled)
        assertEquals(RoutineStatus.CANCELLED, fakeStorage.savedRoutine?.status)
    }

    @Test
    fun testCancelSleepModeWhenNoActiveRoutine() {
        fakeStorage.clearActiveRoutine()
        val result = sleepModeRoutine.cancel()
        assertTrue(result.success)
        assertEquals("No active sleep timer to cancel.", result.message)
    }
}
