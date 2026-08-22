package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.session.AssistantSessionContext
import com.animus.smartroom.core.brain.session.AssistantSessionSummary
import com.animus.smartroom.core.brain.session.ConversationReferenceResolver
import com.animus.smartroom.core.brain.session.ConversationTurn
import org.junit.Assert.*
import org.junit.Test

class Phase5F4ParityCoreBrainTestSuite {

    // 23. ReferenceResolverMakeItLouderBoundsTest
    @Test
    fun `test ConversationReferenceResolver make it louder does not exceed 100`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 95)
        val res = ConversationReferenceResolver.resolveReference("make it louder", session)
        assertNotNull(res)
        assertEquals(100, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 24. ReferenceResolverTurnItDownBoundsTest
    @Test
    fun `test ConversationReferenceResolver turn it down does not go below 0`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 5)
        val res = ConversationReferenceResolver.resolveReference("turn it down", session)
        assertNotNull(res)
        assertEquals(0, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 25. ReferenceResolverBareNumberOutOfRangeIgnoredTest
    @Test
    fun `test ConversationReferenceResolver bare number out of temperature range ignored when AC active`() {
        val session = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 24)
        val res = ConversationReferenceResolver.resolveReference("45", session)
        assertNull(res)
    }

    // 26. ReferenceResolverMakeThatTempOutOfRangeIgnoredTest
    @Test
    fun `test ConversationReferenceResolver make that temp out of range ignored`() {
        val session = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 24)
        val res = ConversationReferenceResolver.resolveReference("make that 40", session)
        assertNull(res)
    }

    // 27. AssistantSessionContextAddTurnTimestampOrderTest
    @Test
    fun `test AssistantSessionContext keeps chronological order of turns`() {
        val session = AssistantSessionContext()
        session.addTurn("USER", "Turn 1", timestamp = 1000L)
        session.addTurn("ASSISTANT", "Turn 2", timestamp = 2000L)
        val summary = session.toSummary(now = 2500L)
        assertEquals(2, summary.recentTurns.size)
        assertEquals(1000L, summary.recentTurns[0].timestamp)
        assertEquals(2000L, summary.recentTurns[1].timestamp)
    }

    // 28. AssistantSessionContextMultipleUpdatesPreservedTest
    @Test
    fun `test AssistantSessionContext multiple updates maintain consistency`() {
        val session = AssistantSessionContext()
        session.updateActiveMusic("Tum Hi Ho")
        session.updateVolume(65)
        session.updateTemperature(21)
        session.updateScheduledAction("AC", 45)

        val summary = session.toSummary()
        assertEquals("Tum Hi Ho", summary.lastActiveTrack)
        assertEquals(65, summary.lastRequestedVolume)
        assertEquals(21, summary.lastRequestedTemperature)
        assertEquals("AC", summary.lastScheduledActionTarget)
        assertEquals(45, summary.lastScheduledActionDelayMinutes)
    }

    // 29. ReferenceResolverSwitchItOffClarificationTest
    @Test
    fun `test ConversationReferenceResolver switch it off asks clarification when both AC and music active`() {
        val session = AssistantSessionSummary(lastActiveTrack = "Kesariya", lastActiveDevice = "AC")
        val res = ConversationReferenceResolver.resolveReference("switch it off", session)
        assertTrue(res is BrainResponse.Clarification)
    }

    // 30. ReferenceResolverStopItClarificationTest
    @Test
    fun `test ConversationReferenceResolver stop it asks clarification when both AC and music active`() {
        val session = AssistantSessionSummary(lastActiveTrack = "Kesariya", lastActiveDevice = "AC")
        val res = ConversationReferenceResolver.resolveReference("stop it", session)
        assertTrue(res is BrainResponse.Clarification)
    }

    // 31. ReferenceResolverActuallyMakeThatMinutesTest
    @Test
    fun `test ConversationReferenceResolver actually make that 45 minutes`() {
        val session = AssistantSessionSummary(lastScheduledActionTarget = "AC", lastScheduledActionDelayMinutes = 30)
        val res = ConversationReferenceResolver.resolveReference("actually make that 45 minutes", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(45, ((res as BrainResponse.Command).actions[0] as BrainAction.ScheduleAction).delayMinutes)
    }

    // 32. ReferenceResolverMakeThatHoursTest
    @Test
    fun `test ConversationReferenceResolver make that 1 hour`() {
        val session = AssistantSessionSummary(lastScheduledActionTarget = "AC", lastScheduledActionDelayMinutes = 30)
        val res = ConversationReferenceResolver.resolveReference("make that 1 hour", session)
        assertNotNull(res)
        assertTrue(res is BrainResponse.Command)
        assertEquals(60, ((res as BrainResponse.Command).actions[0] as BrainAction.ScheduleAction).delayMinutes)
    }

    // 33. AssistantSessionSummaryDataClassCopyTest
    @Test
    fun `test AssistantSessionSummary copy and equality`() {
        val s1 = AssistantSessionSummary(lastActiveDevice = "AC", lastRequestedTemperature = 24)
        val s2 = s1.copy(lastRequestedTemperature = 22)
        assertNotEquals(s1, s2)
        assertEquals(22, s2.lastRequestedTemperature)
    }

    // 34. ConversationTurnDataClassCopyTest
    @Test
    fun `test ConversationTurn copy and equality`() {
        val t1 = ConversationTurn("USER", "Hello", 1000L)
        val t2 = t1.copy(text = "Hello World")
        assertNotEquals(t1, t2)
        assertEquals("Hello World", t2.text)
    }

    // 35. ReferenceResolverTurnItUpTest
    @Test
    fun `test ConversationReferenceResolver handles turn it up`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 30)
        val res = ConversationReferenceResolver.resolveReference("turn it up", session)
        assertNotNull(res)
        assertEquals(40, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 36. ReferenceResolverLowerVolumeTest
    @Test
    fun `test ConversationReferenceResolver handles lower volume`() {
        val session = AssistantSessionSummary(lastRequestedVolume = 60)
        val res = ConversationReferenceResolver.resolveReference("lower volume", session)
        assertNotNull(res)
        assertEquals(50, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 37. ReferenceResolverMakeItQuieterDefaultVolumeTest
    @Test
    fun `test ConversationReferenceResolver make it quieter uses default 50 when volume null`() {
        val session = AssistantSessionSummary(lastRequestedVolume = null)
        val res = ConversationReferenceResolver.resolveReference("make it quieter", session)
        assertNotNull(res)
        assertEquals(40, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }

    // 38. ReferenceResolverMakeItLouderDefaultVolumeTest
    @Test
    fun `test ConversationReferenceResolver make it louder uses default 50 when volume null`() {
        val session = AssistantSessionSummary(lastRequestedVolume = null)
        val res = ConversationReferenceResolver.resolveReference("make it louder", session)
        assertNotNull(res)
        assertEquals(60, ((res as BrainResponse.Command).actions[0] as BrainAction.SetVolume).percentage)
    }
}
