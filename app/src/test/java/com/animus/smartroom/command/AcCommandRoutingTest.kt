package com.animus.smartroom.command

import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.device.adapter.MockAirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AcCommandRoutingTest {

    private lateinit var parser: LocalCommandParser
    private lateinit var registry: DeviceRegistry
    private lateinit var mockAcAdapter: MockAirConditionerAdapter
    private lateinit var router: CommandRouter

    @Before
    fun setUp() {
        parser = LocalCommandParser()
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
                DeviceCapability.FanSpeed,
                DeviceCapability.Swing
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
    fun testParseNaturalLanguageAcCommands() {
        // Temperature
        val cmdTemp1 = parser.parse("set AC to 24 degrees")
        assertTrue(cmdTemp1 is AnimusCommand.SetDeviceCapability)
        val capTemp1 = cmdTemp1 as AnimusCommand.SetDeviceCapability
        assertEquals(DeviceCapability.Temperature, capTemp1.capability)
        assertEquals(24, capTemp1.value)

        val cmdTemp2 = parser.parse("set temperature to 22°c")
        assertTrue(cmdTemp2 is AnimusCommand.SetDeviceCapability)
        val capTemp2 = cmdTemp2 as AnimusCommand.SetDeviceCapability
        assertEquals(DeviceCapability.Temperature, capTemp2.capability)
        assertEquals(22, capTemp2.value)

        // Power
        val cmdPowerOn = parser.parse("turn on the AC")
        assertTrue(cmdPowerOn is AnimusCommand.SetDeviceCapability)
        val capOn = cmdPowerOn as AnimusCommand.SetDeviceCapability
        assertEquals(DeviceCapability.Power, capOn.capability)
        assertEquals(true, capOn.value)

        val cmdPowerOff = parser.parse("turn off air conditioner")
        assertTrue(cmdPowerOff is AnimusCommand.SetDeviceCapability)
        val capOff = cmdPowerOff as AnimusCommand.SetDeviceCapability
        assertEquals(DeviceCapability.Power, capOff.capability)
        assertEquals(false, capOff.value)

        // Mode
        val cmdMode = parser.parse("set AC to cool mode")
        assertTrue(cmdMode is AnimusCommand.SetDeviceCapability)
        val capMode = cmdMode as AnimusCommand.SetDeviceCapability
        assertEquals(DeviceCapability.HvacMode, capMode.capability)
        assertEquals("COOL", capMode.value)
    }

    @Test
    fun testValidateGeminiSetDeviceJson() {
        val rawJson = """
            {
                "commands": [
                    {
                        "command": "SET_DEVICE",
                        "target": "Bedroom AC",
                        "capability": "TEMPERATURE",
                        "value": 23
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(1, valid.commands.size)

        val cmd = valid.commands[0] as AnimusCommand.SetDeviceCapability
        assertEquals("Bedroom AC", cmd.target)
        assertEquals(DeviceCapability.Temperature, cmd.capability)
        assertEquals(23, cmd.value)
    }

    @Test
    fun testExecuteAcCommandViaRouter() = runBlocking {
        val command = AnimusCommand.SetDeviceCapability(
            target = "AC",
            capability = DeviceCapability.Temperature,
            value = 21
        )

        val result = router.execute(command)
        assertTrue(result.success)
        assertEquals(21, mockAcAdapter.currentTemperature)
        assertTrue(result.message.contains("21°C"))
    }

    @Test
    fun testMultiIntentMusicAndAc() = runBlocking {
        val rawJson = """
            {
                "commands": [
                    {
                        "command": "SET_DEVICE",
                        "target": "AC",
                        "capability": "TEMPERATURE",
                        "value": 24
                    },
                    {
                        "command": "SET_VOLUME",
                        "value": 50
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(2, valid.commands.size)

        assertTrue(valid.commands[0] is AnimusCommand.SetDeviceCapability)
        assertTrue(valid.commands[1] is AnimusCommand.SetVolume)
    }
}
