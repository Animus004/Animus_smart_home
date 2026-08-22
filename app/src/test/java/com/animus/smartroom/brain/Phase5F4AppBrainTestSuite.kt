package com.animus.smartroom.brain

import com.animus.smartroom.brain.provider.GeminiBrainProvider
import com.animus.smartroom.brain.provider.LocalBrainProvider
import com.animus.smartroom.brain.repository.AndroidMemoryRepository
import com.animus.smartroom.brain.repository.AndroidTaskRepository
import com.animus.smartroom.brain.session.AndroidSessionContextRepository
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.core.brain.BrainMode
import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.port.VoiceOutputPort
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class Phase5F4AppBrainTestSuite {

    @Before
    fun setup() {
        AndroidSessionContextRepository.reset()
    }

    // 1. MultiTurnVolumeFlowTest
    @Test
    fun `test multi-turn volume resolution Play Zara Zara then Make it louder then 30`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        // Turn 1: Play music
        val (res1, cmd1) = engine.processInput("play Zara Zara")
        assertTrue(res1 is BrainResponse.Command)
        assertTrue(cmd1[0] is AnimusCommand.PlayMusic)

        // Turn 2: Make it louder
        val (res2, cmd2) = engine.processInput("make it louder")
        assertTrue(res2 is BrainResponse.Command)
        assertTrue(cmd2[0] is AnimusCommand.SetVolume)

        // Turn 3: 30
        val (res3, cmd3) = engine.processInput("30")
        assertTrue(res3 is BrainResponse.Command)
        assertTrue(cmd3[0] is AnimusCommand.SetVolume)
        assertEquals(30, (cmd3[0] as AnimusCommand.SetVolume).percentage)
    }

    // 2. MultiTurnAcTemperatureFlowTest
    @Test
    fun `test multi-turn AC temperature resolution Set AC to 24 then Make it 23`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        // Turn 1: Set AC to 24
        val (res1, cmd1) = engine.processInput("set AC to 24")
        assertTrue(res1 is BrainResponse.Command)
        assertTrue(cmd1[0] is AnimusCommand.SetDeviceCapability)

        // Turn 2: Make it 23
        val (res2, cmd2) = engine.processInput("make it 23")
        assertTrue(res2 is BrainResponse.Command)
        assertTrue(cmd2[0] is AnimusCommand.SetDeviceCapability)
        assertEquals(23, (cmd2[0] as AnimusCommand.SetDeviceCapability).value)
    }

    // 3. MultiTurnScheduleAdjustmentTest
    @Test
    fun `test multi-turn schedule timer adjustment`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        // Turn 1: Turn AC off after 2 hours
        val (res1, _) = engine.processInput("turn the ac off after 2 hours")
        assertTrue(res1 is BrainResponse.Command)

        // Turn 2: Actually make that 3 hours
        val (res2, cmd2) = engine.processInput("actually make that 3 hours")
        assertTrue(res2 is BrainResponse.Command)
        assertTrue(cmd2[0] is AnimusCommand.ScheduleDeviceAction)
        assertEquals(180, (cmd2[0] as AnimusCommand.ScheduleDeviceAction).delayMinutes)
    }

    // 4. SessionExplicitResetTest
    @Test
    fun `test forget this conversation resets session context`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("set AC to 24")
        assertNotNull(AndroidSessionContextRepository.getSummary().lastRequestedTemperature)

        val (resetRes, _) = engine.processInput("forget this conversation")
        assertTrue(resetRes is BrainResponse.Conversation)
        assertNull(AndroidSessionContextRepository.getSummary().lastRequestedTemperature)
    }

    // 5. AmbiguousTurnItOffClarificationTest
    @Test
    fun `test AnimusBrainEngine requests clarification on ambiguous turn it off when both music and AC active`() = runBlocking {
        val modeController = BrainModeControllerImpl(BrainMode.LOCAL)
        val local = LocalBrainProvider()
        val remote = GeminiBrainProvider(apiKeyProvider = { null })
        val engine = AnimusBrainEngine(modeController, local, remote)

        engine.processInput("play Zara Zara")
        engine.processInput("set AC to 24")

        val (res, cmds) = engine.processInput("turn it off")
        assertTrue(res is BrainResponse.Clarification)
        assertEquals(0, cmds.size)
        assertEquals("Do you mean the AC or the music?", (res as BrainResponse.Clarification).question)
    }
}
