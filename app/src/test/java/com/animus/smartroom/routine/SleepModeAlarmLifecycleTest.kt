package com.animus.smartroom.routine

import com.animus.smartroom.routine.model.RoutineState
import com.animus.smartroom.routine.model.RoutineStatus
import com.animus.smartroom.routine.model.RoutineType
import com.animus.smartroom.routine.storage.RoutineStorage
import org.junit.Assert.*
import org.junit.Test

class SleepModeAlarmLifecycleTest {

    private class InMemRoutineStorage : RoutineStorage(null) {
        var current: RoutineState? = null

        override fun saveActiveRoutine(routine: RoutineState?) {
            current = routine
        }

        override fun getActiveRoutine(): RoutineState? {
            return current
        }

        override fun clearActiveRoutine() {
            current = null
        }
    }

    @Test
    fun testRoutineAlarmingStateTransitions() {
        val storage = InMemRoutineStorage()

        // 1. Enter ACTIVE state
        val activeRoutine = RoutineState(
            id = "routine_001",
            type = RoutineType.SLEEP,
            createdAt = System.currentTimeMillis(),
            scheduledWakeTime = System.currentTimeMillis() + 60000L,
            status = RoutineStatus.ACTIVE
        )
        storage.saveActiveRoutine(activeRoutine)
        assertTrue(storage.getActiveRoutine()!!.isActive)
        assertFalse(storage.getActiveRoutine()!!.isAlarming)

        // 2. Transition to ALARMING on wake-up trigger
        val alarmingRoutine = activeRoutine.copy(status = RoutineStatus.ALARMING)
        storage.saveActiveRoutine(alarmingRoutine)
        assertTrue(storage.getActiveRoutine()!!.isActive)
        assertTrue(storage.getActiveRoutine()!!.isAlarming)
        assertEquals(RoutineStatus.ALARMING, storage.getActiveRoutine()!!.status)

        // 3. Transition to COMPLETED on user STOP
        val completedRoutine = alarmingRoutine.copy(status = RoutineStatus.COMPLETED)
        storage.saveActiveRoutine(completedRoutine)
        assertFalse(storage.getActiveRoutine()!!.isActive)
        assertFalse(storage.getActiveRoutine()!!.isAlarming)
        assertEquals(RoutineStatus.COMPLETED, storage.getActiveRoutine()!!.status)
    }

    @Test
    fun testRealRoutineStorageFlowEmission() {
        val storage = RoutineStorage(null)
        val routine = RoutineState(
            id = "routine_test",
            status = RoutineStatus.ALARMING
        )
        storage.saveActiveRoutine(routine)
        assertEquals(RoutineStatus.ALARMING, RoutineStorage.activeRoutineFlow.value?.status)

        val completed = routine.copy(status = RoutineStatus.COMPLETED)
        storage.saveActiveRoutine(completed)
        assertEquals(RoutineStatus.COMPLETED, RoutineStorage.activeRoutineFlow.value?.status)
    }
}
