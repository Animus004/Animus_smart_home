package com.animus.smartroom.core.brain.session

data class ConversationTurn(
    val speaker: String, // "USER" or "ASSISTANT"
    val text: String,
    val timestamp: Long = System.currentTimeMillis()
)

data class AssistantSessionSummary(
    val recentTurns: List<ConversationTurn> = emptyList(),
    val lastActiveDevice: String? = null,
    val lastActiveTrack: String? = null,
    val lastRequestedVolume: Int? = null,
    val lastRequestedTemperature: Int? = null,
    val lastScheduledActionTarget: String? = null,
    val lastScheduledActionDelayMinutes: Int? = null,
    val lastTaskId: String? = null,
    val lastTaskTitle: String? = null,
    val pendingClarification: String? = null
)

class AssistantSessionContext(
    private val expiryDurationMs: Long = DEFAULT_EXPIRY_MS
) {
    companion object {
        const val MAX_TURNS = 8
        const val MAX_TEXT_LENGTH_PER_TURN = 300
        const val DEFAULT_EXPIRY_MS = 5 * 60 * 1000L // 5 minutes inactivity expiry
    }

    private val turns = mutableListOf<ConversationTurn>()
    private var lastActivityTimestamp: Long = System.currentTimeMillis()

    var lastActiveDevice: String? = null
        private set
    var lastActiveTrack: String? = null
        private set
    var lastRequestedVolume: Int? = null
        private set
    var lastRequestedTemperature: Int? = null
        private set
    var lastScheduledActionTarget: String? = null
        private set
    var lastScheduledActionDelayMinutes: Int? = null
        private set
    var lastTaskId: String? = null
        private set
    var lastTaskTitle: String? = null
        private set
    var pendingClarification: String? = null
        private set

    fun addTurn(speaker: String, text: String, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        val boundedText = if (text.length > MAX_TEXT_LENGTH_PER_TURN) text.take(MAX_TEXT_LENGTH_PER_TURN) + "..." else text
        turns.add(ConversationTurn(speaker, boundedText, timestamp))
        if (turns.size > MAX_TURNS) {
            turns.removeAt(0)
        }
        lastActivityTimestamp = timestamp
    }

    fun updateActiveMusic(trackTitle: String?, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        lastActiveTrack = trackTitle
        lastActivityTimestamp = timestamp
    }

    fun updateVolume(volume: Int, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        lastRequestedVolume = volume.coerceIn(0, 100)
        lastActivityTimestamp = timestamp
    }

    fun updateTemperature(temp: Int, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        lastActiveDevice = "AC"
        lastRequestedTemperature = temp.coerceIn(16, 30)
        lastActivityTimestamp = timestamp
    }

    fun updateScheduledAction(target: String, delayMinutes: Int?, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        lastScheduledActionTarget = target
        lastScheduledActionDelayMinutes = delayMinutes
        lastActivityTimestamp = timestamp
    }

    fun updateLastTask(id: String, title: String, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        lastTaskId = id
        lastTaskTitle = title
        lastActivityTimestamp = timestamp
    }

    fun setPendingClarification(question: String?, timestamp: Long = System.currentTimeMillis()) {
        checkExpiry(timestamp)
        pendingClarification = question
        lastActivityTimestamp = timestamp
    }

    fun toSummary(now: Long = System.currentTimeMillis()): AssistantSessionSummary {
        checkExpiry(now)
        return AssistantSessionSummary(
            recentTurns = turns.toList(),
            lastActiveDevice = lastActiveDevice,
            lastActiveTrack = lastActiveTrack,
            lastRequestedVolume = lastRequestedVolume,
            lastRequestedTemperature = lastRequestedTemperature,
            lastScheduledActionTarget = lastScheduledActionTarget,
            lastScheduledActionDelayMinutes = lastScheduledActionDelayMinutes,
            lastTaskId = lastTaskId,
            lastTaskTitle = lastTaskTitle,
            pendingClarification = pendingClarification
        )
    }

    fun reset() {
        turns.clear()
        lastActiveDevice = null
        lastActiveTrack = null
        lastRequestedVolume = null
        lastRequestedTemperature = null
        lastScheduledActionTarget = null
        lastScheduledActionDelayMinutes = null
        lastTaskId = null
        lastTaskTitle = null
        pendingClarification = null
        lastActivityTimestamp = System.currentTimeMillis()
    }

    private fun checkExpiry(now: Long) {
        if (now - lastActivityTimestamp > expiryDurationMs) {
            reset()
            lastActivityTimestamp = now
        }
    }
}
