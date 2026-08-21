package com.animus.smartroom.core.runtime

import com.animus.smartroom.brain.model.BrainResult

/**
 * Platform-independent command submission contract.
 * MainActivity and future floating overlay both use this to submit commands.
 * Implementation provided by :app layer.
 */
interface RuntimeControlPort {
    /**
     * Submit a natural-language command to Animus Brain for interpretation and execution.
     * Returns the Brain's result including execution outcome.
     */
    suspend fun submitCommand(input: String): BrainResult

    /**
     * Cancel a scheduled action by ID.
     * Returns true if action was found and cancelled.
     */
    suspend fun cancelAction(actionId: String): Boolean
}
