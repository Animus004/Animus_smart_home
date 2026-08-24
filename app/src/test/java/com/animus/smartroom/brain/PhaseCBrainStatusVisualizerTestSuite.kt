package com.animus.smartroom.brain

import com.animus.smartroom.brain.provider.LocalBrainStatus
import com.animus.smartroom.ui.brain.VisualBrainState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class PhaseCBrainStatusVisualizerTestSuite {

    @Test
    fun `visual brain state enum has all required states with valid colors and labels`() {
        val states = VisualBrainState.values()
        assertEquals(5, states.size)

        val ready = VisualBrainState.READY
        assertEquals("READY", ready.label)
        assertEquals("🟢", ready.symbol)
        assertNotNull(ready.color)

        val warming = VisualBrainState.WARMING
        assertEquals("WARMING", warming.label)
        assertEquals("🟡", warming.symbol)
        assertNotNull(warming.color)

        val executing = VisualBrainState.EXECUTING
        assertEquals("EXECUTING", executing.label)
        assertEquals("🔵", executing.symbol)
        assertNotNull(executing.color)

        val completed = VisualBrainState.COMPLETED
        assertEquals("COMPLETED", completed.label)
        assertEquals("🔷", completed.symbol)
        assertNotNull(completed.color)

        val error = VisualBrainState.ERROR
        assertEquals("ERROR", error.label)
        assertEquals("🔴", error.symbol)
        assertNotNull(error.color)
    }

    @Test
    fun `local brain status maps deterministically to visual brain state`() {
        fun mapPortStatusToVisual(status: LocalBrainStatus): VisualBrainState {
            return when (status) {
                LocalBrainStatus.STARTING,
                LocalBrainStatus.WARMING_UP,
                LocalBrainStatus.CONNECTING -> VisualBrainState.WARMING
                LocalBrainStatus.READY,
                LocalBrainStatus.AVAILABLE -> VisualBrainState.READY
                LocalBrainStatus.BUSY -> VisualBrainState.EXECUTING
                LocalBrainStatus.ERROR,
                LocalBrainStatus.OFFLINE,
                LocalBrainStatus.DISCONNECTED,
                LocalBrainStatus.FAILED -> VisualBrainState.ERROR
            }
        }

        assertEquals(VisualBrainState.WARMING, mapPortStatusToVisual(LocalBrainStatus.WARMING_UP))
        assertEquals(VisualBrainState.WARMING, mapPortStatusToVisual(LocalBrainStatus.STARTING))
        assertEquals(VisualBrainState.WARMING, mapPortStatusToVisual(LocalBrainStatus.CONNECTING))
        assertEquals(VisualBrainState.READY, mapPortStatusToVisual(LocalBrainStatus.READY))
        assertEquals(VisualBrainState.READY, mapPortStatusToVisual(LocalBrainStatus.AVAILABLE))
        assertEquals(VisualBrainState.EXECUTING, mapPortStatusToVisual(LocalBrainStatus.BUSY))
        assertEquals(VisualBrainState.ERROR, mapPortStatusToVisual(LocalBrainStatus.ERROR))
        assertEquals(VisualBrainState.ERROR, mapPortStatusToVisual(LocalBrainStatus.FAILED))
        assertEquals(VisualBrainState.ERROR, mapPortStatusToVisual(LocalBrainStatus.OFFLINE))
    }
}
