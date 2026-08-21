package com.animus.smartroom.device.registry

import com.animus.smartroom.device.model.RoomDevice

sealed interface DeviceLookupResult {
    data class Match(val device: RoomDevice) : DeviceLookupResult
    data class Ambiguous(val candidates: List<RoomDevice>, val question: String) : DeviceLookupResult
    data class NotFound(val searchedQuery: String) : DeviceLookupResult
}
