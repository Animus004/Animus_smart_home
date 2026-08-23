package com.animus.smartroom.device.tuya.recovery

import android.util.Log
import com.animus.smartroom.device.model.DeviceConnectionState
import com.animus.smartroom.device.registry.DeviceRegistry
import com.animus.smartroom.device.tuya.TuyaAirConditionerAdapter
import com.animus.smartroom.device.tuya.client.TuyaApiClient
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withContext

class AcRecoveryController(
    private val apiClient: TuyaApiClient,
    private val adapter: TuyaAirConditionerAdapter,
    private val deviceRegistry: DeviceRegistry,
    private val discoveryService: TuyaLocalDiscoveryService = DefaultTuyaLocalDiscoveryService(),
    val expectedDeviceId: String = "76776532a4e57c0a2ca4",
    private val timeProvider: () -> Long = { System.currentTimeMillis() }
) {

    companion object {
        private const val TAG = "AcRecoveryController"
        const val MAX_RECOVERY_ATTEMPTS = 5
    }

    private val _recoveryStatus = MutableStateFlow(
        AcRecoveryStatus(
            deviceId = expectedDeviceId,
            state = AcRecoveryState.IDLE,
            lastSeenTimestamp = timeProvider()
        )
    )
    val recoveryStatus: StateFlow<AcRecoveryStatus> = _recoveryStatus.asStateFlow()

    fun getRecoveryStatus(): AcRecoveryStatus = _recoveryStatus.value

    suspend fun startRecovery(deviceId: String = expectedDeviceId): AcRecoveryStatus = withContext(Dispatchers.IO) {
        DiagnosticBus.log(
            tag = "ac-recovery",
            stage = DiagnosticStage.REQUESTED,
            message = "Starting AC Wi-Fi Recovery for device '$deviceId'"
        )

        // Pre-check: Is the AC already online and responding?
        val precheck = apiClient.fetchStatus(deviceId)
        if (precheck.isSuccess && !precheck.getOrNull().isNullOrEmpty()) {
            adapter.applyTuyaStatus(precheck.getOrNull()!!)
            deviceRegistry.updateDeviceConnectionState(deviceId, DeviceConnectionState.Connected)
            val healthy = _recoveryStatus.value.copy(
                deviceId = deviceId,
                state = AcRecoveryState.RECOVERED,
                deviceDiscovered = true,
                cloudReachable = true,
                sameDeviceIdVerified = true,
                reason = "AC is already online and fully responsive.",
                nextAction = "None. AC is operating normally.",
                lastSeenTimestamp = timeProvider(),
                confidence = RecoveryConfidence.HIGH
            )
            _recoveryStatus.value = healthy
            DiagnosticBus.log(
                tag = "ac-recovery",
                stage = DiagnosticStage.COMPLETED,
                message = "AC already online and verified."
            )
            return@withContext healthy
        }

        // Device is offline
        deviceRegistry.updateDeviceConnectionState(deviceId, DeviceConnectionState.Disconnected)
        val waitingState = _recoveryStatus.value.copy(
            deviceId = deviceId,
            state = AcRecoveryState.WAITING_FOR_USER,
            deviceDiscovered = false,
            cloudReachable = false,
            sameDeviceIdVerified = false,
            attemptCount = 0,
            reason = "AC Wi-Fi association was lost during router power restoration.",
            nextAction = "Press and hold TURBO + FAN for ~3 seconds on the physical remote (or toggle AC power switch) to trigger Wi-Fi wake.",
            lastSeenTimestamp = timeProvider(),
            confidence = RecoveryConfidence.HIGH
        )
        _recoveryStatus.value = waitingState

        DiagnosticBus.log(
            tag = "ac-recovery",
            stage = DiagnosticStage.VALIDATING,
            message = "AC marked OFFLINE / WAITING_FOR_USER. Prompting physical remote / power wake."
        )
        waitingState
    }

    fun detectProvisioningMode(modeHint: String): AcRecoveryStatus {
        val normalized = modeHint.trim().uppercase()
        val newState = when (normalized) {
            "EZ", "FAST", "FAST_BLINK" -> AcRecoveryState.FAST_BLINK_DETECTED
            "AP", "SLOW", "SLOW_BLINK" -> AcRecoveryState.SLOW_BLINK_DETECTED
            else -> AcRecoveryState.DISCOVERING
        }
        val updated = _recoveryStatus.value.copy(
            state = newState,
            provisioningMode = if (normalized.contains("EZ") || normalized.contains("FAST")) "EZ" else if (normalized.contains("AP") || normalized.contains("SLOW")) "AP" else "UNKNOWN",
            reason = "Provisioning mode detected: $normalized",
            nextAction = "Monitoring local UDP broadcast and Tuya cloud gateway for association.",
            lastSeenTimestamp = timeProvider()
        )
        _recoveryStatus.value = updated
        DiagnosticBus.log(
            tag = "ac-recovery",
            stage = DiagnosticStage.EXECUTING,
            message = "Provisioning mode set: ${updated.provisioningMode} (State=${updated.state.name})"
        )
        return updated
    }

    suspend fun discoverAc(timeoutMs: Long = 8000L): Result<TuyaDiscoveredDevice> = withContext(Dispatchers.IO) {
        _recoveryStatus.update { it.copy(state = AcRecoveryState.DISCOVERING) }
        DiagnosticBus.log(
            tag = "ac-recovery",
            stage = DiagnosticStage.EXECUTING,
            message = "Listening for local UDP 6667 packets from device '$expectedDeviceId'..."
        )

        val result = discoveryService.listenForDevice(expectedDeviceId, timeoutMs)
        if (result.isSuccess) {
            val dev = result.getOrNull()!!
            val sameId = dev.gwId.equals(expectedDeviceId, ignoreCase = true)
            _recoveryStatus.update {
                it.copy(
                    state = AcRecoveryState.WAITING_FOR_NETWORK,
                    deviceDiscovered = true,
                    currentIp = dev.ip,
                    sameDeviceIdVerified = sameId,
                    lastSeenTimestamp = timeProvider()
                )
            }
            DiagnosticBus.log(
                tag = "ac-recovery",
                stage = DiagnosticStage.DEVICE_RESPONSE,
                message = "Device discovered on LAN: IP=${dev.ip}, gwId=${dev.gwId} (SameId=$sameId)"
            )
        }
        result
    }

    suspend fun recoverConnection(
        maxAttempts: Int = MAX_RECOVERY_ATTEMPTS,
        attemptDelayMs: Long = 1000L
    ): AcRecoveryStatus = withContext(Dispatchers.IO) {
        var attempts = 0
        _recoveryStatus.update {
            it.copy(
                state = AcRecoveryState.DISCOVERING,
                attemptCount = 0,
                maxAttempts = maxAttempts
            )
        }

        while (attempts < maxAttempts) {
            attempts++
            _recoveryStatus.update { it.copy(attemptCount = attempts) }

            DiagnosticBus.log(
                tag = "ac-recovery",
                stage = DiagnosticStage.EXECUTING,
                message = "Recovery attempt $attempts/$maxAttempts: Checking Tuya Cloud status & local UDP discovery..."
            )

            // Step 1: Probe Cloud Status
            val cloudStatus = apiClient.fetchStatus(expectedDeviceId)
            if (cloudStatus.isSuccess && !cloudStatus.getOrNull().isNullOrEmpty()) {
                val items = cloudStatus.getOrNull()!!
                _recoveryStatus.update {
                    it.copy(
                        state = AcRecoveryState.VERIFYING,
                        cloudReachable = true
                    )
                }

                val verified = verifyRecovery(expectedDeviceId)
                if (verified) {
                    val recoveredStatus = _recoveryStatus.value.copy(
                        state = AcRecoveryState.RECOVERED,
                        deviceDiscovered = true,
                        cloudReachable = true,
                        sameDeviceIdVerified = true,
                        reason = "AC successfully reconnected to Wi-Fi and verified with Tuya Cloud.",
                        nextAction = "None. Recovery complete.",
                        lastSeenTimestamp = timeProvider(),
                        confidence = RecoveryConfidence.HIGH
                    )
                    _recoveryStatus.value = recoveredStatus
                    deviceRegistry.updateDeviceConnectionState(expectedDeviceId, DeviceConnectionState.Connected)
                    DiagnosticBus.log(
                        tag = "ac-recovery",
                        stage = DiagnosticStage.COMPLETED,
                        message = "AC recovery successful on attempt $attempts. DeviceRegistry synchronized to Connected."
                    )
                    return@withContext recoveredStatus
                }
            }

            // Step 2: If cloud not yet ready, attempt brief local discovery
            val discResult = discoveryService.listenForDevice(expectedDeviceId, 2000L)
            if (discResult.isSuccess) {
                val dev = discResult.getOrNull()!!
                _recoveryStatus.update {
                    it.copy(
                        deviceDiscovered = true,
                        currentIp = dev.ip,
                        sameDeviceIdVerified = dev.gwId.equals(expectedDeviceId, ignoreCase = true),
                        state = AcRecoveryState.WAITING_FOR_NETWORK
                    )
                }
            }

            if (attempts < maxAttempts) {
                kotlinx.coroutines.delay(attemptDelayMs)
            }
        }

        // Exhausted bounded attempts
        deviceRegistry.updateDeviceConnectionState(expectedDeviceId, DeviceConnectionState.Disconnected)
        val failedStatus = _recoveryStatus.value.copy(
            state = AcRecoveryState.FAILED,
            attemptCount = attempts,
            reason = "Recovery timed out after $maxAttempts attempts without verified cloud readback.",
            nextAction = "Manual intervention required: Use physical remote to power on AC or check router 2.4 GHz Wi-Fi beacon.",
            lastSeenTimestamp = timeProvider(),
            confidence = RecoveryConfidence.HIGH
        )
        _recoveryStatus.value = failedStatus

        DiagnosticBus.log(
            tag = "ac-recovery",
            stage = DiagnosticStage.FAILED,
            message = "AC recovery failed after $maxAttempts attempts. Marked FAILED / MANUAL_INTERVENTION_REQUIRED."
        )
        failedStatus
    }

    suspend fun verifyRecovery(
        deviceId: String = expectedDeviceId,
        maxVerificationPolls: Int = 3
    ): Boolean = withContext(Dispatchers.IO) {
        if (!deviceId.equals(expectedDeviceId, ignoreCase = true)) {
            Log.e(TAG, "[verify] Mismatched device ID: expected=$expectedDeviceId, got=$deviceId")
            return@withContext false
        }

        var pollsPassed = 0
        for (i in 0 until maxVerificationPolls) {
            val statusResult = apiClient.fetchStatus(deviceId)
            if (statusResult.isSuccess && !statusResult.getOrNull().isNullOrEmpty()) {
                val items = statusResult.getOrNull()!!
                adapter.applyTuyaStatus(items)
                pollsPassed++
            }
            if (i < maxVerificationPolls - 1) {
                kotlinx.coroutines.delay(500L)
            }
        }

        val allPassed = pollsPassed == maxVerificationPolls
        Log.i(TAG, "[verify] Verification polls passed: $pollsPassed/$maxVerificationPolls (Success=$allPassed)")
        allPassed
    }

    fun cancelRecovery(): AcRecoveryStatus {
        DiagnosticBus.log(
            tag = "ac-recovery",
            stage = DiagnosticStage.COMPLETED,
            message = "AC recovery manually cancelled by caller."
        )
        val cancelled = _recoveryStatus.value.copy(
            state = AcRecoveryState.IDLE,
            reason = "Recovery sequence was cancelled.",
            nextAction = "Idle."
        )
        _recoveryStatus.value = cancelled
        return cancelled
    }
}
