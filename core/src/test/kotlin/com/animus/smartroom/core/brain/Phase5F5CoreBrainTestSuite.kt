package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.Memory
import com.animus.smartroom.core.brain.model.MemoryCategory
import com.animus.smartroom.core.brain.personal.PersonalContextSummary
import com.animus.smartroom.core.brain.personal.PersonalProfile
import com.animus.smartroom.core.brain.personal.PersonalProfileBootstrap
import org.junit.Assert.*
import org.junit.Test

class Phase5F5CoreBrainTestSuite {

    // 1. PersonalProfileDefaultsTest
    @Test
    fun `test PersonalProfile defaults and bounds`() {
        val profile = PersonalProfile()
        assertEquals("User", profile.preferredName)
        assertEquals("LG SNC4R", profile.primarySpeaker)
        assertEquals(24, profile.preferredAcTemperatureCelsius)
        assertTrue(profile.activeProjects.contains("Animus Smart Room Assistant"))
    }

    // 2. PersonalProfileBootstrapSeedsMemoriesTest
    @Test
    fun `test PersonalProfileBootstrap provides default initial memories`() {
        val memories = PersonalProfileBootstrap.createInitialMemories()
        assertTrue(memories.isNotEmpty())
        assertTrue(memories.any { it.category == MemoryCategory.PREFERENCE })
        assertTrue(memories.any { it.category == MemoryCategory.FACT })
        assertTrue(memories.any { it.category == MemoryCategory.PROJECT })
        assertTrue(memories.any { it.category == MemoryCategory.GOAL })
        assertTrue(memories.all { it.source == "BOOTSTRAP" })
    }

    // 3. MemoryCategoryExpansionTest
    @Test
    fun `test MemoryCategory includes PROJECT GOAL and EXPLICIT_MEMORY`() {
        val categories = MemoryCategory.values().map { it.name }
        assertTrue(categories.contains("PROJECT"))
        assertTrue(categories.contains("GOAL"))
        assertTrue(categories.contains("EXPLICIT_MEMORY"))
        assertTrue(categories.contains("PREFERENCE"))
    }

    // 4. PersonalContextSummaryDataClassTest
    @Test
    fun `test PersonalContextSummary fields and copy`() {
        val summary = PersonalContextSummary(
            preferredName = "Alex",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 23,
            activeProjects = listOf("Animus"),
            primaryGoals = listOf("Smart Automation"),
            relevantPersonalKnowledge = listOf("Prefers 23C")
        )
        val copy = summary.copy(preferredAcTemp = 22)
        assertEquals(23, summary.preferredAcTemp)
        assertEquals(22, copy.preferredAcTemp)
        assertEquals("Alex", copy.preferredName)
    }

    // 5. BrainContextBoundedPersonalContextPreservedTest
    @Test
    fun `test BrainContext bounded preserves personalContext`() {
        val p = PersonalContextSummary(
            preferredName = "Sayan",
            primarySpeaker = "LG SNC4R",
            preferredAcTemp = 24
        )
        val ctx = com.animus.smartroom.core.brain.model.BrainContext.bounded(personalContext = p)
        assertNotNull(ctx.personalContext)
        assertEquals("Sayan", ctx.personalContext?.preferredName)
        assertEquals(24, ctx.personalContext?.preferredAcTemp)
    }

    // 6. MemoryRelevanceRankingForPersonalKnowledgeTest
    @Test
    fun `test MemoryRelevanceEngine ranks relevant personal knowledge`() {
        val memories = listOf(
            Memory(content = "User prefers AC at 24C", category = MemoryCategory.PREFERENCE),
            Memory(content = "User works on Animus project", category = MemoryCategory.PROJECT),
            Memory(content = "Speaker is LG SNC4R", category = MemoryCategory.FACT)
        )
        val ranked = com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine.rankMemories("AC temperature", memories, null, 2)
        assertEquals(1, ranked.size)
        assertTrue(ranked[0].content.contains("AC at 24C"))
    }

    // 7. MemoryRelevanceRankingNoMatchReturnsEmptyTest
    @Test
    fun `test MemoryRelevanceEngine returns empty when no keywords match`() {
        val memories = listOf(
            Memory(content = "User prefers AC at 24C", category = MemoryCategory.PREFERENCE),
            Memory(content = "User works on Animus project", category = MemoryCategory.PROJECT)
        )
        val ranked = com.animus.smartroom.core.brain.memory.MemoryRelevanceEngine.rankMemories("xyz nonexistent", memories, null, 2)
        assertTrue(ranked.isEmpty())
    }

    // 8. PersonalProfileLimitsConstantTest
    @Test
    fun `test PersonalProfile constants meet limits`() {
        assertEquals(50, PersonalProfile.MAX_PROFILE_ITEMS)
        assertEquals(300, PersonalProfile.MAX_TEXT_LENGTH)
    }

    // 9. MemoryDataClassExplicitMemoryTypeTest
    @Test
    fun `test Memory with EXPLICIT_MEMORY category`() {
        val mem = Memory(content = "Remember that I like Zara Zara", category = MemoryCategory.EXPLICIT_MEMORY)
        assertEquals(MemoryCategory.EXPLICIT_MEMORY, mem.category)
        assertTrue(mem.content.contains("Zara Zara"))
    }

    // 10. MemoryDataClassProjectCategoryTest
    @Test
    fun `test Memory with PROJECT category`() {
        val mem = Memory(content = "Project Animus Smart Assistant", category = MemoryCategory.PROJECT)
        assertEquals(MemoryCategory.PROJECT, mem.category)
    }
}
