package com.animus.smartroom.core.brain.router

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ExecutionPlannerTest {

    @Test
    fun `test movie mode routine generates 2 distinct dependency stages`() {
        val routine = BrainIntent.RoutineCommand("MOVIE_MODE")
        val plan = ExecutionPlanner.planRoutine(routine)

        assertEquals("MOVIE_MODE", plan.routineName)
        assertEquals(2, plan.stages.size)

        val stage1 = plan.stages[0]
        assertEquals(1, stage1.stageIndex)
        assertEquals(3, stage1.actions.size)
        assertTrue(stage1.actions.any { it.capability == CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON })
        assertTrue(stage1.actions.any { it.capability == CapabilityRegistry.ActionCapability.FIRE_TV_WAKE })
        assertTrue(stage1.actions.any { it.capability == CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG })

        val stage2 = plan.stages[1]
        assertEquals(2, stage2.stageIndex)
        assertEquals(1, stage2.actions.size)
        assertEquals(CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT, stage2.actions[0].capability)
    }

    @Test
    fun `test multi-action command separates independent and dependent stages`() {
        val multi = BrainIntent.MultiActionCommand(
            actions = listOf(
                BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                    capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON
                ),
                BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.FIRE_TV,
                    capability = CapabilityRegistry.ActionCapability.FIRE_TV_WAKE
                ),
                BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                    capability = CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
                    parameters = mapOf("input" to "HDMI_1")
                )
            )
        )

        val plan = ExecutionPlanner.planMultiAction(multi)
        assertEquals(2, plan.stages.size)
        assertEquals(2, plan.stages[0].actions.size)
        assertEquals(1, plan.stages[1].actions.size)
        assertEquals(CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT, plan.stages[1].actions[0].capability)
    }
}
