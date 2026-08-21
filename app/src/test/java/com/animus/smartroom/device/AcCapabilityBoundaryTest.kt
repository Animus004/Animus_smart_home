package com.animus.smartroom.device

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.device.tuya.model.TuyaAcState
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class AcCapabilityBoundaryTest {

    private lateinit var fakeClient: FakeTuyaApiClient
    private lateinit var adapter: TuyaAirConditionerAdapter
    private lateinit var testDevice: RoomDevice

    private class FakeTuyaApiClient : TuyaApiClient {
        val sentCommands = mutableListOf<Map<String, Any>>()

        override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
            sentCommands.addAll(commands)
            return Result.success(true)
        }

        override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
            return Result.success(
                listOf(
                    TuyaDeviceStatusItem("switch", true),
                    TuyaDeviceStatusItem("temp_set", 24),
                    TuyaDeviceStatusItem("mode", "auto"),
                    TuyaDeviceStatusItem("fan_speed_enum", "auto")
                )
            )
        }
    }

    @Before
    fun setUp() {
        fakeClient = FakeTuyaApiClient()
        adapter = TuyaAirConditionerAdapter(fakeClient, allowWriteCommands = true)
        testDevice = RoomDevice(
            id = "test_ac_001",
            displayName = "Bedroom AC",
            type = DeviceType.AIR_CONDITIONER,
            connectionState = DeviceConnectionState.Connected
        )
    }

    @Test
    fun testLowerTemperatureBoundaryRejection() = runBlocking {
        // 15°C must be rejected without calling API
        val result = adapter.setTemperature(testDevice, 15)
        assertFalse(result.success)
        assertTrue(result.message.contains("only supports 16°C to 30°C"))
        assertTrue("No Tuya API commands should be sent for 15°C", fakeClient.sentCommands.isEmpty())
    }

    @Test
    fun testUpperTemperatureBoundaryRejection() = runBlocking {
        // 31°C must be rejected without calling API
        val result = adapter.setTemperature(testDevice, 31)
        assertFalse(result.success)
        assertTrue(result.message.contains("only supports 16°C to 30°C"))
        assertTrue("No Tuya API commands should be sent for 31°C", fakeClient.sentCommands.isEmpty())
    }

    @Test
    fun testHeatModeRejection() = runBlocking {
        // HEAT mode must be rejected
        val result = adapter.setMode(testDevice, AcMode.HEAT)
        assertFalse(result.success)
        assertTrue(result.message.contains("does not support heating mode"))
        assertTrue("No Tuya API commands should be sent for HEAT mode", fakeClient.sentCommands.isEmpty())
    }

    @Test
    fun testSwingRejection() = runBlocking {
        val result = adapter.setSwing(testDevice, com.animus.smartroom.device.adapter.AcSwing.HORIZONTAL)
        assertFalse(result.success)
        assertTrue(result.message.contains("does not support motorized swing"))
    }
}
