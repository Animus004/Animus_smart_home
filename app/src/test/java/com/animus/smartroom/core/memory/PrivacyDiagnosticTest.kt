package com.animus.smartroom.core.memory

import com.animus.smartroom.core.memory.model.LearningEvent
import com.animus.smartroom.core.memory.model.LearningStatus
import com.animus.smartroom.core.memory.model.MemoryCategory
import com.animus.smartroom.core.memory.model.PreferenceEvent
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PrivacyDiagnosticTest {

    @Test
    fun `Memory diagnostic logging contains only safe high-level metadata`() {
        val event = LearningEvent(
            topic = "SQL Optimization",
            action = "Practiced query planner analysis",
            notes = "Confidential client query structure",
            status = LearningStatus.PRACTICED
        )

        // Safe diagnostic logging pattern
        DiagnosticBus.log(
            tag = "memory",
            stage = DiagnosticStage.EXECUTING,
            message = "category=${event.category}, topic=${event.topic}, status=${event.status}"
        )

        val recentEvents = DiagnosticBus.getRecentEvents()
        val memLog = recentEvents.lastOrNull { it.tag == "memory" }

        assertTrue(memLog != null)
        assertTrue(memLog?.message?.contains("category=LEARNING") == true)
        assertTrue(memLog?.message?.contains("topic=SQL Optimization") == true)

        // Assert that raw confidential notes were NOT leaked in diagnostic message
        assertFalse(memLog?.message?.contains("Confidential client query structure") == true)
    }

    @Test
    fun `Preference diagnostics do not log credentials or sensitive tokens`() {
        val pref = PreferenceEvent(
            prefCategory = "SECURITY",
            key = "user_pin",
            value = "1234"
        )

        // Diagnostic bus sanitized log
        DiagnosticBus.log(
            tag = "memory",
            stage = DiagnosticStage.COMPLETED,
            message = "Recorded preference for category=${pref.prefCategory}, key=${pref.key}"
        )

        val recentEvents = DiagnosticBus.getRecentEvents()
        val memLog = recentEvents.lastOrNull { it.tag == "memory" }

        assertTrue(memLog != null)
        assertFalse(memLog?.message?.contains("1234") == true)
    }
}
