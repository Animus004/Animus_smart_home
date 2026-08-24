package com.animus.smartroom.core.brain.adaptive

import java.util.Locale

/**
 * Deterministic Priority Hierarchy & Conflict Resolver for competing routines.
 * Prevents race conditions and state corruption when multiple routines or commands collide.
 */
object RoutinePriorityMatrix {

    const val PRIORITY_GOODNIGHT = 100
    const val PRIORITY_ALARM = 90
    const val PRIORITY_MOVIE = 70
    const val PRIORITY_MUSIC = 50
    const val PRIORITY_DIRECT_COMMAND = 40
    const val PRIORITY_WORK = 30
    const val PRIORITY_IDLE = 0

    fun getPriority(routineOrIntentName: String?): Int {
        if (routineOrIntentName.isNullOrBlank()) return PRIORITY_IDLE
        val norm = routineOrIntentName.trim().uppercase(Locale.ROOT)
        return when {
            norm.contains("GOODNIGHT") || norm.contains("SHUTDOWN") || norm.contains("EMERGENCY") -> PRIORITY_GOODNIGHT
            norm.contains("ALARM") || norm.contains("WAKE") -> PRIORITY_ALARM
            norm.contains("MOVIE") || norm.contains("CINEMA") -> PRIORITY_MOVIE
            norm.contains("MUSIC") || norm.contains("SONG") || norm.contains("PLAY") -> PRIORITY_MUSIC
            norm.contains("WORK") || norm.contains("STUDY") -> PRIORITY_WORK
            else -> PRIORITY_DIRECT_COMMAND
        }
    }

    /**
     * Determines whether incoming routine has strictly higher priority than active routine
     * and should safely preempt active routine.
     */
    fun shouldPreempt(activeRoutine: String?, incomingRoutine: String): Boolean {
        if (activeRoutine.isNullOrBlank()) return true
        val pActive = getPriority(activeRoutine)
        val pIncoming = getPriority(incomingRoutine)
        return pIncoming > pActive
    }

    /**
     * Resolves the winner between two simultaneously competing routine requests.
     */
    fun resolveConflict(routineA: String, routineB: String): String {
        val pA = getPriority(routineA)
        val pB = getPriority(routineB)
        return if (pA >= pB) routineA else routineB
    }
}
