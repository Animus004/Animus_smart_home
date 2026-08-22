package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.session.AssistantSessionContext
import com.animus.smartroom.core.brain.session.AssistantSessionSummary
import com.animus.smartroom.core.brain.session.ConversationReferenceResolver
import org.junit.Assert.*
import org.junit.Test

class Phase5F4ExpandedCoreBrainTestSuite {

    // 11. ConversationReferenceResolverQuieterTest
    @Test
    fun `test ConversationReferenceResolver handles softer and quieter`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 70)
        val res = ConversationReferenceResolver.resolveReference("softer", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(60, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 12. ConversationReferenceResolverIncreaseVolumeTest
    @Test
    fun `test ConversationReferenceResolver handles increase volume`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 50)
        val res = ConversationReferenceResolver.resolveReference("increase volume", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(60, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 13. ConversationReferenceResolverMakeItMinutesTest
    @Test
    fun `test ConversationReferenceResolver handles actually 30 minutes`() {
        val session = AssistantSessionSummary(lastScheduledActionTarget = "AC", lastScheduledActionDelayMinutes = 60)
        val res = ConversationReferenceResolver.resolveReference("actually 30 minutes", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(30, ((res as BrainResponse.Command).actions[0] as BrainAction.ScheduleAction).delayMinutes)
    }

    // 14. AssistantSessionContextUpdateVolumeBoundsTest
    @Test
    fun `test AssistantSessionContext updateVolume clamps value 0 to 100`() {
        val session = AssistantSessionContext()
        session.updateVolume(150)
        assertEquals(100, session.lastRequestedVolume)

        session.updateVolume(-20)
        assertEquals(0, session.lastRequestedVolume)
    }

    // 15. AssistantSessionContextUpdateTemperatureBoundsTest
    @Test
    fun `test AssistantSessionContext updateTemperature clamps value 16 to 30`() {
        val session = AssistantSessionContext()
        session.updateTemperature(35)
        assertEquals(30, session.lastRequestedTemperature)

        session.updateTemperature(10)
        assertEquals(16, session.lastRequestedTemperature)
    }

    // 16. AssistantSessionContextClarificationResetTest
    @Test
    fun `test AssistantSessionContext setPendingClarification`() {
        val session = AssistantSessionContext()
        session.setPendingClarification("Which speaker?")
        assertEquals("Which speaker?", session.pendingClarification)

        session.setPendingClarification(null)
        assertNull(session.pendingClarification)
    }

    // 17. AssistantSessionContextLastTaskUpdateTest
    @Test
    fun `test AssistantSessionContext updateLastTask`() {
        val session = AssistantSessionContext()
        session.updateLastTask("task-100", "Buy groceries")
        assertEquals("task-100", session.lastTaskId)
        assertEquals("Buy groceries", session.lastTaskTitle)
    }

    // 18. AssistantSessionContextResetAllFieldsTest
    @Test
    fun `test AssistantSessionContext reset clears all state`() {
        val session = AssistantSessionContext()
        session.updateActiveMusic("Zara Zara")
        session.updateVolume(45)
        session.updateTemperature(23)
        session.updateScheduledAction("AC", 30)
        session.updateLastTask("t1", "Task 1")
        session.setPendingClarification("Question?")
        session.addTurn("USER", "Hello")

        session.reset()

        val summary = session.toSummary()
        assertNull(summary.lastActiveTrack)
        assertNull(summary.lastRequestedVolume)
        assertNull(summary.lastRequestedTemperature)
        assertNull(summary.lastScheduledActionTarget)
        assertNull(summary.lastTaskId)
        assertNull(summary.pendingClarification)
        assertTrue(summary.recentTurns.isEmpty())
    }

    // 19. BrainContextBoundedSessionSummaryPreservedTest
    @Test
    fun `test BrainContext bounded preserves sessionSummary`() {
        val summary = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 22)
        val ctx = BrainContext.bounded(sessionSummary = summary)
        assertNotNull(ctx.sessionSummary)
        assertEquals("AC", ctx.sessionSummary?.lastActiveDevice)
        assertEquals(22, ctx.sessionSummary?.lastRequestedTemperature)
    }

    // 20. ConversationReferenceResolverMakeItVolumeWhenMusicActiveTest
    @Test
    fun `test ConversationReferenceResolver make it 75 when music active`() {
        val session = AssistantSessionSummary(lastActiveTrack = "Zara Zara", lastRequestedVolume = 50)
        val res = ConversationReferenceResolver.resolveReference("make it 75", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(75, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 21. ConversationReferenceResolverMakeThatTempWhenAcActiveTest
    @Test
    fun `test ConversationReferenceResolver make that 25 when AC active`() {
        val session = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 22)
        val res = ConversationReferenceResolver.resolveReference("make that 25", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(25, ((res as BrainResponse.Command).actions[0] as BrainAction.DeviceCommand).value)
    }

    // 22. ConversationReferenceResolverActuallyMakeItTempTest
    @Test
    fun `test ConversationReferenceResolver actually make it 24`() {
        val session = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 22)
        val res = ConversationReferenceResolver.resolveReference("actually make it 24", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(24, ((res as BrainResponse.Command).actions[0] as BrainAction.DeviceCommand).value)
    }
}
