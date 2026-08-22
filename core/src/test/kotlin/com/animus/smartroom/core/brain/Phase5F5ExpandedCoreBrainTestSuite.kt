package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.personal.PersonalContextSummary
import com.animus.smartroom.core.brain.personal.PersonalProfile
import com.animus.smartroom.core.brain.personal.PersonalProfileBootstrap
import org.junit.Assert.*
import org.junit.Test

class Phase5F5ExpandedCoreBrainTestSuite {

    // 11. PersonalProfileCustomNotesTest
    @Test
    fun `test PersonalProfile with custom notes`() {
        val profile = PersonalProfile(
            customNotes = listOf("Prefers dim lights at night", "Sleeps by 11 PM")
        )
        assertEquals(2, profile.customNotes.size)
        assertEquals("Prefers dim lights at night", profile.customNotes[0])
    }

    // 12. PersonalProfileInteractionStyleTest
    @Test
    fun `test PersonalProfile interactionStyle customization`() {
        val profile = PersonalProfile(interactionStyle = "Friendly and detailed")
        assertEquals("Friendly and detailed", profile.interactionStyle)
    }

    // 13. PersonalContextSummaryEmptyListsTest
    @Test
    fun `test PersonalContextSummary default empty collections`() {
        val summary = PersonalContextSummary(
            preferredName = "User",
            primarySpeaker = null,
            preferredAcTemp = null
        )
        assertTrue(summary.activeProjects.isEmpty())
        assertTrue(summary.primaryGoals.isEmpty())
        assertTrue(summary.relevantPersonalKnowledge.isEmpty())
    }

    // 14. PersonalProfileBootstrapUniquenessTest
    @Test
    fun `test PersonalProfileBootstrap memories have unique IDs`() {
        val memories = PersonalProfileBootstrap.createInitialMemories()
        val ids = memories.map { it.id }
        assertEquals(ids.size, ids.distinct().size)
    }

    // 15. MemoryCategoryGoalCategoryAssignmentTest
    @Test
    fun `test Memory assigned GOAL category behaves correctly`() {
        val goalMem = Memory(
            content = "Turn Animus into a smart room product",
            category = MemoryCategory.GOAL,
            relevance = 0.9f
        )
        assertEquals(MemoryCategory.GOAL, goalMem.category)
        assertEquals(0.9f, goalMem.relevance, 0.001f)
    }

    // 16. MemoryCategoryRoutineCategoryAssignmentTest
    @Test
    fun `test Memory assigned ROUTINE_SCHEDULE category`() {
        val routineMem = Memory(
            content = "Turn AC on sleep mode at 11 PM",
            category = MemoryCategory.ROUTINE_SCHEDULE
        )
        assertEquals(MemoryCategory.ROUTINE_SCHEDULE, routineMem.category)
    }

    // 17. PersonalContextSummaryEqualityTest
    @Test
    fun `test PersonalContextSummary equality and hashcode`() {
        val s1 = PersonalContextSummary("User", "LG SNC4R", 24)
        val s2 = PersonalContextSummary("User", "LG SNC4R", 24)
        assertEquals(s1, s2)
        assertEquals(s1.hashCode(), s2.hashCode())
    }

    // 18. PersonalProfileDataClassCopyTest
    @Test
    fun `test PersonalProfile copy modification`() {
        val p1 = PersonalProfile(preferredName = "User")
        val p2 = p1.copy(preferredName = "Sayan", preferredAcTemperatureCelsius = 23)
        assertEquals("Sayan", p2.preferredName)
        assertEquals(23, p2.preferredAcTemperatureCelsius)
    }

    // 19. MemoryRelevanceEngineCategoryFilterTest
    @Test
    fun `test MemoryRelevanceEngine filters by category`() {
        val memories = listOf(
            Memory(content = "AC at 24C", category = MemoryCategory.PREFERENCE),
            Memory(content = "AC filter maintenance", category = MemoryCategory.FACT)
        )
        val filtered = com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine.rankMemories("AC", memories, MemoryCategory.PREFERENCE, 5)
        assertEquals(1, filtered.size)
        assertEquals(MemoryCategory.PREFERENCE, filtered[0].category)
    }

    // 20. BrainContextBoundedPersonalContextLimitsTest
    @Test
    fun `test BrainContext bounded limits memories while preserving personalContext`() {
        val longMemories = (1..20).map {
            Memory(content = "Memory item $it", category = MemoryCategory.GENERAL)
        }
        val p = PersonalContextSummary("User", "Speaker", 24)
        val ctx = BrainContext.bounded(relevantMemories = longMemories, personalContext = p)
        assertEquals(BrainContext.MAX_MEMORIES, ctx.relevantMemories.size)
        assertNotNull(ctx.personalContext)
        assertEquals("User", ctx.personalContext?.preferredName)
    }
}
