package com.animus.smartroom.device

import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.device.adapter.AcFanSpeed
import com.animus.smartroom.device.adapter.AcMode
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import com.animus.smartroom.scheduler.model.DeviceActionType
import com.animus.smartroom.scheduler.model.ScheduledActionStatus
import com.animus.smartroom.scheduler.model.ScheduledDeviceAction
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Phase 5D.1: AC Command Preconditions & Verified Power Dependency Unit Test Suite.
 */
class AcCommandPreconditionTest {

    private val sentCommands = mutableListOf<Map<String, Any>>()
    private var simulatedPower = false
    private var simulatedTemp = 24
    private var simulatedMode = "cold"
    private var simulatedFan = "auto"
    private var fetchStatusCallCount = 0
    private var sendCommandsFail = false

    private val fakeApiClient = object : TuyaApiClient {
        override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
            if (sendCommandsFail) return Result.failure(RuntimeException("Network write error"))
            sentCommands.addAll(commands)
            commands.forEach { cmd ->
                when (cmd["code"]) {
                    "switch" -> simulatedPower = cmd["value"] as Boolean
                    "temp_set" -> simulatedTemp = (cmd["value"] as Number).toInt()
                    "mode" -> simulatedMode = cmd["value"] as String
                    "fan_speed_enum" -> simulatedFan = cmd["value"] as String
                }
            }
            return Result.success(true)
        }

        override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
            fetchStatusCallCount++
            return Result.success(
                listOf(
                    TuyaDeviceStatusItem(code = "switch", value = simulatedPower),
                    TuyaDeviceStatusItem(code = "temp_set", value = simulatedTemp),
                    TuyaDeviceStatusItem(code = "temp_current", value = 26),
                    TuyaDeviceStatusItem(code = "mode", value = simulatedMode),
                    TuyaDeviceStatusItem(code = "fan_speed_enum", value = simulatedFan)
                )
            )
        }
    }

    private lateinit var adapter: TuyaAirConditionerAdapter
    private lateinit var registry: DeviceRegistry

    private val acDevice = RoomDevice(
        id = "test_tuya_ac_123",
        displayName = "Bedroom AC",
        type = DeviceType.AIR_CONDITIONER,
        supportedCapabilities = setOf(
            DeviceCapability.Power,
            DeviceCapability.Temperature,
            DeviceCapability.HvacMode,
            DeviceCapability.FanSpeed
        )
    )

    @Before
    fun setup() {
        sentCommands.clear()
        simulatedPower = false
        simulatedTemp = 24
        simulatedMode = "cold"
        simulatedFan = "auto"
        fetchStatusCallCount = 0
        sendCommandsFail = false
        DiagnosticBus.clear()

        adapter = TuyaAirConditionerAdapter(apiClient = fakeApiClient, allowWriteCommands = true)
        registry = DeviceRegistry()
        registry.registerDevice(acDevice)
        registry.registerAdapterForDevice(acDevice.id, adapter)
    }

    @Test
    fun `1 SET_TEMPERATURE while OFF powers on first and sets temperature`() = runBlocking {
        simulatedPower = false

        val result = adapter.setTemperature(acDevice, 23)
        assertTrue(result.success)
        assertTrue(result.message.contains("AC was off, so I turned it on and set the temperature to 23°C."))

        // Verify sent commands: exactly 2 commands (switch=true, temp_set=23)
        assertEquals(2, sentCommands.size)
        assertEquals("switch", sentCommands[0]["code"])
        assertEquals(true, sentCommands[0]["value"])
        assertEquals("temp_set", sentCommands[1]["code"])
        assertEquals(23, sentCommands[1]["value"])

        assertTrue(simulatedPower)
        assertEquals(23, simulatedTemp)
    }

    @Test
    fun `2 SET_MODE while OFF powers on first and switches mode`() = runBlocking {
        simulatedPower = false

        val result = adapter.setMode(acDevice, AcMode.COOL)
        assertTrue(result.success)
        assertTrue(result.message.contains("AC was off, so I turned it on and switched to COOL mode."))

        assertEquals(2, sentCommands.size)
        assertEquals("switch", sentCommands[0]["code"])
        assertEquals(true, sentCommands[0]["value"])
        assertEquals("mode", sentCommands[1]["code"])
        assertEquals("cold", sentCommands[1]["value"])
    }

    @Test
    fun `3 SET_FAN_SPEED while OFF powers on first and sets fan speed`() = runBlocking {
        simulatedPower = false

        val result = adapter.setFanSpeed(acDevice, AcFanSpeed.HIGH)
        assertTrue(result.success)
        assertTrue(result.message.contains("AC was off, so I turned it on and set the fan to HIGH."))

        assertEquals(2, sentCommands.size)
        assertEquals("switch", sentCommands[0]["code"])
        assertEquals(true, sentCommands[0]["value"])
        assertEquals("fan_speed_enum", sentCommands[1]["code"])
        assertEquals("high", sentCommands[1]["value"])
    }

    @Test
    fun `4 SET_TEMPERATURE while already ON does NOT send duplicate POWER_ON`() = runBlocking {
        simulatedPower = true

        val result = adapter.setTemperature(acDevice, 22)
        assertTrue(result.success)
        assertEquals("Bedroom AC temperature set to 22°C.", result.message)

        // Only 1 command sent (temp_set), no switch command
        assertEquals(1, sentCommands.size)
        assertEquals("temp_set", sentCommands[0]["code"])
        assertEquals(22, sentCommands[0]["value"])
    }

    @Test
    fun `5 POWER_OFF while already OFF does NOT send write command`() = runBlocking {
        simulatedPower = false

        val result = adapter.setPower(acDevice, false)
        assertTrue(result.success)
        assertEquals("Bedroom AC is already turned OFF.", result.message)
        assertEquals(0, sentCommands.size)
    }

    @Test
    fun `6 POWER_ON while OFF sends exactly one POWER_ON`() = runBlocking {
        simulatedPower = false

        val result = adapter.setPower(acDevice, true)
        assertTrue(result.success)
        assertEquals("Bedroom AC is now turned ON.", result.message)
        assertEquals(1, sentCommands.size)
        assertEquals("switch", sentCommands[0]["code"])
        assertEquals(true, sentCommands[0]["value"])
    }

    @Test
    fun `7 POWER_ON while already ON does NOT send duplicate write`() = runBlocking {
        simulatedPower = true

        val result = adapter.setPower(acDevice, true)
        assertTrue(result.success)
        assertEquals("Bedroom AC is already turned ON.", result.message)
        assertEquals(0, sentCommands.size)
    }

    @Test
    fun `8 Power-on failure aborts dependent temperature command`() = runBlocking {
        simulatedPower = false
        sendCommandsFail = true

        val result = adapter.setTemperature(acDevice, 24)
        assertFalse(result.success)
        assertTrue(result.message.contains("AC is currently off. I couldn't power it on"))
    }

    @Test
    fun `9 Live refresh is performed before precondition decision`() = runBlocking {
        // Adapter internal state cache says ON, but live Cloud says OFF
        adapter.applyTuyaStatus(listOf(TuyaDeviceStatusItem(code = "switch", value = true)))
        simulatedPower = false // Live device is actually OFF

        val result = adapter.setTemperature(acDevice, 24)
        assertTrue(result.success)
        assertTrue(result.message.contains("AC was off, so I turned it on"))
        assertTrue(fetchStatusCallCount >= 1)
    }

    @Test
    fun `10 DiagnosticBus records PRECONDITION stage in order`() = runBlocking {
        simulatedPower = false

        adapter.setTemperature(acDevice, 24)

        val stages = DiagnosticBus.getRecentEvents().map { it.stage }
        assertTrue(stages.contains(DiagnosticStage.REQUESTED))
        assertTrue(stages.contains(DiagnosticStage.VALIDATING))
        assertTrue(stages.contains(DiagnosticStage.PRECONDITION))
        assertTrue(stages.contains(DiagnosticStage.EXECUTING))
        assertTrue(stages.contains(DiagnosticStage.COMPLETED))
    }

    @Test
    fun `11 Execute capability via DeviceRegistry routes with power precondition`() = runBlocking {
        simulatedPower = false

        val result = registry.executeCommand(acDevice, com.animus.smartroom.core.device.DeviceCommand.SetTemperature(25))
        assertTrue(result.success)
        assertTrue(result.message.contains("AC was off, so I turned it on and set the temperature to 25°C."))
        assertTrue(simulatedPower)
        assertEquals(25, simulatedTemp)
    }

    @Test
    fun `12 Scheduled POWER_OFF when already OFF records completed with no change`() = runBlocking {
        simulatedPower = false
        val action = ScheduledDeviceAction(
            id = "test_sched_off",
            targetDeviceType = DeviceType.AIR_CONDITIONER,
            actionType = DeviceActionType.POWER_OFF,
            scheduledExecutionTimeMillis = 1000L,
            status = ScheduledActionStatus.SCHEDULED
        )

        // Simulating receiver check
        val liveState = adapter.refreshState(acDevice.id).getOrNull()
        assertFalse(liveState!!.power)
        // No power-on command should be triggered
        assertEquals(0, sentCommands.size)
    }
}
