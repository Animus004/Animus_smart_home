package com.animus.smartroom.core.brain

import com.animus.smartroom.core.brain.model.*
import com.animus.smartroom.core.brain.personal.PersonalContextSummary
import com.animus.smartroom.core.brain.personal.PersonalProfile
import com.animus.smartroom.core.brain.personal.PersonalProfileBootstrap
import org.junit.Assert.*
import org.junit.Test

class Phase5F5ParityCoreBrainTestSuite {

    // 21. PersonalProfilePreferredNameValidationTest
    @Test
    fun `test PersonalProfile with custom name`() {
        val p = PersonalProfile(preferredName = "Commander")
        assertEquals("Commander", p.preferredName)
    }

    // 22. PersonalProfilePrimarySpeakerValidationTest
    @Test
    fun `test PersonalProfile with custom primary speaker`() {
        val p = PersonalProfile(primarySpeaker = "Living Room Soundbar")
        assertEquals("Living Room Soundbar", p.primarySpeaker)
    }

    // 23. PersonalProfilePrimaryAcDeviceValidationTest
    @Test
    fun `test PersonalProfile primaryAcDevice default`() {
        val p = PersonalProfile()
        assertEquals("Tuya Inverter AC", p.primaryAcDevice)
    }

    // 24. PersonalProfileActiveProjectsListTest
    @Test
    fun `test PersonalProfile custom projects list`() {
        val p = PersonalProfile(activeProjects = listOf("Project Alpha", "Project Beta"))
        assertEquals(2, p.activeProjects.size)
        assertTrue(p.activeProjects.contains("Project Alpha"))
    }

    // 25. PersonalProfilePrimaryGoalsListTest
    @Test
    fun `test PersonalProfile custom goals list`() {
        val p = PersonalProfile(primaryGoals = listOf("Goal 1", "Goal 2"))
        assertEquals(2, p.primaryGoals.size)
        assertTrue(p.primaryGoals.contains("Goal 1"))
    }

    // 26. PersonalContextSummaryConstructorTest
    @Test
    fun `test PersonalContextSummary full constructor initialization`() {
        val summary = PersonalContextSummary(
            preferredName = "Alice",
            primarySpeaker = "Bedroom LG",
            preferredAcTemp = 22,
            activeProjects = listOf("Animus"),
            primaryGoals = listOf("Build smart home"),
            relevantPersonalKnowledge = listOf("Alice likes 22C")
        )
        assertEquals("Alice", summary.preferredName)
        assertEquals("Bedroom LG", summary.primarySpeaker)
        assertEquals(22, summary.preferredAcTemp)
        assertEquals(1, summary.activeProjects.size)
        assertEquals(1, summary.primaryGoals.size)
        assertEquals(1, summary.relevantPersonalKnowledge.size)
    }

    // 27. MemoryCategoryExplicitMemoryEnumTest
    @Test
    fun `test MemoryCategory EXPLICIT_MEMORY enum value exists and matches`() {
        val cat = MemoryCategory.valueOf("EXPLICIT_MEMORY")
        assertEquals(MemoryCategory.EXPLICIT_MEMORY, cat)
    }

    // 28. MemoryCategoryProjectEnumTest
    @Test
    fun `test MemoryCategory PROJECT enum value exists and matches`() {
        val cat = MemoryCategory.valueOf("PROJECT")
        assertEquals(MemoryCategory.PROJECT, cat)
    }

    // 29. MemoryCategoryGoalEnumTest
    @Test
    fun `test MemoryCategory GOAL enum value exists and matches`() {
        val cat = MemoryCategory.valueOf("GOAL")
        assertEquals(MemoryCategory.GOAL, cat)
    }

    // 30. PersonalProfileBootstrapContentIntegrityTest
    @Test
    fun `test PersonalProfileBootstrap memories contain accurate content strings`() {
        val list = PersonalProfileBootstrap.createInitialMemories()
        assertTrue(list.any { it.content.contains("24 degrees") })
        assertTrue(list.any { it.content.contains("LG SNC4R") })
        assertTrue(list.any { it.content.contains("Animus") })
    }
}
