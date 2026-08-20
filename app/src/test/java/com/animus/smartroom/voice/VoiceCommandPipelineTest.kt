package com.animus.smartroom.voice

import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.command.router.DeviceResolutionResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class VoiceCommandPipelineTest {

    private lateinit var brainManager: AnimusBrainManager

    private val pairedDevices = listOf(
        BluetoothAudioDevice(
            name = "LG SNC4R(79)",
            macAddress = "54:15:89:DC:A5:79",
            alias = "Bedroom Speaker",
            isConnected = true,
            isAudioDevice = true
        ),
        BluetoothAudioDevice(
            name = "Stone Spinx Pro",
            macAddress = "04:7D:46:72:A7:E9",
            alias = "Desk Speaker",
            isConnected = false,
            isAudioDevice = true
        )
    )

    @Before
    fun setUp() {
        brainManager = AnimusBrainManager()
    }

    @Test
    fun testVoiceTranscribedMusicCommandEntersBrain() = runBlocking {
        val voiceTranscribedText = "play Zara Zara by Bombay Jayashri"

        val brainResult = brainManager.interpret(voiceTranscribedText)
        assertTrue(brainResult is BrainResult.Success)

        val command = (brainResult as BrainResult.Success).command
        assertTrue(command is AnimusCommand.PlayMusic)
        assertEquals("Zara Zara", (command as AnimusCommand.PlayMusic).title)
        assertEquals("Bombay Jayashri", command.artist)
    }

    @Test
    fun testVoiceTranscribedVolumeCommandEntersBrain() = runBlocking {
        val voiceTranscribedText = "volume 50"

        val brainResult = brainManager.interpret(voiceTranscribedText)
        assertTrue(brainResult is BrainResult.Success)

        val command = (brainResult as BrainResult.Success).command
        assertTrue(command is AnimusCommand.SetVolume)
        assertEquals(50, (command as AnimusCommand.SetVolume).percentage)
    }

    @Test
    fun testVoiceTranscribedSwitchDeviceCommandResolvesAlias() = runBlocking {
        val voiceTranscribedText = "switch to Bedroom Speaker"

        val brainResult = brainManager.interpret(voiceTranscribedText)
        assertTrue(brainResult is BrainResult.Success)

        val command = (brainResult as BrainResult.Success).command
        assertTrue(command is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("Bedroom Speaker", (command as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val resolution = CommandRouter.resolveDeviceTarget(command.deviceName, pairedDevices)
        assertTrue(resolution is DeviceResolutionResult.Match)
        assertEquals("54:15:89:DC:A5:79", (resolution as DeviceResolutionResult.Match).device.macAddress)
    }

    @Test
    fun testVoiceTranscribedNoiseOrUnknownDoesNotCrash() = runBlocking {
        val noiseText = "muffled background noise"

        val brainResult = brainManager.interpret(noiseText)
        assertTrue(brainResult is BrainResult.Success)

        val command = (brainResult as BrainResult.Success).command
        assertTrue(command is AnimusCommand.UnknownCommand)
        assertEquals("muffled background noise", (command as AnimusCommand.UnknownCommand).rawText)
    }
}
