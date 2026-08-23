package com.animus.smartroom.core.brain.router

import java.util.Locale

/**
 * Validates intents against the CapabilityRegistry, parameter boundaries, and security rules.
 */
object IntentValidator {

    sealed interface ValidationResult {
        data class Valid(val intent: BrainIntent) : ValidationResult
        data class Invalid(val reason: String, val message: String) : ValidationResult
    }

    private val FORBIDDEN_SECURITY_PATTERNS = listOf(
        "adb shell", "reboot", "rm -rf", "curl ", "powershell", "cmd.exe", "bash", "python",
        "drop table", "shutdown /s", "exec(", "eval("
    )

    fun validate(intent: BrainIntent): ValidationResult {
        return when (intent) {
            is BrainIntent.DirectCommand -> validateDirectCommand(intent)
            is BrainIntent.RoutineCommand -> validateRoutineCommand(intent)
            is BrainIntent.MultiActionCommand -> validateMultiActionCommand(intent)
            is BrainIntent.ClarificationRequired -> ValidationResult.Valid(intent)
            is BrainIntent.Rejection -> ValidationResult.Valid(intent)
            is BrainIntent.ConversationalOnly -> ValidationResult.Valid(intent)
        }
    }

    private fun validateDirectCommand(cmd: BrainIntent.DirectCommand): ValidationResult {
        // 1. Security scan
        for (param in cmd.parameters.values) {
            val strVal = param?.toString()?.lowercase(Locale.ROOT) ?: ""
            if (FORBIDDEN_SECURITY_PATTERNS.any { strVal.contains(it) }) {
                return ValidationResult.Invalid(
                    reason = "SECURITY_VIOLATION",
                    message = "Forbidden command pattern detected."
                )
            }
        }

        // 2. Target & Capability check
        if (cmd.capability.target != cmd.target) {
            return ValidationResult.Invalid(
                reason = "MISMATCHED_TARGET_CAPABILITY",
                message = "Capability ${cmd.capability.name} does not match target ${cmd.target.name}."
            )
        }

        // 3. Parameter checks
        when (cmd.capability) {
            CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE -> {
                val tempRaw = cmd.parameters["temperature"] ?: cmd.parameters["temp"] ?: cmd.parameters["value"]
                val temp = when (tempRaw) {
                    is Number -> tempRaw.toInt()
                    is String -> tempRaw.toIntOrNull()
                    else -> null
                }
                if (temp == null) {
                    return ValidationResult.Invalid("INVALID_PARAMETER", "Missing temperature parameter.")
                }
                if (temp < CapabilityRegistry.MIN_AC_TEMP || temp > CapabilityRegistry.MAX_AC_TEMP) {
                    return ValidationResult.Invalid(
                        "INVALID_PARAMETER_RANGE",
                        "AC temperature $temp°C is outside allowed range (${CapabilityRegistry.MIN_AC_TEMP}°C - ${CapabilityRegistry.MAX_AC_TEMP}°C)."
                    )
                }
            }

            CapabilityRegistry.ActionCapability.AC_SET_MODE -> {
                val modeRaw = (cmd.parameters["mode"] ?: cmd.parameters["value"])?.toString()?.uppercase()
                if (modeRaw == null || modeRaw !in CapabilityRegistry.ALLOWED_AC_MODES) {
                    return ValidationResult.Invalid(
                        "INVALID_MODE",
                        "AC mode '$modeRaw' is not supported. Allowed modes: ${CapabilityRegistry.ALLOWED_AC_MODES}"
                    )
                }
            }

            CapabilityRegistry.ActionCapability.AC_SET_FAN_SPEED -> {
                val speedRaw = (cmd.parameters["fan_speed"] ?: cmd.parameters["speed"] ?: cmd.parameters["value"])?.toString()?.uppercase()
                if (speedRaw == null || speedRaw !in CapabilityRegistry.ALLOWED_AC_FAN_SPEEDS) {
                    return ValidationResult.Invalid(
                        "INVALID_FAN_SPEED",
                        "AC fan speed '$speedRaw' is not supported. Allowed speeds: ${CapabilityRegistry.ALLOWED_AC_FAN_SPEEDS}"
                    )
                }
            }

            CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT -> {
                val inputRaw = (cmd.parameters["input"] ?: cmd.parameters["source"] ?: cmd.parameters["value"])?.toString()?.uppercase()
                if (inputRaw == null || inputRaw !in CapabilityRegistry.ALLOWED_PROJECTOR_INPUTS) {
                    return ValidationResult.Invalid(
                        "INVALID_PROJECTOR_INPUT",
                        "Projector input '$inputRaw' is not supported. Allowed inputs: ${CapabilityRegistry.ALLOWED_PROJECTOR_INPUTS}"
                    )
                }
            }

            CapabilityRegistry.ActionCapability.MEDIA_SET_VOLUME -> {
                val volRaw = cmd.parameters["volume"] ?: cmd.parameters["percentage"] ?: cmd.parameters["value"]
                val vol = when (volRaw) {
                    is Number -> volRaw.toInt()
                    is String -> volRaw.toIntOrNull()
                    else -> null
                }
                if (vol == null || vol < 0 || vol > 100) {
                    return ValidationResult.Invalid(
                        "INVALID_VOLUME",
                        "Volume '$volRaw' must be an integer between 0 and 100."
                    )
                }
            }

            else -> {}
        }

        return ValidationResult.Valid(cmd)
    }

    private fun validateRoutineCommand(routine: BrainIntent.RoutineCommand): ValidationResult {
        val upper = routine.routineName.uppercase()
        val allowedRoutines = setOf(
            "MOVIE_MODE", "ROUTINE_MOVIE_MODE",
            "MUSIC_MODE", "ROUTINE_MUSIC_MODE",
            "WORK_MODE", "ROUTINE_WORK_MODE",
            "GOODNIGHT_MODE", "ROUTINE_GOODNIGHT_MODE", "SLEEP_ROUTINE"
        )
        if (upper !in allowedRoutines) {
            return ValidationResult.Invalid(
                reason = "UNKNOWN_ROUTINE",
                message = "Routine '${routine.routineName}' is not defined in the capability registry."
            )
        }
        return ValidationResult.Valid(routine)
    }

    private fun validateMultiActionCommand(multi: BrainIntent.MultiActionCommand): ValidationResult {
        if (multi.actions.isEmpty()) {
            return ValidationResult.Invalid("EMPTY_MULTI_ACTION", "MultiActionCommand contains zero actions.")
        }
        for (action in multi.actions) {
            val res = validateDirectCommand(action)
            if (res is ValidationResult.Invalid) {
                return res
            }
        }
        return ValidationResult.Valid(multi)
    }
}
