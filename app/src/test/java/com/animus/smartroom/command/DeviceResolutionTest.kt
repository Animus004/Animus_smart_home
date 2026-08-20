package com.animus.smartroom.command

import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.command.router.DeviceResolutionResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DeviceResolutionTest {

    private val deviceLg = BluetoothAudioDevice(
        name = "LG SNC4R(79)",
        macAddress = "54:15:89:DC:A5:79",
        alias = "Bedroom Speaker",
        isConnected = true,
        isAudioDevice = true
    )

    private val deviceStone = BluetoothAudioDevice(
        name = "Stone Spinx Pro",
        macAddress = "04:7D:46:72:A7:E9",
        alias = "Desk Speaker",
        isConnected = false,
        isAudioDevice = true
    )

    private val deviceTv = BluetoothAudioDevice(
        name = "Aavante Bar 1550",
        macAddress = "11:22:33:44:55:66",
        alias = "TV Soundbar",
        isConnected = false,
        isAudioDevice = true
    )

    private val deviceHeadphones = BluetoothAudioDevice(
        name = "Sony WH-1000XM4",
        macAddress = "AA:BB:CC:DD:EE:FF",
        alias = null,
        isConnected = false,
        isAudioDevice = true
    )

    @Test
    fun testExactAliasResolution() {
        val paired = listOf(deviceLg, deviceStone, deviceTv)

        val result1 = CommandRouter.resolveDeviceTarget("Bedroom Speaker", paired)
        assertTrue(result1 is DeviceResolutionResult.Match)
        assertEquals("54:15:89:DC:A5:79", (result1 as DeviceResolutionResult.Match).device.macAddress)

        val result2 = CommandRouter.resolveDeviceTarget("my bedroom speaker", paired)
        assertTrue(result2 is DeviceResolutionResult.Match)
        assertEquals("54:15:89:DC:A5:79", (result2 as DeviceResolutionResult.Match).device.macAddress)

        val result3 = CommandRouter.resolveDeviceTarget("TV Soundbar", paired)
        assertTrue(result3 is DeviceResolutionResult.Match)
        assertEquals("11:22:33:44:55:66", (result3 as DeviceResolutionResult.Match).device.macAddress)
    }

    @Test
    fun testExactAndSubstringAndroidNameResolution() {
        val paired = listOf(deviceLg, deviceStone, deviceTv, deviceHeadphones)

        // Exact name
        val result1 = CommandRouter.resolveDeviceTarget("Stone Spinx Pro", paired)
        assertTrue(result1 is DeviceResolutionResult.Match)
        assertEquals("04:7D:46:72:A7:E9", (result1 as DeviceResolutionResult.Match).device.macAddress)

        // Substring name
        val result2 = CommandRouter.resolveDeviceTarget("Aavante", paired)
        assertTrue(result2 is DeviceResolutionResult.Match)
        assertEquals("11:22:33:44:55:66", (result2 as DeviceResolutionResult.Match).device.macAddress)

        val result3 = CommandRouter.resolveDeviceTarget("LG", paired)
        assertTrue(result3 is DeviceResolutionResult.Match)
        assertEquals("54:15:89:DC:A5:79", (result3 as DeviceResolutionResult.Match).device.macAddress)
    }

    @Test
    fun testGenericSpeakerResolutionSingleVsMultiple() {
        val singleList = listOf(deviceStone)

        // Single speaker: resolves automatically
        val resultSingle = CommandRouter.resolveDeviceTarget("speaker", singleList)
        assertTrue(resultSingle is DeviceResolutionResult.Match)
        assertEquals("04:7D:46:72:A7:E9", (resultSingle as DeviceResolutionResult.Match).device.macAddress)

        // Multiple speakers where 1 is connected and 1 is disconnected: switches to the disconnected speaker
        val twoSpeakers = listOf(deviceLg, deviceStone)
        val resultTwo = CommandRouter.resolveDeviceTarget("speaker", twoSpeakers)
        assertTrue(resultTwo is DeviceResolutionResult.Match)
        assertEquals("04:7D:46:72:A7:E9", (resultTwo as DeviceResolutionResult.Match).device.macAddress)

        // Multiple disconnected speakers (ambiguous): asks user which one
        val multipleDisconnected = listOf(
            deviceStone.copy(isConnected = false),
            deviceTv.copy(isConnected = false)
        )
        val resultAmbiguous = CommandRouter.resolveDeviceTarget("speaker", multipleDisconnected)
        assertTrue(resultAmbiguous is DeviceResolutionResult.Ambiguous)
        assertEquals("Which speaker do you want to use?", (resultAmbiguous as DeviceResolutionResult.Ambiguous).question)
    }

    @Test
    fun testHeadphoneResolution() {
        val paired = listOf(deviceLg, deviceHeadphones)

        val result = CommandRouter.resolveDeviceTarget("headphones", paired)
        assertTrue(result is DeviceResolutionResult.Match)
        assertEquals("AA:BB:CC:DD:EE:FF", (result as DeviceResolutionResult.Match).device.macAddress)
    }

    @Test
    fun testParserExtractsAliasTargetsCleanly() {
        val parser = LocalCommandParser()

        val cmd1 = parser.parse("switch to Bedroom Speaker")
        assertTrue(cmd1 is com.animus.smartroom.command.model.AnimusCommand.SwitchBluetoothDevice)
        assertEquals("Bedroom Speaker", (cmd1 as com.animus.smartroom.command.model.AnimusCommand.SwitchBluetoothDevice).deviceName)

        val cmd2 = parser.parse("switch to my bedroom speaker")
        assertTrue(cmd2 is com.animus.smartroom.command.model.AnimusCommand.SwitchBluetoothDevice)
        assertEquals("bedroom speaker", (cmd2 as com.animus.smartroom.command.model.AnimusCommand.SwitchBluetoothDevice).deviceName)

        val cmd3 = parser.parse("switch to the TV soundbar")
        assertTrue(cmd3 is com.animus.smartroom.command.model.AnimusCommand.SwitchBluetoothDevice)
        assertEquals("TV soundbar", (cmd3 as com.animus.smartroom.command.model.AnimusCommand.SwitchBluetoothDevice).deviceName)
    }
}
