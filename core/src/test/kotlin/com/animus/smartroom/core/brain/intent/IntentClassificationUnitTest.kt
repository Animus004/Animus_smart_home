package com.animus.smartroom.core.brain.intent

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class IntentClassificationUnitTest {

    @Test
    fun `test parse direct movie command`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "intent",
              "intent": "MOVIE",
              "confidence": 0.98,
              "parameters": {
                "content": "Interstellar"
              }
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals("1.0", payload.schemaVersion)
        assertEquals("intent", payload.type)
        assertEquals(UserIntent.MOVIE, payload.intent)
        assertEquals(0.98, payload.confidence, 0.001)
        assertEquals(ConfidenceTier.HIGH, payload.confidenceTier)
        assertEquals("Interstellar", payload.parameters["content"])
        assertFalse(payload.requiresClarification)
    }

    @Test
    fun `test parse direct AC general command`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "intent",
              "intent": "GENERAL_COMMAND",
              "confidence": 0.95,
              "parameters": {
                "target": "AC",
                "action": "SET_TEMPERATURE",
                "value": 23
              }
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals(UserIntent.GENERAL_COMMAND, payload.intent)
        assertEquals(0.95, payload.confidence, 0.001)
        assertEquals("AC", payload.parameters["target"])
        assertEquals("SET_TEMPERATURE", payload.parameters["action"])
        assertEquals(23, payload.parameters["value"])
    }

    @Test
    fun `test parse direct music command`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "intent",
              "intent": "MUSIC",
              "confidence": 0.92,
              "parameters": {
                "title": "Zara Zara",
                "artist": "Bombay Jayashri"
              }
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals(UserIntent.MUSIC, payload.intent)
        assertEquals("Zara Zara", payload.parameters["title"])
        assertEquals("Bombay Jayashri", payload.parameters["artist"])
    }

    @Test
    fun `test parse conversational request with context signals`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "intent",
              "intent": "MOVIE",
              "confidence": 0.94,
              "parameters": {
                "category": "relaxing"
              },
              "context": {
                "mood": "tired",
                "energy": "low",
                "desired_atmosphere": "relaxing"
              }
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals(UserIntent.MOVIE, payload.intent)
        assertNotNull(payload.context)
        assertEquals("tired", payload.context?.mood)
        assertEquals("low", payload.context?.energy)
        assertEquals("relaxing", payload.context?.desiredAtmosphere)
    }

    @Test
    fun `test parse pure conversation without action`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "conversation",
              "intent": "CONVERSATION",
              "confidence": 0.95,
              "spoken_response": "I'm sorry to hear that. Let me know if you want to relax with a movie or music."
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals("conversation", payload.type)
        assertEquals(UserIntent.CONVERSATION, payload.intent)
        assertEquals("I'm sorry to hear that. Let me know if you want to relax with a movie or music.", payload.spokenResponse)
        assertFalse(payload.requiresClarification)
    }

    @Test
    fun `test parse multi intent with sub intents`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "multi_intent",
              "intent": "MULTI_INTENT",
              "confidence": 0.97,
              "sub_intents": [
                {
                  "schema_version": "1.0",
                  "type": "intent",
                  "intent": "MOVIE",
                  "confidence": 0.98,
                  "parameters": {
                    "content": "Interstellar"
                  }
                },
                {
                  "schema_version": "1.0",
                  "type": "intent",
                  "intent": "GENERAL_COMMAND",
                  "confidence": 0.96,
                  "parameters": {
                    "target": "AC",
                    "action": "SET_TEMPERATURE",
                    "value": 23
                  }
                }
              ]
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals("multi_intent", payload.type)
        assertEquals(UserIntent.MULTI_INTENT, payload.intent)
        assertNotNull(payload.subIntents)
        assertEquals(2, payload.subIntents?.size)
        assertEquals(UserIntent.MOVIE, payload.subIntents?.get(0)?.intent)
        assertEquals("Interstellar", payload.subIntents?.get(0)?.parameters?.get("content"))
        assertEquals(UserIntent.GENERAL_COMMAND, payload.subIntents?.get(1)?.intent)
        assertEquals("AC", payload.subIntents?.get(1)?.parameters?.get("target"))
    }

    @Test
    fun `test parse ambiguous request requires clarification`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "clarification",
              "intent": "CLARIFICATION_REQUIRED",
              "confidence": 0.90,
              "requires_clarification": true,
              "clarification_reason": "Do you want music, a movie, or YouTube?"
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals("clarification", payload.type)
        assertEquals(UserIntent.CLARIFICATION_REQUIRED, payload.intent)
        assertTrue(payload.requiresClarification)
        assertEquals("Do you want music, a movie, or YouTube?", payload.clarificationReason)
    }

    @Test
    fun `test low confidence auto promotion to clarification required`() {
        val json = """
            {
              "schema_version": "1.0",
              "type": "intent",
              "intent": "MOVIE",
              "confidence": 0.45,
              "parameters": {
                "query": "something"
              }
            }
        """.trimIndent()

        val payload = IntentClassifier.parse(json)
        assertEquals(ConfidenceTier.LOW, payload.confidenceTier)
        assertEquals(UserIntent.CLARIFICATION_REQUIRED, payload.intent)
        assertTrue(payload.requiresClarification)
        assertNotNull(payload.clarificationReason)
    }

    @Test
    fun `test confidence tier boundaries`() {
        assertEquals(ConfidenceTier.HIGH, ConfidenceTier.fromScore(0.95))
        assertEquals(ConfidenceTier.HIGH, ConfidenceTier.fromScore(0.85))
        assertEquals(ConfidenceTier.MEDIUM, ConfidenceTier.fromScore(0.84))
        assertEquals(ConfidenceTier.MEDIUM, ConfidenceTier.fromScore(0.60))
        assertEquals(ConfidenceTier.LOW, ConfidenceTier.fromScore(0.59))
        assertEquals(ConfidenceTier.LOW, ConfidenceTier.fromScore(0.10))
    }

    @Test
    fun `test markdown code fences stripped cleanly`() {
        val fenced = """
            ```json
            {
              "schema_version": "1.0",
              "type": "intent",
              "intent": "WEATHER",
              "confidence": 0.91,
              "parameters": {
                "location": "current"
              }
            }
            ```
        """.trimIndent()

        val payload = IntentClassifier.parse(fenced)
        assertEquals(UserIntent.WEATHER, payload.intent)
        assertEquals("current", payload.parameters["location"])
    }

    @Test
    fun `test raw non-json fallback to conversation`() {
        val raw = "Hello Animus, how are you today?"
        val payload = IntentClassifier.parse(raw)

        assertEquals("conversation", payload.type)
        assertEquals(UserIntent.CONVERSATION, payload.intent)
        assertEquals("Hello Animus, how are you today?", payload.spokenResponse)
    }

    @Test
    fun `test IntentPromptBuilder contains strict rules and registry`() {
        val prompt = IntentPromptBuilder.buildSystemPrompt()
        assertTrue(prompt.contains("Intent Classifier for Animus Smart Room"))
        assertTrue(prompt.contains("GENERAL_COMMAND"))
        assertTrue(prompt.contains("MOVIE"))
        assertTrue(prompt.contains("MULTI_INTENT"))
        assertTrue(prompt.contains("CLARIFICATION_REQUIRED"))
        assertTrue(prompt.contains("OUTPUT RAW JSON ONLY"))
    }
}
