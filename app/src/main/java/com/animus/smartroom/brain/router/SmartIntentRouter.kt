package com.animus.smartroom.brain.router

import android.util.Log
import com.animus.smartroom.core.brain.intent.ConfidenceTier
import com.animus.smartroom.core.brain.intent.IntentClassifier
import com.animus.smartroom.core.brain.intent.IntentPromptBuilder
import com.animus.smartroom.core.brain.intent.UserIntent
import com.animus.smartroom.core.brain.port.LocalInferencePort
import com.animus.smartroom.core.brain.router.AmbiguityDetector
import com.animus.smartroom.core.brain.router.BrainIntent
import com.animus.smartroom.core.brain.router.CapabilityRegistry
import com.animus.smartroom.core.brain.router.ContextResolver
import com.animus.smartroom.core.brain.router.ExecutionResult
import com.animus.smartroom.core.brain.router.IntentNormalizer
import com.animus.smartroom.core.brain.router.IntentValidator
import com.animus.smartroom.core.brain.router.ObservabilityTracer
import java.util.Locale
import java.util.UUID

/**
 * Smart Intent Router for Animus Smart Room.
 * Translates natural language into strictly validated deterministic intents
 * and coordinates execution with the DeterministicExecutionEngine.
 */
class SmartIntentRouter(
    private val inferencePort: LocalInferencePort? = null,
    private val executionEngine: DeterministicExecutionEngine? = null,
    private val contextResolver: ContextResolver = ContextResolver()
) {
    companion object {
        private const val TAG = "SmartIntentRouter"
    }

    suspend fun routeAndExecute(input: String, correlationId: String = UUID.randomUUID().toString()): ExecutionResult {
        val tracer = ObservabilityTracer(correlationId)
        val trimmed = input.trim()

        if (trimmed.isBlank()) {
            tracer.mark("FINAL_RESULT")
            return ExecutionResult(
                status = ExecutionResult.Status.REJECTED,
                correlationId = correlationId,
                intent = "UNKNOWN",
                message = "Input is blank.",
                reason = "BLANK_INPUT",
                latencyTraceMs = tracer.getTraceLatencies()
            )
        }

        // 1. Ambiguity check
        val lastTarget = contextResolver.getLastTarget()
        val ambiguity = AmbiguityDetector.checkAmbiguity(trimmed, lastTarget)
        if (ambiguity.isAmbiguous) {
            tracer.mark("FINAL_RESULT")
            return ExecutionResult(
                status = ExecutionResult.Status.CLARIFICATION_REQUIRED,
                correlationId = correlationId,
                intent = "CLARIFICATION_REQUIRED",
                message = ambiguity.question ?: "Please clarify your request.",
                reason = ambiguity.reason ?: "AMBIGUOUS_COMMAND",
                latencyTraceMs = tracer.getTraceLatencies()
            )
        }

        // 2. Intent Classification via LLM or Local Normalization
        val intent = classifyUserIntent(trimmed, correlationId, tracer)
        tracer.mark("INTENT_CLASSIFICATION")

        // 3. Validation against CapabilityRegistry & Safety Rules
        val valResult = IntentValidator.validate(intent)
        tracer.mark("INTENT_VALIDATED")

        if (valResult is IntentValidator.ValidationResult.Invalid) {
            tracer.mark("FINAL_RESULT")
            return ExecutionResult(
                status = ExecutionResult.Status.REJECTED,
                correlationId = correlationId,
                intent = "REJECTED",
                message = valResult.message,
                reason = valResult.reason,
                latencyTraceMs = tracer.getTraceLatencies()
            )
        }

        // Update bounded conversational context if applicable
        if (intent is BrainIntent.DirectCommand) {
            contextResolver.updateContext(
                target = intent.target,
                temperature = (intent.parameters["temperature"] as? Number)?.toInt(),
                mediaTitle = intent.parameters["title"]?.toString()
            )
        }

        // 4. Deterministic Execution
        val engine = executionEngine ?: DeterministicExecutionEngine()
        val execResult = engine.execute(intent, tracer)

        Log.i(TAG, "[SmartRouter] Execution complete for '$trimmed': status=${execResult.status}, latency=${execResult.latencyTraceMs}")
        return execResult
    }

    private suspend fun classifyUserIntent(input: String, correlationId: String, tracer: ObservabilityTracer): BrainIntent {
        tracer.mark("LLM_CLASSIFICATION_START")
        // Attempt LLM Classification if port is available
        if (inferencePort != null && inferencePort.isAvailable()) {
            try {
                val prompt = IntentPromptBuilder.buildSystemPrompt()
                val rawLlm = inferencePort.generate(input, listOf(prompt))
                val payload = IntentClassifier.parse(rawLlm)

                if (payload.requiresClarification || payload.intent == UserIntent.CLARIFICATION_REQUIRED) {
                    return BrainIntent.ClarificationRequired(
                        reason = payload.clarificationReason ?: "AMBIGUOUS_COMMAND",
                        question = payload.clarificationReason ?: "Could you please clarify what you'd like to do?",
                        correlationId = correlationId
                    )
                }

                if (payload.intent == UserIntent.CONVERSATION) {
                    return BrainIntent.ConversationalOnly(
                        spokenResponse = payload.spokenResponse ?: "I understood your request.",
                        correlationId = correlationId
                    )
                }

                val subList = payload.subIntents
                if (subList != null && subList.isNotEmpty()) {
                    val subActions = subList.mapNotNull { sub ->
                        val target = contextResolver.resolveTarget(input, sub.parameters["target"]?.toString())
                            ?: CapabilityRegistry.DeviceTarget.AC
                        val cap = IntentNormalizer.normalizeAction(target, sub.parameters["action"]?.toString() ?: sub.intent.name)
                        if (cap != null) {
                            BrainIntent.DirectCommand(target, cap, sub.parameters, correlationId)
                        } else null
                    }
                    if (subActions.isNotEmpty()) {
                        return BrainIntent.MultiActionCommand(subActions, correlationId)
                    }
                }

                // Check for routine intent
                if (payload.intent in setOf(UserIntent.WORK_MODE, UserIntent.SLEEP_ROUTINE, UserIntent.MOVIE)) {
                    val routineName = when (payload.intent) {
                        UserIntent.WORK_MODE -> "WORK_MODE"
                        UserIntent.SLEEP_ROUTINE -> "GOODNIGHT_MODE"
                        UserIntent.MOVIE -> "MOVIE_MODE"
                        else -> payload.intent.name
                    }
                    return BrainIntent.RoutineCommand(routineName, payload.parameters, correlationId)
                }

                // Direct command mapping
                val target = contextResolver.resolveTarget(input, payload.parameters["target"]?.toString())
                    ?: when (payload.intent) {
                        UserIntent.MUSIC -> CapabilityRegistry.DeviceTarget.MEDIA
                        UserIntent.MOVIE -> CapabilityRegistry.DeviceTarget.PROJECTOR
                        UserIntent.GENERAL_COMMAND -> CapabilityRegistry.DeviceTarget.AC
                        else -> CapabilityRegistry.DeviceTarget.AC
                    }

                val actionName = payload.parameters["action"]?.toString() ?: payload.intent.name
                val capability = IntentNormalizer.normalizeAction(target, actionName)
                    ?: CapabilityRegistry.ActionCapability.fromString(target, actionName)
                    ?: CapabilityRegistry.ActionCapability.AC_POWER_ON

                return BrainIntent.DirectCommand(
                    target = target,
                    capability = capability,
                    parameters = payload.parameters,
                    correlationId = correlationId
                )
            } catch (e: Exception) {
                Log.w(TAG, "LLM inference failed, using deterministic rule fallback: ${e.message}")
            }
        }

        // Deterministic Rule Fallback
        return parseDeterministicFallback(input, correlationId)
    }

    private fun parseDeterministicFallback(input: String, correlationId: String): BrainIntent {
        val lower = input.lowercase(Locale.ROOT)
        val cleaned = lower
            .replace(Regex("""\b(a|an|the|my|please|up|device)\b"""), " ")
            .replace(Regex("""\s+"""), " ")
            .trim()

        // Movie Mode
        if (cleaned.contains("movie mode") || cleaned.contains("movie night") || (cleaned.contains("watch") && cleaned.contains("movie")) || cleaned.contains("cinema mode") || cleaned.contains("watch something")) {
            return BrainIntent.RoutineCommand("MOVIE_MODE", emptyMap(), correlationId)
        }

        // Bare Play / Resume / Unpause
        if (cleaned == "play" || cleaned == "resume" || cleaned == "unpause" || cleaned == "continue") {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.MEDIA,
                capability = CapabilityRegistry.ActionCapability.MEDIA_PLAY,
                parameters = emptyMap(),
                correlationId = correlationId
            )
        }

        // Specific track
        if (cleaned.startsWith("play ")) {
            val rawTitle = cleaned.removePrefix("play ").trim()
            if (rawTitle.isNotEmpty()) {
                val formattedTitle = if (rawTitle.equals("zara", ignoreCase = true) || rawTitle.equals("zara zara", ignoreCase = true)) "Zara Zara" else rawTitle
                return BrainIntent.DirectCommand(
                    target = CapabilityRegistry.DeviceTarget.MEDIA,
                    capability = CapabilityRegistry.ActionCapability.MEDIA_PLAY,
                    parameters = mapOf("title" to formattedTitle),
                    correlationId = correlationId
                )
            }
        }

        // Music Mode
        if (cleaned.contains("music mode") || cleaned.contains("play music") || cleaned.contains("listen to music")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.MEDIA,
                capability = CapabilityRegistry.ActionCapability.MEDIA_PLAY,
                parameters = emptyMap(),
                correlationId = correlationId
            )
        }

        // Work Mode
        if (cleaned.contains("work mode") || cleaned.contains("focus mode") || cleaned.contains("study mode") || cleaned.contains("time to study")) {
            return BrainIntent.RoutineCommand("WORK_MODE", emptyMap(), correlationId)
        }

        // Goodnight Mode
        if (cleaned.contains("goodnight") || cleaned.contains("sleep routine") || cleaned.contains("turn everything off") || cleaned.contains("bedtime") || cleaned.contains("all off")) {
            return BrainIntent.RoutineCommand("GOODNIGHT_MODE", emptyMap(), correlationId)
        }

        // AC temperature
        val tempRegex = Regex("""(?:ac|temperature|cooler)\s*(?:to|at)?\s*(\d{2})|set\s*ac\s*to\s*(\d{2})|(\d{2})\s*degrees""")
        val match = tempRegex.find(cleaned)
        if (match != null) {
            val temp = (match.groups[1]?.value ?: match.groups[2]?.value ?: match.groups[3]?.value)?.toIntOrNull() ?: 23
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.AC,
                capability = CapabilityRegistry.ActionCapability.AC_SET_TEMPERATURE,
                parameters = mapOf("temperature" to temp),
                correlationId = correlationId
            )
        }

        // AC Power
        if (cleaned.contains("turn on ac") || cleaned.contains("start ac") || cleaned.contains("power on ac") || cleaned.contains("power ac")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.AC,
                capability = CapabilityRegistry.ActionCapability.AC_POWER_ON,
                correlationId = correlationId
            )
        }
        if (cleaned.contains("turn off ac") || cleaned.contains("stop ac") || cleaned.contains("power off ac")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.AC,
                capability = CapabilityRegistry.ActionCapability.AC_POWER_OFF,
                correlationId = correlationId
            )
        }

        // Projector Power
        if (cleaned.contains("turn on projector") || cleaned.contains("start projector") || cleaned.contains("wake projector") || cleaned.contains("power projector")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_ON,
                correlationId = correlationId
            )
        }
        if (cleaned.contains("turn off projector") || cleaned.contains("stop projector") || cleaned.contains("power off projector")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                capability = CapabilityRegistry.ActionCapability.PROJECTOR_POWER_OFF,
                correlationId = correlationId
            )
        }

        // Projector Input
        if (cleaned.contains("hdmi 1") || cleaned.contains("hdmi1") || cleaned.contains("hdmi 2") || cleaned.contains("hdmi2")) {
            val inputVal = if (cleaned.contains("hdmi 2") || cleaned.contains("hdmi2")) "HDMI_2" else "HDMI_1"
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.PROJECTOR,
                capability = CapabilityRegistry.ActionCapability.PROJECTOR_SET_INPUT,
                parameters = mapOf("input" to inputVal),
                correlationId = correlationId
            )
        }

        // Fire TV Wake
        if (cleaned.contains("wake fire tv") || cleaned.contains("turn on fire tv") || cleaned.contains("fire tv wake") || cleaned.contains("fire tv on")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.FIRE_TV,
                capability = CapabilityRegistry.ActionCapability.FIRE_TV_WAKE,
                correlationId = correlationId
            )
        }

        // Audio Connect
        if (cleaned.contains("connect soundbar") || cleaned.contains("connect lg") || cleaned.contains("connect speaker") || cleaned.contains("pair soundbar")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.AUDIO,
                capability = CapabilityRegistry.ActionCapability.AUDIO_CONNECT_LG,
                correlationId = correlationId
            )
        }
        if (cleaned.contains("disconnect soundbar") || cleaned.contains("disconnect lg") || cleaned.contains("disconnect speaker") || cleaned.contains("unpair soundbar")) {
            return BrainIntent.DirectCommand(
                target = CapabilityRegistry.DeviceTarget.AUDIO,
                capability = CapabilityRegistry.ActionCapability.AUDIO_DISCONNECT_LG,
                correlationId = correlationId
            )
        }

        // Fallback to Conversational
        return BrainIntent.ConversationalOnly(
            spokenResponse = "I understood '$input'.",
            correlationId = correlationId
        )
    }
}
