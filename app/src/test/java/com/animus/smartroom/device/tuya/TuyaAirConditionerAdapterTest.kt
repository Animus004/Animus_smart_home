package com.animus.smartroom.device.tuya

import com.animus.smartroom.device.ac.BackendAcClient
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TuyaAirConditionerAdapterTest {

    private val testDevice = RoomDevice(
        id = "ac_test_1",
        displayName = "Lloyd AC",
        type = DeviceType.AIR_CONDITIONER
    )

    @Test
    fun testStatusUsesBackend() = runBlocking {
        val fakeClient = object : BackendAcClient() {
            override suspend fun getStatus(): Result<JSONObject> {
                val statusJson = JSONObject().apply {
                    put("power", true)
                    put("target_temperature", 24)
                    put("ambient_temperature", 26)
                    put("mode", "COOL")
                    put("fan_speed", "HIGH")
                    put("is_online", true)
                }
                return Result.success(statusJson)
            }
        }

        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)
        val state = adapter.getAcState(testDevice)

        assertTrue(state.power)
        assertEquals(24, state.targetTemperature)
        assertEquals(26, state.ambientTemperature)
        assertEquals(AcMode.COOL, state.mode)
        assertEquals(AcFanSpeed.HIGH, state.fanSpeed)
    }

    @Test
    fun testTemperatureCommandUsesBackend() = runBlocking {
        val fakeClient = object : BackendAcClient() {
            override suspend fun setTemperature(celsius: Int): Result<JSONObject> {
                val respJson = JSONObject().apply {
                    put("status", "SUCCESS")
                    put("target_temperature", celsius)
                    put("power", true)
                }
                return Result.success(respJson)
            }
        }

        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)
        val result = adapter.setTemperature(testDevice, 22)

        assertTrue(result.success)
        assertEquals(22, adapter.acState.value.targetTemperature)
    }

    @Test
    fun testPowerCommandUsesBackend() = runBlocking {
        val fakeClient = object : BackendAcClient() {
            override suspend fun setPower(on: Boolean): Result<JSONObject> {
                val respJson = JSONObject().apply {
                    put("status", "SUCCESS")
                    put("power", on)
                }
                return Result.success(respJson)
            }
        }

        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)
        val result = adapter.setPower(testDevice, true)

        assertTrue(result.success)
        assertTrue(adapter.acState.value.power)
    }

    @Test
    fun testBackendFailureDoesNotSimulateSuccess() = runBlocking {
        val fakeClient = object : BackendAcClient() {
            override suspend fun setTemperature(celsius: Int): Result<JSONObject> {
                return Result.failure(Exception("TCP 6668 timeout on PC"))
            }
        }

        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)
        val result = adapter.setTemperature(testDevice, 24)

        assertFalse(result.success)
        assertTrue(result.message.contains("Failed to set"))
    }

    @Test
    fun testTimeoutDoesNotSimulateSuccess() = runBlocking {
        val fakeClient = object : BackendAcClient() {
            override suspend fun setPower(on: Boolean): Result<JSONObject> {
                return Result.failure(Exception("Connect timeout"))
            }
        }

        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)
        val result = adapter.setPower(testDevice, true)

        assertFalse(result.success)
        assertTrue(result.message.contains("Connect timeout"))
    }

    @Test
    fun testInvalidTemperatureRejectedLocally() = runBlocking {
        val fakeClient = BackendAcClient()
        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)

        val resultLow = adapter.setTemperature(testDevice, 14)
        assertFalse(resultLow.success)
        assertTrue(resultLow.message.contains("Invalid temperature"))

        val resultHigh = adapter.setTemperature(testDevice, 35)
        assertFalse(resultHigh.success)
        assertTrue(resultHigh.message.contains("Invalid temperature"))
    }

    @Test
    fun testHeatModeRejected() = runBlocking {
        val fakeClient = BackendAcClient()
        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)

        val result = adapter.setMode(testDevice, AcMode.HEAT)
        assertFalse(result.success)
        assertTrue(result.message.contains("does not support heating mode"))
    }

    @Test
    fun testActualBackendResponseIsMappedToUiState() = runBlocking {
        val fakeClient = object : BackendAcClient() {
            override suspend fun setMode(modeStr: String): Result<JSONObject> {
                val respJson = JSONObject().apply {
                    put("status", "SUCCESS")
                    put("actual_state", JSONObject().apply {
                        put("power", true)
                        put("target_temperature", 25)
                        put("ambient_temperature", 27)
                        put("mode", "DRY")
                        put("fan_speed", "LOW")
                    })
                }
                return Result.success(respJson)
            }
        }

        val adapter = TuyaAirConditionerAdapter(backendAcClient = fakeClient)
        val result = adapter.setMode(testDevice, AcMode.DRY)

        assertTrue(result.success)
        assertEquals(AcMode.DRY, adapter.acState.value.mode)
        assertEquals(25, adapter.acState.value.targetTemperature)
        assertEquals(AcFanSpeed.LOW, adapter.acState.value.fanSpeed)
    }
}
