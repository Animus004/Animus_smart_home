package com.animus.smartroom.core.brain.execution

import com.animus.smartroom.core.brain.router.CapabilityRegistry

/**
 * Action parameter validation result.
 */
sealed interface ActionValidationResult {
    object Valid : ActionValidationResult
    data class Invalid(val reason: String, val message: String) : ActionValidationResult
}

/**
 * Strict centralized Action Registry and Parameter Validator.
 * Prevents arbitrary command injection, restricts actions to approved capabilities,
 * and validates parameter boundaries.
 */
object ActionRegistry {

    private val FORBIDDEN_SECURITY_PATTERNS = listOf(
        "adb shell", "curl ", "http://", "https://", "bash", "powershell",
        "rm -rf", "reboot", "eval(", "exec(", "subprocess", "Kill-Process",
        "cmd.exe", "/bin/sh"
    )

    fun validateAction(
        target: CapabilityRegistry.DeviceTarget,
        capability: CapabilityRegistry.ActionCapability,
        parameters: Map<String, Any?>
    ): ActionValidationResult {
        // 1. Security check on all string parameter values
        for ((key, value) in parameters) {
            val str = value?.toString() ?: continue
            for (forbidden in FORBIDDEN_SECURITY_PATTERNS) {
                if (str.contains(forbidden, ignoreCase = true) || key.contains(forbidden, ignoreCase = true)) {
                    return ActionValidationResult.Invalid(
                        reason = "SECURITY_VIOLATION",
                        message = "Parameter '$key' contains forbidden execution pattern."
                    )
                }
            }
        }

        // 2. Capability target validity
        if (capability.target != target) {
            return ActionValidationResult.Invalid(
                reason = "MISMATCHED_TARGET",
                message = "Capability ${capability.name} does not belong to target ${target.name}"
            )
        }

        // 3. Parameter bounds checks
        when (capability) {
            CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE -> {
                val temp = (parameters["temperature"] ?: parameters["value"]) as? Number
                    ?: return ActionValidationResult.Invalid("MISSING_PARAMETER", "Missing temperature value.")
                val tempInt = temp.toInt()
                if (tempInt < CapabilityRegistry.MIN_AC_TEMP || tempInt > CapabilityRegistry.MAX_AC_TEMP) {
                    return ActionValidationResult.Invalid(
                        reason = "INVALID_PARAMETER_RANGE",
                        message = "Temperature $tempInt°C is out of valid range (${CapabilityRegistry.MIN_AC_TEMP}-${CapabilityRegistry.MAX_AC_TEMP}°C)."
                    )
                }
            }

            CapabilityRegistry.ActionCapability.AC_SET_MODE -> {
                val mode = parameters["mode"]?.toString()?.uppercase()
                    ?: return ActionValidationResult.Invalid("MISSING_PARAMETER", "Missing mode value.")
                if (mode !in CapabilityRegistry.ALLOWED_AC_MODES) {
                    return ActionValidationResult.Invalid(
                        reason = "INVALID_MODE",
                        message = "AC mode '$mode' is not supported. Allowed: ${CapabilityRegistry.ALLOWED_AC_MODES}"
                    )
                }
            }

            CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT -> {
                val input = parameters["input"]?.toString()?.uppercase()
                    ?: return ActionValidationResult.Invalid("MISSING_PARAMETER", "Missing input source.")
                if (input !in CapabilityRegistry.ALLOWED_PROJECTOR_INPUTS) {
                    return ActionValidationResult.Invalid(
                        reason = "INVALID_INPUT_SOURCE",
                        message = "Projector input '$input' is not supported. Allowed: ${CapabilityRegistry.ALLOWED_PROJECTOR_INPUTS}"
                    )
                }
            }

            CapabilityRegistry.ActionCapability.MEDIA_SET_VOLUME -> {
                val vol = (parameters["volume"] ?: parameters["value"]) as? Number
                    ?: return ActionValidationResult.Invalid("MISSING_PARAMETER", "Missing volume value.")
                val volInt = vol.toInt()
                if (volInt < 0 || volInt > 100) {
                    return ActionValidationResult.Invalid(
                        reason = "INVALID_VOLUME_RANGE",
                        message = "Volume $volInt is out of range (0-100)."
                    )
                }
            }

            else -> {
                // Action is in allowlist without specific parameter bounds
            }
        }

        return ActionValidationResult.Valid
    }
}
