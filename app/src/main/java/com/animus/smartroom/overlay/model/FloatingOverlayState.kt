package com.animus.smartroom.overlay.model

import com.animus.smartroom.core.diagnostics.model.ActionStatus
import com.animus.smartroom.core.diagnostics.model.AnimusActionEvent
import com.animus.smartroom.core.port.VoicePortState
import com.animus.smartroom.device.model.DeviceType

/**
 * Visibility state machine for the floating control surface.
 */
enum class FloatingOverlayVisibility {
    HIDDEN,
    COLLAPSED,
    EXPANDED,
    MUSIC_PERSISTENT,
    LISTENING
}

/**
 * Represents a single sub-action in a command card.
 */
data class SubActionItem(
    val id: String,
    val deviceType: DeviceType?,
    val action: String,
    val description: String,
    val status: ActionStatus,
    val verified: Boolean = false
)

/**
 * Grouped command visualization model derived from correlated [AnimusActionEvent]s.
 */
data class CorrelatedCommandCard(
    val correlationId: String,
    val rawPrompt: String? = null,
    val subActions: List<SubActionItem> = emptyList(),
    val overallStatus: ActionStatus = ActionStatus.PENDING,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Active timer countdown model for the overlay.
 */
data class OverlayTimerCard(
    val actionId: String,
    val deviceType: DeviceType,
    val actionType: String,
    val targetTimestamp: Long,
    val formattedTargetTime: String = ""
) {
    fun remainingMillis(now: Long = System.currentTimeMillis()): Long =
        (targetTimestamp - now).coerceAtLeast(0L)

    fun formattedRemaining(now: Long = System.currentTimeMillis()): String {
        val rem = remainingMillis(now)
        val totalSec = (rem + 999L) / 1000L
        val hours = totalSec / 3600
        val mins = (totalSec % 3600) / 60
        val secs = totalSec % 60
        return if (hours > 0) {
            String.format("%02d:%02d:%02d", hours, mins, secs)
        } else {
            String.format("%02d:%02d", mins, secs)
        }
    }
}

/**
 * Output music summary state for overlay display.
 */
data class OverlayMusicSummary(
    val trackTitle: String? = null,
    val outputDeviceName: String? = null,
    val isConnected: Boolean = false,
    val isPlaying: Boolean = false
)

/**
 * Immutable state model for the floating control surface.
 */
data class FloatingOverlayState(
    val visibility: FloatingOverlayVisibility = FloatingOverlayVisibility.COLLAPSED,
    val isExpanded: Boolean = false,
    val voiceState: VoicePortState = VoicePortState.Idle,
    val activeCommandCard: CorrelatedCommandCard? = null,
    val recentCompletedActions: List<SubActionItem> = emptyList(),
    val activeTimer: OverlayTimerCard? = null,
    val musicSummary: OverlayMusicSummary = OverlayMusicSummary(),
    val isVoiceProcessing: Boolean = false,
    val lastStatusMessage: String? = null,
    val lastMeaningfulEventTimestamp: Long = System.currentTimeMillis()
) {
    val isMusicPersistent: Boolean
        get() = visibility == FloatingOverlayVisibility.MUSIC_PERSISTENT ||
                (musicSummary.isPlaying && visibility != FloatingOverlayVisibility.HIDDEN)
}
