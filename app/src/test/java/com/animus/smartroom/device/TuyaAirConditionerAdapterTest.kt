package com.animus.smartroom.device

import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.adapter.AcSwing
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class TuyaAirConditionerAdapterTest {

    private lateinit var fakeClient: FakeTuyaApiClient
    private lateinit var adapter: TuyaAirConditionerAdapter
    private lateinit var testDevice: RoomDevice

    class FakeTuyaApiClient : TuyaApiClient {
        val sentCommands = mutableListOf<Map<String, Any>>()
        var statusToReturn = listOf<TuyaDeviceStatusItem>()
        var shouldSucceed = true

        override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
            return if (shouldSucceed) Result.success(statusToReturn)
            else Result.failure(RuntimeException("Network error"))
        }

        override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
            return if (shouldSucceed) {
                sentCommands.addAll(commands)
                val newStatus = statusToReturn.toMutableList()
                for (cmd in commands) {
                    val code = cmd["code"]?.toString() ?: continue
                    val value = cmd["value"] ?: continue
                    newStatus.removeAll { it.code == code }
                    newStatus.add(TuyaDeviceStatusItem(code, value))
                }
                statusToReturn = newStatus
                Result.success(true)
            } else {
                Result.failure(RuntimeException("Command write error"))
            }
        }
    }

    @Before
    fun setUp() {
        fakeClient = FakeTuyaApiClient()
        adapter = TuyaAirConditionerAdapter(
            apiClient = fakeClient,
            allowWriteCommands = true // enabled for adapter command mapping tests
        )

        testDevice = RoomDevice(
            id = "test_ac_id",
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
    }

    @Test
    fun testTranslateTuyaStatusToAnimusState() {
        val rawItems = listOf(
            TuyaDeviceStatusItem(code = "switch", value = true),
            TuyaDeviceStatusItem(code = "temp_set", value = 22),
            TuyaDeviceStatusItem(code = "temp_current", value = 25),
            TuyaDeviceStatusItem(code = "mode", value = "cold"),
            TuyaDeviceStatusItem(code = "fan_speed_enum", value = "mid")
        )

        val state = adapter.applyTuyaStatus(rawItems)

        assertTrue(state.power)
        assertEquals(22, state.targetTemperature)
        assertEquals(25, state.ambientTemperature)
        assertEquals(AcMode.COOL, state.mode)
        assertEquals(AcFanSpeed.MEDIUM, state.fanSpeed)
        assertTrue(state.isOnline)
    }

    @Test
    fun testTranslateTuyaStatusAllModesAndFanSpeeds() {
        // Auto mode, auto fan
        val statusAuto = adapter.applyTuyaStatus(
            listOf(
                TuyaDeviceStatusItem("mode", "auto"),
                TuyaDeviceStatusItem("fan_speed_enum", "auto")
            )
        )
        assertEquals(AcMode.AUTO, statusAuto.mode)
        assertEquals(AcFanSpeed.AUTO, statusAuto.fanSpeed)

        // Wet mode (DRY), low fan
        val statusDry = adapter.applyTuyaStatus(
            listOf(
                TuyaDeviceStatusItem("mode", "wet"),
                TuyaDeviceStatusItem("fan_speed_enum", "low")
            )
        )
        assertEquals(AcMode.DRY, statusDry.mode)
        assertEquals(AcFanSpeed.LOW, statusDry.fanSpeed)

        // Wind mode (FAN), high fan
        val statusFan = adapter.applyTuyaStatus(
            listOf(
                TuyaDeviceStatusItem("mode", "wind"),
                TuyaDeviceStatusItem("fan_speed_enum", "high")
            )
        )
        assertEquals(AcMode.FAN, statusFan.mode)
        assertEquals(AcFanSpeed.HIGH, statusFan.fanSpeed)
    }

    @Test
    fun testSetPowerTranslation() = runBlocking {
        val resultOn = adapter.setPower(testDevice, true)
        assertTrue(resultOn.success)
        assertEquals(1, fakeClient.sentCommands.size)
        assertEquals("switch", fakeClient.sentCommands[0]["code"])
        assertEquals(true, fakeClient.sentCommands[0]["value"])

        val resultOff = adapter.setPower(testDevice, false)
        assertTrue(resultOff.success)
        assertEquals(2, fakeClient.sentCommands.size)
        assertEquals("switch", fakeClient.sentCommands[1]["code"])
        assertEquals(false, fakeClient.sentCommands[1]["value"])
    }

    @Test
    fun testValidTemperatureTranslation() = runBlocking {
        val result24 = adapter.setTemperature(testDevice, 24)
        assertTrue(result24.success)
        assertEquals("temp_set", fakeClient.sentCommands[0]["code"])
        assertEquals(24, fakeClient.sentCommands[0]["value"])

        val result16 = adapter.setTemperature(testDevice, 16)
        assertTrue(result16.success)
        assertEquals(16, fakeClient.sentCommands[1]["value"])

        val result30 = adapter.setTemperature(testDevice, 30)
        assertTrue(result30.success)
        assertEquals(30, fakeClient.sentCommands[2]["value"])
    }

    @Test
    fun testSetTemperature24ExactControlledWrite() = runBlocking {
        val singleClient = FakeTuyaApiClient()
        val singleAdapter = TuyaAirConditionerAdapter(singleClient, allowWriteCommands = true)

        val result = singleAdapter.setTemperature(testDevice, 24)
        assertTrue(result.success)
        assertEquals(1, singleClient.sentCommands.size)
        assertEquals("temp_set", singleClient.sentCommands[0]["code"])
        assertEquals(24, singleClient.sentCommands[0]["value"])
        assertEquals(24, singleAdapter.acState.value.targetTemperature)
    }

    @Test
    fun testInvalidTemperatureRejection() = runBlocking {
        // Below 16°C
        val result15 = adapter.setTemperature(testDevice, 15)
        assertFalse(result15.success)
        assertTrue(result15.message.contains("15°C"))
        assertTrue(result15.message.contains("16°C to 30°C"))

        // Above 30°C
        val result31 = adapter.setTemperature(testDevice, 31)
        assertFalse(result31.success)
        assertTrue(result31.message.contains("31°C"))
        assertTrue(result31.message.contains("16°C to 30°C"))

        // No commands dispatched to Tuya for invalid temperatures
        assertEquals(0, fakeClient.sentCommands.size)
    }

    @Test
    fun testModeTranslation() = runBlocking {
        // COOL -> cold
        val resultCool = adapter.setMode(testDevice, AcMode.COOL)
        assertTrue(resultCool.success)
        assertEquals("mode", fakeClient.sentCommands[0]["code"])
        assertEquals("cold", fakeClient.sentCommands[0]["value"])

        // AUTO -> auto
        val resultAuto = adapter.setMode(testDevice, AcMode.AUTO)
        assertTrue(resultAuto.success)
        assertEquals("mode", fakeClient.sentCommands[1]["code"])
        assertEquals("auto", fakeClient.sentCommands[1]["value"])

        // DRY -> wet
        val resultDry = adapter.setMode(testDevice, AcMode.DRY)
        assertTrue(resultDry.success)
        assertEquals("mode", fakeClient.sentCommands[2]["code"])
        assertEquals("wet", fakeClient.sentCommands[2]["value"])

        // FAN -> wind
        val resultFan = adapter.setMode(testDevice, AcMode.FAN)
        assertTrue(resultFan.success)
        assertEquals("mode", fakeClient.sentCommands[3]["code"])
        assertEquals("wind", fakeClient.sentCommands[3]["value"])
    }

    @Test
    fun testUnsupportedHeatModeRejection() = runBlocking {
        val resultHeat = adapter.setMode(testDevice, AcMode.HEAT)
        assertFalse(resultHeat.success)
        assertTrue(resultHeat.message.contains("does not support heating mode"))
        assertEquals(0, fakeClient.sentCommands.size)
    }

    @Test
    fun testFanSpeedTranslation() = runBlocking {
        // LOW -> low
        val resultLow = adapter.setFanSpeed(testDevice, AcFanSpeed.LOW)
        assertTrue(resultLow.success)
        assertEquals("fan_speed_enum", fakeClient.sentCommands[0]["code"])
        assertEquals("low", fakeClient.sentCommands[0]["value"])

        // MEDIUM -> mid
        val resultMed = adapter.setFanSpeed(testDevice, AcFanSpeed.MEDIUM)
        assertTrue(resultMed.success)
        assertEquals("fan_speed_enum", fakeClient.sentCommands[1]["code"])
        assertEquals("mid", fakeClient.sentCommands[1]["value"])

        // HIGH -> high
        val resultHigh = adapter.setFanSpeed(testDevice, AcFanSpeed.HIGH)
        assertTrue(resultHigh.success)
        assertEquals("fan_speed_enum", fakeClient.sentCommands[2]["code"])
        assertEquals("high", fakeClient.sentCommands[2]["value"])

        // AUTO -> auto
        val resultAuto = adapter.setFanSpeed(testDevice, AcFanSpeed.AUTO)
        assertTrue(resultAuto.success)
        assertEquals("fan_speed_enum", fakeClient.sentCommands[3]["code"])
        assertEquals("auto", fakeClient.sentCommands[3]["value"])
    }

    @Test
    fun testUnsupportedSwingRejection() = runBlocking {
        val resultSwing = adapter.setSwing(testDevice, AcSwing.VERTICAL)
        assertFalse(resultSwing.success)
        assertTrue(resultSwing.message.contains("manual louvers"))
        assertEquals(0, fakeClient.sentCommands.size)
    }

    @Test
    fun testReadOnlySafetyGuard() = runBlocking {
        val readOnlyAdapter = TuyaAirConditionerAdapter(
            apiClient = fakeClient,
            allowWriteCommands = false // READ-ONLY MODE
        )

        val resultTemp = readOnlyAdapter.setTemperature(testDevice, 23)
        assertTrue(resultTemp.success)
        // Verified mapping reported in message but 0 commands dispatched to Tuya
        assertTrue(resultTemp.message.contains("23°C"))
        assertEquals(0, fakeClient.sentCommands.size)
        assertEquals(23, readOnlyAdapter.acState.value.targetTemperature)
    }

    @Test
    fun testReadbackMismatchRejection() = runBlocking {
        // When cloud accepts command but status returns old value (verification failure)
        val staticClient = object : TuyaApiClient {
            override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
                return Result.success(listOf(TuyaDeviceStatusItem("switch", false)))
            }
            override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
                return Result.success(true)
            }
        }
        val mismatchAdapter = TuyaAirConditionerAdapter(staticClient, allowWriteCommands = true)
        val result = mismatchAdapter.setPower(testDevice, true)
        assertFalse(result.success)
        assertTrue(result.message.contains("readback power was not ON"))
    }
}
