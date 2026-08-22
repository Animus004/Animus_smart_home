package com.animus.smartroom.core.brain.session

import com.animus.smartroom.core.brain.model.*

object ConversationReferenceResolver {

    fun resolveReference(
        input: String,
        session: AssistantSessionSummary
    ): BrainResponse? {
        val trimmed = input.trim().lowercase()

        // 1. Bare numeric value resolution
        val numericMatch = Regex("^(\\d{1,3})$").find(trimmed)
        if (numericMatch != null) {
            val num = numericMatch.groupValues[1].toInt()
            if (session.lastRequestedVolume != null || session.lastActiveTrack != null) {
                // Resolved as volume if volume context was active
                return BrainResponse.Command(
                    spokenResponse = "Setting volume to $num%.",
                    actions = listOf(BrainAction.SetVolume(num))
                )
            } else if (session.lastRequestedTemperature != null && num in 16..30) {
                // Resolved as temperature
                return BrainResponse.Command(
                    spokenResponse = "Setting AC to $num degrees.",
                    actions = listOf(BrainAction.DeviceCommand("AC", "SET_TEMPERATURE", num))
                )
            }
        }

        // 2. Relative Volume ("make it louder", "turn it down", "louder", "quieter")
        if (trimmed in setOf("make it louder", "louder", "turn it up", "increase volume")) {
            val current = session.lastRequestedVolume ?: 50
            val target = (current + 10).coerceAtMost(100)
            return BrainResponse.Command(
                spokenResponse = "Increasing volume to $target%.",
                actions = listOf(BrainAction.SetVolume(target))
            )
        }
        if (trimmed in setOf("make it quieter", "quieter", "turn it down", "lower volume", "softer")) {
            val current = session.lastRequestedVolume ?: 50
            val target = (current - 10).coerceAtLeast(0)
            return BrainResponse.Command(
                spokenResponse = "Lowering volume to $target%.",
                actions = listOf(BrainAction.SetVolume(target))
            )
        }

        // 3. "Make it X" / "Make that X" / "Set to X"
        val makeItTemp = Regex("""^(?:make it|make that|set to|actually make it|actually)\s*(\d{2})$""").find(trimmed)
        if (makeItTemp != null) {
            val value = makeItTemp.groupValues[1].toInt()
            if (value in 16..30 && session.lastActiveDevice == "AC") {
                return BrainResponse.Command(
                    spokenResponse = "Setting AC to $value degrees.",
                    actions = listOf(BrainAction.DeviceCommand("AC", "SET_TEMPERATURE", value))
                )
            } else if (session.lastActiveTrack != null || session.lastRequestedVolume != null) {
                return BrainResponse.Command(
                    spokenResponse = "Setting volume to $value%.",
                    actions = listOf(BrainAction.SetVolume(value))
                )
            }
        }

        // 4. "Actually make that X hours" / "Actually X minutes" for scheduled actions
        val schedAdjust = Regex("""^(?:actually make that|actually|make that)\s*(\d+)\s*(hours?|hrs?|minutes?|mins?)$""").find(trimmed)
        if (schedAdjust != null && session.lastScheduledActionTarget != null) {
            val count = schedAdjust.groupValues[1].toInt()
            val unit = schedAdjust.groupValues[2]
            val totalMins = if (unit.startsWith("h")) count * 60 else count
            return BrainResponse.Command(
                spokenResponse = "Updated timer to $count $unit.",
                actions = listOf(BrainAction.ScheduleAction(session.lastScheduledActionTarget, "TURN_OFF", delayMinutes = totalMins))
            )
        }

        // 5. Ambiguous "Turn it off" when both AC and Music are active
        if (trimmed in setOf("turn it off", "switch it off", "turn off", "stop it")) {
            if (session.lastActiveTrack != null && session.lastActiveDevice == "AC") {
                return BrainResponse.Clarification(
                    question = "Do you mean the AC or the music?",
                    options = listOf("AC", "Music")
                )
            }
        }

        return null
    }
}
