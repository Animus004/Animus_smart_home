package com.animus.smartroom.brain

import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.brain.model.BrainProviderType
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.brain.provider.CloudAnimusBrain
import com.animus.smartroom.brain.provider.GeminiApiClient
import com.animus.smartroom.brain.provider.LocalAnimusBrain
import com.animus.smartroom.brain.validator.BrainCommandValidator
import com.animus.smartroom.brain.validator.BrainValidationResult
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.resolver.MusicResolutionCache
import com.animus.smartroom.media.resolver.MusicResolutionResult
import com.animus.smartroom.media.resolver.ResolutionSource
import com.animus.smartroom.media.resolver.YouTubeDataApiClient
import com.animus.smartroom.media.resolver.YouTubeMusicResolver
import com.animus.smartroom.media.resolver.YouTubeSearchCandidate
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class MultiIntentCommandRoutingTest {

    private lateinit var localBrain: LocalAnimusBrain
    private lateinit var cache: MusicResolutionCache

    @Before
    fun setUp() {
        localBrain = LocalAnimusBrain()
        cache = MusicResolutionCache(prefs = null, maxEntries = 50)
    }

    // 1. Local simple: "Set volume to 40%" → exactly 1 local command
    @Test
    fun testLocalSimpleSetVolume() = runBlocking {
        val result = localBrain.interpret("Set volume to 40%")
        assertTrue(result is BrainResult.Success)
        val success = result as BrainResult.Success
        assertEquals(1, success.commands.size)
        val cmd = success.commands[0]
        assertTrue(cmd is AnimusCommand.SetVolume)
        assertEquals(40, (cmd as AnimusCommand.SetVolume).percentage)
    }

    // 2. Local simple: "Mute" / "Pause" → exactly 1 local command
    @Test
    fun testLocalSimplePauseAndVolumeZero() = runBlocking {
        val pauseResult = localBrain.interpret("pause")
        assertTrue(pauseResult is BrainResult.Success)
        val pauseSuccess = pauseResult as BrainResult.Success
        assertEquals(1, pauseSuccess.commands.size)
        assertEquals(AnimusCommand.PauseMusic, pauseSuccess.commands[0])

        val volZeroResult = localBrain.interpret("set volume to 0%")
        assertTrue(volZeroResult is BrainResult.Success)
        val volSuccess = volZeroResult as BrainResult.Success
        assertEquals(1, volSuccess.commands.size)
        assertEquals(0, (volSuccess.commands[0] as AnimusCommand.SetVolume).percentage)
    }

    // 3. Gemini multi-intent: "Play Zaroori Tha and set volume to 20%" → 2 commands
    @Test
    fun testGeminiMultiIntentPlayAndVolume() {
        val rawGeminiJson = """
            {
                "commands": [
                    {
                        "command": "PLAY_MUSIC",
                        "title": "Zaroori Tha",
                        "artist": "Rahat Fateh Ali Khan"
                    },
                    {
                        "command": "SET_VOLUME",
                        "value": 20
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawGeminiJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(2, valid.commands.size)

        val cmd1 = valid.commands[0] as AnimusCommand.PlayMusic
        assertEquals("Zaroori Tha", cmd1.title)
        assertEquals("Rahat Fateh Ali Khan", cmd1.artist)

        val cmd2 = valid.commands[1] as AnimusCommand.SetVolume
        assertEquals(20, cmd2.percentage)
    }

    // 4. Gemini reversed order: "Set volume to 20% and play Zaroori Tha" → 2 commands, preserved order
    @Test
    fun testGeminiMultiIntentReversedOrder() {
        val rawGeminiJson = """
            {
                "commands": [
                    {
                        "command": "SET_VOLUME",
                        "value": 20
                    },
                    {
                        "command": "PLAY_MUSIC",
                        "title": "Zaroori Tha"
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawGeminiJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(2, valid.commands.size)

        // Preserved exact order
        val cmd1 = valid.commands[0] as AnimusCommand.SetVolume
        assertEquals(20, cmd1.percentage)

        val cmd2 = valid.commands[1] as AnimusCommand.PlayMusic
        assertEquals("Zaroori Tha", cmd2.title)
    }

    // 5. Three commands: "Play Zara Zara, set volume to 30%, and connect LG soundbar" → 3 commands
    @Test
    fun testGeminiThreeSequentialCommands() {
        val rawGeminiJson = """
            {
                "commands": [
                    {
                        "command": "PLAY_MUSIC",
                        "title": "Zara Zara",
                        "artist": "Bombay Jayashri"
                    },
                    {
                        "command": "SET_VOLUME",
                        "value": 30
                    },
                    {
                        "command": "CONNECT_BLUETOOTH_DEVICE",
                        "target": "LG soundbar"
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawGeminiJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(3, valid.commands.size)

        assertTrue(valid.commands[0] is AnimusCommand.PlayMusic)
        assertEquals("Zara Zara", (valid.commands[0] as AnimusCommand.PlayMusic).title)

        assertTrue(valid.commands[1] is AnimusCommand.SetVolume)
        assertEquals(30, (valid.commands[1] as AnimusCommand.SetVolume).percentage)

        assertTrue(valid.commands[2] is AnimusCommand.ConnectBluetoothDevice)
        assertEquals("LG soundbar", (valid.commands[2] as AnimusCommand.ConnectBluetoothDevice).deviceName)
    }

    // 6. Song title containing conjunction-like words: verify natural-language parsing does not blindly split on "and"
    @Test
    fun testSongTitleWithConjunctionAnd() {
        val rawGeminiJson = """
            {
                "commands": [
                    {
                        "command": "PLAY_MUSIC",
                        "title": "Romeo and Juliet",
                        "artist": "Dire Straits"
                    },
                    {
                        "command": "SET_VOLUME",
                        "value": 50
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawGeminiJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(2, valid.commands.size)

        val musicCmd = valid.commands[0] as AnimusCommand.PlayMusic
        assertEquals("Romeo and Juliet", musicCmd.title)
        assertEquals("Dire Straits", musicCmd.artist)

        val volCmd = valid.commands[1] as AnimusCommand.SetVolume
        assertEquals(50, volCmd.percentage)
    }

    // 7. Music-only: "Play Zaroori Tha" → 1 PLAY_MUSIC command → YouTubeMusicResolver still works
    @Test
    fun testSingleMusicQueryWithResolver() = runBlocking {
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                return Result.success(YouTubeSearchCandidate("60ItHLz5WEA", "Zaroori Tha", "Universal Music India"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val resolution = resolver.resolveTrack("Zaroori Tha", null)
        assertTrue(resolution is MusicResolutionResult.Resolved)
        val resolved = resolution as MusicResolutionResult.Resolved
        assertEquals("60ItHLz5WEA", resolved.videoId)
        assertEquals(ResolutionSource.YouTubeDataApi, resolved.source)
    }

    // 8. Cache: repeat the same song → resolver should use the existing cache
    @Test
    fun testCacheReuseOnRepeatedSong() = runBlocking {
        val apiCallCount = AtomicInteger(0)
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                apiCallCount.incrementAndGet()
                return Result.success(YouTubeSearchCandidate("60ItHLz5WEA", "Zaroori Tha", "Universal Music India"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        // 1st call -> Cache Miss, queries API
        val res1 = resolver.resolveTrack("Zaroori Tha", null)
        assertEquals("60ItHLz5WEA", (res1 as MusicResolutionResult.Resolved).videoId)
        assertEquals(1, apiCallCount.get())

        // 2nd call -> Cache Hit, no API call
        val res2 = resolver.resolveTrack("Zaroori Tha", null)
        assertEquals("60ItHLz5WEA", (res2 as MusicResolutionResult.Resolved).videoId)
        assertEquals(ResolutionSource.Cache, (res2 as MusicResolutionResult.Resolved).source)
        assertEquals(1, apiCallCount.get())
    }

    // 9. Gemini failure: multi-intent command with network/API failure → graceful fallback behavior
    @Test
    fun testGeminiFailureFallbackToLocal() = runBlocking {
        val fakeCloud = object : AnimusBrain {
            override val providerType = BrainProviderType.GEMINI
            override suspend fun interpret(input: String): BrainResult {
                return BrainResult.Failure("Network timeout (HTTP 503)")
            }
        }

        val manager = AnimusBrainManager(
            localBrain = localBrain,
            cloudBrain = fakeCloud,
            initialProvider = BrainProviderType.GEMINI
        )

        val fallbackResult = manager.interpret("set volume to 35%")
        assertTrue(fallbackResult is BrainResult.Success)
        val cmd = (fallbackResult as BrainResult.Success).commands[0]
        assertTrue(cmd is AnimusCommand.SetVolume)
        assertEquals(35, (cmd as AnimusCommand.SetVolume).percentage)
    }

    // 10. Regression: PLAY_MUSIC with title="Ramta Jogi", artist=null, playbackUrl=null, directVideoId=null
    @Test
    fun testPlayMusicWithExplicitNullPlaybackUrlDoesNotFailUrlValidation() = runBlocking {
        val rawJson = """
            {
                "commands": [
                    {
                        "command": "PLAY_MUSIC",
                        "title": "Ramta Jogi",
                        "artist": null,
                        "playbackUrl": null,
                        "directVideoId": null
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(1, valid.commands.size)

        val musicCmd = valid.commands[0] as AnimusCommand.PlayMusic
        assertEquals("Ramta Jogi", musicCmd.title)
        assertEquals(null, musicCmd.artist)
        assertEquals(null, musicCmd.directVideoId)

        // Verify resolver works on this command
        val fakeClient = object : YouTubeDataApiClient {
            override suspend fun searchVideo(apiKey: String, query: String): Result<YouTubeSearchCandidate> {
                return Result.success(YouTubeSearchCandidate("QxwmIXIWO7I", "Ramta Jogi", "Tips Official"))
            }
        }

        val resolver = YouTubeMusicResolver(
            apiKeyProvider = { "dummy-key" },
            cache = cache,
            apiClient = fakeClient
        )

        val resolution = resolver.resolveTrack(musicCmd.title, musicCmd.artist, musicCmd.directVideoId)
        assertTrue(resolution is MusicResolutionResult.Resolved)
        val resolved = resolution as MusicResolutionResult.Resolved
        assertEquals("QxwmIXIWO7I", resolved.videoId)
        assertEquals(ResolutionSource.YouTubeDataApi, resolved.source)
    }

    // 11. Multi-intent: "Play Ramta Jogi and set volume to 60%" with null playbackUrl
    @Test
    fun testMultiIntentRamtaJogiAndVolume60WithNullPlaybackUrl() = runBlocking {
        val rawJson = """
            {
                "commands": [
                    {
                        "command": "PLAY_MUSIC",
                        "title": "Ramta Jogi",
                        "artist": null,
                        "playbackUrl": null
                    },
                    {
                        "command": "SET_VOLUME",
                        "value": 60
                    }
                ]
            }
        """.trimIndent()

        val validation = BrainCommandValidator.parseAndValidateJson(rawJson)
        assertTrue(validation is BrainValidationResult.Valid)
        val valid = validation as BrainValidationResult.Valid
        assertEquals(2, valid.commands.size)

        val musicCmd = valid.commands[0] as AnimusCommand.PlayMusic
        assertEquals("Ramta Jogi", musicCmd.title)
        assertEquals(null, musicCmd.artist)
        assertEquals(null, musicCmd.directVideoId)

        val volCmd = valid.commands[1] as AnimusCommand.SetVolume
        assertEquals(60, volCmd.percentage)
    }
}
