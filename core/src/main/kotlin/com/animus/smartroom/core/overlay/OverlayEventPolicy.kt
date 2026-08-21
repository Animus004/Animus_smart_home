package com.animus.smartroom.core.overlay

import com.animus.smartroom.core.diagnostics.model.ActionStage
import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.device.model.DeviceType

/**
 * Result classification of how the floating overlay should react to an incoming AnimusActionEvent.
 */
enum class OverlayEventAction {
    SURFACE_IMMEDIATELY,
    SURFACE_MUSIC_PERSISTENT,
    SURFACE_TIMER_COMPLETION,
    SHOW_ONLY_IF_VISIBLE,
    IGNORE
}

/**
 * Pure JVM Centralized event classification policy for the floating overlay.
 * Prevents noisy internal diagnostics from popping up over other applications.
 */
object OverlayEventPolicy {

    fun evaluate(event: AnimusActionEvent, isMusicActive: Boolean = false): OverlayEventAction {
        // 1. Music playback events
        if (event.targetDevice == DeviceType.BLUETOOTH_AUDIO || event.action.contains("MUSIC", ignoreCase = true)) {
            return when {
                event.stage == ActionStage.COMPLETED && event.status == ActionStatus.SUCCESS -> OverlayEventAction.SURFACE_MUSIC_PERSISTENT
                event.stage == ActionStage.EXECUTING || event.stage == ActionStage.RESOLVING -> OverlayEventAction.SURFACE_IMMEDIATELY
                event.status == ActionStatus.FAILED -> OverlayEventAction.SURFACE_IMMEDIATELY
                else -> OverlayEventAction.SHOW_ONLY_IF_VISIBLE
            }
        }

        // 2. Scheduled Timer Events
        if (event.source == com.animus.smartroom.core.diagnostics.model.ActionSource.SCHEDULER ||
            event.action.contains("SCHEDULED", ignoreCase = true) ||
            event.action.contains("TIMER", ignoreCase = true)
        ) {
            return when {
                event.stage == ActionStage.TRIGGERED || event.stage == ActionStage.EXECUTING -> OverlayEventAction.SURFACE_TIMER_COMPLETION
                event.stage == ActionStage.COMPLETED || event.status == ActionStatus.FAILED -> OverlayEventAction.SURFACE_TIMER_COMPLETION
                else -> OverlayEventAction.SHOW_ONLY_IF_VISIBLE
            }
        }

        // 3. User device actions (AC, Lights, Bluetooth switch, etc.)
        if (event.targetDevice == DeviceType.AIR_CONDITIONER || event.targetDevice == DeviceType.LIGHT) {
            return when (event.stage) {
                ActionStage.RECEIVED,
                ActionStage.TRIGGERED,
                ActionStage.EXECUTING,
                ActionStage.COMPLETED -> OverlayEventAction.SURFACE_IMMEDIATELY
                ActionStage.VERIFYING,
                ActionStage.PRECONDITION -> OverlayEventAction.SHOW_ONLY_IF_VISIBLE
                else -> if (event.status == ActionStatus.FAILED) OverlayEventAction.SURFACE_IMMEDIATELY else OverlayEventAction.IGNORE
            }
        }

        // 4. Low level stages
        return when (event.stage) {
            ActionStage.RECEIVED -> OverlayEventAction.SURFACE_IMMEDIATELY
            ActionStage.COMPLETED -> if (event.status == ActionStatus.SUCCESS || event.status == ActionStatus.FAILED) OverlayEventAction.SURFACE_IMMEDIATELY else OverlayEventAction.SHOW_ONLY_IF_VISIBLE
            ActionStage.PARSING, ActionStage.RESOLVING -> OverlayEventAction.SHOW_ONLY_IF_VISIBLE
            else -> OverlayEventAction.IGNORE
        }
    }
}
