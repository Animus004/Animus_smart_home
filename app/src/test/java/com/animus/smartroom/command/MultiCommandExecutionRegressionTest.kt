package com.animus.smartroom.command

import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.device.adapter.MockAirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class MultiCommandExecutionRegressionTest {

    private lateinit var registry: DeviceRegistry
    private lateinit var mockAcAdapter: MockAirConditionerAdapter
    private lateinit var router: CommandRouter

    @Before
    fun setUp() {
        registry = DeviceRegistry()
        mockAcAdapter = MockAirConditionerAdapter()

        val acDevice = RoomDevice(
            id = "bedroom_ac",
            displayName = "Bedroom AC",
            type = DeviceType.AIR_CONDITIONER,
            connectionState = DeviceConnectionState.Available,
            supportedCapabilities = setOf(
                DeviceCapability.Power,
                DeviceCapability.Temperature,
                DeviceCapability.HvacMode,
                DeviceCapability.FanSpeed
            ),
            aliases = listOf("AC", "Air Conditioner", "Room AC")
        )

        registry.registerDevice(acDevice)
        registry.registerAdapterForType(DeviceType.AIR_CONDITIONER, mockAcAdapter)

        router = CommandRouter(
            deviceRegistry = registry
        )
    }

    @Test
    fun testThreeCommandsExecution() = runBlocking {
        val commands = listOf(
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Power,
                value = true
            ),
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Temperature,
                value = 23
            ),
            AnimusCommand.SetVolume(percentage = 40)
        )

        val result = router.execute(commands)
        // SetVolume with null controller reports "Volume set to 40%" (or message)
        assertTrue(result.success)
        assertTrue(mockAcAdapter.powerState)
        assertEquals(23, mockAcAdapter.currentTemperature)
        assertTrue(result.message.contains("23°C"))
        assertTrue(result.message.contains("40%"))
    }

    @Test
    fun testFourCommandsExecutionMixed() = runBlocking {
        val commands = listOf(
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Power,
                value = true
            ),
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Temperature,
                value = 21
            ),
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.HvacMode,
                value = "COOL"
            ),
            AnimusCommand.SetVolume(percentage = 60)
        )

        val result = router.execute(commands)
        assertTrue(result.success)
        assertTrue(mockAcAdapter.powerState)
        assertEquals(21, mockAcAdapter.currentTemperature)
        assertEquals(com.animus.smartroom.device.adapter.AcMode.COOL, mockAcAdapter.currentMode)
        assertTrue(result.message.contains("21°C"))
        assertTrue(result.message.contains("60%"))
    }

    @Test
    fun testDependencyReorderingConnectionBeforePlayback() {
        val originalList = listOf(
            AnimusCommand.PlayMusic(title = "Mahi Ve", artist = ""),
            AnimusCommand.SetVolume(percentage = 35),
            AnimusCommand.ConnectBluetoothDevice(deviceName = "LG soundbar")
        )

        val reordered = router.orderCommandsForExecution(originalList)

        assertEquals(3, reordered.size)
        // Connect command moved to front
        assertTrue(reordered[0] is AnimusCommand.ConnectBluetoothDevice)
        assertEquals("LG soundbar", (reordered[0] as AnimusCommand.ConnectBluetoothDevice).deviceName)
        // Other commands follow
        assertTrue(reordered[1] is AnimusCommand.PlayMusic)
        assertTrue(reordered[2] is AnimusCommand.SetVolume)
    }

    @Test
    fun testPartialFailurePolicyIndependentContinuation() = runBlocking {
        // Command 1: Valid AC power ON
        // Command 2: Invalid AC Swing (Unsupported capability on this AC)
        // Command 3: Valid AC Temperature
        // Command 4: Valid Volume
        val commands = listOf(
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Power,
                value = true
            ),
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Swing,
                value = "VERTICAL"
            ),
            AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = DeviceCapability.Temperature,
                value = 22
            ),
            AnimusCommand.SetVolume(percentage = 50)
        )

        val result = router.execute(commands)
        // Overall success is false because command #2 failed
        assertFalse(result.success)
        // But commands #1, #3, and #4 continued to execute successfully!
        assertTrue(mockAcAdapter.powerState)
        assertEquals(22, mockAcAdapter.currentTemperature)
        assertTrue(result.message.contains("does not support capability"))
        assertTrue(result.message.contains("22°C"))
        assertTrue(result.message.contains("50%"))
    }
}
