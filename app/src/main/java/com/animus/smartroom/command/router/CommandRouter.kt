package com.animus.smartroom.command.router

import android.util.Log
import com.animus.smartroom.bluetooth.BluetoothAudioDeviceManager
import com.animus.smartroom.bluetooth.model.BluetoothAudioDevice
import com.animus.smartroom.bluetooth.model.BluetoothDeviceState
import com.animus.smartroom.command.model.AnimusCommand
import com.animus.smartroom.command.model.CommandExecutionResult
import com.animus.smartroom.media.MusicController
import com.animus.smartroom.media.resolver.MusicResolutionResult
import com.animus.smartroom.media.resolver.YouTubeMusicResolver
import java.util.Locale

sealed interface DeviceResolutionResult {
    data class Match(val device: BluetoothAudioDevice) : DeviceResolutionResult
    data class Ambiguous(val question: String) : DeviceResolutionResult
    data object NotFound : DeviceResolutionResult
}

class CommandRouter(
    private val bluetoothManager: BluetoothAudioDeviceManager,
    private val musicController: MusicController,
    private val musicResolver: YouTubeMusicResolver? = null
) {

    companion object {
        private const val TAG = "CommandRouter"

        fun resolveDeviceTarget(query: String, paired: List<BluetoothAudioDevice>): DeviceResolutionResult {
            if (paired.isEmpty()) return DeviceResolutionResult.NotFound

            val normalized = query.trim().lowercase(Locale.ROOT)
                .replace(Regex("""^(?:my|the)\s+"""), "")
                .trim()

            val genericSpeakerWords = setOf(
                "speaker", "speakers", "soundbar", "sound bar", "soundbars", "audio", "device", "room audio"
            )
            val genericHeadphoneWords = setOf(
                "headphone", "headphones", "headset", "earphone", "earphones", "earbuds", "earbud", "buds", "airpods"
            )

            val isGenericSpeaker = normalized in genericSpeakerWords
            val isGenericHeadphones = normalized in genericHeadphoneWords

            // 1. Generic speaker / soundbar targets: "speaker", "speakers", "soundbar", "sound bar", "audio", "device", "room audio"
            if (isGenericSpeaker) {
                val speakerCandidates = paired.filter { device ->
                    val lowerName = device.name.lowercase(Locale.ROOT)
                    val isHeadphones = lowerName.contains("head") || lowerName.contains("ear") || lowerName.contains("buds") || lowerName.contains("airpod") || lowerName.contains("wh-") || lowerName.contains("wf-")
                    device.isAudioDevice && !isHeadphones
                }

                return when {
                    speakerCandidates.isEmpty() -> {
                        if (paired.size == 1) DeviceResolutionResult.Match(paired.first())
                        else DeviceResolutionResult.NotFound
                    }
                    speakerCandidates.size == 1 -> {
                        DeviceResolutionResult.Match(speakerCandidates.first())
                    }
                    else -> {
                        val disconnectedSpeakers = speakerCandidates.filter { !it.isConnected }
                        if (disconnectedSpeakers.size == 1) {
                            DeviceResolutionResult.Match(disconnectedSpeakers.first())
                        } else {
                            DeviceResolutionResult.Ambiguous("Which speaker do you want to use?")
                        }
                    }
                }
            }

            // 2. Generic headphones / headset targets: "headphone", "headphones", "headset", "earphone", "earphones", "earbuds", "buds", "airpods"
            if (isGenericHeadphones) {
                val headphoneCandidates = paired.filter { device ->
                    val lowerName = device.name.lowercase(Locale.ROOT)
                    val lowerAlias = (device.alias ?: "").lowercase(Locale.ROOT)
                    lowerName.contains("head") || lowerName.contains("ear") || lowerName.contains("buds") || lowerName.contains("airpod") || lowerName.contains("wh-") || lowerName.contains("wf-") ||
                            lowerAlias.contains("head") || lowerAlias.contains("ear") || lowerAlias.contains("buds") || lowerAlias.contains("airpod") ||
                            (!isSpeakerDevice(device) && device.isAudioDevice)
                }

                return when {
                    headphoneCandidates.size == 1 -> DeviceResolutionResult.Match(headphoneCandidates.first())
                    headphoneCandidates.size > 1 -> {
                        val disconnectedHeadphones = headphoneCandidates.filter { !it.isConnected }
                        if (disconnectedHeadphones.size == 1) {
                            DeviceResolutionResult.Match(disconnectedHeadphones.first())
                        } else {
                            DeviceResolutionResult.Ambiguous("Which headphones do you want to use?")
                        }
                    }
                    else -> {
                        if (paired.size == 1) DeviceResolutionResult.Match(paired.first())
                        else DeviceResolutionResult.NotFound
                    }
                }
            }

            // 3. Exact alias match
            val exactAliasMatch = paired.firstOrNull { device ->
                val alias = device.alias?.trim()?.lowercase(Locale.ROOT)
                alias != null && alias == normalized
            }
            if (exactAliasMatch != null) return DeviceResolutionResult.Match(exactAliasMatch)

            // 4. Exact Android Bluetooth name match
            val exactNameMatch = paired.firstOrNull { device ->
                device.name.trim().lowercase(Locale.ROOT) == normalized
            }
            if (exactNameMatch != null) return DeviceResolutionResult.Match(exactNameMatch)

            // 5. Alias substring match
            val aliasSubstringMatches = paired.filter { device ->
                val alias = device.alias?.trim()?.lowercase(Locale.ROOT)
                alias != null && (alias.contains(normalized) || normalized.contains(alias))
            }
            if (aliasSubstringMatches.size == 1) {
                return DeviceResolutionResult.Match(aliasSubstringMatches.first())
            } else if (aliasSubstringMatches.size > 1) {
                val exactWordMatch = aliasSubstringMatches.firstOrNull {
                    it.alias?.trim()?.equals(normalized, ignoreCase = true) == true
                }
                if (exactWordMatch != null) return DeviceResolutionResult.Match(exactWordMatch)
                return DeviceResolutionResult.Ambiguous("Which ${query.trim()} device do you want to use?")
            }

            // 6. Android name substring match
            val nameSubstringMatches = paired.filter { device ->
                val name = device.name.trim().lowercase(Locale.ROOT)
                name.contains(normalized) || normalized.contains(name)
            }
            if (nameSubstringMatches.size == 1) {
                return DeviceResolutionResult.Match(nameSubstringMatches.first())
            } else if (nameSubstringMatches.size > 1) {
                val exactWordMatch = nameSubstringMatches.firstOrNull {
                    it.name.trim().equals(normalized, ignoreCase = true)
                }
                if (exactWordMatch != null) return DeviceResolutionResult.Match(exactWordMatch)
                return DeviceResolutionResult.Ambiguous("Which ${query.trim()} device do you want to use?")
            }

            return DeviceResolutionResult.NotFound
        }

        private fun isSpeakerDevice(device: BluetoothAudioDevice): Boolean {
            val name = device.name.lowercase(Locale.ROOT)
            val alias = (device.alias ?: "").lowercase(Locale.ROOT)
            return name.contains("sound") || name.contains("snc") || name.contains("lg") ||
                    name.contains("speaker") || name.contains("bar") || name.contains("spinx") ||
                    alias.contains("speaker") || alias.contains("soundbar")
        }
    }

    suspend fun execute(command: AnimusCommand): CommandExecutionResult {
        return execute(listOf(command))
    }

    suspend fun execute(commands: List<AnimusCommand>): CommandExecutionResult {
        val count = commands.size
        Log.i(TAG, "[command-router] Command count received: $count")

        if (commands.isEmpty()) {
            return CommandExecutionResult(success = false, message = "No commands received.")
        }

        val messages = mutableListOf<String>()
        var allSuccess = true

        commands.forEachIndexed { index, cmd ->
            val order = index + 1
            Log.i(TAG, "[command-router] Execution order #$order/$count -> Type: ${cmd::class.simpleName}")
            val res = executeSingle(cmd)
            if (res.message.isNotBlank()) {
                messages.add(res.message)
            }
            if (!res.success) {
                allSuccess = false
            }
        }

        val combined = if (messages.isNotEmpty()) messages.joinToString(" • ") else "Commands executed"
        Log.i(TAG, "[command-router] Finished executing $count commands (Success=$allSuccess): '$combined'")
        return CommandExecutionResult(
            success = allSuccess,
            message = combined
        )
    }

    private suspend fun executeSingle(command: AnimusCommand): CommandExecutionResult {
        Log.i(TAG, "[command-router] Executing single command: ${command::class.simpleName}")

        return when (command) {
            is AnimusCommand.PlayMusic -> {
                val isConnected = musicController.uiState.value.isOutputConnected
                val deviceName = musicController.uiState.value.activeOutputDeviceName

                if (!isConnected) {
                    Log.w(TAG, "[ai] PlayMusic blocked: Bluetooth output is disconnected")
                    return CommandExecutionResult(
                        success = false,
                        message = "Connect a speaker first."
                    )
                }

                Log.d(TAG, "[play-debug] Before resolver: title='${command.title}', artist='${command.artist}', directVideoId='${command.directVideoId}'")

                val resolution = musicResolver?.resolveTrack(
                    title = command.title,
                    artist = command.artist,
                    explicitDirectId = command.directVideoId
                )

                val effectiveVideoId = when (resolution) {
                    is MusicResolutionResult.Resolved -> {
                        Log.i(TAG, "[music-resolver] Resolved '${command.title}' via ${resolution.source} -> videoId='${resolution.videoId}'")
                        resolution.videoId
                    }
                    is MusicResolutionResult.FallbackSearch -> {
                        Log.i(TAG, "[music-resolver] Unresolved track '${command.title}' (${resolution.reason}). Using client fallback.")
                        command.directVideoId
                    }
                    null -> command.directVideoId
                }

                Log.d(TAG, "[play-debug] Resolver result: videoId='$effectiveVideoId'")

                if (effectiveVideoId != null) {
                    Log.i(TAG, "[direct-play] Executing direct playback for '${command.title}' (videoId='$effectiveVideoId') on output '$deviceName'")
                } else {
                    Log.i(TAG, "[music-resolver] Executing search fallback for '${command.title}' on output '$deviceName'")
                }

                musicController.playTrackPreset(
                    title = command.title,
                    artist = command.artist,
                    activeDeviceName = deviceName,
                    directVideoId = effectiveVideoId
                )
                CommandExecutionResult(
                    success = true,
                    message = "Playing ${command.title}"
                )
            }

            is AnimusCommand.PauseMusic -> {
                Log.i(TAG, "[ai] Executing PauseMusic")
                musicController.pause()
                CommandExecutionResult(
                    success = true,
                    message = "Music paused"
                )
            }

            is AnimusCommand.ResumeMusic -> {
                val isConnected = musicController.uiState.value.isOutputConnected
                if (!isConnected) {
                    Log.w(TAG, "[ai] ResumeMusic blocked: Bluetooth output is disconnected")
                    return CommandExecutionResult(
                        success = false,
                        message = "Connect a speaker first."
                    )
                }
                Log.i(TAG, "[ai] Executing ResumeMusic")
                musicController.play()
                CommandExecutionResult(
                    success = true,
                    message = "Resuming playback"
                )
            }

            is AnimusCommand.NextTrack -> {
                Log.i(TAG, "[ai] Executing NextTrack")
                musicController.next()
                CommandExecutionResult(
                    success = true,
                    message = "Next track"
                )
            }

            is AnimusCommand.PreviousTrack -> {
                Log.i(TAG, "[ai] Executing PreviousTrack")
                musicController.previous()
                CommandExecutionResult(
                    success = true,
                    message = "Previous track"
                )
            }

            is AnimusCommand.SetVolume -> {
                val clamped = command.percentage.coerceIn(0, 100)
                Log.i(TAG, "[ai] Executing SetVolume: $clamped%")
                musicController.setVolume(clamped / 100f)
                CommandExecutionResult(
                    success = true,
                    message = "Volume set to $clamped%"
                )
            }

            is AnimusCommand.ConnectBluetoothDevice -> {
                val paired = bluetoothManager.uiState.value.pairedDevices
                if (command.deviceName.isNullOrBlank()) {
                    Log.i(TAG, "[ai] Executing ConnectBluetoothDevice (selected device)")
                    val selected = bluetoothManager.uiState.value.selectedDevice
                    val targetName = selected?.displayName ?: "Speaker"
                    if (selected != null && selected.isConnected) {
                        CommandExecutionResult(
                            success = true,
                            message = "Already connected to $targetName"
                        )
                    } else {
                        bluetoothManager.connect()
                        CommandExecutionResult(
                            success = true,
                            message = "Connecting to $targetName..."
                        )
                    }
                } else {
                    when (val resolution = resolveDeviceTarget(command.deviceName, paired)) {
                        is DeviceResolutionResult.Match -> {
                            val target = resolution.device
                            Log.i(TAG, "[ai] Found matching paired device for '${command.deviceName}': ${target.displayName} (${target.macAddress})")
                            bluetoothManager.selectDevice(target.macAddress)
                            if (target.isConnected) {
                                CommandExecutionResult(
                                    success = true,
                                    message = "Already connected to ${target.displayName}"
                                )
                            } else {
                                bluetoothManager.connect()
                                CommandExecutionResult(
                                    success = true,
                                    message = "Connecting to ${target.displayName}..."
                                )
                            }
                        }
                        is DeviceResolutionResult.Ambiguous -> {
                            CommandExecutionResult(
                                success = false,
                                message = resolution.question
                            )
                        }
                        is DeviceResolutionResult.NotFound -> {
                            Log.w(TAG, "[ai] Device '${command.deviceName}' not found in paired devices: ${paired.map { it.displayName }}")
                            CommandExecutionResult(
                                success = false,
                                message = "Device '${command.deviceName}' not found in paired devices."
                            )
                        }
                    }
                }
            }

            is AnimusCommand.DisconnectBluetoothDevice -> {
                Log.i(TAG, "[ai] Executing DisconnectBluetoothDevice")
                val current = bluetoothManager.uiState.value.connectionState
                when (current) {
                    is BluetoothDeviceState.Disconnected -> {
                        CommandExecutionResult(
                            success = true,
                            message = "Already disconnected"
                        )
                    }
                    is BluetoothDeviceState.Disconnecting -> {
                        CommandExecutionResult(
                            success = true,
                            message = "Disconnecting..."
                        )
                    }
                    else -> {
                        bluetoothManager.disconnect()
                        CommandExecutionResult(
                            success = true,
                            message = "Disconnecting..."
                        )
                    }
                }
            }

            is AnimusCommand.SwitchBluetoothDevice -> {
                val paired = bluetoothManager.uiState.value.pairedDevices
                when (val resolution = resolveDeviceTarget(command.deviceName, paired)) {
                    is DeviceResolutionResult.Match -> {
                        val target = resolution.device
                        val isAlreadyConnected = target.isConnected
                        Log.i(TAG, "[ai] Switching to target: ${target.displayName} (${target.macAddress}), isAlreadyConnected=$isAlreadyConnected")
                        bluetoothManager.selectDevice(target.macAddress)

                        if (isAlreadyConnected) {
                            CommandExecutionResult(
                                success = true,
                                message = "Switched to ${target.displayName}"
                            )
                        } else {
                            bluetoothManager.connect()
                            CommandExecutionResult(
                                success = true,
                                message = "Connecting to ${target.displayName}..."
                            )
                        }
                    }
                    is DeviceResolutionResult.Ambiguous -> {
                        CommandExecutionResult(
                            success = false,
                            message = resolution.question
                        )
                    }
                    is DeviceResolutionResult.NotFound -> {
                        Log.w(TAG, "[ai] Device '${command.deviceName}' not found in paired list: ${paired.map { it.displayName }}")
                        CommandExecutionResult(
                            success = false,
                            message = "Device '${command.deviceName}' not found in paired devices."
                        )
                    }
                }
            }

            is AnimusCommand.UnknownCommand -> {
                Log.w(TAG, "[ai] Unknown command: '${command.rawText}'")
                CommandExecutionResult(
                    success = false,
                    message = "Could not understand command: '${command.rawText}'"
                )
            }
        }
    }
}
