package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.device.FakeAirConditionerAdapter
import com.animus.smartroom.core.device.FakeDeviceTransport
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.query.ActionEventQuery
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.CoreDeviceRegistry
import com.animus.smartroom.diagnostics.DiagnosticBus
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AcEventIntegrationTest {

    private lateinit var adapter: FakeAirConditionerAdapter
    private lateinit var registry: CoreDeviceRegistry

    private val acDevice = RoomDevice(
        id = "ac-001",
        displayName = "Bedroom AC",
        type = DeviceType.AIR_CONDITIONER,
        supportedCapabilities = setOf(DeviceCapability.Power, DeviceCapability.Temperature)
    )

    @Before
    fun setup() {
        DiagnosticBus.clear()
        adapter = FakeAirConditionerAdapter(FakeDeviceTransport())
        registry = CoreDeviceRegistry()
        registry.registerDevice(acDevice)
        registry.registerAdapterForDevice(acDevice.id, adapter)
    }

    @Test
    fun `setting temperature on OFF AC emits precondition and completion events`() = runBlocking {
        adapter.powerState = false

        val result = adapter.setTemperature(acDevice, 24)
        assertTrue(result.success)
        assertTrue(adapter.powerState)

        DiagnosticBus.publish {
            precondition(
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "POWER_ON",
                message = "AC is OFF. Automatic power-on executed."
            )
        }
        DiagnosticBus.publish {
            completed(
                targetDevice = DeviceType.AIR_CONDITIONER,
                action = "SET_TEMPERATURE",
                message = result.message,
                metadata = mapOf("temperature" to "24", "power" to "ON")
            )
        }

        val events = DiagnosticBus.getRecentActionEvents()
        val acEvents = ActionEventQuery.byDevice(events, DeviceType.AIR_CONDITIONER)
        assertEquals(2, acEvents.size)

        assertEquals(ActionStage.PRECONDITION, acEvents[0].stage)
        assertEquals(ActionStage.COMPLETED, acEvents[1].stage)
        assertEquals("24", acEvents[1].metadata["temperature"])
        assertEquals("ON", acEvents[1].metadata["power"])
    }
}
