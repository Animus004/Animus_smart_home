package com.animus.smartroom.device

import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.device.tuya.model.TuyaDeviceStatusItem
import com.animus.smartroom.device.tuya.recovery.AcRecoveryController
import com.animus.smartroom.device.tuya.recovery.AcRecoveryState
import com.animus.smartroom.device.tuya.recovery.RecoveryConfidence
import com.animus.smartroom.device.tuya.recovery.TuyaDiscoveredDevice
import com.animus.smartroom.device.tuya.recovery.TuyaLocalDiscoveryService
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AcRecoveryControllerTest {

    private lateinit var fakeApiClient: FakeTuyaApiClient
    private lateinit var fakeDiscoveryService: FakeTuyaDiscoveryService
    private lateinit var adapter: TuyaAirConditionerAdapter
    private lateinit var deviceRegistry: DeviceRegistry
    private lateinit var controller: AcRecoveryController
    private lateinit var roomDevice: RoomDevice

    private val targetDeviceId = "76776532a4e57c0a2ca4"

    class FakeTuyaApiClient : TuyaApiClient {
        var statusToReturn: List<TuyaDeviceStatusItem>? = null
        var shouldSucceed = true
        var fetchCallCount = 0
        var sentCommands = mutableListOf<Map<String, Any>>()

        override suspend fun fetchStatus(deviceId: String): Result<List<TuyaDeviceStatusItem>> {
            fetchCallCount++
            return if (shouldSucceed && statusToReturn != null) {
                Result.success(statusToReturn!!)
            } else {
                Result.failure(RuntimeException("Device is unreachable / offline"))
            }
        }

        override suspend fun sendCommands(deviceId: String, commands: List<Map<String, Any>>): Result<Boolean> {
            return if (shouldSucceed) {
                sentCommands.addAll(commands)
                Result.success(true)
            } else {
                Result.failure(RuntimeException("Command failed: device offline"))
            }
        }
    }

    class FakeTuyaDiscoveryService : TuyaLocalDiscoveryService {
        var deviceToReturn: TuyaDiscoveredDevice? = null
        var shouldDiscover = true
        var listenCallCount = 0

        override suspend fun listenForDevice(expectedGwId: String, timeoutMs: Long): Result<TuyaDiscoveredDevice> {
            listenCallCount++
            return if (shouldDiscover && deviceToReturn != null) {
                Result.success(deviceToReturn!!)
            } else {
                Result.failure(NoSuchElementException("No discovery packet received"))
            }
        }
    }

    @Before
    fun setUp() {
        fakeApiClient = FakeTuyaApiClient()
        fakeDiscoveryService = FakeTuyaDiscoveryService()
        adapter = TuyaAirConditionerAdapter(apiClient = fakeApiClient, allowWriteCommands = true)
        deviceRegistry = DeviceRegistry().apply {
            registerAdapterForType(DeviceType.AIR_CONDITIONER, adapter)
        }

        roomDevice = RoomDevice(
            id = targetDeviceId,
            displayName = "Bedroom AC",
            type = DeviceType.AIR_CONDITIONER,
            connectionState = DeviceConnectionState.Connected,
            supportedCapabilities = setOf(
                DeviceCapability.Power,
                DeviceCapability.Temperature,
                DeviceCapability.HvacMode,
                DeviceCapability.FanSpeed
            )
        )
        deviceRegistry.registerDevice(roomDevice)

        controller = AcRecoveryController(
            apiClient = fakeApiClient,
            adapter = adapter,
            deviceRegistry = deviceRegistry,
            discoveryService = fakeDiscoveryService,
            expectedDeviceId = targetDeviceId
        )
    }

    @Test
    fun `test 1 - offline detection transitions to WAITING_FOR_USER and updates DeviceRegistry to Disconnected`() = runBlocking {
        fakeApiClient.shouldSucceed = false
        fakeApiClient.statusToReturn = null

        val status = controller.startRecovery(targetDeviceId)

        assertEquals(AcRecoveryState.WAITING_FOR_USER, status.state)
        assertFalse(status.cloudReachable)
        assertFalse(status.deviceDiscovered)
        assertEquals(targetDeviceId, status.deviceId)
        assertEquals(DeviceConnectionState.Disconnected, deviceRegistry.getDevice(targetDeviceId)?.connectionState)
    }

    @Test
    fun `test 2 - recovery when AC is already online completes immediately with RECOVERED`() = runBlocking {
        fakeApiClient.shouldSucceed = true
        fakeApiClient.statusToReturn = listOf(
            TuyaDeviceStatusItem("switch", true),
            TuyaDeviceStatusItem("temp_set", 24),
            TuyaDeviceStatusItem("temp_current", 26),
            TuyaDeviceStatusItem("mode", "cold"),
            TuyaDeviceStatusItem("fan_speed_enum", "low")
        )

        val status = controller.startRecovery(targetDeviceId)

        assertEquals(AcRecoveryState.RECOVERED, status.state)
        assertTrue(status.cloudReachable)
        assertTrue(status.sameDeviceIdVerified)
        assertEquals(DeviceConnectionState.Connected, deviceRegistry.getDevice(targetDeviceId)?.connectionState)
        assertEquals(RecoveryConfidence.HIGH, status.confidence)
    }

    @Test
    fun `test 3 - detectProvisioningMode handles FAST blink and EZ mode correctly`() {
        val statusFast = controller.detectProvisioningMode("FAST_BLINK")
        assertEquals(AcRecoveryState.FAST_BLINK_DETECTED, statusFast.state)
        assertEquals("EZ", statusFast.provisioningMode)

        val statusEz = controller.detectProvisioningMode("EZ")
        assertEquals(AcRecoveryState.FAST_BLINK_DETECTED, statusEz.state)
        assertEquals("EZ", statusEz.provisioningMode)
    }

    @Test
    fun `test 4 - detectProvisioningMode handles SLOW blink and AP mode correctly`() {
        val statusSlow = controller.detectProvisioningMode("SLOW_BLINK")
        assertEquals(AcRecoveryState.SLOW_BLINK_DETECTED, statusSlow.state)
        assertEquals("AP", statusSlow.provisioningMode)

        val statusAp = controller.detectProvisioningMode("AP")
        assertEquals(AcRecoveryState.SLOW_BLINK_DETECTED, statusAp.state)
        assertEquals("AP", statusAp.provisioningMode)
    }

    @Test
    fun `test 5 - local UDP discovery finds device and records IP and sameDeviceIdVerified`() = runBlocking {
        fakeDiscoveryService.deviceToReturn = TuyaDiscoveredDevice(
            ip = "192.168.1.4",
            gwId = targetDeviceId,
            productKey = "XT0UJtiNvEocE9Mu",
            version = "3.3",
            active = 2
        )

        val result = controller.discoverAc()

        assertTrue(result.isSuccess)
        val dev = result.getOrNull()
        assertNotNull(dev)
        assertEquals("192.168.1.4", dev?.ip)
        assertEquals(targetDeviceId, dev?.gwId)

        val currentStatus = controller.getRecoveryStatus()
        assertTrue(currentStatus.deviceDiscovered)
        assertEquals("192.168.1.4", currentStatus.currentIp)
        assertTrue(currentStatus.sameDeviceIdVerified)
        assertEquals(AcRecoveryState.WAITING_FOR_NETWORK, currentStatus.state)
    }

    @Test
    fun `test 6 - mismatched device ID is rejected during verification`() = runBlocking {
        val verified = controller.verifyRecovery(deviceId = "different_random_device_id")
        assertFalse("Mismatched device ID must fail verification", verified)
    }

    @Test
    fun `test 7 - successful recovery cycle connects, verifies readback, and synchronizes DeviceRegistry`() = runBlocking {
        fakeApiClient.shouldSucceed = true
        fakeApiClient.statusToReturn = listOf(
            TuyaDeviceStatusItem("switch", true),
            TuyaDeviceStatusItem("temp_set", 24),
            TuyaDeviceStatusItem("temp_current", 26),
            TuyaDeviceStatusItem("mode", "cold"),
            TuyaDeviceStatusItem("fan_speed_enum", "auto")
        )

        val finalStatus = controller.recoverConnection(maxAttempts = 3, attemptDelayMs = 10L)

        assertEquals(AcRecoveryState.RECOVERED, finalStatus.state)
        assertTrue(finalStatus.cloudReachable)
        assertTrue(finalStatus.sameDeviceIdVerified)
        assertEquals(DeviceConnectionState.Connected, deviceRegistry.getDevice(targetDeviceId)?.connectionState)
        assertEquals(RecoveryConfidence.HIGH, finalStatus.confidence)

        // Verify adapter state
        val acState = adapter.getAcState(roomDevice)
        assertTrue(acState.isOnline)
        assertEquals(24, acState.targetTemperature)
        assertEquals("HEALTHY", acState.recoveryState)
    }

    @Test
    fun `test 8 - failed recovery after bounded retries sets FAILED and MANUAL_INTERVENTION_REQUIRED`() = runBlocking {
        fakeApiClient.shouldSucceed = false
        fakeApiClient.statusToReturn = null
        fakeDiscoveryService.shouldDiscover = false

        val finalStatus = controller.recoverConnection(maxAttempts = 5, attemptDelayMs = 10L)

        assertEquals(AcRecoveryState.FAILED, finalStatus.state)
        assertEquals(5, finalStatus.attemptCount)
        assertFalse(finalStatus.cloudReachable)
        assertEquals(DeviceConnectionState.Disconnected, deviceRegistry.getDevice(targetDeviceId)?.connectionState)
        assertTrue(finalStatus.nextAction.contains("Manual intervention required"))
    }

    @Test
    fun `test 9 - bounded retries strictly terminate without infinite looping`() = runBlocking {
        fakeApiClient.shouldSucceed = false
        fakeDiscoveryService.shouldDiscover = false

        controller.recoverConnection(maxAttempts = 4, attemptDelayMs = 5L)

        val status = controller.getRecoveryStatus()
        assertEquals(4, status.attemptCount)
        assertEquals(AcRecoveryState.FAILED, status.state)
    }

    @Test
    fun `test 10 - cancelRecovery returns state to IDLE safely`() {
        controller.detectProvisioningMode("EZ")
        assertEquals(AcRecoveryState.FAST_BLINK_DETECTED, controller.getRecoveryStatus().state)

        val cancelled = controller.cancelRecovery()
        assertEquals(AcRecoveryState.IDLE, cancelled.state)
    }

    @Test
    fun `test 11 - no destructive commands are sent during entire recovery lifecycle`() = runBlocking {
        fakeApiClient.shouldSucceed = true
        fakeApiClient.statusToReturn = listOf(TuyaDeviceStatusItem("switch", true))

        controller.startRecovery(targetDeviceId)
        controller.discoverAc()
        controller.recoverConnection(maxAttempts = 2, attemptDelayMs = 10L)

        assertTrue(
            "Recovery process must never issue blind write commands or destructive calls",
            fakeApiClient.sentCommands.isEmpty()
        )
    }

    @Test
    fun `test 12 - simulated router-only outage recovery (AC discovers once cloud responds)`() = runBlocking {
        // Initially offline
        fakeApiClient.shouldSucceed = false
        val initial = controller.startRecovery(targetDeviceId)
        assertEquals(AcRecoveryState.WAITING_FOR_USER, initial.state)

        // Router comes back online on attempt 2
        fakeApiClient.shouldSucceed = true
        fakeApiClient.statusToReturn = listOf(
            TuyaDeviceStatusItem("switch", true),
            TuyaDeviceStatusItem("temp_set", 25)
        )

        val recovered = controller.recoverConnection(maxAttempts = 3, attemptDelayMs = 10L)
        assertEquals(AcRecoveryState.RECOVERED, recovered.state)
        assertTrue(recovered.cloudReachable)
        assertEquals(DeviceConnectionState.Connected, deviceRegistry.getDevice(targetDeviceId)?.connectionState)
    }

    @Test
    fun `test 13 - simulated simultaneous AC + router power outage recovery`() = runBlocking {
        // Step 1: AC offline
        fakeApiClient.shouldSucceed = false
        controller.startRecovery(targetDeviceId)
        assertEquals(AcRecoveryState.WAITING_FOR_USER, controller.getRecoveryStatus().state)

        // Step 2: User triggers remote wake -> local UDP broadcast received
        fakeDiscoveryService.deviceToReturn = TuyaDiscoveredDevice(
            ip = "192.168.1.4",
            gwId = targetDeviceId,
            productKey = "XT0UJtiNvEocE9Mu",
            version = "3.3",
            active = 2
        )
        controller.discoverAc()
        assertTrue(controller.getRecoveryStatus().deviceDiscovered)

        // Step 3: Cloud MQTT connection stabilizes -> status query succeeds
        fakeApiClient.shouldSucceed = true
        fakeApiClient.statusToReturn = listOf(
            TuyaDeviceStatusItem("switch", true),
            TuyaDeviceStatusItem("temp_set", 24),
            TuyaDeviceStatusItem("temp_current", 25),
            TuyaDeviceStatusItem("mode", "cold"),
            TuyaDeviceStatusItem("fan_speed_enum", "low")
        )

        val finalStatus = controller.recoverConnection(maxAttempts = 2, attemptDelayMs = 10L)
        assertEquals(AcRecoveryState.RECOVERED, finalStatus.state)
        assertEquals("192.168.1.4", finalStatus.currentIp)
        assertEquals(targetDeviceId, finalStatus.deviceId)
        assertEquals(DeviceConnectionState.Connected, deviceRegistry.getDevice(targetDeviceId)?.connectionState)
    }
}
