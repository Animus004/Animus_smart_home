package com.animus.smartroom.core.diagnostics

import com.animus.smartroom.core.diagnostics.model.ActionSource
import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.sanitizer.EventSanitizer
import com.animus.smartroom.diagnostics.DiagnosticBus
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class PrivacyDiagnosticTest {

    @Before
    fun setup() {
        DiagnosticBus.clear()
    }

    @Test
    fun `EventSanitizer redacts Gemini API key, Bearer tokens, and Tuya credentials`() {
        val rawMessage = "Connecting with AIzaSyD9876543210abcdefghijklmnopq and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        val sanitized = EventSanitizer.sanitizeText(rawMessage)

        assertFalse(sanitized!!.contains("AIzaSyD9876543210abcdefghijklmnopq"))
        assertFalse(sanitized.contains("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"))
        assertTrue(sanitized.contains("[REDACTED_GEMINI_KEY]"))
        assertTrue(sanitized.contains("[REDACTED_BEARER_TOKEN]"))
    }

    @Test
    fun `EventSanitizer redacts sensitive metadata keys and values`() {
        val rawMeta = mapOf(
            "access_token" to "secret_token_12345",
            "tuya_secret" to "secret_key_abcde",
            "regular_key" to "safe_value"
        )
        val sanitized = EventSanitizer.sanitizeMetadata(rawMeta)

        assertEquals("[REDACTED]", sanitized["access_token"])
        assertEquals("[REDACTED]", sanitized["tuya_secret"])
        assertEquals("safe_value", sanitized["regular_key"])
    }

    @Test
    fun `DiagnosticBus automatically sanitizes published events and JSON export`() {
        DiagnosticBus.publish {
            create(
                source = ActionSource.SYSTEM,
                action = "AUTH",
                stage = ActionStage.EXECUTING,
                status = ActionStatus.IN_PROGRESS,
                message = "Using token access_token: super_secret_val",
                metadata = mapOf("apiKey" to "AIzaSySecretKey12345678901234567890")
            )
        }

        val event = DiagnosticBus.getRecentActionEvents().first()
        val json = event.toJson()

        assertFalse(json.contains("AIzaSySecretKey12345678901234567890"))
        assertFalse(json.contains("super_secret_val"))
    }

    private fun assertEquals(expected: String, actual: String?) {
        org.junit.Assert.assertEquals(expected, actual)
    }
}
