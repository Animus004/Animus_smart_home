package com.animus.smartroom.device.registry

import com.animus.smartroom.core.device.DeviceAdapter
import com.animus.smartroom.core.device.DeviceCommand
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

class CoreDeviceRegistry {

    companion object {
        private const val TAG = "CoreDeviceRegistry"
    }

    private val _devices = MutableStateFlow<Map<String, RoomDevice>>(emptyMap())
    val devices: StateFlow<Map<String, RoomDevice>> = _devices.asStateFlow()

    private val deviceAdapters = ConcurrentHashMap<String, DeviceAdapter>()
    private val typeAdapters = ConcurrentHashMap<DeviceType, DeviceAdapter>()

    fun registerDevice(device: RoomDevice) {
        _devices.update { current ->
            current + (device.id to device)
        }
    }

    fun registerDevices(newDevices: List<RoomDevice>) {
        if (newDevices.isEmpty()) return
        _devices.update { current ->
            val updated = current.toMutableMap()
            newDevices.forEach { dev ->
                updated[dev.id] = dev
            }
            updated
        }
    }

    fun unregisterDevice(deviceId: String) {
        _devices.update { current ->
            current - deviceId
        }
        deviceAdapters.remove(deviceId)
    }

    fun registerAdapterForDevice(deviceId: String, adapter: DeviceAdapter) {
        deviceAdapters[deviceId] = adapter
    }

    fun registerAdapterForType(type: DeviceType, adapter: DeviceAdapter) {
        typeAdapters[type] = adapter
    }

    fun getDevice(id: String): RoomDevice? = _devices.value[id]

    fun getDevicesByType(type: DeviceType): List<RoomDevice> =
        _devices.value.values.filter { it.type == type }

    fun getAdapterForDevice(device: RoomDevice): DeviceAdapter? =
        deviceAdapters[device.id] ?: typeAdapters[device.type]

    fun getAdapterForType(type: DeviceType): DeviceAdapter? =
        typeAdapters[type]

    fun updateDeviceState(device: RoomDevice) {
        _devices.update { current ->
            current + (device.id to device)
        }
    }

    fun findDeviceByQuery(query: String, explicitDeviceType: DeviceType? = null): DeviceLookupResult {
        val currentDevices = _devices.value.values.toList()
        val normalizedQuery = query.trim().lowercase(Locale.ROOT)
            .replace(Regex("""^(?:my|the)\s+"""), "")
            .trim()

        if (normalizedQuery.isBlank()) {
            return DeviceLookupResult.NotFound(query)
        }

        // 1. Direct ID match
        val byId = currentDevices.firstOrNull { it.id.equals(query.trim(), ignoreCase = true) }
        if (byId != null) return DeviceLookupResult.Match(byId)

        // 2. Exact Display Name match
        val byDisplayName = currentDevices.filter {
            it.displayName.equals(normalizedQuery, ignoreCase = true)
        }
        if (byDisplayName.size == 1) return DeviceLookupResult.Match(byDisplayName.first())
        if (byDisplayName.size > 1) {
            return DeviceLookupResult.Ambiguous(byDisplayName, "Multiple devices named '$query'. Which one?")
        }

        // 3. Exact Alias match
        val byAlias = currentDevices.filter { dev ->
            dev.aliases.any { alias -> alias.equals(normalizedQuery, ignoreCase = true) }
        }
        if (byAlias.size == 1) return DeviceLookupResult.Match(byAlias.first())
        if (byAlias.size > 1) {
            return DeviceLookupResult.Ambiguous(byAlias, "Which ${query.trim()} do you mean?")
        }

        // 4. Substring / Token match on Display Name
        val bySubstringName = currentDevices.filter { dev ->
            dev.displayName.lowercase(Locale.ROOT).contains(normalizedQuery)
        }
        if (bySubstringName.size == 1) return DeviceLookupResult.Match(bySubstringName.first())

        // 5. Semantic / Type Category Keywords
        val genericAcWords = setOf("ac", "air conditioner", "cooler", "aircon", "room ac")
        val isAcQuery = normalizedQuery in genericAcWords

        if (isAcQuery || explicitDeviceType == DeviceType.AIR_CONDITIONER) {
            val acs = currentDevices.filter { it.type == DeviceType.AIR_CONDITIONER }
            if (acs.size == 1) return DeviceLookupResult.Match(acs.first())
            if (acs.size > 1) {
                return DeviceLookupResult.Ambiguous(acs, "You have multiple ACs. Which one would you like to control?")
            }
        }

        val genericSpeakerWords = setOf("speaker", "speakers", "soundbar", "sound bar", "audio", "room audio")
        val isSpeakerQuery = normalizedQuery in genericSpeakerWords

        if (isSpeakerQuery || explicitDeviceType == DeviceType.BLUETOOTH_AUDIO) {
            val speakers = currentDevices.filter { it.type == DeviceType.BLUETOOTH_AUDIO }
            if (speakers.size == 1) return DeviceLookupResult.Match(speakers.first())
            if (speakers.size > 1) {
                return DeviceLookupResult.Ambiguous(speakers, "Which speaker would you like to use?")
            }
        }

        return DeviceLookupResult.NotFound(query)
    }

    suspend fun executeCommand(device: RoomDevice, command: DeviceCommand): DeviceCommandResult {
        val adapter = getAdapterForDevice(device)
            ?: return DeviceCommandResult(false, "No adapter registered for device ${device.displayName}")
        return adapter.execute(device, command)
    }
}
