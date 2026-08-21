package com.animus.smartroom.overlay

import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OverlaySecurityTest {

    @Test
    fun `EventSanitizer sanitizes Gemini and Bearer tokens before overlay display`() {
        val rawMessage = "Command with AIzaSyABCDEFGH1234567890abcdef12345 and Bearer eyJhbGciOiJIUzI1NiJ9.abc.xyz"
        val sanitized = EventSanitizer.sanitizeText(rawMessage)

        assertFalse(sanitized!!.contains("AIzaSyABCDEFGH1234567890abcdef12345"))
        assertFalse(sanitized.contains("eyJhbGciOiJIUzI1NiJ9.abc.xyz"))
        assertTrue(sanitized.contains("[REDACTED_GEMINI_KEY]"))
        assertTrue(sanitized.contains("[REDACTED_BEARER_TOKEN]"))
    }

    @Test
    fun `EventSanitizer protects sensitive metadata in overlay cards`() {
        val meta = mapOf("access_token" to "secret_tok_12345", "power" to "ON")
        val sanitized = EventSanitizer.sanitizeMetadata(meta)

        assertEquals("[REDACTED]", sanitized["access_token"])
        assertEquals("ON", sanitized["power"])
    }
}
