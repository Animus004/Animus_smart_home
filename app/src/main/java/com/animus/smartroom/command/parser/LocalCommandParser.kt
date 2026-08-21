package com.animus.smartroom.command.parser

import com.animus.smartroom.command.model.AnimusCommand
import java.util.Locale
import java.util.regex.Pattern

class LocalCommandParser : CommandParser {

    companion object {
        private val VOLUME_PERCENT_REGEX = Pattern.compile(
            """(?:set\s+)?(?:the\s+)?volume\s+(?:to\s+|up\s+to\s+|down\s+to\s+)?(\d{1,3})(?:\s*(?:%|percent|percentage))?""",
            Pattern.CASE_INSENSITIVE
        )

        private val VOLUME_ONLY_DIGIT_REGEX = Pattern.compile(
            """^volume\s+(\d{1,3})$""",
            Pattern.CASE_INSENSITIVE
        )

        private val SWITCH_DEVICE_REGEX = Pattern.compile(
            """^(?:switch|change)(?:\s+(?:the|audio|bluetooth)?\s*device)?(?:\s+to)?(?:\s+(?:my|the))?\s+(.+)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val CONNECT_DEVICE_REGEX = Pattern.compile(
            """^connect(?:\s+(?:to|bluetooth(?:\s+to)?))?(?:\s+(?:my|the))?\s*(.*)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val PLAY_SONG_BY_ARTIST_REGEX = Pattern.compile(
            """^play(?:\s+(?:song|track|the\s+song|the\s+track))?\s+(.+?)\s+by\s+(.+)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val PLAY_SONG_REGEX = Pattern.compile(
            """^play(?:\s+(?:song|track|the\s+song|the\s+track))?\s+(.+)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_TEMP_REGEX = Pattern.compile(
            """^(?:(?:set|change|make)\s+)?(?:the\s+)?(?:ac|air\s+conditioner)\s+(?:temperature\s+|temp\s+)?(?:to\s+)?(\d{2})(?:\s*(?:degrees|degree|°c|°|c|deg))?$""",
            Pattern.CASE_INSENSITIVE
        )

        private val TEMP_ONLY_REGEX = Pattern.compile(
            """^(?:(?:set|change)\s+)?(?:the\s+)?(?:temperature|temp)\s+(?:to\s+)?(\d{2})(?:\s*(?:degrees|degree|°c|°|c|deg))?$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_MODE_REGEX = Pattern.compile(
            """^(?:(?:set|change)\s+)?(?:the\s+)?(?:ac|air\s+conditioner)\s+(?:mode\s+)?(?:to\s+)?(cool|heat|fan|auto|dry)(?:\s+mode)?$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_FAN_SPEED_REGEX = Pattern.compile(
            """^(?:(?:set|change)\s+)?(?:the\s+)?(?:ac|air\s+conditioner)\s+(?:fan(?:\s+speed)?)\s+(?:to\s+)?(low|medium|high|auto)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_SWING_REGEX = Pattern.compile(
            """^(?:(?:set|change|turn)\s+)?(?:the\s+)?(?:ac|air\s+conditioner)\s+(?:swing)\s+(?:to\s+)?(on|off|vertical|horizontal|both)$""",
            Pattern.CASE_INSENSITIVE
        )
    }

    override fun parse(input: String): AnimusCommand {
        val trimmed = input.trim().replace(Regex("""[.!?,;]+$"""), "").trim()
        if (trimmed.isBlank()) {
            return AnimusCommand.UnknownCommand(input)
        }

        val normalized = trimmed.lowercase(Locale.ROOT)

        // 1. Pause commands
        if (normalized in setOf(
                "pause",
                "pause music",
                "pause the music",
                "pause song",
                "pause the song",
                "pause playback",
                "stop",
                "stop music",
                "stop the music",
                "stop playback"
            )
        ) {
            return AnimusCommand.PauseMusic
        }

        // 2. Resume / Play current commands
        if (normalized in setOf(
                "resume",
                "resume music",
                "resume playback",
                "continue",
                "continue playing",
                "unpause",
                "play",
                "play music",
                "play the music"
            )
        ) {
            return AnimusCommand.ResumeMusic
        }

        // 3. Next track commands
        if (normalized in setOf(
                "next",
                "next song",
                "next track",
                "skip",
                "skip song",
                "skip track",
                "play next"
            )
        ) {
            return AnimusCommand.NextTrack
        }

        // 4. Previous track commands
        if (normalized in setOf(
                "previous",
                "previous song",
                "previous track",
                "prev",
                "prev song",
                "prev track",
                "back",
                "go back",
                "play previous"
            )
        ) {
            return AnimusCommand.PreviousTrack
        }

        // 5. Disconnect commands
        if (normalized in setOf(
                "disconnect",
                "disconnect bluetooth",
                "disconnect device",
                "disconnect speaker",
                "disconnect from speaker",
                "disconnect soundbar"
            )
        ) {
            return AnimusCommand.DisconnectBluetoothDevice
        }

        // 6. AC Power Commands
        if (normalized in setOf(
                "turn on ac",
                "turn on the ac",
                "turn the ac on",
                "turn on air conditioner",
                "turn on the air conditioner",
                "power on ac",
                "start ac",
                "start the ac",
                "ac on"
            )
        ) {
            return AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = com.animus.smartroom.device.model.DeviceCapability.Power,
                value = true
            )
        }

        if (normalized in setOf(
                "turn off ac",
                "turn off the ac",
                "turn the ac off",
                "turn off air conditioner",
                "turn off the air conditioner",
                "power off ac",
                "stop ac",
                "stop the ac",
                "shut off ac",
                "ac off"
            )
        ) {
            return AnimusCommand.SetDeviceCapability(
                target = "AC",
                capability = com.animus.smartroom.device.model.DeviceCapability.Power,
                value = false
            )
        }

        // 7. AC Temperature Commands
        val acTempMatcher = AC_TEMP_REGEX.matcher(trimmed)
        if (acTempMatcher.find()) {
            val temp = acTempMatcher.group(1)?.toIntOrNull()
            if (temp != null) {
                return AnimusCommand.SetDeviceCapability(
                    target = "AC",
                    capability = com.animus.smartroom.device.model.DeviceCapability.Temperature,
                    value = temp
                )
            }
        }

        val tempOnlyMatcher = TEMP_ONLY_REGEX.matcher(trimmed)
        if (tempOnlyMatcher.find()) {
            val temp = tempOnlyMatcher.group(1)?.toIntOrNull()
            if (temp != null) {
                return AnimusCommand.SetDeviceCapability(
                    target = "AC",
                    capability = com.animus.smartroom.device.model.DeviceCapability.Temperature,
                    value = temp
                )
            }
        }

        // 8. AC Mode Commands
        val acModeMatcher = AC_MODE_REGEX.matcher(trimmed)
        if (acModeMatcher.find()) {
            val modeStr = acModeMatcher.group(1)?.trim()?.uppercase(Locale.ROOT)
            if (modeStr != null) {
                return AnimusCommand.SetDeviceCapability(
                    target = "AC",
                    capability = com.animus.smartroom.device.model.DeviceCapability.HvacMode,
                    value = modeStr
                )
            }
        }

        // 9. AC Fan Speed Commands
        val acFanMatcher = AC_FAN_SPEED_REGEX.matcher(trimmed)
        if (acFanMatcher.find()) {
            val fanStr = acFanMatcher.group(1)?.trim()?.uppercase(Locale.ROOT)
            if (fanStr != null) {
                return AnimusCommand.SetDeviceCapability(
                    target = "AC",
                    capability = com.animus.smartroom.device.model.DeviceCapability.FanSpeed,
                    value = fanStr
                )
            }
        }

        // 10. AC Swing Commands
        val acSwingMatcher = AC_SWING_REGEX.matcher(trimmed)
        if (acSwingMatcher.find()) {
            val swingStr = acSwingMatcher.group(1)?.trim()?.uppercase(Locale.ROOT)
            if (swingStr != null) {
                return AnimusCommand.SetDeviceCapability(
                    target = "AC",
                    capability = com.animus.smartroom.device.model.DeviceCapability.Swing,
                    value = swingStr
                )
            }
        }

        // 11. Volume commands
        val volumeOnlyMatcher = VOLUME_ONLY_DIGIT_REGEX.matcher(trimmed)
        if (volumeOnlyMatcher.find()) {
            val percent = volumeOnlyMatcher.group(1)?.toIntOrNull()
            if (percent != null && percent in 0..100) {
                return AnimusCommand.SetVolume(percent)
            }
        }

        val volumeMatcher = VOLUME_PERCENT_REGEX.matcher(trimmed)
        if (volumeMatcher.find()) {
            val percent = volumeMatcher.group(1)?.toIntOrNull()
            if (percent != null && percent in 0..100) {
                return AnimusCommand.SetVolume(percent)
            }
        }

        // 7. Switch device commands
        val switchMatcher = SWITCH_DEVICE_REGEX.matcher(trimmed)
        if (switchMatcher.find()) {
            var targetDevice = switchMatcher.group(1)?.trim()
            if (!targetDevice.isNullOrBlank()) {
                targetDevice = targetDevice.replace(Regex("""^(?:my|the)\s+""", RegexOption.IGNORE_CASE), "").trim()
                if (targetDevice.isNotBlank()) {
                    return AnimusCommand.SwitchBluetoothDevice(targetDevice)
                }
            }
        }

        // 8. Connect device commands
        val connectMatcher = CONNECT_DEVICE_REGEX.matcher(trimmed)
        if (connectMatcher.find()) {
            val targetDevice = connectMatcher.group(1)?.trim()
            return if (targetDevice.isNullOrBlank() || targetDevice.lowercase(Locale.ROOT) in setOf("bluetooth", "device", "speaker", "audio")) {
                AnimusCommand.ConnectBluetoothDevice(null)
            } else {
                AnimusCommand.ConnectBluetoothDevice(targetDevice)
            }
        }

        // 9. Play with Artist: "play {title} by {artist}"
        val playByMatcher = PLAY_SONG_BY_ARTIST_REGEX.matcher(trimmed)
        if (playByMatcher.find()) {
            val title = playByMatcher.group(1)?.trim()
            val artist = playByMatcher.group(2)?.trim()
            if (!title.isNullOrBlank()) {
                return AnimusCommand.PlayMusic(title = title, artist = if (artist.isNullOrBlank()) null else artist)
            }
        }

        // 10. Play Song Title: "play {title}"
        val playMatcher = PLAY_SONG_REGEX.matcher(trimmed)
        if (playMatcher.find()) {
            val title = playMatcher.group(1)?.trim()
            if (!title.isNullOrBlank() && title.lowercase(Locale.ROOT) !in setOf("music", "the music", "song", "the song")) {
                return AnimusCommand.PlayMusic(title = title, artist = null)
            }
        }

        return AnimusCommand.UnknownCommand(input)
    }
}
