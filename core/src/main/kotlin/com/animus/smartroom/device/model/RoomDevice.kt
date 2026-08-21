package com.animus.smartroom.device.model

/**
 * Pure state/data model representing a physical or logical device in the room.
 * Runtime adapters are resolved separately via DeviceRegistry.
 */
data class RoomDevice(
    val id: String,
    val displayName: String,
    val type: DeviceType,
    val connectionState: DeviceConnectionState = DeviceConnectionState.Available,
    val supportedCapabilities: Set<DeviceCapability> = emptySet(),
    val aliases: List<String> = emptyList()
) {
    fun supportsCapability(capability: DeviceCapability): Boolean {
        return supportedCapabilities.contains(capability)
    }
}
