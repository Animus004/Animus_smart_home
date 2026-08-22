package com.animus.smartroom.core.brain.model

enum class MusicActionType {
    PAUSE,
    RESUME,
    NEXT,
    PREVIOUS
}

enum class TaskActionType {
    CREATE,
    COMPLETE,
    CANCEL,
    LIST
}

enum class MemoryActionType {
    CREATE,
    DELETE,
    QUERY
}

sealed interface BrainAction {

    data class DeviceCommand(
        val target: String,
        val capability: String,
        val value: Any? = null
    ) : BrainAction

    data class PlayMusic(
        val title: String,
        val artist: String? = null
    ) : BrainAction

    data class MusicControl(
        val action: MusicActionType
    ) : BrainAction

    data class SetVolume(
        val percentage: Int
    ) : BrainAction

    data class ConnectBluetooth(
        val deviceName: String? = null
    ) : BrainAction

    data object DisconnectBluetooth : BrainAction

    data class ScheduleAction(
        val target: String,
        val action: String,
        val delayMinutes: Int? = null,
        val scheduledTime: String? = null,
        val recurrence: String? = null,
        val parameters: Map<String, Any> = emptyMap()
    ) : BrainAction

    data class CancelScheduledAction(
        val target: String,
        val actionType: String? = null
    ) : BrainAction

    data class TaskAction(
        val actionType: TaskActionType,
        val task: Task
    ) : BrainAction

    data class MemoryAction(
        val actionType: MemoryActionType,
        val memory: Memory
    ) : BrainAction
}
