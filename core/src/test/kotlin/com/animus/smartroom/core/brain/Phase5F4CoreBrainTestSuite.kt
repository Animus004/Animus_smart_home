package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.session.AssistantSessionContext
import com.animus.smartroom.core.brain.session.AssistantSessionSummary
import com.animus.smartroom.core.brain.session.ConversationReferenceResolver
import org.junit.Assert.*
import org.junit.Test

class Phase5F4CoreBrainTestSuite {

    // 1. AssistantSessionContextBoundedTurnsTest
    @Test
    fun `test AssistantSessionContext caps turns to MAX_TURNS`() {
        val session = AssistantSessionContext()
        for (i in 1..20) {
            session.addTurn("USER", "Turn message $i")
        }
        val summary = session.toSummary()
        assertEquals(AssistantSessionContext.MAX_TURNS, summary.recentTurns.size)
        assertEquals("Turn message 20", summary.recentTurns.last().text)
    }

    // 2. AssistantSessionContextTextTruncationTest
    @Test
    fun `test AssistantSessionContext truncates overly long turn texts`() {
        val session = AssistantSessionContext()
        val longText = "A".repeat(500)
        session.addTurn("USER", longText)
        val summary = session.toSummary()
        assertTrue(summary.recentTurns[0].text.length <= AssistantSessionContext.MAX_TEXT_LENGTH_PER_TURN + 3)
    }

    // 3. AssistantSessionContextExpiryTest
    @Test
    fun `test AssistantSessionContext resets state on expiry`() {
        val session = AssistantSessionContext(expiryDurationMs = 1000) // 1 sec expiry
        session.updateTemperature(22, timestamp = 1000L)
        session.updateActiveMusic("Zara Zara", timestamp = 1000L)

        // Query before expiry
        val s1 = session.toSummary(now = 1500L)
        assertEquals(22, s1.lastRequestedTemperature)
        assertEquals("Zara Zara", s1.lastActiveTrack)

        // Query after expiry
        val s2 = session.toSummary(now = 3000L)
        assertNull(s2.lastRequestedTemperature)
        assertNull(s2.lastActiveTrack)
        assertTrue(s2.recentTurns.isEmpty())
    }

    // 4. ConversationReferenceResolverBareVolumeTest
    @Test
    fun `test ConversationReferenceResolver resolves bare number as volume when music was active`() {
        val session = AssistantSessionSummary(lastActiveTrack = "Zara Zara", lastRequestedVolume = 40)
        val res = ConversationReferenceResolver.resolveReference("30", session)

        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("Setting volume to 30%.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.SetVolume)
        assertEquals(30, (cmd.actions[0] as BrainAction.SetVolume).percentage)
    }

    // 5. ConversationReferenceResolverBareTemperatureTest
    @Test
    fun `test ConversationReferenceResolver resolves bare number as temperature when AC was active`() {
        val session = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 24)
        val res = ConversationReferenceResolver.resolveReference("23", session)

        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals("Setting AC to 23 degrees.", cmd.spokenResponse)
        assertEquals(1, cmd.actions.size)
        assertTrue(cmd.actions[0] is BrainAction.DeviceCommand)
        assertEquals(23, (cmd.actions[0] as BrainAction.DeviceCommand).value)
    }

    // 6. ConversationReferenceResolverMakeItLouderTest
    @Test
    fun `test ConversationReferenceResolver handles make it louder`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 40)
        val res = ConversationReferenceResolver.resolveReference("make it louder", session)

        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(50, (cmd.actions[0] as BrainAction.SetVolume).percentage)
    }

    // 7. ConversationReferenceResolverMakeItQuieterTest
    @Test
    fun `test ConversationReferenceResolver handles turn it down`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 40)
        val res = ConversationReferenceResolver.resolveReference("turn it down", session)

        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(30, (cmd.actions[0] as BrainAction.SetVolume).percentage)
    }

    // 8. ConversationReferenceResolverScheduleAdjustmentTest
    @Test
    fun `test ConversationReferenceResolver handles actually make that 3 hours for schedule`() {
        val session = AssistantSessionSummary(lastScheduledActionTarget = "AC", lastScheduledActionDelayMinutes = 120)
        val res = ConversationReferenceResolver.resolveReference("actually make that 3 hours", session)

        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        val cmd = res as BrainResponse.Command
        assertEquals(180, (cmd.actions[0] as BrainAction.ScheduleAction).delayMinutes)
    }

    // 9. ConversationReferenceResolverAmbiguityClarificationTest
    @Test
    fun `test ConversationReferenceResolver asks clarification on ambiguous turn it off`() {
        val session = AssistantSessionSummary(lastActiveDevice = "AC", lastActiveTrack = "Zara Zara")
        val res = ConversationReferenceResolver.resolveReference("turn it off", session)

        assertNotNull(res)
        assertTrue(res is BrainResponse.Clarification)
        val clar = res as BrainResponse.Clarification
        assertEquals("Do you mean the AC or the music?", clar.question)
    }

    // 10. ConversationReferenceResolverUnrelatedInputReturnsNullTest
    @Test
    fun `test ConversationReferenceResolver returns null for unhandled input`() {
        val session = AssistantSessionSummary()
        val res = ConversationReferenceResolver.resolveReference("What is the capital of France", session)
        assertNull(res)
    }
}
