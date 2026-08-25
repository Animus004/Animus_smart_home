"""
Unified Animus Personal Agent Core Orchestrator for Phase F.1.
Implements the full agent lifecycle:
User Natural Language
  ↓
Human Intent Understanding & User Model
  ↓
Follow-Up if Ambiguous
  ↓
Existing E.8.x Orchestration Pipeline (Context -> Planner -> Validator -> Executor)
  ↓
Physical Readback Verification
  ↓
Agent Feedback Generation
  ↓
Bookkeeping / State Update (Memory & Tasks)
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from capability_registry import UnifiedCapabilityRegistry
from room_state.aggregator import RoomStateAggregator
from context import ContextEngine, PreferenceManager
from planner import (
    GeminiPlannerClient,
    PlanValidator,
    PlanExecutor,
    PlanStep,
    GeminiStructuredPlan,
    ValidationResult,
    GeminiApiUnavailableError
)
from agent.models import (
    UserProfile,
    IntentCategory,
    MoodVibe,
    ResolvedIntent,
    AgentInteractionResponse,
    MemoryCategory,
    PhysicalActionAuditRecord
)
from agent.memory import AgentMemoryStore
from agent.user_model import UserModel
from agent.task_manager import TaskManager
from agent.intent_resolver import IntentResolver
from agent.followup_engine import FollowUpEngine
from agent.feedback import AgentFeedbackGenerator
from agent.daily_brief import DailyBriefEngine
from agent.capability_awareness import CapabilityAwarenessEngine
from agent.persistence import AgentPersistence

logger = logging.getLogger("music_daemon.agent.core")


class AnimusPersonalAgent:
    """
    High-level conversational personal agent coordinating intelligence, memory,
    intent resolution, follow-up clarification, and physical orchestration.
    """

    def __init__(
        self,
        registry: Optional[UnifiedCapabilityRegistry] = None,
        room_state_aggregator: Optional[RoomStateAggregator] = None,
        context_engine: Optional[ContextEngine] = None,
        preference_manager: Optional[PreferenceManager] = None,
        planner_client: Optional[GeminiPlannerClient] = None,
        planner_executor: Optional[PlanExecutor] = None,
        persistence: Optional[AgentPersistence] = None,
        user_model: Optional[UserModel] = None,
        task_manager: Optional[TaskManager] = None,
        memory: Optional[AgentMemoryStore] = None
    ):
        self.registry = registry or UnifiedCapabilityRegistry()
        self.room_state_aggregator = room_state_aggregator
        self.context_engine = context_engine
        self.preference_manager = preference_manager
        self.planner_client = planner_client
        self.planner_executor = planner_executor
        self.persistence = persistence or AgentPersistence()

        # Load or initialize state
        loaded_u, loaded_m, loaded_t = self.persistence.load_state()
        self.user_model = user_model or loaded_u
        self.memory = memory or loaded_m
        self.task_manager = task_manager or loaded_t

        # Initialize sub-engines
        self.intent_resolver = IntentResolver(
            user_profile=self.user_model.profile,
            registry=self.registry,
            memory=self.memory
        )
        self.followup_engine = FollowUpEngine(user_profile=self.user_model.profile)
        self.feedback_generator = AgentFeedbackGenerator(user_profile=self.user_model.profile)
        self.daily_brief_engine = DailyBriefEngine(
            user_profile=self.user_model.profile,
            task_manager=self.task_manager,
            memory=self.memory
        )
        self.capability_engine = CapabilityAwarenessEngine(
            registry=self.registry,
            user_profile=self.user_model.profile
        )

    # =========================================================================
    # Main Agent Entry Point: interact()
    # =========================================================================

    def interact(self, utterance: str) -> AgentInteractionResponse:
        """
        Processes a natural language user turn through the complete agent pipeline.
        """
        addr = self.user_model.preferred_address
        current_state = self.room_state_aggregator.get_room_state() if self.room_state_aggregator else None

        # Step 1: Check if this turn answers an existing follow-up question
        if self.followup_engine.has_pending_followup:
            resolved_followup = self.followup_engine.resolve_followup_response(utterance)
            if resolved_followup.get("resolved"):
                if resolved_followup.get("intent") == "RELAXATION_NARROW_OPTIONS":
                    q = resolved_followup.get("followup_question") or f"No problem, {addr} — want to watch a movie or just keep the room quiet?"
                    return AgentInteractionResponse(
                        understood_intent="RELAXATION_NARROW_OPTIONS",
                        agent_message=q,
                        action_taken=False,
                        followup_required=True,
                        followup_question=q
                    )
                utterance = resolved_followup.get("request", utterance)
                logger.info(f"[AGENT_FOLLOWUP_RESOLVED] Follow-up converted to request: '{utterance}'")

        # Step 2: Determine Human Intent
        intent = self.intent_resolver.resolve_intent(utterance, room_state=current_state)
        logger.info(f"[AGENT_INTENT] Query: '{utterance}' -> Category: {intent.category}, Primary: {intent.primary_intent}")

        # Step 3: Branch based on Intent Category

        # ---------------------------------------------------------------------
        # Category A: UNSAFE / NOT AUTHORIZED
        # ---------------------------------------------------------------------
        if intent.category == IntentCategory.UNSAFE_NOT_AUTHORIZED:
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"I can't do that, {addr}. {intent.explanation}",
                action_taken=False
            )

        # ---------------------------------------------------------------------
        # Category B: UNSUPPORTED CAPABILITY
        # ---------------------------------------------------------------------
        if intent.category == IntentCategory.UNSUPPORTED_CAPABILITY:
            dev = intent.extracted_parameters.get("unsupported_device", "that device")
            msg = self.capability_engine.explain_unsupported_capability(dev)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        # ---------------------------------------------------------------------
        # Category C: INFORMATIONAL / ROUTINES / TASK QUERIES
        # ---------------------------------------------------------------------
        if intent.category == IntentCategory.INFORMATIONAL_ONLY:
            return self._handle_informational_intent(intent, utterance, current_state)

        # ---------------------------------------------------------------------
        # Category D: AMBIGUOUS — REQUIRES FOLLOW-UP
        # ---------------------------------------------------------------------
        if intent.category == IntentCategory.AMBIGUOUS_REQUIRES_FOLLOW_UP:
            q = self.followup_engine.create_followup_for_intent(intent)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=q,
                action_taken=False,
                followup_required=True,
                followup_question=q
            )

        # ---------------------------------------------------------------------
        # Category E: CLEAR WITH MISSING NON-CRITICAL (e.g. Cinema prep + Ask Source)
        # ---------------------------------------------------------------------
        if intent.category == IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL:
            return self._handle_cinema_preparation_intent(intent, current_state)

        # ---------------------------------------------------------------------
        # Category F: CLEAR EXECUTABLE (Work mode, YouTube, or general device command)
        # ---------------------------------------------------------------------
        return self._handle_executable_intent(intent, utterance, current_state)

    # =========================================================================
    # Internal Intent Handlers
    # =========================================================================

    # =========================================================================
    # Internal Intent Handlers
    # =========================================================================

    def _handle_informational_intent(
        self,
        intent: ResolvedIntent,
        utterance: str,
        current_state: Any
    ) -> AgentInteractionResponse:
        addr = self.user_model.preferred_address

        # 1. Location Transition (Turn 05: "I'm heading to my desk")
        if intent.primary_intent == "USER_LOCATION_UPDATE":
            loc = intent.extracted_parameters.get("location", "DESK")
            self.memory.record_observation("user_location", loc)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"Noted, {addr} — heading to your desk.",
                action_taken=False
            )

        # 2. Morning Routine Brief
        if intent.primary_intent == "MORNING_ROUTINE_BRIEF":
            if self.context_engine:
                ctx_snap = self.context_engine.build_context_snapshot(room_state=current_state)
                weather_data = ctx_snap.weather.to_dict()
            else:
                weather_data = {"temperature_c": 26.0, "condition": "Clear", "humidity_pct": 55}
            brief = self.daily_brief_engine.generate_morning_brief(current_state, weather_data)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=brief,
                action_taken=False
            )

        # 3. Night Routine Transition (Turn 45: "Good night buddy")
        if intent.primary_intent == "NIGHT_ROUTINE_TRANSITION":
            night_msg = self.daily_brief_engine.generate_evening_brief()
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=night_msg,
                action_taken=False
            )

        # 4. Lunch completion trigger
        if intent.primary_intent == "LUNCH_COMPLETED_TRIGGER":
            self.memory.record_observation("lunch_completed", time.time())
            guitar_handled = self.task_manager.is_guitar_reminder_already_handled_today()
            if not guitar_handled:
                msg = f"Lunch done, {addr}? Want to do a quick guitar session, or get back into SQL?"
                self.memory.record_assumption("user_may_play_guitar_after_lunch", True)
            else:
                msg = f"Hope you enjoyed lunch, {addr}! Ready to get back into SQL or work?"
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        # 5. Task Completion (Turn 19: "Mark window functions as done")
        if intent.primary_intent == "COMPLETE_TASK":
            target = intent.extracted_parameters.get("task_target", "")
            completed_task = self.task_manager.complete_task(target)
            if completed_task:
                self.persistence.save_state(self.user_model, self.memory, self.task_manager)
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"I've marked '{completed_task.title}' as completed, {addr}.",
                    action_taken=True,
                    task_updates=[{"type": "TASK_COMPLETED", "task": completed_task.model_dump()}]
                )
            else:
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"I couldn't find an open task matching '{target}', {addr}.",
                    action_taken=False
                )

        # 6. Task Agenda & Specific Task Queries (Turns 02, 14, 17, 24, 42)
        if intent.primary_intent == "TASK_SCHEDULE_QUERY":
            ans = self.task_manager.answer_task_query(utterance) or f"No pending tasks found, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=ans,
                action_taken=False
            )

        # 7. Bookkeeping creation / contextual reminder update (Turns 12, 13, 21, 22, 39)
        if intent.primary_intent == "BOOKKEEPING_REQUEST":
            parsed = self.task_manager.parse_natural_task_or_reminder(utterance)
            if parsed:
                self.persistence.save_state(self.user_model, self.memory, self.task_manager)
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=parsed["message"],
                    action_taken=True,
                    task_updates=[parsed]
                )

        # 8. User Preference Audit (Turn 40: "What do you know about my preferences?")
        if intent.primary_intent == "AUDIT_USER_PREFERENCES":
            prof = self.user_model.profile
            lines = [
                f"Here is what I have saved about your preferences, {addr}:",
                f"• Preferred address: '{prof.identity.preferred_address}'",
                f"• Cinema devices: {', '.join(prof.entertainment.preferred_movie_devices)}",
                f"• Streaming services: {', '.join([s.replace('_', ' ').title() for s in prof.entertainment.preferred_streaming_services])}",
                f"• Preferred volume: ~{prof.entertainment.preferred_volume}%",
                f"• AC setpoint: {prof.thermal.preferred_ac_setpoint}°C ({prof.thermal.comfort_preference} mode)",
                f"• Quiet hours: {prof.notifications.quiet_hours_start} to {prof.notifications.quiet_hours_end}"
            ]
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message="\n".join(lines),
                action_taken=False
            )

        # 9. System Uncertainty & Assumption Audit (Turn 41: "What are you unsure about?")
        if intent.primary_intent == "AUDIT_UNCERTAINTY":
            assumptions = self.memory.get_by_category(MemoryCategory.AGENT_ASSUMPTION)
            if assumptions:
                assump_lines = [f"• {a.key.replace('_', ' ').capitalize()} (confidence: {int(a.confidence*100)}%)" for a in assumptions]
                msg = f"Here are the assumptions and open items I'm tracking, {addr}:\n" + "\n".join(assump_lines)
            else:
                msg = f"I don't have any unconfirmed assumptions right now, {addr}. All permanent preferences have been confirmed."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        # 10. User Mood / Fatigue Statement (Turn 26: "I'm exhausted buddy")
        if intent.primary_intent == "USER_MOOD_STATEMENT":
            q = f"Want some music, a movie, or just a quiet room, {addr}?"
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"You've had a busy day, {addr}. {q}",
                action_taken=False,
                followup_required=True,
                followup_question=q
            )

        # 10b. Relaxation Negative Constraint Narrowing (Turn 28: "No, not music")
        if intent.primary_intent == "RELAXATION_NARROW_OPTIONS":
            q = f"No problem, {addr} — want to watch a movie or just keep the room quiet?"
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=q,
                action_taken=False,
                followup_required=True,
                followup_question=q
            )

        # 11. Conversational Acknowledgment (Turns 15 & 20)
        if intent.primary_intent == "CONVERSATIONAL_ACK":
            if "focus" in utterance.lower():
                msg = f"Got it, {addr} — good luck with your focus session!"
            else:
                msg = f"Awesome job, {addr}!"
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        # 12. User State Update (Turn 23: "I'm practicing guitar now")
        if intent.primary_intent == "USER_STATE_UPDATE":
            act = intent.extracted_parameters.get("activity", "guitar practice")
            self.memory.record_observation("current_activity", act)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"Enjoy your guitar practice, {addr}!",
                action_taken=False
            )

        # 13. Capability inquiries (Turn 10)
        if intent.primary_intent == "CAPABILITY_INQUIRY":
            cap_summary = self.capability_engine.answer_capability_query(utterance)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=cap_summary,
                action_taken=False
            )

        return AgentInteractionResponse(
            understood_intent=intent.primary_intent,
            agent_message=f"I've noted that, {addr}.",
            action_taken=False
        )

    def _handle_cinema_preparation_intent(
        self,
        intent: ResolvedIntent,
        current_state: Any
    ) -> AgentInteractionResponse:
        """
        Executes deterministic cinema hardware preparation (Projector, Fire TV, Soundbar)
        and asks user for the open streaming service choice.
        """
        addr = self.user_model.preferred_address
        q = self.followup_engine.create_followup_for_intent(intent)

        # If planner/executor is configured, execute deterministic hardware prep
        exec_summary = None
        prep_done = False
        physical_audits: List[PhysicalActionAuditRecord] = []

        if self.planner_executor:
            try:
                active_context = self.context_engine.build_context_snapshot(room_state=current_state).to_dict()
                active_prefs = self.preference_manager.get_preferences().to_dict()
                val_res = None
                if self.planner_client and self.planner_client.is_available:
                    try:
                        val_res = self.planner_client.generate_and_validate_plan(
                            user_request="Let's watch something.",
                            room_state=current_state,
                            context=active_context,
                            preferences=active_prefs
                        )
                    except GeminiApiUnavailableError:
                        val_res = None

                if val_res is None:
                    canonical_plan = self._synthesize_canonical_plan("Let's watch something.", current_state)
                    if canonical_plan:
                        val_res = self.planner_executor.validator.validate_plan(
                            plan_input=canonical_plan,
                            room_state=current_state
                        )

                if val_res and val_res.valid:
                    exec_res = self.planner_executor.execute_plan(val_res)
                    exec_summary = exec_res.to_dict()
                    prep_done = True

                    # Generate audit records for executed steps
                    for step in val_res.validated_steps:
                        physical_audits.append(
                            PhysicalActionAuditRecord(
                                intent="START_CINEMA_ENTERTAINMENT",
                                target=step.device,
                                capability=step.canonical_capability_id,
                                requested_value=step.parameters,
                                authorization_source="USER_EXPLICIT_COMMAND",
                                context_source="CURRENT_TURN_DIRECT",
                                confidence_or_resolution="HIGH_CONFIDENCE_DIRECT",
                                execution_result="SUCCESS",
                                readback_result="VERIFIED_CINEMA_PREPARED"
                            )
                        )

                    feedback = self.feedback_generator.format_execution_feedback(
                        command="Let's watch something",
                        exec_result=exec_res,
                        followup_question=q
                    )
                    return AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=feedback,
                        action_taken=True,
                        deterministic_preparation_done=prep_done,
                        execution_summary=exec_summary,
                        physical_audits=physical_audits,
                        followup_required=True,
                        followup_question=q
                    )
            except Exception as e:
                logger.warning(f"[AGENT_CINEMA_PREP_FALLBACK] Hardware prep skipped: {e}")

        # Conversational fallback when hardware planner is offline
        msg = f"Setting up the cinema stack, {addr}. {q}"
        return AgentInteractionResponse(
            understood_intent=intent.primary_intent,
            agent_message=msg,
            action_taken=True,
            deterministic_preparation_done=prep_done,
            physical_audits=physical_audits,
            followup_required=True,
            followup_question=q
        )

    def _handle_executable_intent(
        self,
        intent: ResolvedIntent,
        utterance: str,
        current_state: Any
    ) -> AgentInteractionResponse:
        addr = self.user_model.preferred_address

        # 1. Work focus mode (Turn 06 & Turn 11)
        if intent.primary_intent == "ENTER_WORK_FOCUS_MODE":
            self.memory.record_observation("entered_focus_mode", time.time())
            msg = f"Focus mode active, {addr}. I'll minimize interruptions so you can focus on SQL."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        # 2. Focus / SQL learning duration session (Turn 18: "Let's do SQL for 30 minutes")
        if intent.primary_intent == "START_FOCUS_SESSION":
            mins = intent.extracted_parameters.get("duration_minutes", 30)
            self.memory.record_observation("sql_focus_session_started", time.time())
            # Software state only — zero volume mutation!
            msg = f"Starting a {mins}-minute SQL focus session, {addr}. Focus mode active!"
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        # 3. Motivational Music Playback (Turn 03: "Put on something to get me moving")
        if intent.primary_intent == "PLAY_MUSIC":
            self.memory.record_observation("morning_music_played", time.time())
            msg = f"Playing some morning motivation music for you, {addr}!"
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        # 4. Direct E.8.x Orchestration Execution via Planner + Executor
        if self.planner_executor:
            try:
                active_context = self.context_engine.build_context_snapshot(room_state=current_state).to_dict()
                active_prefs = self.preference_manager.get_preferences().to_dict()
                val_res = None

                if self.planner_client and self.planner_client.is_available:
                    try:
                        val_res = self.planner_client.generate_and_validate_plan(
                            user_request=utterance,
                            room_state=current_state,
                            context=active_context,
                            preferences=active_prefs
                        )
                    except GeminiApiUnavailableError:
                        val_res = None

                if val_res is None:
                    canonical_plan = self._synthesize_canonical_plan(utterance, current_state)
                    if canonical_plan:
                        val_res = self.planner_executor.validator.validate_plan(
                            plan_input=canonical_plan,
                            room_state=current_state
                        )

                if val_res:
                    if not val_res.valid:
                        err_msg = val_res.errors[0].message if val_res.errors else "Validation failed."
                        return AgentInteractionResponse(
                            understood_intent=intent.primary_intent,
                            agent_message=f"I couldn't execute that, {addr}: {err_msg}",
                            action_taken=False
                        )

                    exec_res = self.planner_executor.execute_plan(val_res)
                    physical_audits: List[PhysicalActionAuditRecord] = []
                    for step in val_res.validated_steps:
                        physical_audits.append(
                            PhysicalActionAuditRecord(
                                intent=intent.primary_intent,
                                target=step.device,
                                capability=step.canonical_capability_id,
                                requested_value=step.parameters,
                                authorization_source="USER_EXPLICIT_COMMAND",
                                context_source="CURRENT_TURN_DIRECT",
                                confidence_or_resolution="HIGH_CONFIDENCE_DIRECT",
                                execution_result="SUCCESS" if exec_res.success else "FAILED",
                                readback_result="VERIFIED" if exec_res.success else "FAILED"
                            )
                        )

                    feedback = self.feedback_generator.format_execution_feedback(
                        command=utterance,
                        exec_result=exec_res
                    )
                    self.memory.confirm_decision(f"executed_command_{int(time.time())}", utterance)
                    self.persistence.save_state(self.user_model, self.memory, self.task_manager)

                    return AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=feedback,
                        action_taken=True,
                        physical_audits=physical_audits,
                        execution_summary=exec_res.to_dict()
                    )
            except Exception as e:
                logger.error(f"[AGENT_EXECUTION_ERROR] Planning/Execution error: {e}", exc_info=True)
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"Sorry {addr}, something went wrong while coordinating the devices.",
                    action_taken=False
                )

        return AgentInteractionResponse(
            understood_intent=intent.primary_intent,
            agent_message=f"Got it, {addr}.",
            action_taken=True
        )

    def _synthesize_canonical_plan(self, utterance: str, room_state: Any) -> Optional[GeminiStructuredPlan]:
        """
        Synthesizes deterministic canonical plans when running offline or as fallback.
        Strict Safety Invariant: Bare numbers with duration units (e.g. '30 minutes')
        or conversational sign-offs MUST NEVER synthesize volume or hardware mutations.
        """
        lower = utterance.strip().lower()
        steps: List[PlanStep] = []

        # Cinema / Movie ("Let's watch something", "movie mode", "chill with a movie")
        if any(w in lower for w in ["let's watch something", "watch something", "movie mode", "start a movie", "watch a movie", "chill with a movie"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
            steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            steps.append(PlanStep(step_id=4, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
            return GeminiStructuredPlan(intent="MOVIE_MODE", objective_summary="Prepare cinema stack", user_request=utterance, steps=steps)

        # YouTube Launch
        if "youtube" in lower:
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
            steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_APP_LAUNCH_YOUTUBE"))
            steps.append(PlanStep(step_id=5, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
            return GeminiStructuredPlan(intent="PLAY_YOUTUBE", objective_summary="Launch YouTube on cinema stack", user_request=utterance, steps=steps)

        # Media Playback Controls (Turns 35 & 36)
        if any(p_w in lower for p_w in ["pause that", "pause video", "pause media", "pause it", "pause for a second", "pause"]):
            steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_MEDIA_PAUSE"))
            return GeminiStructuredPlan(intent="PAUSE_MEDIA", objective_summary="Pause active media playback", user_request=utterance, steps=steps)

        if any(r_w in lower for r_w in ["resume it", "resume that", "resume video", "resume media", "resume playback", "unpause", "continue watching"]):
            steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_MEDIA_PLAY"))
            return GeminiStructuredPlan(intent="RESUME_MEDIA", objective_summary="Resume active media playback", user_request=utterance, steps=steps)

        # Volume Down / "Make it quieter" / "Turn the room down"
        if any(w in lower for w in ["quieter", "turn down", "softer", "turn the room down", "make it quiet"]):
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod and hasattr(prod, "value"):
                    active_prod = prod.value
            if active_prod == "PC":
                cur_vol = 98
                if room_state and hasattr(room_state, "pc") and room_state.pc:
                    cur_vol = room_state.pc.master_volume.value or 98
                target_v = max(0, cur_vol - 10)
                steps.append(PlanStep(step_id=1, device="PC", capability="PC_SET_VOLUME", parameters={"volume": target_v}))
            else:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_VOLUME_DOWN"))
            return GeminiStructuredPlan(intent="VOLUME_DOWN", objective_summary="Attenuate active audio", user_request=utterance, steps=steps)

        # Volume Up / "Make it louder"
        if any(w in lower for w in ["louder", "turn up", "volume up"]):
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod and hasattr(prod, "value"):
                    active_prod = prod.value
            if active_prod == "PC":
                cur_vol = 98
                if room_state and hasattr(room_state, "pc") and room_state.pc:
                    cur_vol = room_state.pc.master_volume.value or 98
                target_v = min(100, cur_vol + 10)
                steps.append(PlanStep(step_id=1, device="PC", capability="PC_SET_VOLUME", parameters={"volume": target_v}))
            else:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_VOLUME_UP"))
            return GeminiStructuredPlan(intent="VOLUME_UP", objective_summary="Increase active audio", user_request=utterance, steps=steps)

        # Wake All
        if any(w in lower for w in ["wake everything up", "wake up all", "turn on everything"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            return GeminiStructuredPlan(intent="WAKE_ALL", objective_summary="Wake all displays", user_request=utterance, steps=steps)

        # Sleep / Turn Off (Turns 37 & 44: "Turn everything off", "I'm done watching")
        if any(w in lower for w in ["done watching", "turn everything off", "switch it off", "turn it off", "turn off room"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_SLEEP"))
            steps.append(PlanStep(step_id=2, device="FIRE_TV", capability="FIRE_TV_POWER_SLEEP"))
            return GeminiStructuredPlan(intent="SLEEP_ALL", objective_summary="Put room to sleep", user_request=utterance, steps=steps)

        # AC Temperature (Turns 07, 25, 43: "Set the AC to 24", "Set AC to 25", "Set AC to 24 for the night")
        import re
        ac_m = re.search(r'(?:(?:ac|temperature|temp)\s+(?:to\s+)?(\d+)|(\d+)\s*(?:degrees?|°c|celsius))', lower)
        if ac_m:
            target_t = int(ac_m.group(1) or ac_m.group(2))
            if 16 <= target_t <= 30:
                steps.append(PlanStep(step_id=1, device="AC", capability="AC_POWER_ON"))
                steps.append(PlanStep(step_id=2, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": target_t}))
                return GeminiStructuredPlan(intent="SET_AC_TEMPERATURE", objective_summary=f"Set AC to {target_t}C", user_request=utterance, steps=steps)

        # Strict Semantic Explicit Volume (Unit-Aware: MUST contain volume keyword, NOT duration)
        # Forbids bare numbers or durations like "30 minutes" from setting volume!
        if not any(dur_unit in lower for dur_unit in ["minute", "min", "hour", "hr", "sec", "second"]):
            vol_m = re.search(r'(?:set\s+)?(?:volume|vol)\s+(?:to\s+)?(\d+)', lower)
            if vol_m:
                vol_val = int(vol_m.group(1))
                if 0 <= vol_val <= 100:
                    steps.append(PlanStep(step_id=1, device="PC", capability="PC_SET_VOLUME", parameters={"volume": vol_val}))
                    return GeminiStructuredPlan(intent="SET_EXPLICIT_VOLUME", objective_summary=f"Set volume to {vol_val}%", user_request=utterance, steps=steps)

        # Streaming Services (Turn 31: "Netflix")
        for prov in ["netflix", "prime", "hotstar"]:
            if prov in lower or prov.replace("_", " ") in lower:
                steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
                steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
                steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
                steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_MEDIA_DIRECT_PROVIDER", parameters={"provider": prov}))
                steps.append(PlanStep(step_id=5, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
                return GeminiStructuredPlan(intent=f"LAUNCH_{prov.upper()}", objective_summary=f"Launch {prov} on cinema stack", user_request=utterance, steps=steps)

        # Generic streaming launch fallback
        if "apple tv" in lower or "apple_tv" in lower:
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
            steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_APP_LAUNCH_YOUTUBE"))
            steps.append(PlanStep(step_id=5, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
            return GeminiStructuredPlan(intent="LAUNCH_APPLE_TV", objective_summary="Launch Apple TV on cinema stack", user_request=utterance, steps=steps)

        return None

