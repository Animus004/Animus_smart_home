package com.animus.smartroom.brain

import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.parser.LocalCommandParser
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainResponse
import com.animus.smartroom.core.brain.session.AssistantSessionContext
import com.animus.smartroom.core.brain.session.ConversationReferenceResolver
import com.animus.smartroom.device.adapter.ProjectorDeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.provider.PcLocalMusicProvider
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PhaseE12TruthfulRecoveryTestSuite {

    private val parser = LocalCommandParser()

    // ─── 1. PROJECTOR COMMAND COVERAGE ───────────────────────────────────────────

    @Test
    fun testE12_01_ProjectorNaturalPhrases_ParsedToSetDeviceCapability() {
        val offPhrases = listOf(
            "turn off projector",
            "switch off projector",
            "turn the projector off",
            "projector off",
            "shut down projector"
        )
        for (phrase in offPhrases) {
            val cmd = parser.parse(phrase)
            assertTrue("Phrase '$phrase' should parse to SetDeviceCapability", cmd is AnimusCommand.SetDeviceCapability)
            val devCmd = cmd as AnimusCommand.SetDeviceCapability
            assertEquals("PROJECTOR", devCmd.target)
            assertEquals(DeviceCapability.Power, devCmd.capability)
            assertEquals(false, devCmd.value)
        }

        val onPhrases = listOf(
            "turn on projector",
            "switch on projector",
            "turn the projector on",
            "projector on"
        )
        for (phrase in onPhrases) {
            val cmd = parser.parse(phrase)
            assertTrue("Phrase '$phrase' should parse to SetDeviceCapability", cmd is AnimusCommand.SetDeviceCapability)
            val devCmd = cmd as AnimusCommand.SetDeviceCapability
            assertEquals("PROJECTOR", devCmd.target)
            assertEquals(DeviceCapability.Power, devCmd.capability)
            assertEquals(true, devCmd.value)
        }
    }

    @Test
    fun testE12_02_ProjectorSourceCommands_ParsedCorrectly() {
        val hdmi1Cmd = parser.parse("switch projector to HDMI 1")
        assertTrue(hdmi1Cmd is AnimusCommand.SetDeviceCapability)
        val devCmd = hdmi1Cmd as AnimusCommand.SetDeviceCapability
        assertEquals("PROJECTOR", devCmd.target)
        assertEquals(DeviceCapability.SelectInput, devCmd.capability)
        assertEquals("HDMI_1", devCmd.value)

        val setHdmiCmd = parser.parse("set projector to HDMI 2")
        assertTrue(setHdmiCmd is AnimusCommand.SetDeviceCapability)
        val devCmd2 = setHdmiCmd as AnimusCommand.SetDeviceCapability
        assertEquals("PROJECTOR", devCmd2.target)
        assertEquals(DeviceCapability.SelectInput, devCmd2.capability)
        assertEquals("HDMI_2", devCmd2.value)
    }

    @Test
    fun testE12_03_ProjectorAdapter_PhysicalVerificationFailure_ReturnsError() = runBlocking {
        val mockPcProvider = object : PcLocalMusicProvider() {
            override fun setProjectorPower(on: Boolean): Pair<Boolean, String> {
                return Pair(true, "Dispatched power on command")
            }
            override fun getProjectorStatus(): JSONObject {
                // Readback telemetry indicates projector is still physically OFF
                return JSONObject().apply {
                    put("power_state", "OFF")
                    put("source", "HDMI_1")
                    put("connected", true)
                }
            }
        }

        val adapter = ProjectorDeviceAdapter(mockPcProvider)
        val device = RoomDevice(
            id = "room_projector",
            displayName = "Smart Projector",
            type = DeviceType.PROJECTOR,
            connectionState = DeviceConnectionState.Connected
        )

        val result = adapter.executeCapability(device, DeviceCapability.Power, true)
        assertFalse("Physical readback OFF must fail power ON request", result.success)
        assertEquals("Projector did not turn on.", result.message)
    }

    @Test
    fun testE12_04_ProjectorAdapter_PhysicalVerificationSuccess_ReturnsCompleted() = runBlocking {
        val mockPcProvider = object : PcLocalMusicProvider() {
            override fun setProjectorPower(on: Boolean): Pair<Boolean, String> {
                return Pair(true, "Power command sent")
            }
            override fun getProjectorStatus(): JSONObject {
                // Readback telemetry confirms projector is physically ON
                return JSONObject().apply {
                    put("power_state", "ON")
                    put("source", "HDMI_1")
                    put("connected", true)
                }
            }
        }

        val adapter = ProjectorDeviceAdapter(mockPcProvider)
        val device = RoomDevice(
            id = "room_projector",
            displayName = "Smart Projector",
            type = DeviceType.PROJECTOR,
            connectionState = DeviceConnectionState.Connected
        )

        val result = adapter.executeCapability(device, DeviceCapability.Power, true)
        assertTrue("Physical readback ON must report success", result.success)
        assertEquals("Projector is now ON.", result.message)
    }

    // ─── 2. AUDIO OWNERSHIP & BLUETOOTH COVERAGE ────────────────────────────────

    @Test
    fun testE12_05_AudioOwnershipCommands_ParsedToAudioOwnershipTargets() {
        val pcPhrases = listOf(
            "connect the speaker to my computer",
            "connect Bluetooth to my computer",
            "connect the soundbar to my computer",
            "connect my computer to the speaker",
            "switch audio to my computer",
            "give the speaker back to the computer"
        )
        for (phrase in pcPhrases) {
            val cmd = parser.parse(phrase)
            assertTrue("Phrase '$phrase' should parse to Connect/Switch Bluetooth target PC",
                cmd is AnimusCommand.ConnectBluetoothDevice || cmd is AnimusCommand.SwitchBluetoothDevice)
            val dev = if (cmd is AnimusCommand.ConnectBluetoothDevice) cmd.deviceName else (cmd as AnimusCommand.SwitchBluetoothDevice).deviceName
            assertEquals("PC", dev)
        }

        val fireTvPhrases = listOf(
            "connect the speaker to Fire TV",
            "switch audio to Fire TV",
            "give the speaker to the TV"
        )
        for (phrase in fireTvPhrases) {
            val cmd = parser.parse(phrase)
            assertTrue("Phrase '$phrase' should parse to Connect/Switch Bluetooth target FIRE_TV",
                cmd is AnimusCommand.ConnectBluetoothDevice || cmd is AnimusCommand.SwitchBluetoothDevice)
            val dev = if (cmd is AnimusCommand.ConnectBluetoothDevice) cmd.deviceName else (cmd as AnimusCommand.SwitchBluetoothDevice).deviceName
            assertEquals("FIRE_TV", dev)
        }
    }

    @Test
    fun testE12_06_CommandRouter_AudioOwnership_SwitchToPc_Verified() = runBlocking {
        val mockPcProvider = object : PcLocalMusicProvider() {
            override fun switchAudioOwnership(target: String): Pair<Boolean, String> {
                return if (target.equals("PC", ignoreCase = true)) {
                    Pair(true, "Audio ownership switched to PC (LG SNC4R active WASAPI endpoint)")
                } else {
                    Pair(false, "Unknown target")
                }
            }
        }

        val mockController = object : MusicController() {
            override fun getPcLocalProvider(): PcLocalMusicProvider = mockPcProvider
        }

        val router = CommandRouter(musicController = mockController)
        val result = router.execute(AnimusCommand.ConnectBluetoothDevice("PC"))
        assertTrue("Switching audio to PC with verified endpoint must succeed", result.success)
        assertEquals("Soundbar connected to computer.", result.message)
    }

    @Test
    fun testE12_07_CommandRouter_AudioOwnership_ConnectionFailure_ReturnsTruthfulError() = runBlocking {
        val mockPcProvider = object : PcLocalMusicProvider() {
            override fun switchAudioOwnership(target: String): Pair<Boolean, String> {
                return Pair(false, "Bluetooth connection timeout: soundbar offline")
            }
        }

        val mockController = object : MusicController() {
            override fun getPcLocalProvider(): PcLocalMusicProvider = mockPcProvider
        }

        val router = CommandRouter(musicController = mockController)
        val result = router.execute(AnimusCommand.ConnectBluetoothDevice("PC"))
        assertFalse("Connection failure must return false", result.success)
        assertEquals("Could not connect the soundbar to the computer.", result.message)
    }

    // ─── 3. MOVIE MODE STOP / CANCELLATION ────────────────────────────────────────

    @Test
    fun testE12_08_MovieModeStopVariants_ParsedCorrectly() {
        val stopPhrases = listOf(
            "stop movie mode",
            "turn off movie mode",
            "exit movie mode",
            "cancel movie mode",
            "I'm done watching",
            "stop the movie setup",
            "stop watching",
            "done watching"
        )
        for (phrase in stopPhrases) {
            val cmd = parser.parse(phrase)
            assertTrue("Phrase '$phrase' should parse to StopMovieMode", cmd is AnimusCommand.StopMovieMode)
        }
    }

    @Test
    fun testE12_09_CommandRouter_StopMovieMode_ReturnsStructuredFeedback() = runBlocking {
        val mockPcProvider = object : PcLocalMusicProvider() {
            override fun stopMovieModeWithFeedback(): MovieModeResult {
                return MovieModeResult(
                    success = true,
                    status = "OFF",
                    message = "Movie Mode stopped. Audio returned to the computer.",
                    spokenResponse = "Movie Mode stopped. Audio returned to the computer."
                )
            }
        }

        val mockController = object : MusicController() {
            override fun getPcLocalProvider(): PcLocalMusicProvider = mockPcProvider
            override fun stopMovieModeWithFeedback(): PcLocalMusicProvider.MovieModeResult = mockPcProvider.stopMovieModeWithFeedback()
        }

        val router = CommandRouter(musicController = mockController)
        val result = router.execute(AnimusCommand.StopMovieMode)
        assertTrue("Stopping Movie Mode should succeed", result.success)
        assertEquals("Movie Mode stopped. Audio returned to the computer.", result.message)
    }

    // ─── 4. CONVERSATIONAL CONTEXT DISAMBIGUATION ─────────────────────────────────

    @Test
    fun testE12_10_ContextualTurnItOff_ResolvesToActiveMovieMode() {
        val sessionContext = AssistantSessionContext()
        sessionContext.updateMovieMode(active = true, title = "Article 15")

        val resolved = ConversationReferenceResolver.resolveReference("turn it off", sessionContext.toSummary())
        assertNotNull("Contextual 'turn it off' must resolve when Movie Mode is active", resolved)
        assertTrue(resolved is BrainResponse.Command)
        val cmdResp = resolved as BrainResponse.Command
        assertTrue(cmdResp.actions.any { it is BrainAction.StopMovieMode })
    }

    @Test
    fun testE12_11_ContextualSwitchItBack_ResolvesToPreviousAudioOwner() {
        val sessionContext = AssistantSessionContext()
        sessionContext.updateAudioOwner("FIRE_TV")
        // Now previous audio owner is recorded as PC
        val resolved = ConversationReferenceResolver.resolveReference("switch it back", sessionContext.toSummary())
        assertNotNull("Contextual 'switch it back' must resolve to previous owner", resolved)
        assertTrue(resolved is BrainResponse.Command)
        val cmdResp = resolved as BrainResponse.Command
        val btAction = cmdResp.actions.firstOrNull { it is BrainAction.ConnectBluetooth } as? BrainAction.ConnectBluetooth
        assertNotNull(btAction)
        assertEquals("PC", btAction?.deviceName)
    }

    // ─── 5. TRUTHFUL ERROR CLASSIFICATION ────────────────────────────────────────

    @Test
    fun testE12_12_UnknownCommand_ParsedToUnknownCommand() {
        val unknown = parser.parse("tell me a random story about martians")
        assertTrue(unknown is AnimusCommand.UnknownCommand)
    }
}
