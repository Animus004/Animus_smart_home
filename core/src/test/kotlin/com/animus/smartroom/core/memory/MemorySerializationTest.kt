package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.DailyActivityEvent
import com.animus.smartroom.core.memory.model.DevicePreferenceEvent
import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.MemoryEvent
import com.animus.smartroom.core.memory.model.PreferenceEvent
import com.animus.smartroom.core.memory.model.ProjectProgressEvent
import com.animus.smartroom.core.memory.model.ProjectStatus
import com.animus.smartroom.core.memory.model.RoutineHistoryEvent
import com.animus.smartroom.core.memory.model.SystemMilestoneEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class MemorySerializationTest {

    @Test
    fun `LearningEvent roundtrip serialization`() {
        val event = LearningEvent(
            id = "learn_123",
            timestamp = 1700000000L,
            source = "USER",
            topic = "SQL",
            subtopic = "JOINs",
            action = "Practiced FULL OUTER JOIN",
            notes = "Tricky with NULL handling",
            status = LearningStatus.PRACTICED,
            metadata = mapOf("difficulty" to "medium")
        )

        val json = event.toJson()
        val deserialized = MemoryEvent.fromJson(json) as? LearningEvent

        assertNotNull(deserialized)
        assertEquals(event.id, deserialized?.id)
        assertEquals(event.timestamp, deserialized?.timestamp)
        assertEquals(event.topic, deserialized?.topic)
        assertEquals(event.subtopic, deserialized?.subtopic)
        assertEquals(event.action, deserialized?.action)
        assertEquals(event.notes, deserialized?.notes)
        assertEquals(event.status, deserialized?.status)
    }

    @Test
    fun `ProjectProgressEvent roundtrip serialization`() {
        val event = ProjectProgressEvent(
            id = "proj_123",
            timestamp = 1700000000L,
            projectName = "Steam Games",
            projectId = "sg_01",
            milestone = "ETL Pipeline",
            action = "Implemented data parser",
            status = ProjectStatus.MILESTONE_COMPLETED,
            notes = "Parsed 50k rows"
        )

        val json = event.toJson()
        val deserialized = MemoryEvent.fromJson(json) as? ProjectProgressEvent

        assertNotNull(deserialized)
        assertEquals(event.id, deserialized?.id)
        assertEquals(event.projectName, deserialized?.projectName)
        assertEquals(event.projectId, deserialized?.projectId)
        assertEquals(event.milestone, deserialized?.milestone)
        assertEquals(event.action, deserialized?.action)
        assertEquals(event.status, deserialized?.status)
    }

    @Test
    fun `PreferenceEvent roundtrip serialization`() {
        val event = PreferenceEvent(
            prefCategory = "HVAC",
            key = "sleep_temp",
            value = "24",
            confidence = 0.95f
        )
        val deserialized = MemoryEvent.fromJson(event.toJson()) as? PreferenceEvent
        assertNotNull(deserialized)
        assertEquals("HVAC", deserialized?.prefCategory)
        assertEquals("sleep_temp", deserialized?.key)
        assertEquals("24", deserialized?.value)
        assertEquals(0.95f, deserialized?.confidence ?: 0f, 0.01f)
    }

    @Test
    fun `DevicePreferenceEvent roundtrip serialization`() {
        val event = DevicePreferenceEvent(
            targetDevice = "ac_bedroom",
            preferredState = mapOf("temp" to 24, "mode" to "COOL"),
            contextTag = "SLEEP"
        )
        val deserialized = MemoryEvent.fromJson(event.toJson()) as? DevicePreferenceEvent
        assertNotNull(deserialized)
        assertEquals("ac_bedroom", deserialized?.targetDevice)
        assertEquals("SLEEP", deserialized?.contextTag)
    }

    @Test
    fun `RoutineHistoryEvent roundtrip serialization`() {
        val event = RoutineHistoryEvent(
            routineName = "Sleep Mode",
            startedAt = 1000L,
            completedAt = 2000L,
            outcome = "COMPLETED",
            routineSummary = "Slept for 8 hours"
        )
        val deserialized = MemoryEvent.fromJson(event.toJson()) as? RoutineHistoryEvent
        assertNotNull(deserialized)
        assertEquals("Sleep Mode", deserialized?.routineName)
        assertEquals("COMPLETED", deserialized?.outcome)
    }

    @Test
    fun `DailyActivityEvent roundtrip serialization`() {
        val event = DailyActivityEvent(
            title = "Morning Workout",
            description = "30 mins cardio",
            tags = listOf("health", "fitness")
        )
        val deserialized = MemoryEvent.fromJson(event.toJson()) as? DailyActivityEvent
        assertNotNull(deserialized)
        assertEquals("Morning Workout", deserialized?.title)
        assertEquals(listOf("health", "fitness"), deserialized?.tags)
    }

    @Test
    fun `SystemMilestoneEvent roundtrip serialization`() {
        val event = SystemMilestoneEvent(
            milestoneName = "Phase 5C Completed",
            description = "Personal memory foundation added",
            versionOrPhase = "v5.3"
        )
        val deserialized = MemoryEvent.fromJson(event.toJson()) as? SystemMilestoneEvent
        assertNotNull(deserialized)
        assertEquals("Phase 5C Completed", deserialized?.milestoneName)
        assertEquals("v5.3", deserialized?.versionOrPhase)
    }

    @Test
    fun `Malformed or unknown JSON returns null without throwing`() {
        assertNull(MemoryEvent.fromJson("{ invalid json }"))
        assertNull(MemoryEvent.fromJson("{\"category\":\"UNKNOWN_CAT\"}"))
        assertNull(MemoryEvent.fromJson("{}"))
    }
}
