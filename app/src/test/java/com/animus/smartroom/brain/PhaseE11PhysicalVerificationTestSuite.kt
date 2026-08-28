package com.animus.smartroom.brain

import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.provider.PcLocalMusicProvider
import com.animus.smartroom.media.provider.ProviderResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PhaseE11PhysicalVerificationTestSuite {

    // E11-1: Music dispatch failure cannot become COMPLETED
    @Test
    fun testE11_01_MusicDispatchFailure_ReturnsError() = runBlocking {
        val mockController = object : MusicController() {
            override fun playTrackPreset(title: String, artist: String?, activeDeviceName: String, directVideoId: String?): ProviderResult {
                return ProviderResult.Failed("AUDIO_OUTPUT_UNAVAILABLE: Soundbar is disconnected")
            }
        }

        val router = CommandRouter(
            musicController = mockController
        )

        val result = router.execute(AnimusCommand.PlayMusic(title = "Janamann"))
        assertFalse("Music dispatch failure must produce false success", result.success)
        assertTrue("Message must indicate playback failure", result.message.contains("Playback failed"))
    }

    // E11-2: Music confirmed playback produces true success
    @Test
    fun testE11_02_MusicPlaybackConfirmed_ReturnsSuccess() = runBlocking {
        val mockController = object : MusicController() {
            override fun playTrackPreset(title: String, artist: String?, activeDeviceName: String, directVideoId: String?): ProviderResult {
                return ProviderResult.PlaybackConfirmed
            }
        }

        val router = CommandRouter(
            musicController = mockController
        )

        val result = router.execute(AnimusCommand.PlayMusic(title = "Janamann"))
        assertTrue("Music playback confirmation must produce true success", result.success)
        assertEquals("Playing Janamann", result.message)
    }

    // E11-3: AC API success without matching telemetry cannot become COMPLETED
    @Test
    fun testE11_03_AcTelemetryMismatch_ReturnsError() = runBlocking {
        val mockTuyaClient = object : TuyaApiClient {
            override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
                // Returns power = false despite sending command true
                return Result.success(listOf(
                    TuyaDeviceStatusItem("switch", false),
                    TuyaDeviceStatusItem("temp_set", 24),
                    TuyaDeviceStatusItem("temp_current", 26),
                    TuyaDeviceStatusItem("mode", "cold")
                ))
            }

            override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
                return Result.success(true) // Cloud accepted, but physical device remained OFF
            }
        }

        val adapter = TuyaAirConditionerAdapter(
            apiClient = mockTuyaClient,
            allowWriteCommands = true
        )

        val device = RoomDevice(
            id = "test_ac",
            displayName = "Bedroom AC",
            type = DeviceType.AIR_CONDITIONER,
            connectionState = DeviceConnectionState.Connected,
            supportedCapabilities = setOf(DeviceCapability.Power)
        )

        val result = adapter.setPower(device, on = true)
        assertFalse("AC telemetry mismatch must not report success", result.success)
        assertTrue("Failure message must indicate readback power was not ON", result.message.contains("readback power was not ON"))
    }

    // E11-4: AC API success with verified matching telemetry returns COMPLETED
    @Test
    fun testE11_04_AcTelemetryMatch_ReturnsSuccess() = runBlocking {
        var currentPower = false
        val mockTuyaClient = object : TuyaApiClient {
            override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
                return Result.success(listOf(
                    TuyaDeviceStatusItem("switch", currentPower),
                    TuyaDeviceStatusItem("temp_set", 24),
                    TuyaDeviceStatusItem("temp_current", 26),
                    TuyaDeviceStatusItem("mode", "cold")
                ))
            }

            override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
                currentPower = true
                return Result.success(true)
            }
        }

        val adapter = TuyaAirConditionerAdapter(
            apiClient = mockTuyaClient,
            allowWriteCommands = true
        )

        val device = RoomDevice(
            id = "test_ac",
            displayName = "Bedroom AC",
            type = DeviceType.AIR_CONDITIONER,
            connectionState = DeviceConnectionState.Connected,
            supportedCapabilities = setOf(DeviceCapability.Power)
        )

        val result = adapter.setPower(device, on = true)
        assertTrue("AC matching readback must report success", result.success)
        assertEquals("Bedroom AC is now turned ON.", result.message)
    }

    // E11-5: Movie Mode partial hardware success cannot become COMPLETED
    @Test
    fun testE11_05_MovieModePartialHardwareFailure_ReturnsError() = runBlocking {
        val mockController = object : MusicController() {
            override fun startMovieModeWithFeedback(contentTitle: String?, provider: String?): PcLocalMusicProvider.MovieModeResult {
                return PcLocalMusicProvider.MovieModeResult(
                    success = false,
                    status = "PROJECTOR_OFF_REQUIRES_MANUAL_ACTION",
                    message = "The projector is currently off. Please turn on the projector manually.",
                    spokenResponse = "The projector is currently off. Please turn on the projector manually."
                )
            }
        }

        val router = CommandRouter(
            musicController = mockController
        )

        val result = router.execute(AnimusCommand.StartMovieMode(contentTitle = "Article 15"))
        assertFalse("Movie Mode with projector off must return false", result.success)
        assertTrue(result.message.contains("projector is currently off"))
    }

    // E11-6: Movie Mode full hardware success returns COMPLETED
    @Test
    fun testE11_06_MovieModeAllInvariantsVerified_ReturnsSuccess() = runBlocking {
        val mockController = object : MusicController() {
            override fun startMovieModeWithFeedback(contentTitle: String?, provider: String?): PcLocalMusicProvider.MovieModeResult {
                return PcLocalMusicProvider.MovieModeResult(
                    success = true,
                    status = "HEALTHY",
                    message = "Movie Mode started",
                    spokenResponse = "Movie Mode started"
                )
            }
        }

        val router = CommandRouter(
            musicController = mockController
        )

        val result = router.execute(AnimusCommand.StartMovieMode(contentTitle = "Article 15"))
        assertTrue("Movie Mode with all verified invariants must return true", result.success)
        assertTrue(result.message.contains("Starting Movie Mode for 'Article 15'"))
    }
}
