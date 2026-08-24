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

        private val SLEEP_DURATION_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:(?:i\s+(?:want|need)\s+to\s+)?(?:sleep|nap|rest)(?:\s+for\s+)?|\s*)(\d+)\s*(?:minutes?|mins?|hours?|hrs?)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val SLEEP_HOUR_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:(?:i\s+(?:want|need)\s+to\s+)?(?:sleep|nap|rest)(?:\s+for\s+)?|\s*)(?:an?|1)\s+hour$""",
            Pattern.CASE_INSENSITIVE
        )

        private val SLEEP_WAKE_TIME_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:wake\s+me\s+up\s+at|sleep\s+until)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val CANCEL_SLEEP_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:cancel\s+(?:my\s+)?(?:sleep(?:\s+timer|\s+mode)?|timer)|don't\s+wake\s+me(?:\s+up)?|stop\s+sleep(?:\s+mode)?)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val UNPARAMETERIZED_SLEEP_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:i\s+(?:am|'m)\s+tired(?:\s+and\s+(?:want|need)\s+to\s+sleep)?|i\s+(?:want|need)\s+to\s+sleep|sleep|nap|time\s+to\s+sleep)$""",
            Pattern.CASE_INSENSITIVE
        )

        // Scheduled Device Action Regexes
        private val AC_TIMER_DELAY_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:turn|switch|set)?\s*(?:the\s+)?ac\s+(?:to\s+)?(on|off)\s+(?:after|in)\s+(\d+)\s*(minutes?|mins?|hours?|hrs?)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_TIMER_HOUR_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:turn|switch|set)?\s*(?:the\s+)?ac\s+(?:to\s+)?(on|off)\s+(?:after|in)\s+(?:an?|1)\s+hour$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_TIMER_AT_TIME_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:turn|switch|set)?\s*(?:the\s+)?ac\s+(?:to\s+)?(on|off)\s+(?:at|tomorrow\s+at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AC_TIMER_RECURRING_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:turn|switch|set)?\s*(?:the\s+)?ac\s+(?:to\s+)?(on|off)\s+every\s+(?:night|day|morning)?\s*(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val CANCEL_AC_TIMER_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:cancel|stop|delete)\s+(?:my\s+)?(?:ac\s+(?:timer|schedule)|timer)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val QUERY_AC_TIMER_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:how\s+much\s+time\s+(?:is\s+)?left\s+(?:on\s+(?:the|my)\s+ac\s+timer|on\s+ac\s+timer|on\s+timer)|when\s+is\s+(?:my|the)\s+ac\s+turning\s+off|check\s+ac\s+timer|ac\s+timer\s+status)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val WATCH_CONTENT_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?(?:(?:i\s+(?:want|would\s+like)\s+to\s+)?watch|let's\s+watch)\s+(?:the\s+movie\s+|movie\s+|the\s+film\s+|film\s+|the\s+)?(.+)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val PLAY_MOVIE_REGEX = Pattern.compile(
            """^(?:buddy,?\s+)?play\s+(?:the\s+movie\s+|movie\s+|the\s+film\s+|film\s+)(.+)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val PROJECTOR_SOURCE_REGEX = Pattern.compile(
            """^(?:(?:switch|set|change)\s+)?(?:the\s+)?projector\s+(?:source\s+|input\s+)?(?:to\s+)?(hdmi\s*[123]|android|usb|av|vga)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val SWITCH_TO_HDMI_REGEX = Pattern.compile(
            """^(?:switch|set|change)\s+(?:(?:the\s+)?(?:source|input)\s+)?(?:to\s+)?(hdmi\s*[123])$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AUDIO_OWNERSHIP_PC_REGEX = Pattern.compile(
            """^(?:(?:buddy|hey animus|animus|please|i\s+(?:want|inqant)(?:\s+you)?\s+to|can\s+you|could\s+you)\s+)?(?:(?:switch|connect|transfer|route|give)\s+(?:to\s+)?(?:the\s+)?(?:lg\s+)?(?:audio|soundbar|speaker|bluetooth)(?:\s+back)?\s+(?:to|from|form|with)\s+(?:my\s+|the\s+)?(?:computer|pc)|connect\s+(?:to\s+)?(?:the\s+)?(?:lg\s+)?(?:speaker|soundbar)\s+(?:from|form|with|to)\s+(?:my\s+|the\s+)?(?:computer|pc)|connect\s+(?:my\s+|the\s+)?(?:computer|pc)\s+to\s+(?:the\s+)?(?:lg\s+)?(?:speaker|soundbar|bluetooth)|connect\s+(?:with\s+)?bluetooth\s+(?:from|form)\s+(?:my\s+|the\s+)?(?:computer|pc)|give\s+(?:the\s+)?(?:speaker|soundbar|audio)\s+back)$""",
            Pattern.CASE_INSENSITIVE
        )

        private val AUDIO_OWNERSHIP_FIRETV_REGEX = Pattern.compile(
            """^(?:(?:buddy|hey animus|animus|please|i\s+(?:want|inqant)(?:\s+you)?\s+to|can\s+you|could\s+you)\s+)?(?:(?:switch|connect|transfer|route|give)\s+(?:to\s+)?(?:the\s+)?(?:audio|soundbar|speaker|bluetooth)\s+to\s+(?:the\s+|my\s+)?(?:fire\s*tv|tv|television|stick)|switch\s+to\s+(?:the\s+|my\s+)?(?:fire\s*tv|tv|television|stick))$""",
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

        // 5.5 Movie Mode & Content Watch Commands
        if (normalized in setOf(
                "start movie mode",
                "turn on movie mode",
                "start a movie",
                "movie mode on",
                "enable movie mode",
                "start movie",
                "movie mode",
                "cinema mode"
            )
        ) {
            return AnimusCommand.StartMovieMode()
        }

        if (normalized in setOf(
                "turn movie mode off",
                "stop movie mode",
                "turn off movie mode",
                "movie mode off",
                "disable movie mode",
                "stop movie",
                "exit movie mode",
                "cancel movie mode",
                "i'm done watching",
                "im done watching",
                "i am done watching",
                "stop the movie setup",
                "stop watching",
                "stop the movie",
                "done watching"
            )
        ) {
            return AnimusCommand.StopMovieMode
        }

        // 5.6 Projector Power & Source Commands
        if (normalized in setOf(
                "turn on projector",
                "turn on the projector",
                "turn the projector on",
                "turn projector on",
                "switch on projector",
                "switch on the projector",
                "switch the projector on",
                "switch projector on",
                "projector on",
                "power on projector",
                "power on the projector",
                "power the projector on",
                "power projector on",
                "start projector",
                "start the projector",
                "turn on project",
                "turn the project on",
                "project on"
            )
        ) {
            return AnimusCommand.SetDeviceCapability(
                target = "PROJECTOR",
                capability = com.animus.smartroom.device.model.DeviceCapability.Power,
                value = true
            )
        }

        if (normalized in setOf(
                "turn off projector",
                "turn off the projector",
                "turn the projector off",
                "turn projector off",
                "switch off projector",
                "switch off the projector",
                "switch the projector off",
                "switch projector off",
                "projector off",
                "power off projector",
                "power off the projector",
                "power the projector off",
                "power projector off",
                "shut down projector",
                "shut down the projector",
                "shut off projector",
                "shut off the projector",
                "stop projector",
                "stop the projector",
                "turn off project",
                "turn the project off",
                "project off",
                "turn project off",
                "switch off project"
            )
        ) {
            return AnimusCommand.SetDeviceCapability(
                target = "PROJECTOR",
                capability = com.animus.smartroom.device.model.DeviceCapability.Power,
                value = false
            )
        }

        if (normalized in setOf(
                "soundbar",
                "speaker",
                "lg speaker",
                "lg soundbar",
                "connect soundbar",
                "connect speaker",
                "connect lg speaker"
            )
        ) {
            return AnimusCommand.ConnectBluetoothDevice(deviceName = "PC")
        }

        val projSourceMatcher = PROJECTOR_SOURCE_REGEX.matcher(trimmed)
        if (projSourceMatcher.find()) {
            val rawSource = projSourceMatcher.group(1)?.trim()?.uppercase(Locale.ROOT)
            val formatted = when {
                rawSource?.startsWith("HDMI") == true -> rawSource.replace(" ", "_")
                rawSource != null -> rawSource
                else -> "HDMI_1"
            }
            return AnimusCommand.SetDeviceCapability(
                target = "PROJECTOR",
                capability = com.animus.smartroom.device.model.DeviceCapability.SelectInput,
                value = formatted
            )
        }

        val switchToHdmiMatcher = SWITCH_TO_HDMI_REGEX.matcher(trimmed)
        if (switchToHdmiMatcher.find()) {
            val rawSource = switchToHdmiMatcher.group(1)?.trim()?.uppercase(Locale.ROOT)
            val formatted = rawSource?.replace(" ", "_") ?: "HDMI_1"
            return AnimusCommand.SetDeviceCapability(
                target = "PROJECTOR",
                capability = com.animus.smartroom.device.model.DeviceCapability.SelectInput,
                value = formatted
            )
        }

        val playMovieMatcher = PLAY_MOVIE_REGEX.matcher(trimmed)
        if (playMovieMatcher.find()) {
            val content = playMovieMatcher.group(1)?.trim()
            if (!content.isNullOrBlank()) {
                return AnimusCommand.WatchContent(title = content)
            }
        }

        val watchMatcher = WATCH_CONTENT_REGEX.matcher(trimmed)
        if (watchMatcher.find()) {
            val content = watchMatcher.group(1)?.trim()
            if (!content.isNullOrBlank()) {
                val lowerContent = content.lowercase(Locale.ROOT)
                return if (lowerContent in setOf("movie", "a movie", "the movie", "something", "tv")) {
                    AnimusCommand.StartMovieMode()
                } else {
                    AnimusCommand.WatchContent(title = content)
                }
            }
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

        // 10. AC Scheduled Timer Commands
        val queryTimerMatcher = QUERY_AC_TIMER_REGEX.matcher(trimmed)
        if (queryTimerMatcher.find()) {
            return AnimusCommand.QueryScheduledAction(target = "AC")
        }

        val cancelTimerMatcher = CANCEL_AC_TIMER_REGEX.matcher(trimmed)
        if (cancelTimerMatcher.find()) {
            return AnimusCommand.CancelScheduledAction(target = "AC")
        }

        val acTimerRecurringMatcher = AC_TIMER_RECURRING_REGEX.matcher(trimmed)
        if (acTimerRecurringMatcher.find()) {
            val powerState = acTimerRecurringMatcher.group(1)?.trim()?.uppercase(Locale.ROOT) ?: "OFF"
            val timeStr = acTimerRecurringMatcher.group(2)?.trim()
            val action = if (powerState == "ON") "POWER_ON" else "POWER_OFF"
            return AnimusCommand.ScheduleDeviceAction(
                target = "AC",
                action = action,
                scheduledTime = timeStr,
                recurrence = "DAILY"
            )
        }

        val acTimerHourMatcher = AC_TIMER_HOUR_REGEX.matcher(trimmed)
        if (acTimerHourMatcher.find()) {
            val powerState = acTimerHourMatcher.group(1)?.trim()?.uppercase(Locale.ROOT) ?: "OFF"
            val action = if (powerState == "ON") "POWER_ON" else "POWER_OFF"
            return AnimusCommand.ScheduleDeviceAction(
                target = "AC",
                action = action,
                delayMinutes = 60
            )
        }

        val acTimerDelayMatcher = AC_TIMER_DELAY_REGEX.matcher(trimmed)
        if (acTimerDelayMatcher.find()) {
            val powerState = acTimerDelayMatcher.group(1)?.trim()?.uppercase(Locale.ROOT) ?: "OFF"
            val amount = acTimerDelayMatcher.group(2)?.toIntOrNull() ?: 30
            val unit = acTimerDelayMatcher.group(3)?.lowercase(Locale.ROOT) ?: "minutes"
            val delayMinutes = if (unit.startsWith("hour") || unit.startsWith("hr")) amount * 60 else amount
            val action = if (powerState == "ON") "POWER_ON" else "POWER_OFF"
            return AnimusCommand.ScheduleDeviceAction(
                target = "AC",
                action = action,
                delayMinutes = delayMinutes
            )
        }

        val acTimerAtMatcher = AC_TIMER_AT_TIME_REGEX.matcher(trimmed)
        if (acTimerAtMatcher.find()) {
            val powerState = acTimerAtMatcher.group(1)?.trim()?.uppercase(Locale.ROOT) ?: "OFF"
            val timeStr = acTimerAtMatcher.group(2)?.trim()
            val action = if (powerState == "ON") "POWER_ON" else "POWER_OFF"
            return AnimusCommand.ScheduleDeviceAction(
                target = "AC",
                action = action,
                scheduledTime = timeStr
            )
        }

        // 11. Sleep Mode Commands
        val cancelSleepMatcher = CANCEL_SLEEP_REGEX.matcher(trimmed)
        if (cancelSleepMatcher.find()) {
            return AnimusCommand.CancelSleepMode
        }

        val sleepHourMatcher = SLEEP_HOUR_REGEX.matcher(trimmed)
        if (sleepHourMatcher.find()) {
            return AnimusCommand.ActivateSleepMode(durationMinutes = 60, wakeTime = null)
        }

        val sleepDurationMatcher = SLEEP_DURATION_REGEX.matcher(trimmed)
        if (sleepDurationMatcher.find()) {
            val duration = sleepDurationMatcher.group(1)?.toIntOrNull()
            if (duration != null && duration > 0) {
                return AnimusCommand.ActivateSleepMode(durationMinutes = duration, wakeTime = null)
            }
        }

        val sleepWakeTimeMatcher = SLEEP_WAKE_TIME_REGEX.matcher(trimmed)
        if (sleepWakeTimeMatcher.find()) {
            val wakeTimeStr = sleepWakeTimeMatcher.group(1)?.trim()
            if (!wakeTimeStr.isNullOrBlank()) {
                return AnimusCommand.ActivateSleepMode(durationMinutes = null, wakeTime = wakeTimeStr)
            }
        }

        val unparamSleepMatcher = UNPARAMETERIZED_SLEEP_REGEX.matcher(trimmed)
        if (unparamSleepMatcher.find()) {
            return AnimusCommand.ActivateSleepMode(durationMinutes = null, wakeTime = null)
        }

        // 12. Volume commands
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

        // 7. Authoritative Audio Ownership Commands (PC vs Fire TV)
        if (AUDIO_OWNERSHIP_PC_REGEX.matcher(trimmed).find()) {
            return AnimusCommand.SwitchBluetoothDevice("PC")
        }

        if (AUDIO_OWNERSHIP_FIRETV_REGEX.matcher(trimmed).find()) {
            return AnimusCommand.SwitchBluetoothDevice("FIRE_TV")
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
