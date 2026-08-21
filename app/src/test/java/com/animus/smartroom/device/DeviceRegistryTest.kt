package com.animus.smartroom.device

import com.animus.smartroom.device.adapter.DeviceAdapter
import com.animus.smartroom.device.adapter.MockAirConditionerAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceLookupResult
import com.animus.smartroom.device.registry.DeviceRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class DeviceRegistryTest {

    private lateinit var registry: DeviceRegistry
    private lateinit var mockAcAdapter: MockAirConditionerAdapter

    private val bedroomAc = RoomDevice(
        id = "ac_bedroom",
        displayName = "Bedroom AC",
        type = DeviceType.AIR_CONDITIONER,
        connectionState = DeviceConnectionState.Available,
        supportedCapabilities = setOf(
            DeviceCapability.Power,
            DeviceCapability.Temperature,
            DeviceCapability.HvacMode,
            DeviceCapability.FanSpeed,
            DeviceCapability.Swing
        ),
        aliases = listOf("AC", "Air Conditioner", "Room AC")
    )

    private val lgSpeaker = RoomDevice(
        id = "54:15:89:DC:A5:79",
        displayName = "LG SNC4R(79)",
        type = DeviceType.BLUETOOTH_AUDIO,
        connectionState = DeviceConnectionState.Connected,
        supportedCapabilities = setOf(
            DeviceCapability.Connect,
            DeviceCapability.Disconnect,
            DeviceCapability.Volume,
            DeviceCapability.Play,
            DeviceCapability.Pause
        ),
        aliases = listOf("Bedroom Speaker", "Soundbar")
    )

    @Before
    fun setUp() {
        registry = DeviceRegistry()
        mockAcAdapter = MockAirConditionerAdapter()

        registry.registerDevice(bedroomAc)
        registry.registerDevice(lgSpeaker)
        registry.registerAdapterForType(DeviceType.AIR_CONDITIONER, mockAcAdapter)
    }

    @Test
    fun testRegisterAndRetrieveDevices() {
        val all = registry.getAllDevices()
        assertEquals(2, all.size)

        val ac = registry.getDevice("ac_bedroom")
        assertNotNull(ac)
        assertEquals("Bedroom AC", ac?.displayName)

        val btDevices = registry.getDevicesByType(DeviceType.BLUETOOTH_AUDIO)
        assertEquals(1, btDevices.size)
        assertEquals("54:15:89:DC:A5:79", btDevices[0].id)
    }

    @Test
    fun testLookupByAliasAndGenericKeyword() {
        // Generic AC keyword
        val resAc = registry.findDeviceByNameOrAlias("AC")
        assertTrue(resAc is DeviceLookupResult.Match)
        assertEquals("ac_bedroom", (resAc as DeviceLookupResult.Match).device.id)

        val resAirCond = registry.findDeviceByNameOrAlias("the air conditioner")
        assertTrue(resAirCond is DeviceLookupResult.Match)
        assertEquals("ac_bedroom", (resAirCond as DeviceLookupResult.Match).device.id)

        // Exact Alias match
        val resSpeaker = registry.findDeviceByNameOrAlias("Bedroom Speaker")
        assertTrue(resSpeaker is DeviceLookupResult.Match)
        assertEquals("54:15:89:DC:A5:79", (resSpeaker as DeviceLookupResult.Match).device.id)

        // Generic speaker keyword
        val resGenericSpeaker = registry.findDeviceByNameOrAlias("speaker")
        assertTrue(resGenericSpeaker is DeviceLookupResult.Match)
        assertEquals("54:15:89:DC:A5:79", (resGenericSpeaker as DeviceLookupResult.Match).device.id)

        // Unknown device
        val resNotFound = registry.findDeviceByNameOrAlias("kitchen microwave")
        assertTrue(resNotFound is DeviceLookupResult.NotFound)
    }

    @Test
    fun testAmbiguousDeviceResolution() {
        val livingRoomAc = RoomDevice(
            id = "ac_living",
            displayName = "Living Room AC",
            type = DeviceType.AIR_CONDITIONER,
            supportedCapabilities = setOf(DeviceCapability.Temperature),
            aliases = listOf("Hall AC")
        )
        registry.registerDevice(livingRoomAc)

        val res = registry.findDeviceByNameOrAlias("AC")
        assertTrue(res is DeviceLookupResult.Ambiguous)
        assertEquals(2, (res as DeviceLookupResult.Ambiguous).candidates.size)
    }

    @Test
    fun testExecuteCapabilitySuccess() = runBlocking {
        val result = registry.executeCapability("AC", DeviceCapability.Temperature, 22)
        assertTrue(result.success)
        assertEquals(22, mockAcAdapter.currentTemperature)
        assertTrue(result.message.contains("22°C"))
    }

    @Test
    fun testExecuteCapabilityUnsupportedRejection() = runBlocking {
        // Speaker does NOT support Temperature
        val result = registry.executeCapability("Bedroom Speaker", DeviceCapability.Temperature, 22)
        assertFalse(result.success)
        assertTrue(result.message.contains("does not support capability TEMPERATURE"))
    }

    @Test
    fun testExecuteCapabilityNoAdapter() = runBlocking {
        // Unregister adapter for BLUETOOTH_AUDIO
        val result = registry.executeCapability("Bedroom Speaker", DeviceCapability.Connect, null)
        assertFalse(result.success)
        assertTrue(result.message.contains("No adapter registered"))
    }
}
