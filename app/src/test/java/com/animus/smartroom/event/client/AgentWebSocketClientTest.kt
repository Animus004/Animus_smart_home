package com.animus.smartroom.event.client

import com.animus.smartroom.event.model.AgentEventDto
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class AgentWebSocketClientTest {

    @Test
    fun testEventDtoParsing() {
        val jsonStr = """
            {
                "event_id": "evt-1787654383-a1b2c3d4",
                "event_type": "REMINDER_DUE",
                "timestamp": 1787654383.0,
                "priority": "NORMAL",
                "message": "Buddy, here is your reminder: Practice guitar.",
                "payload": {
                    "reminder_id": "rem-1",
                    "reminder_message": "Practice guitar"
                }
            }
        """.trimIndent()

        val json = JSONObject(jsonStr)
        val dto = AgentEventDto.fromJson(json)

        assertEquals("evt-1787654383-a1b2c3d4", dto.eventId)
        assertEquals("REMINDER_DUE", dto.eventType)
        assertEquals("Buddy, here is your reminder: Practice guitar.", dto.message)
        assertEquals("NORMAL", dto.priority)
        assertNotNull(dto.payload)
        assertEquals("rem-1", dto.payload.getString("reminder_id"))
    }

    @Test
    fun testFollowupEventDtoParsing() {
        val jsonStr = """
            {
                "event_id": "evt-1787654383-e5f6g7h8",
                "event_type": "FOLLOWUP_REQUIRED",
                "timestamp": 1787654383.0,
                "priority": "NORMAL",
                "message": "Which room did you mean, buddy?",
                "payload": {
                    "followup_question": "Which room did you mean, buddy?"
                }
            }
        """.trimIndent()

        val json = JSONObject(jsonStr)
        val dto = AgentEventDto.fromJson(json)

        assertEquals("FOLLOWUP_REQUIRED", dto.eventType)
        assertEquals("Which room did you mean, buddy?", dto.message)
        assertEquals("Which room did you mean, buddy?", dto.payload.getString("followup_question"))
    }

    @Test
    fun testClientInstantiation() {
        val client = AgentWebSocketClient(hostProvider = { "127.0.0.1" }, port = 8095)
        assertEquals("http://127.0.0.1:8095", client.baseUrl)
    }
}
