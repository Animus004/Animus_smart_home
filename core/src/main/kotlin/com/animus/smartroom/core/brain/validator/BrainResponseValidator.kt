package com.animus.smartroom.core.brain.validator

import com.animus.smartroom.core.brain.model.BrainAction
import com.animus.smartroom.core.brain.model.BrainResponse

sealed interface ValidationResult {
    data object Valid : ValidationResult
    data class Invalid(val reason: String) : ValidationResult
}

object BrainResponseValidator {

    private val credentialPatterns = listOf(
        Regex("AIza[0-9A-Za-z-_]+"),
        Regex("Bearer\\s+[A-Za-z0-9-_.]+"),
        Regex("(?i)tuya.*secret"),
        Regex("(?i)client_secret")
    )

    private val unsafeCommandPatterns = listOf(
        Regex("(?i)rm\\s+-rf"),
        Regex("(?i)drop\\s+table"),
        Regex("(?i)exec\\s*\\("),
        Regex("(?i)eval\\s*\\("),
        Regex("(?i)system\\s*\\(")
    )

    private val allowedTargets = setOf(
        "AC", "AIR_CONDITIONER", "LIGHT", "SPEAKER", "BLUETOOTH", "MUSIC", "PHONE", "SYSTEM"
    )

    fun validate(response: BrainResponse): ValidationResult {
        return when (response) {
            is BrainResponse.Command -> {
                if (response.actions.isEmpty()) {
                    return ValidationResult.Invalid("Command response must contain at least one action.")
                }
                if (response.spokenResponse != null && containsSensitiveData(response.spokenResponse)) {
                    return ValidationResult.Invalid("Spoken response contains credential or sensitive data.")
                }
                for (action in response.actions) {
                    val actionResult = validateAction(action)
                    if (actionResult is ValidationResult.Invalid) {
                        return actionResult
                    }
                }
                ValidationResult.Valid
            }
            is BrainResponse.Conversation -> {
                if (response.spokenResponse.isBlank()) {
                    return ValidationResult.Invalid("Conversation response cannot be blank.")
                }
                if (containsSensitiveData(response.spokenResponse)) {
                    return ValidationResult.Invalid("Conversation response contains sensitive data.")
                }
                ValidationResult.Valid
            }
            is BrainResponse.Clarification -> {
                if (response.question.isBlank()) {
                    return ValidationResult.Invalid("Clarification question cannot be blank.")
                }
                ValidationResult.Valid
            }
            is BrainResponse.Failure -> {
                if (response.reason.isBlank()) {
                    return ValidationResult.Invalid("Failure reason cannot be blank.")
                }
                ValidationResult.Valid
            }
        }
    }

    fun validateAction(action: BrainAction): ValidationResult {
        return when (action) {
            is BrainAction.DeviceCommand -> {
                val normalizedTarget = action.target.trim().uppercase()
                if (normalizedTarget !in allowedTargets && !normalizedTarget.startsWith("DEV_")) {
                    return ValidationResult.Invalid("Unknown or unauthorized device target: '${action.target}'")
                }
                if (action.capability.isBlank()) {
                    return ValidationResult.Invalid("Capability cannot be blank.")
                }
                if (action.value is String && containsUnsafeSyntax(action.value)) {
                    return ValidationResult.Invalid("Device command value contains unsafe syntax.")
                }
                ValidationResult.Valid
            }
            is BrainAction.PlayMusic -> {
                if (action.title.isBlank()) {
                    return ValidationResult.Invalid("Music title cannot be blank.")
                }
                ValidationResult.Valid
            }
            is BrainAction.SetVolume -> {
                if (action.percentage !in 0..100) {
                    return ValidationResult.Invalid("Volume percentage must be between 0 and 100.")
                }
                ValidationResult.Valid
            }
            is BrainAction.ScheduleAction -> {
                val normalizedTarget = action.target.trim().uppercase()
                if (normalizedTarget !in allowedTargets && !normalizedTarget.startsWith("DEV_")) {
                    return ValidationResult.Invalid("Unknown or unauthorized schedule target: '${action.target}'")
                }
                if (action.action.isBlank()) {
                    return ValidationResult.Invalid("Scheduled action name cannot be blank.")
                }
                val delay = action.delayMinutes
                if (delay != null && delay <= 0) {
                    return ValidationResult.Invalid("Schedule delayMinutes must be greater than 0.")
                }
                ValidationResult.Valid
            }
            is BrainAction.CancelScheduledAction -> {
                if (action.target.isBlank()) {
                    return ValidationResult.Invalid("Cancel action target cannot be blank.")
                }
                ValidationResult.Valid
            }
            is BrainAction.TaskAction -> {
                if (action.task.title.isBlank()) {
                    return ValidationResult.Invalid("Task title cannot be blank.")
                }
                ValidationResult.Valid
            }
            is BrainAction.MemoryAction -> {
                if (action.memory.content.isBlank()) {
                    return ValidationResult.Invalid("Memory content cannot be blank.")
                }
                ValidationResult.Valid
            }
            is BrainAction.ConnectBluetooth,
            is BrainAction.DisconnectBluetooth,
            is BrainAction.MusicControl -> ValidationResult.Valid
        }
    }

    private fun containsSensitiveData(text: String): Boolean {
        return credentialPatterns.any { it.containsMatchIn(text) }
    }

    private fun containsUnsafeSyntax(text: String): Boolean {
        return unsafeCommandPatterns.any { it.containsMatchIn(text) }
    }
}
