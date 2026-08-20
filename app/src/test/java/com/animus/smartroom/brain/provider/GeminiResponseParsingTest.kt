package com.animus.smartroom.brain.provider

import com.animus.smartroom.brain.AnimusBrain
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.media.provider.YouTubeMusicProvider
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GeminiResponseParsingTest {

    @Test
    fun testCentralizedModelConfiguration() {
        assertEquals("gemini-3.5-flash-lite", GeminiModelConfig.DEFAULT_GEMINI_MODEL)
        val expectedEndpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
        assertEquals(expectedEndpoint, GeminiModelConfig.getGenerateContentUrl())
    }

    @Test
    fun testZaraZaraVerifiedMappingPreserved() {
        assertEquals("IWjbBSMsQJg", YouTubeMusicProvider.ZARA_ZARA_VIDEO_ID)
    }

    @Test
    fun testValidPlayMusicCommandWithoutUrl() {
        val json = """
            {
              "command": "PLAY_MUSIC",
              "title": "Ramta Jogi",
              "artist": "Alka Yagnik"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Valid)

        val cmd = (validation as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.PlayMusic)
        val play = cmd as AnimusCommand.PlayMusic
        assertEquals("Ramta Jogi", play.title)
        assertEquals("Alka Yagnik", play.artist)
        assertNull(play.directVideoId)
    }

    @Test
    fun testValidPlayMusicCommandWithYouTubeMusicUrl() {
        val json = """
            {
              "command": "PLAY_MUSIC",
              "title": "Ramta Jogi",
              "artist": "Alka Yagnik",
              "playbackUrl": "https://music.youtube.com/watch?v=k1bEaBcDeFg"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Valid)

        val cmd = (validation as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.PlayMusic)
        val play = cmd as AnimusCommand.PlayMusic
        assertEquals("Ramta Jogi", play.title)
        assertEquals("Alka Yagnik", play.artist)
        assertEquals("k1bEaBcDeFg", play.directVideoId)
    }

    @Test
    fun testValidPlayMusicTeraMeraRishta() {
        val json = """
            {
              "command": "PLAY_MUSIC",
              "title": "Tera Mera Rishta",
              "artist": "Mustafa Zahid",
              "playbackUrl": "https://music.youtube.com/watch?v=aBcDeFgHiJk"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Valid)

        val cmd = (validation as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.PlayMusic)
        val play = cmd as AnimusCommand.PlayMusic
        assertEquals("Tera Mera Rishta", play.title)
        assertEquals("Mustafa Zahid", play.artist)
        assertEquals("aBcDeFgHiJk", play.directVideoId)
    }

    @Test
    fun testValidPlayMusicTumSeHi() {
        val json = """
            {
              "command": "PLAY_MUSIC",
              "title": "Tum Se Hi",
              "artist": "Mohit Chauhan",
              "playbackUrl": "https://youtu.be/lMnOpQrStUv"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Valid)

        val cmd = (validation as BrainValidationResult.Valid).command
        assertTrue(cmd is AnimusCommand.PlayMusic)
        val play = cmd as AnimusCommand.PlayMusic
        assertEquals("Tum Se Hi", play.title)
        assertEquals("Mohit Chauhan", play.artist)
        assertEquals("lMnOpQrStUv", play.directVideoId)
    }

    @Test
    fun testRejectInvalidDomainInPlaybackUrl() {
        val json = """
            {
              "command": "PLAY_MUSIC",
              "title": "Ramta Jogi",
              "playbackUrl": "https://unauthorized-domain.com/watch?v=k1bEaBcDeFg"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Invalid)
        val reason = (validation as BrainValidationResult.Invalid).reason
        assertTrue(reason.contains("Unauthorized") || reason.contains("Invalid"))
    }

    @Test
    fun testRejectMalformedUrlInPlaybackUrl() {
        val json = """
            {
              "command": "PLAY_MUSIC",
              "title": "Ramta Jogi",
              "playbackUrl": "javascript:alert(1)"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Invalid)
    }

    @Test
    fun testRejectMissingTitleInPlayMusic() {
        val json = """
            {
              "command": "PLAY_MUSIC"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Invalid)
    }

    @Test
    fun testRejectMissingCommandField() {
        val json = """
            {
              "title": "Ramta Jogi"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Invalid)
    }

    @Test
    fun testRejectInvalidVolumeRange() {
        val json = """
            {
              "command": "SET_VOLUME",
              "value": 150
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Invalid)
    }

    @Test
    fun testRejectUnsupportedCommand() {
        val json = """
            {
              "command": "LAUNCH_MISSILE"
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(json)
        assertTrue(validation is BrainValidationResult.Invalid)
    }

    @Test
    fun testApiKeyFingerprintComputation() {
        val testKey = "AIzaSyDummyKeyForTesting12345"
        val fp = GeminiApiClient.computeKeyFingerprint(testKey)
        assertEquals(8, fp.length)
        assertTrue(fp.matches(Regex("^[0-9A-F]{8}$")))
    }

    @Test
    fun testApiKeyMaskingInText() {
        val secretKey = "AIzaSyDummySecretKey987654321"
        val rawMessage = "Failed to connect using $secretKey to endpoint."
        val masked = GeminiApiClient.maskKeyInText(rawMessage, secretKey)
        assertTrue(!masked.contains(secretKey))
        assertTrue(masked.contains("API_KEY_MASKED["))
    }

    @Test
    fun testParseGoogleError429ResourceExhaustedWithDetails() {
        val client = GeminiApiClient()
        val errorJson = """
            {
              "error": {
                "code": 429,
                "message": "Resource has been exhausted (e.g. check quota).",
                "status": "RESOURCE_EXHAUSTED",
                "details": [
                  {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "RATE_LIMIT_EXCEEDED",
                    "metadata": { "quota_limit": "15RPM" }
                  }
                ]
              }
            }
        """.trimIndent()

        val parsed = client.parseDetailedGoogleError(
            code = 429,
            rawBody = errorJson,
            retryAfter = "12",
            requestId = "req-12345"
        )

        assertTrue(parsed.contains("HTTP 429 (RESOURCE_EXHAUSTED)"))
        assertTrue(parsed.contains("gemini-3.5-flash-lite"))
        assertTrue(parsed.contains("RATE_LIMIT_EXCEEDED"))
        assertTrue(parsed.contains("Retry-After: 12"))
        assertTrue(parsed.contains("RequestId: req-12345"))
    }

    @Test
    fun testParseGoogleError404ModelNotFound() {
        val client = GeminiApiClient(modelId = "gemini-1.5-flash")
        val errorJson = """
            {
              "error": {
                "code": 404,
                "message": "models/gemini-1.5-flash is not found for API version v1beta",
                "status": "NOT_FOUND"
              }
            }
        """.trimIndent()

        val parsed = client.parseDetailedGoogleError(
            code = 404,
            rawBody = errorJson,
            model = "gemini-1.5-flash"
        )

        assertTrue(parsed.contains("HTTP 404"))
        assertTrue(parsed.contains("gemini-1.5-flash"))
        assertTrue(parsed.contains("not found"))
    }

    @Test
    fun testParseGoogleError403PermissionDenied() {
        val client = GeminiApiClient()
        val errorJson = """
            {
              "error": {
                "code": 403,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "PERMISSION_DENIED"
              }
            }
        """.trimIndent()

        val parsed = client.parseDetailedGoogleError(
            code = 403,
            rawBody = errorJson
        )

        assertTrue(parsed.contains("HTTP 403"))
        assertTrue(parsed.contains("PERMISSION_DENIED"))
        assertTrue(parsed.contains("API key not valid"))
    }

    @Test
    fun testParseGoogleError503Overloaded() {
        val client = GeminiApiClient()
        val errorJson = """
            {
              "error": {
                "code": 503,
                "message": "The model is overloaded. Please try again later.",
                "status": "UNAVAILABLE"
              }
            }
        """.trimIndent()

        val parsed = client.parseDetailedGoogleError(
            code = 503,
            rawBody = errorJson,
            retryAfter = "5"
        )

        assertTrue(parsed.contains("HTTP 503"))
        assertTrue(parsed.contains("temporarily overloaded"))
        assertTrue(parsed.contains("Retry-After: 5"))
    }

    @Test
    fun testCloudBrainMissingApiKeyReturnsFailure() = runBlocking {
        val brain = CloudAnimusBrain(apiKeyProvider = { null })
        val result = brain.interpret("Play Ramta Jogi")

        assertTrue(result is BrainResult.Failure)
        val failure = result as BrainResult.Failure
        assertTrue(failure.errorMessage.contains("API key is required"))
    }

    @Test
    fun testBrainManagerFallsBackToLocalWhenCloudUnavailable() = runBlocking {
        val fakeLocal = LocalAnimusBrain()
        val fakeCloud = object : AnimusBrain {
            override val providerType = BrainProviderType.GEMINI
            override suspend fun interpret(input: String): BrainResult = BrainResult.Unavailable
        }

        val manager = AnimusBrainManager(localBrain = fakeLocal, cloudBrain = fakeCloud)
        manager.setProvider(BrainProviderType.GEMINI)

        val result = manager.interpret("volume 30")
        assertTrue(result is BrainResult.Success)

        val command = (result as BrainResult.Success).command
        assertTrue(command is AnimusCommand.SetVolume)
        assertEquals(30, (command as AnimusCommand.SetVolume).percentage)
    }
}

