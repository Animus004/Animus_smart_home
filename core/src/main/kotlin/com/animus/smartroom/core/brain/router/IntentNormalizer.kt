package com.animus.smartroom.core.brain.router

import java.util.Locale

/**
 * Normalizes linguistic variations into canonical targets, actions, and parameters.
 */
object IntentNormalizer {

    fun normalizeTarget(rawTarget: String?): CapabilityRegistry.DeviceTarget? {
        return CapabilityRegistry.DeviceTarget.fromString(rawTarget)
    }

    fun normalizeAction(target: CapabilityRegistry.DeviceTarget, rawAction: String?): CapabilityRegistry.ActionCapability? {
        if (rawAction == null) return null
        val cleaned = rawAction.trim().uppercase(Locale.ROOT)
            .replace(Regex("^(TURN_|SET_|SWITCH_|CHANGE_)"), "")
            .replace(Regex("^(POWER_)"), "")

        return when (target) {
            CapabilityRegistry.DeviceTarget.AC -> when (cleaned) {
                "ON", "POWER_ON", "START" -> CapabilityRegistry.ActionCapability.AC_POWER_ON
                "OFF", "POWER_OFF", "STOP", "SHUTDOWN" -> CapabilityRegistry.ActionCapability.AC_POWER_OFF
                "TEMPERATURE", "SET_TEMPERATURE", "TEMP" -> CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE
                "MODE", "SET_MODE", "COOL", "HEAT", "FAN" -> CapabilityRegistry.ActionCapability.AC_SET_MODE
                "FAN_SPEED", "SPEED", "BLOWER" -> CapabilityRegistry.ActionCapability.AC_SET_FAN_SPEED
                "STATE", "STATUS", "GET_STATE" -> CapabilityRegistry.ActionCapability.AC_GET_STATE
                else -> CapabilityRegistry.ActionCapability.fromString(target, rawAction)
            }
            CapabilityRegistry.DeviceTarget.PROJECTOR -> when (cleaned) {
                "ON", "POWER_ON", "START", "WAKE" -> CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON
                "OFF", "POWER_OFF", "STOP", "SHUTDOWN" -> CapabilityRegistry.ActionCapability.PROJECTOR_POWER_OFF
                "INPUT", "SOURCE", "HDMI", "HDMI_1", "HDMI_2", "SET_INPUT" -> CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT
                "STATE", "STATUS", "GET_STATE" -> CapabilityRegistry.ActionCapability.PROJECTOR_GET_STATE
                else -> CapabilityRegistry.ActionCapability.fromString(target, rawAction)
            }
            CapabilityRegistry.DeviceTarget.FIRE_TV -> when (cleaned) {
                "WAKE", "ON", "START", "POWER_ON" -> CapabilityRegistry.ActionCapability.FIRE_TV_WAKE
                "HOME", "MENU" -> CapabilityRegistry.ActionCapability.FIRE_TV_HOME
                "BACK", "RETURN" -> CapabilityRegistry.ActionCapability.FIRE_TV_BACK
                "NAVIGATE", "UP", "DOWN", "LEFT", "RIGHT", "SELECT", "OK" -> CapabilityRegistry.ActionCapability.FIRE_TV_NAVIGATE
                "LAUNCH", "LAUNCH_APP", "OPEN", "OPEN_APP" -> CapabilityRegistry.ActionCapability.FIRE_TV_LAUNCH_APP
                "STATE", "STATUS", "GET_STATE" -> CapabilityRegistry.ActionCapability.FIRE_TV_GET_STATE
                else -> CapabilityRegistry.ActionCapability.fromString(target, rawAction)
            }
            CapabilityRegistry.DeviceTarget.AUDIO -> when (cleaned) {
                "CONNECT", "CONNECT_LG", "ON", "PAIR" -> CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG
                "DISCONNECT", "DISCONNECT_LG", "OFF", "UNPAIR" -> CapabilityRegistry.ActionCapability.AUDIO_DISCONNECT_LG
                "STATE", "STATUS", "GET_STATE" -> CapabilityRegistry.ActionCapability.AUDIO_GET_STATE
                else -> CapabilityRegistry.ActionCapability.fromString(target, rawAction)
            }
            CapabilityRegistry.DeviceTarget.MEDIA -> when (cleaned) {
                "PLAY", "START", "RESUME" -> CapabilityRegistry.ActionCapability.MEDIA_PLAY
                "PAUSE" -> CapabilityRegistry.ActionCapability.MEDIA_PAUSE
                "STOP" -> CapabilityRegistry.ActionCapability.MEDIA_STOP
                "NEXT", "SKIP" -> CapabilityRegistry.ActionCapability.MEDIA_NEXT
                "PREVIOUS", "PREV" -> CapabilityRegistry.ActionCapability.MEDIA_PREVIOUS
                "VOLUME", "SET_VOLUME" -> CapabilityRegistry.ActionCapability.MEDIA_SET_VOLUME
                else -> CapabilityRegistry.ActionCapability.fromString(target, rawAction)
            }
            CapabilityRegistry.DeviceTarget.ROUTINES -> when (cleaned) {
                "MOVIE", "MOVIE_MODE", "CINEMA", "CINEMA_MODE", "WATCH_MOVIE" -> CapabilityRegistry.ActionCapability.ROUTINE_MOVIE_MODE
                "MUSIC", "MUSIC_MODE", "LISTEN_MUSIC" -> CapabilityRegistry.ActionCapability.ROUTINE_MUSIC_MODE
                "WORK", "WORK_MODE", "FOCUS", "STUDY" -> CapabilityRegistry.ActionCapability.ROUTINE_WORK_MODE
                "SLEEP", "GOODNIGHT", "BEDTIME", "GOODNIGHT_MODE", "SHUTDOWN_ALL", "ALL_OFF" -> CapabilityRegistry.ActionCapability.ROUTINE_GOODNIGHT_MODE
                else -> CapabilityRegistry.ActionCapability.fromString(target, rawAction)
            }
        }
    }
}
