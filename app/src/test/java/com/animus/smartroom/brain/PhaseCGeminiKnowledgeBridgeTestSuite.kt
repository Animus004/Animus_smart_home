package com.animus.smartroom.brain

import com.animus.smartroom.brain.knowledge.GeminiKnowledgeBridge
import com.animus.smartroom.brain.knowledge.MediaServiceOption
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class PhaseCGeminiKnowledgeBridgeTestSuite {

    private lateinit var bridge: GeminiKnowledgeBridge

    @Before
    fun setup() {
        bridge = GeminiKnowledgeBridge()
    }

    @Test
    fun `isFreshKnowledgeQuery detects streaming availability queries correctly`() {
        assertTrue(bridge.isFreshKnowledgeQuery("Where can I watch Article 15?"))
        assertTrue(bridge.isFreshKnowledgeQuery("where to watch inception"))
        assertTrue(bridge.isFreshKnowledgeQuery("Is Article 15 available on Netflix?"))
        assertTrue(bridge.isFreshKnowledgeQuery("Where is Interstellar streaming?"))
        assertTrue(bridge.isFreshKnowledgeQuery("Tell me about the movie Oppenheimer"))
        assertTrue(bridge.isFreshKnowledgeQuery("Who directed Inception?"))
        assertTrue(bridge.isFreshKnowledgeQuery("What is the latest movie of Shah Rukh Khan?"))
    }

    @Test
    fun `isFreshKnowledgeQuery excludes deterministic hardware and playback commands`() {
        assertFalse(bridge.isFreshKnowledgeQuery("Set AC to 24 degrees"))
        assertFalse(bridge.isFreshKnowledgeQuery("Turn off the AC"))
        assertFalse(bridge.isFreshKnowledgeQuery("Turn on projector"))
        assertFalse(bridge.isFreshKnowledgeQuery("Set volume to 40"))
        assertFalse(bridge.isFreshKnowledgeQuery("Play Kesariya"))
        assertFalse(bridge.isFreshKnowledgeQuery("Sleep for 45 minutes"))
        assertFalse(bridge.isFreshKnowledgeQuery("Cancel sleep mode"))
    }

    @Test
    fun `queryKnowledge returns graceful failure when API key is not configured`() = runBlocking {
        val result = bridge.queryKnowledge("Where can I watch Article 15?", apiKey = null)
        assertFalse(result.isSuccess)
        assertEquals("API_KEY_NOT_CONFIGURED", result.errorMessage)
        assertTrue(result.summary.contains("unavailable"))
    }

    @Test
    fun `queryKnowledge returns graceful failure when API key is empty or blank`() = runBlocking {
        val result = bridge.queryKnowledge("Where can I watch Article 15?", apiKey = "   ")
        assertFalse(result.isSuccess)
        assertEquals("API_KEY_NOT_CONFIGURED", result.errorMessage)
    }

    @Test
    fun `media service options hold structured availability data correctly`() {
        val option = MediaServiceOption(
            serviceName = "Netflix",
            isAvailable = true,
            confidence = "HIGH",
            notes = "Included with standard plan"
        )
        assertEquals("Netflix", option.serviceName)
        assertTrue(option.isAvailable)
        assertEquals("HIGH", option.confidence)
        assertEquals("Included with standard plan", option.notes)
    }
}
