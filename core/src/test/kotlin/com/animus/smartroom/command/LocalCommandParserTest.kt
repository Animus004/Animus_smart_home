package com.animus.smartroom.command

import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LocalCommandParserTest {

    private lateinit var parser: LocalCommandParser

    @Before
    fun setUp() {
        parser = LocalCommandParser()
    }

    @Test
    fun testPlayZaraZara() {
        val result = parser.parse("play Zara Zara")
        assertTrue(result is AnimusCommand.PlayMusic)
        val play = result as AnimusCommand.PlayMusic
        assertEquals("Zara Zara", play.title)
        assertEquals(null, play.artist)
    }

    @Test
    fun testPlayZaraZaraByArtist() {
        val result = parser.parse("play Zara Zara by Bombay Jayashri")
        assertTrue(result is AnimusCommand.PlayMusic)
        val play = result as AnimusCommand.PlayMusic
        assertEquals("Zara Zara", play.title)
        assertEquals("Bombay Jayashri", play.artist)
    }

    @Test
    fun testPauseCommands() {
        assertEquals(AnimusCommand.PauseMusic, parser.parse("pause"))
        assertEquals(AnimusCommand.PauseMusic, parser.parse("pause the music"))
        assertEquals(AnimusCommand.PauseMusic, parser.parse("stop music"))
    }

    @Test
    fun testResumeCommands() {
        assertEquals(AnimusCommand.ResumeMusic, parser.parse("resume"))
        assertEquals(AnimusCommand.ResumeMusic, parser.parse("continue playing"))
        assertEquals(AnimusCommand.ResumeMusic, parser.parse("unpause"))
    }

    @Test
    fun testNextCommands() {
        assertEquals(AnimusCommand.NextTrack, parser.parse("next"))
        assertEquals(AnimusCommand.NextTrack, parser.parse("next song"))
        assertEquals(AnimusCommand.NextTrack, parser.parse("skip track"))
    }

    @Test
    fun testPreviousCommands() {
        assertEquals(AnimusCommand.PreviousTrack, parser.parse("previous"))
        assertEquals(AnimusCommand.PreviousTrack, parser.parse("previous song"))
        assertEquals(AnimusCommand.PreviousTrack, parser.parse("prev track"))
    }

    @Test
    fun testVolumeCommands() {
        val vol40 = parser.parse("volume 40")
        assertTrue(vol40 is AnimusCommand.SetVolume)
        assertEquals(40, (vol40 as AnimusCommand.SetVolume).percentage)

        val vol75 = parser.parse("set volume to 75 percent")
        assertTrue(vol75 is AnimusCommand.SetVolume)
        assertEquals(75, (vol75 as AnimusCommand.SetVolume).percentage)

        val vol100 = parser.parse("set the volume to 100%")
        assertTrue(vol100 is AnimusCommand.SetVolume)
        assertEquals(100, (vol100 as AnimusCommand.SetVolume).percentage)
    }

    @Test
    fun testConnectCommands() {
        val connectLg = parser.parse("connect my LG soundbar")
        assertTrue(connectLg is AnimusCommand.ConnectBluetoothDevice)
        assertEquals("LG soundbar", (connectLg as AnimusCommand.ConnectBluetoothDevice).deviceName)

        val connectGeneric = parser.parse("connect")
        assertTrue(connectGeneric is AnimusCommand.ConnectBluetoothDevice)
        assertEquals(null, (connectGeneric as AnimusCommand.ConnectBluetoothDevice).deviceName)
    }

    @Test
    fun testDisconnectCommands() {
        assertEquals(AnimusCommand.DisconnectBluetoothDevice, parser.parse("disconnect"))
        assertEquals(AnimusCommand.DisconnectBluetoothDevice, parser.parse("disconnect bluetooth"))
        assertEquals(AnimusCommand.DisconnectBluetoothDevice, parser.parse("disconnect speaker"))
    }

    @Test
    fun testSwitchDeviceCommands() {
        val switchSpeaker = parser.parse("switch speaker")
        assertTrue(switchSpeaker is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("speaker", (switchSpeaker as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchToSpeaker = parser.parse("switch to speaker")
        assertTrue(switchToSpeaker is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("speaker", (switchToSpeaker as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchSpeakers = parser.parse("switch speakers")
        assertTrue(switchSpeakers is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("speakers", (switchSpeakers as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchToMySpeaker = parser.parse("switch to my speaker")
        assertTrue(switchToMySpeaker is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("speaker", (switchToMySpeaker as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchToLg = parser.parse("switch to LG")
        assertTrue(switchToLg is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("LG", (switchToLg as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchToStone = parser.parse("switch to Stone Spinx Pro")
        assertTrue(switchToStone is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("Stone Spinx Pro", (switchToStone as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val changeSpeaker = parser.parse("change speaker")
        assertTrue(changeSpeaker is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("speaker", (changeSpeaker as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val changeToSpeaker = parser.parse("change to speaker")
        assertTrue(changeToSpeaker is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("speaker", (changeToSpeaker as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchHeadphones = parser.parse("switch to headphones")
        assertTrue(switchHeadphones is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("headphones", (switchHeadphones as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val switchSoundbar = parser.parse("switch device to LG SNC4R")
        assertTrue(switchSoundbar is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("LG SNC4R", (switchSoundbar as AnimusCommand.SwitchBluetoothDevice).deviceName)

        val changeDeviceHeadphones = parser.parse("change device to headphones")
        assertTrue(changeDeviceHeadphones is AnimusCommand.SwitchBluetoothDevice)
        assertEquals("headphones", (changeDeviceHeadphones as AnimusCommand.SwitchBluetoothDevice).deviceName)
    }

    @Test
    fun testUnknownCommands() {
        val result = parser.parse("random unsupported sentence")
        assertTrue(result is AnimusCommand.UnknownCommand)
        assertEquals("random unsupported sentence", (result as AnimusCommand.UnknownCommand).rawText)
    }
}
