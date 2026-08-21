package com.animus.smartroom.device.registry

import android.util.Log
import com.animus.smartroom.device.adapter.DeviceAdapter
import com.animus.smartroom.device.model.DeviceCapability
import com.animus.smartroom.device.model.DeviceCommandResult
import com.animus.smartroom.device.model.DeviceType
import com.animus.smartroom.device.model.RoomDevice
import com.animus.smartroom.diagnostics.DiagnosticBus
import com.animus.smartroom.diagnostics.DiagnosticStage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

class DeviceRegistry {

    companion object {
        private const val TAG = "DeviceRegistry"
    }

    private val _devices = MutableStateFlow<Map<String, RoomDevice>>(emptyMap())
    val devices: StateFlow<Map<String, RoomDevice>> = _devices.asStateFlow()

    private val deviceAdapters = ConcurrentHashMap<String, DeviceAdapter>()
    private val typeAdapters = ConcurrentHashMap<DeviceType, DeviceAdapter>()

    fun registerDevice(device: RoomDevice) {
        Log.i(TAG, "[register] Registering device: ${device.id} (${device.displayName}, Type=${device.type})")
        _devices.update { current ->
            current + (device.id to device)
        }
    }

    fun registerDevices(newDevices: List<RoomDevice>) {
        if (newDevices.isEmpty()) return
        Log.i(TAG, "[register] Registering batch of ${newDevices.size} devices")
        _devices.update { current ->
            val updated = current.toMutableMap()
            newDevices.forEach { dev ->
                updated[dev.id] = dev
            }
            updated
        }
    }

    fun unregisterDevice(deviceId: String) {
        Log.i(TAG, "[unregister] Unregistering device: $deviceId")
        _devices.update { current ->
            current - deviceId
        }
        deviceAdapters.remove(deviceId)
    }

    fun registerAdapterForDevice(deviceId: String, adapter: DeviceAdapter) {
        Log.i(TAG, "[adapter] Registering adapter for deviceId=$deviceId -> ${adapter::class.simpleName}")
        deviceAdapters[deviceId] = adapter
    }

    fun registerAdapterForType(type: DeviceType, adapter: DeviceAdapter) {
        Log.i(TAG, "[adapter] Registering adapter for type=$type -> ${adapter::class.simpleName}")
        typeAdapters[type] = adapter
    }

    fun getAdapterForDevice(device: RoomDevice): DeviceAdapter? {
        return deviceAdapters[device.id] ?: typeAdapters[device.type]
    }

    fun getAllDevices(): List<RoomDevice> {
        return _devices.value.values.toList()
    }

    fun getDevicesByType(type: DeviceType): List<RoomDevice> {
        return _devices.value.values.filter { it.type == type }
    }

    fun getDevice(id: String): RoomDevice? {
        return _devices.value[id]
    }

    fun findDeviceByNameOrAlias(query: String, preferredType: DeviceType? = null): DeviceLookupResult {
        val all = getAllDevices()
        if (all.isEmpty()) return DeviceLookupResult.NotFound(query)

        val normalized = query.trim().lowercase(Locale.ROOT)
            .replace(Regex("""^(?:my|the)\s+"""), "")
            .trim()

        if (normalized.isBlank()) return DeviceLookupResult.NotFound(query)

        // 1. Generic AC keywords
        val acKeywords = setOf("ac", "air conditioner", "air conditioning", "cooling", "cooler", "hvac", "room ac", "bedroom ac")
        if (normalized in acKeywords) {
            val acDevices = all.filter { it.type == DeviceType.AIR_CONDITIONER }
            return when {
                acDevices.isEmpty() -> DeviceLookupResult.NotFound(query)
                acDevices.size == 1 -> DeviceLookupResult.Match(acDevices.first())
                else -> DeviceLookupResult.Ambiguous(acDevices, "Which AC do you want to control?")
            }
        }

        // 2. Generic Speaker keywords
        val speakerKeywords = setOf("speaker", "speakers", "soundbar", "sound bar", "soundbars", "audio", "room audio", "bluetooth speaker")
        if (normalized in speakerKeywords) {
            val audioDevices = all.filter { it.type == DeviceType.BLUETOOTH_AUDIO }
            return when {
                audioDevices.isEmpty() -> DeviceLookupResult.NotFound(query)
                audioDevices.size == 1 -> DeviceLookupResult.Match(audioDevices.first())
                else -> DeviceLookupResult.Ambiguous(audioDevices, "Which speaker do you want to use?")
            }
        }

        // 3. Generic Light keywords
        val lightKeywords = setOf("light", "lights", "lamp", "room light", "bedroom light")
        if (normalized in lightKeywords) {
            val lightDevices = all.filter { it.type == DeviceType.LIGHT }
            return when {
                lightDevices.isEmpty() -> DeviceLookupResult.NotFound(query)
                lightDevices.size == 1 -> DeviceLookupResult.Match(lightDevices.first())
                else -> DeviceLookupResult.Ambiguous(lightDevices, "Which lights do you want to control?")
            }
        }

        // 4. Filter by preferred type if provided
        val searchPool = if (preferredType != null) all.filter { it.type == preferredType } else all

        // 5. Exact ID match
        val exactIdMatch = searchPool.firstOrNull { it.id.equals(normalized, ignoreCase = true) }
        if (exactIdMatch != null) return DeviceLookupResult.Match(exactIdMatch)

        // 6. Exact Alias match
        val exactAliasMatch = searchPool.firstOrNull { dev ->
            dev.aliases.any { it.trim().equals(normalized, ignoreCase = true) }
        }
        if (exactAliasMatch != null) return DeviceLookupResult.Match(exactAliasMatch)

        // 7. Exact Display Name match
        val exactNameMatch = searchPool.firstOrNull {
            it.displayName.trim().equals(normalized, ignoreCase = true)
        }
        if (exactNameMatch != null) return DeviceLookupResult.Match(exactNameMatch)

        // 8. Alias Substring match
        val aliasSubstringMatches = searchPool.filter { dev ->
            dev.aliases.any { alias ->
                val lowerAlias = alias.trim().lowercase(Locale.ROOT)
                lowerAlias.contains(normalized) || normalized.contains(lowerAlias)
            }
        }
        if (aliasSubstringMatches.size == 1) {
            return DeviceLookupResult.Match(aliasSubstringMatches.first())
        } else if (aliasSubstringMatches.size > 1) {
            val exactWord = aliasSubstringMatches.firstOrNull { dev ->
                dev.aliases.any { it.trim().equals(normalized, ignoreCase = true) }
            }
            if (exactWord != null) return DeviceLookupResult.Match(exactWord)
            return DeviceLookupResult.Ambiguous(aliasSubstringMatches, "Which '$query' device do you mean?")
        }

        // 9. Display Name Substring match
        val nameSubstringMatches = searchPool.filter { dev ->
            val lowerName = dev.displayName.trim().lowercase(Locale.ROOT)
            lowerName.contains(normalized) || normalized.contains(lowerName)
        }
        if (nameSubstringMatches.size == 1) {
            return DeviceLookupResult.Match(nameSubstringMatches.first())
        } else if (nameSubstringMatches.size > 1) {
            val exactWord = nameSubstringMatches.firstOrNull {
                it.displayName.trim().equals(normalized, ignoreCase = true)
            }
            if (exactWord != null) return DeviceLookupResult.Match(exactWord)
            return DeviceLookupResult.Ambiguous(nameSubstringMatches, "Which '$query' device do you mean?")
        }

        return DeviceLookupResult.NotFound(query)
    }

    suspend fun executeCapability(
        targetQuery: String,
        capability: DeviceCapability,
        value: Any?
    ): DeviceCommandResult {
        DiagnosticBus.log(
            tag = "device-registry",
            stage = DiagnosticStage.REQUESTED,
            message = "Target='$targetQuery', Capability=${capability.name}, Value='$value'"
        )

        val lookup = findDeviceByNameOrAlias(targetQuery)
        return when (lookup) {
            is DeviceLookupResult.Match -> {
                val device = lookup.device
                DiagnosticBus.log(
                    tag = "device-registry",
                    stage = DiagnosticStage.RESOLVING,
                    message = "Resolved device '${device.displayName}' (Type=${device.type})"
                )

                if (!device.supportsCapability(capability)) {
                    val msg = "${device.displayName} does not support capability ${capability.name}."
                    DiagnosticBus.log(
                        tag = "device-registry",
                        stage = DiagnosticStage.FAILED,
                        message = msg
                    )
                    return DeviceCommandResult(
                        success = false,
                        message = msg
                    )
                }

                val adapter = getAdapterForDevice(device)
                if (adapter == null) {
                    val msg = "No adapter registered for ${device.displayName} (Type=${device.type})."
                    DiagnosticBus.log(
                        tag = "device-registry",
                        stage = DiagnosticStage.FAILED,
                        message = msg
                    )
                    return DeviceCommandResult(
                        success = false,
                        message = msg
                    )
                }

                DiagnosticBus.log(
                    tag = "device-registry",
                    stage = DiagnosticStage.EXECUTING,
                    message = "Dispatching ${capability.name}=$value to adapter ${adapter::class.simpleName}"
                )

                val result = adapter.executeCapability(device, capability, value)
                if (result.success) {
                    DiagnosticBus.log(
                        tag = "device-registry",
                        stage = DiagnosticStage.COMPLETED,
                        message = "Capability ${capability.name} executed successfully: ${result.message}"
                    )
                } else {
                    DiagnosticBus.log(
                        tag = "device-registry",
                        stage = DiagnosticStage.FAILED,
                        message = "Capability ${capability.name} execution failed: ${result.message}"
                    )
                }
                result
            }
            is DeviceLookupResult.Ambiguous -> {
                DiagnosticBus.log(
                    tag = "device-registry",
                    stage = DiagnosticStage.FAILED,
                    message = "Ambiguous target query: '$targetQuery' -> ${lookup.question}"
                )
                DeviceCommandResult(
                    success = false,
                    message = lookup.question
                )
            }
            is DeviceLookupResult.NotFound -> {
                val msg = "Device '$targetQuery' not found in registered devices."
                DiagnosticBus.log(
                    tag = "device-registry",
                    stage = DiagnosticStage.FAILED,
                    message = msg
                )
                DeviceCommandResult(
                    success = false,
                    message = msg
                )
            }
        }
    }
}
