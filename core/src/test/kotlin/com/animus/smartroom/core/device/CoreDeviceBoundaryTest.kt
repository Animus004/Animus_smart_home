package com.animus.smartroom.core.device

import com.animus.smartroom.device.model.AcFanSpeed
import com.animus.smartroom.device.model.AcMode
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceLookupResult
import com.animus.smartroom.device.registry.CoreDeviceRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CoreDeviceBoundaryTest {

    private lateinit var transport: FakeDeviceTransport
    private lateinit var acAdapter: FakeAirConditionerAdapter
    private lateinit var audioAdapter: FakeAudioOutputAdapter
    private lateinit var registry: CoreDeviceRegistry

    private val acDevice = RoomDevice(
        id = "ac_test_123",
        displayName = "Bedroom AC",
        type = DeviceType.AIR_CONDITIONER,
        supportedCapabilities = setOf(
            DeviceCapability.Power,
            DeviceCapability.Temperature,
            DeviceCapability.HvacMode,
            DeviceCapability.FanSpeed
        )
    )

    private val speakerDevice = RoomDevice(
        id = "speaker_test_456",
        displayName = "LG Soundbar",
        type = DeviceType.BLUETOOTH_AUDIO,
        supportedCapabilities = setOf(
            DeviceCapability.Connect,
            DeviceCapability.Disconnect
        )
    )

    @Before
    fun setup() {
        transport = FakeDeviceTransport()
        acAdapter = FakeAirConditionerAdapter(transport)
        audioAdapter = FakeAudioOutputAdapter()
        registry = CoreDeviceRegistry()

        registry.registerDevice(acDevice)
        registry.registerDevice(speakerDevice)
        registry.registerAdapterForDevice(acDevice.id, acAdapter)
        registry.registerAdapterForDevice(speakerDevice.id, audioAdapter)
    }

    @Test
    fun `DeviceTransport sends commands and reads state successfully`() = runBlocking {
        val sendRes = transport.send(acDevice, DeviceCommand.Power(true))
        assertTrue(sendRes.success)
        assertEquals(1, transport.sentCommands.size)
        assertEquals(DeviceCommand.Power(true), transport.sentCommands.first().second)

        transport.mockState = mapOf("switch" to true, "temp_set" to 23)
        val readRes = transport.readState(acDevice)
        assertTrue(readRes.success)
        assertEquals(true, readRes.stateProperties["switch"])
        assertEquals(23, readRes.stateProperties["temp_set"])
    }

    @Test
    fun `DeviceTransport handles transport write and read failures`() = runBlocking {
        transport.shouldFailSend = true
        val sendRes = transport.send(acDevice, DeviceCommand.Power(true))
        assertFalse(sendRes.success)
        assertEquals("Simulated transport error", sendRes.message)

        transport.shouldFailRead = true
        val readRes = transport.readState(acDevice)
        assertFalse(readRes.success)
        assertEquals("Simulated read error", readRes.errorMessage)
    }

    @Test
    fun `AirConditionerDeviceAdapter executes power and temperature commands`() = runBlocking {
        val pwrRes = acAdapter.setPower(acDevice, true)
        assertTrue(pwrRes.success)
        assertTrue(acAdapter.powerState)

        val tempRes = acAdapter.setTemperature(acDevice, 23)
        assertTrue(tempRes.success)
        assertEquals(23, acAdapter.currentTemperature)

        val invalidTempRes = acAdapter.setTemperature(acDevice, 32)
        assertFalse(invalidTempRes.success)
        assertEquals(23, acAdapter.currentTemperature)
    }

    @Test
    fun `AirConditionerDeviceAdapter executes modes and fan speeds`() = runBlocking {
        val modeRes = acAdapter.setMode(acDevice, AcMode.COOL)
        assertTrue(modeRes.success)
        assertEquals(AcMode.COOL, acAdapter.currentMode)

        val fanRes = acAdapter.setFanSpeed(acDevice, AcFanSpeed.HIGH)
        assertTrue(fanRes.success)
        assertEquals(AcFanSpeed.HIGH, acAdapter.currentFanSpeed)
    }

    @Test
    fun `AirConditionerDeviceAdapter automatically powers on when temperature is set while OFF`() = runBlocking {
        acAdapter.powerState = false
        val tempRes = acAdapter.setTemperature(acDevice, 24)
        assertTrue(tempRes.success)
        assertTrue(acAdapter.powerState)
        assertTrue(tempRes.message.contains("AC was off, so I turned it on and set the temperature to 24°C."))
    }

    @Test
    fun `AudioOutputAdapter connects and disconnects`() = runBlocking {
        val connRes = audioAdapter.connect(speakerDevice)
        assertTrue(connRes.success)
        assertTrue(audioAdapter.isConnected)

        val discRes = audioAdapter.disconnect(speakerDevice)
        assertTrue(discRes.success)
        assertFalse(audioAdapter.isConnected)
    }

    @Test
    fun `CoreDeviceRegistry lookups and command execution`() = runBlocking {
        val lookup = registry.findDeviceByQuery("bedroom ac")
        assertTrue(lookup is DeviceLookupResult.Match)
        assertEquals(acDevice.id, (lookup as DeviceLookupResult.Match).device.id)

        val execRes = registry.executeCommand(acDevice, DeviceCommand.SetTemperature(24))
        assertTrue(execRes.success)
        assertEquals(24, acAdapter.currentTemperature)
    }

    @Test
    fun `MusicPlaybackPort basic operations`() = runBlocking {
        val musicPort = FakeMusicPlaybackPort()
        val track = ResolvedTrack(title = "Zara Zara", artist = "Bombay Jayashri", videoId = "3Yx1e15X-2s")

        val playRes = musicPort.play(track, "LG Soundbar")
        assertTrue(playRes.isSuccess)
        assertTrue(musicPort.isPlaying)
        assertEquals(track, musicPort.currentTrack)

        val pauseRes = musicPort.pause()
        assertTrue(pauseRes.isSuccess)
        assertFalse(musicPort.isPlaying)

        val volRes = musicPort.setVolume(25)
        assertTrue(volRes.isSuccess)
        assertEquals(25, musicPort.currentVolume)
    }
}
