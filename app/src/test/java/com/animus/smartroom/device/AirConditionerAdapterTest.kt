package com.animus.smartroom.device

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.adapter.AcSwing
import com.animus.smartroom.device.adapter.MockAirConditionerAdapter
import com.animus.smartroom.device.adapter.UnconfiguredAirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AirConditionerAdapterTest {

    private lateinit var mockAdapter: MockAirConditionerAdapter
    private lateinit var unconfiguredAdapter: UnconfiguredAirConditionerAdapter
    private lateinit var acDevice: RoomDevice

    @Before
    fun setUp() {
        mockAdapter = MockAirConditionerAdapter()
        unconfiguredAdapter = UnconfiguredAirConditionerAdapter()
        acDevice = RoomDevice(
            id = "ac_test",
            displayName = "Test AC",
            type = DeviceType.AIR_CONDITIONER,
            supportedCapabilities = setOf(
                DeviceCapability.Power,
                DeviceCapability.Temperature,
                DeviceCapability.HvacMode,
                DeviceCapability.FanSpeed,
                DeviceCapability.Swing
            )
        )
    }

    @Test
    fun testPowerCapability() = runBlocking {
        val onRes = mockAdapter.executeCapability(acDevice, DeviceCapability.Power, true)
        assertTrue(onRes.success)
        assertTrue(mockAdapter.powerState)

        val offRes = mockAdapter.executeCapability(acDevice, DeviceCapability.Power, false)
        assertTrue(offRes.success)
        assertFalse(mockAdapter.powerState)
    }

    @Test
    fun testTemperatureCapabilityValidRange() = runBlocking {
        val res24 = mockAdapter.executeCapability(acDevice, DeviceCapability.Temperature, 24)
        assertTrue(res24.success)
        assertEquals(24, mockAdapter.currentTemperature)

        val res16 = mockAdapter.executeCapability(acDevice, DeviceCapability.Temperature, "16")
        assertTrue(res16.success)
        assertEquals(16, mockAdapter.currentTemperature)

        val res30 = mockAdapter.executeCapability(acDevice, DeviceCapability.Temperature, 30)
        assertTrue(res30.success)
        assertEquals(30, mockAdapter.currentTemperature)
    }

    @Test
    fun testTemperatureCapabilityOutOfRangeRejection() = runBlocking {
        val res15 = mockAdapter.executeCapability(acDevice, DeviceCapability.Temperature, 15)
        assertFalse(res15.success)
        assertTrue(res15.message.contains("out of supported range"))

        val res35 = mockAdapter.executeCapability(acDevice, DeviceCapability.Temperature, 35)
        assertFalse(res35.success)
        assertTrue(res35.message.contains("out of supported range"))
    }

    @Test
    fun testModeCapability() = runBlocking {
        val coolRes = mockAdapter.executeCapability(acDevice, DeviceCapability.HvacMode, "COOL")
        assertTrue(coolRes.success)
        assertEquals(AcMode.COOL, mockAdapter.currentMode)

        val heatRes = mockAdapter.executeCapability(acDevice, DeviceCapability.HvacMode, AcMode.HEAT)
        assertTrue(heatRes.success)
        assertEquals(AcMode.HEAT, mockAdapter.currentMode)

        val invalidMode = mockAdapter.executeCapability(acDevice, DeviceCapability.HvacMode, "TURBO_ICE")
        assertFalse(invalidMode.success)
        assertTrue(invalidMode.message.contains("Invalid AC mode"))
    }

    @Test
    fun testFanSpeedAndSwingCapability() = runBlocking {
        val fanRes = mockAdapter.executeCapability(acDevice, DeviceCapability.FanSpeed, "HIGH")
        assertTrue(fanRes.success)
        assertEquals(AcFanSpeed.HIGH, mockAdapter.currentFanSpeed)

        val swingRes = mockAdapter.executeCapability(acDevice, DeviceCapability.Swing, "VERTICAL")
        assertTrue(swingRes.success)
        assertEquals(AcSwing.VERTICAL, mockAdapter.currentSwing)
    }

    @Test
    fun testUnconfiguredAdapterTruthfulMessage() = runBlocking {
        val res = unconfiguredAdapter.executeCapability(acDevice, DeviceCapability.Temperature, 24)
        assertFalse(res.success)
        assertTrue(res.message.contains("Physical AC hardware setup is pending"))
    }
}
