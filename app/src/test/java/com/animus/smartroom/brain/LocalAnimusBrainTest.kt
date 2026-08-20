package com.animus.smartroom.brain

import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.command.model.AnimusCommand
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LocalAnimusBrainTest {

    private lateinit var brain: LocalAnimusBrain

    @Before
    fun setUp() {
        brain = LocalAnimusBrain()
    }

    @Test
    fun testPlayCommands() = runBlocking {
        val res1 = brain.interpret("play Zara Zara")
        assertTrue(res1 is BrainResult.Success)
        val cmd1 = (res1 as BrainResult.Success).command as AnimusCommand.PlayMusic
        assertEquals("Zara Zara", cmd1.title)
        assertEquals(null, cmd1.artist)

        val res2 = brain.interpret("play Zara Zara by Bombay Jayashri")
        assertTrue(res2 is BrainResult.Success)
        val cmd2 = (res2 as BrainResult.Success).command as AnimusCommand.PlayMusic
        assertEquals("Zara Zara", cmd2.title)
        assertEquals("Bombay Jayashri", cmd2.artist)
    }

    @Test
    fun testTransportControls() = runBlocking {
        val pauseRes = brain.interpret("pause")
        assertTrue(pauseRes is BrainResult.Success)
        assertEquals(AnimusCommand.PauseMusic, (pauseRes as BrainResult.Success).command)

        val resumeRes = brain.interpret("resume playback")
        assertTrue(resumeRes is BrainResult.Success)
        assertEquals(AnimusCommand.ResumeMusic, (resumeRes as BrainResult.Success).command)

        val nextRes = brain.interpret("skip track")
        assertTrue(nextRes is BrainResult.Success)
        assertEquals(AnimusCommand.NextTrack, (nextRes as BrainResult.Success).command)

        val prevRes = brain.interpret("previous song")
        assertTrue(prevRes is BrainResult.Success)
        assertEquals(AnimusCommand.PreviousTrack, (prevRes as BrainResult.Success).command)
    }

    @Test
    fun testVolumeCommands() = runBlocking {
        val volRes = brain.interpret("set volume to 45%")
        assertTrue(volRes is BrainResult.Success)
        val cmd = (volRes as BrainResult.Success).command as AnimusCommand.SetVolume
        assertEquals(45, cmd.percentage)
    }

    @Test
    fun testBluetoothCommands() = runBlocking {
        val switchRes1 = brain.interpret("switch to Bedroom Speaker")
        assertTrue(switchRes1 is BrainResult.Success)
        val cmd1 = (switchRes1 as BrainResult.Success).command as AnimusCommand.SwitchBluetoothDevice
        assertEquals("Bedroom Speaker", cmd1.deviceName)

        val switchRes2 = brain.interpret("switch speaker")
        assertTrue(switchRes2 is BrainResult.Success)
        val cmd2 = (switchRes2 as BrainResult.Success).command as AnimusCommand.SwitchBluetoothDevice
        assertEquals("speaker", cmd2.deviceName)

        val disconnectRes = brain.interpret("disconnect")
        assertTrue(disconnectRes is BrainResult.Success)
        assertEquals(AnimusCommand.DisconnectBluetoothDevice, (disconnectRes as BrainResult.Success).command)
    }

    @Test
    fun testUnknownCommands() = runBlocking {
        val unknownRes = brain.interpret("something completely unrecognized")
        assertTrue(unknownRes is BrainResult.Success)
        val cmd = (unknownRes as BrainResult.Success).command as AnimusCommand.UnknownCommand
        assertEquals("something completely unrecognized", cmd.rawText)
    }
}
