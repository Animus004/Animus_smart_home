package com.animus.smartroom.runtime

import android.util.Log
import com.animus.smartroom.brain.AnimusBrainManager
import com.animus.smartroom.brain.model.BrainResult
import com.animus.smartroom.command.router.CommandRouter
import com.animus.smartroom.core.port.VoiceOutputPort
import com.animus.smartroom.core.runtime.RuntimeControlPort
import com.animus.smartroom.scheduler.DeviceSchedulerEngine

/**
 * Concrete implementation of [RuntimeControlPort] on Android.
 * Connects command submissions from UI layers (MainActivity, FloatingAnimusService)
 * directly to AnimusBrainManager and CommandRouter without duplicating logic or calling device drivers directly.
 */
class RuntimeControlPortImpl(
    private val brainManager: AnimusBrainManager,
    private val commandRouter: CommandRouter,
    private val deviceSchedulerEngine: DeviceSchedulerEngine,
    private val voiceOutputPort: VoiceOutputPort? = null
) : RuntimeControlPort {

    companion object {
        private const val TAG = "RuntimeControlPortImpl"
    }

    override suspend fun submitCommand(input: String): BrainResult {
        val trimmed = input.trim()
        if (trimmed.isBlank()) {
            return BrainResult.Failure(errorMessage = "Command input was blank", cause = IllegalArgumentException("Empty command"))
        }

        Log.i(TAG, "[submitCommand] Interpreting command: '$trimmed'")
        val brainResult = brainManager.interpret(trimmed)

        when (brainResult) {
            is BrainResult.RemoteAgentSuccess -> {
                Log.i(TAG, "[submitCommand] Authoritative Phase F agent response: intent='${brainResult.understoodIntent}', actionTaken=${brainResult.actionTaken}")
                if (brainResult.agentMessage.isNotBlank()) {
                    voiceOutputPort?.speak(brainResult.agentMessage)
                }
                // Zero local duplicate execution: Phase F backend already performed planning, validation, and physical execution.
            }
            is BrainResult.Success -> {
                Log.i(TAG, "[submitCommand] Executing legacy interpreted commands (${brainResult.commands.size})")
                val execResult = commandRouter.execute(brainResult.commands)
                Log.i(TAG, "[submitCommand] Execution finished: success=${execResult.success}, message='${execResult.message}'")
            }
            is BrainResult.Failure -> {
                Log.w(TAG, "[submitCommand] Brain returned failure: ${brainResult.errorMessage}")
                voiceOutputPort?.speak("Sorry buddy, I couldn't reach the smart room daemon.")
            }
            is BrainResult.Unavailable -> {
                Log.w(TAG, "[submitCommand] Brain returned unavailable")
                voiceOutputPort?.speak("The smart room agent is currently unreachable.")
            }
            is BrainResult.InvalidResponse -> {
                Log.w(TAG, "[submitCommand] Brain returned invalid response: ${brainResult.reason}")
            }
        }

        return brainResult
    }

    override suspend fun cancelAction(actionId: String): Boolean {
        if (actionId.isBlank()) {
            Log.w(TAG, "[cancelAction] Blank actionId provided")
            return false
        }

        Log.i(TAG, "[cancelAction] Cancelling scheduled action: $actionId")
        return deviceSchedulerEngine.cancelAction(actionId)
    }
}

