package com.animus.smartroom.context.model

import org.json.JSONObject

private fun JSONObject?.extractString(key: String, default: String = "UNKNOWN"): String {
    if (this == null) return default
    val fieldObj = optJSONObject(key)
    if (fieldObj != null) {
        val v = fieldObj.opt("value")
        return if (v == null || v == JSONObject.NULL) default else v.toString()
    }
    val v = opt(key)
    return if (v == null || v == JSONObject.NULL) default else v.toString()
}

private fun JSONObject?.extractBoolean(key: String, default: Boolean = false): Boolean {
    if (this == null) return default
    val fieldObj = optJSONObject(key)
    if (fieldObj != null) {
        val v = fieldObj.opt("value")
        return when (v) {
            is Boolean -> v
            is String -> v.equals("true", ignoreCase = true) || v.equals("on", ignoreCase = true) || v.equals("awake", ignoreCase = true)
            else -> default
        }
    }
    val v = opt(key)
    return when (v) {
        is Boolean -> v
        is String -> v.equals("true", ignoreCase = true) || v.equals("on", ignoreCase = true) || v.equals("awake", ignoreCase = true)
        else -> default
    }
}

private fun JSONObject?.extractInt(key: String, default: Int = 0): Int {
    if (this == null) return default
    val fieldObj = optJSONObject(key)
    if (fieldObj != null) {
        val v = fieldObj.opt("value")
        return when (v) {
            is Number -> v.toInt()
            is String -> v.toIntOrNull() ?: default
            else -> default
        }
    }
    val v = opt(key)
    return when (v) {
        is Number -> v.toInt()
        is String -> v.toIntOrNull() ?: default
        else -> default
    }
}

data class ProjectorStateDto(
    val powerState: String = "UNKNOWN",
    val inputSource: String = "UNKNOWN",
    val brightness: Int = 50,
    val hasSignal: Boolean = false,
    val isConnected: Boolean = false,
    val contentTitle: String? = null
) {
    val isPowerOn: Boolean get() = powerState.equals("ON", ignoreCase = true) || powerState.equals("AWAKE", ignoreCase = true)

    companion object {
        fun fromJson(json: JSONObject?): ProjectorStateDto {
            if (json == null) return ProjectorStateDto()
            val rawPower = json.extractString("power_state", "")
            val powerBool = json.extractBoolean("power", false)
            val effectivePower = when {
                rawPower.isNotBlank() && rawPower != "UNKNOWN" -> rawPower
                powerBool -> "ON"
                else -> "OFF"
            }

            return ProjectorStateDto(
                powerState = effectivePower,
                inputSource = json.extractString("input_source", "UNKNOWN"),
                brightness = json.extractInt("brightness", 50),
                hasSignal = json.extractBoolean("signal_active", json.extractBoolean("has_signal", false)),
                isConnected = json.extractBoolean("online", json.extractBoolean("is_connected", true)),
                contentTitle = json.extractString("content_title", "")
            )
        }
    }
}

data class AcStateDto(
    val power: Boolean = false,
    val targetTemperature: Int = 24,
    val ambientTemperature: Int = 24,
    val hvacMode: String = "COOL",
    val fanSpeed: String = "AUTO",
    val isOnline: Boolean = false
) {
    companion object {
        fun fromJson(json: JSONObject?): AcStateDto {
            if (json == null) return AcStateDto()
            return AcStateDto(
                power = json.extractBoolean("power", false),
                targetTemperature = json.extractInt("target_temperature", 24),
                ambientTemperature = json.extractInt("ambient_temperature", 24),
                hvacMode = json.extractString("mode", json.extractString("hvac_mode", "COOL")),
                fanSpeed = json.extractString("fan_speed", "AUTO"),
                isOnline = json.extractBoolean("online", json.extractBoolean("is_online", true))
            )
        }
    }
}

data class FireTvStateDto(
    val powerState: String = "UNKNOWN",
    val currentApp: String = "UNKNOWN",
    val playbackState: String = "IDLE",
    val soundbarConnected: Boolean = false,
    val isOnline: Boolean = false
) {
    val isPowerOn: Boolean get() = powerState.equals("ON", ignoreCase = true) || powerState.equals("AWAKE", ignoreCase = true)

    companion object {
        fun fromJson(json: JSONObject?): FireTvStateDto {
            if (json == null) return FireTvStateDto()
            val rawApp = json.extractString("current_app", "")
            val contentTitle = json.extractString("content_title", "")
            val fgApp = json.extractString("foreground_app", "")
            val effectiveApp = when {
                rawApp.isNotBlank() && rawApp != "UNKNOWN" -> rawApp
                contentTitle.isNotBlank() && contentTitle != "UNKNOWN" -> contentTitle
                fgApp.isNotBlank() && fgApp != "UNKNOWN" -> fgApp
                else -> "UNKNOWN"
            }

            return FireTvStateDto(
                powerState = json.extractString("power_state", "UNKNOWN"),
                currentApp = effectiveApp,
                playbackState = json.extractString("playback_state", "IDLE"),
                soundbarConnected = json.extractBoolean("soundbar_connected", false),
                isOnline = json.extractBoolean("online", json.extractBoolean("is_online", false))
            )
        }
    }
}

data class PcStateDto(
    val isOnline: Boolean = false,
    val volume: Int = 50,
    val isMuted: Boolean = false,
    val activeEndpoint: String = "UNKNOWN",
    val soundbarConnected: Boolean = false
) {
    companion object {
        fun fromJson(json: JSONObject?): PcStateDto {
            if (json == null) return PcStateDto()
            val vol = json.extractInt("master_volume", json.extractInt("volume", 50))
            val ep = json.extractString("default_audio_endpoint", json.extractString("active_endpoint", "UNKNOWN"))

            return PcStateDto(
                isOnline = json.extractBoolean("online", json.extractBoolean("is_online", false)),
                volume = vol,
                isMuted = json.extractBoolean("is_muted", false),
                activeEndpoint = ep,
                soundbarConnected = json.extractBoolean("soundbar_connected", false)
            )
        }
    }
}

data class SoundbarStateDto(
    val isConnected: Boolean = false,
    val connectedDevice: String = "DISCONNECTED",
    val powerState: String = "UNKNOWN"
) {
    companion object {
        fun fromJson(json: JSONObject?): SoundbarStateDto {
            if (json == null) return SoundbarStateDto()
            val owner = json.extractString("current_owner", json.extractString("connected_device", "DISCONNECTED"))
            return SoundbarStateDto(
                isConnected = json.extractBoolean("is_connected", false),
                connectedDevice = owner,
                powerState = json.extractString("power_state", "UNKNOWN")
            )
        }
    }
}

data class RoomEnvironmentStateDto(
    val mode: String = "IDLE",
    val activeAudioRoute: String = "UNKNOWN"
) {
    companion object {
        fun fromJson(json: JSONObject?): RoomEnvironmentStateDto {
            if (json == null) return RoomEnvironmentStateDto()
            return RoomEnvironmentStateDto(
                mode = json.extractString("mode", json.extractString("room_mode", "IDLE")),
                activeAudioRoute = json.extractString("active_audio_route", "UNKNOWN")
            )
        }
    }
}

data class RoomStateDto(
    val timestamp: Double = 0.0,
    val isConsistent: Boolean = true,
    val projector: ProjectorStateDto = ProjectorStateDto(),
    val ac: AcStateDto = AcStateDto(),
    val fireTv: FireTvStateDto = FireTvStateDto(),
    val pc: PcStateDto = PcStateDto(),
    val soundbar: SoundbarStateDto = SoundbarStateDto(),
    val environment: RoomEnvironmentStateDto = RoomEnvironmentStateDto()
) {
    companion object {
        fun fromJson(json: JSONObject): RoomStateDto {
            return RoomStateDto(
                timestamp = json.optDouble("timestamp", 0.0),
                isConsistent = json.optBoolean("is_consistent", true),
                projector = ProjectorStateDto.fromJson(json.optJSONObject("projector")),
                ac = AcStateDto.fromJson(json.optJSONObject("ac")),
                fireTv = FireTvStateDto.fromJson(json.optJSONObject("fire_tv")),
                pc = PcStateDto.fromJson(json.optJSONObject("pc")),
                soundbar = SoundbarStateDto.fromJson(json.optJSONObject("soundbar")),
                environment = RoomEnvironmentStateDto.fromJson(json.optJSONObject("environment"))
            )
        }
    }
}
