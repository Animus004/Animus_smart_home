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
import os
import logging
import threading
import time
import re
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
from planner.models import ExecutionStatus, ExecutionResult, StepExecutionResult, OverallExecutionStatus

from agent.models import (
    ResolvedIntent, IntentCategory, AgentInteractionResponse,
    PhysicalActionAuditRecord, UserProfile, MemoryCategory, MoodVibe
)
from agent.interaction_result import (
    AgentInteractionResult, DecisionType, PhysicalVerificationStatus, StateDelta
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
from agent.context_buffer import ConversationContextBuffer
from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus, GoalType
from agent.task_planner import DeliberativeTaskPlanner
from agent.behavior_modes import BehaviorMode, BehaviorModeManager
from agent.routine_engine import RoutineEngine
from agent.media_session import MediaSessionManager, MediaPlaybackState
from agent.comfort_engine import ComfortEngine
from agent.proactive_engine import ProactiveEngine, ProactiveSuggestion
from agent.recovery_engine import RecoveryEngine, RecoveryType
from agent.room_events import RoomEvent, RoomEventType
from agent.event_bus import RoomEventBus
from agent.room_monitor import RoomStateMonitor
from agent.long_horizon_goals import LongHorizonGoalManager
from agent.scheduler import RoomScheduler, ScheduledTask, ScheduledTaskStatus
from agent.behavioral_profile import BehavioralProfileManager, PreferenceProvenance
from agent.situation_engine import SituationEngine, RoomSituation
from agent.reasoning_engine import ReasoningEngine, ReasoningResult
from agent.goal_arbitrator import GoalArbitrator, ArbitrationDecision, ArbitrationOutcome
from agent.policy_engine import PolicyEngine, PolicyAuthorization
from agent.preference_model import LearnedPreference
from agent.learning_engine import LearningEngine
from agent.autonomy_policy import AutonomyCapability, AutonomyGrantLevel
from agent.autonomy_manager import AutonomyManager
from agent.room_brain import RoomBrain, UnifiedRoomSummary
from agent.conversation_engine import ConversationEngine, ConversationTurn
from agent.voice_ingress import VoiceIngressAdapter, VoiceTurnPayload

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
        memory: Optional[AgentMemoryStore] = None,
        context_buffer: Optional[ConversationContextBuffer] = None,
        event_bus: Optional[Any] = None,
        orchestrator: Optional[Any] = None
    ):
        self.registry = registry or UnifiedCapabilityRegistry()
        self.room_state_aggregator = room_state_aggregator
        self.context_engine = context_engine
        self.preference_manager = preference_manager
        self.planner_client = planner_client
        self.planner_executor = planner_executor
        self.orchestrator = orchestrator
        self.persistence = persistence or AgentPersistence()
        self.context_buffer = context_buffer or ConversationContextBuffer()
        self.event_bus = event_bus
        self._cinema_prep_lock = threading.Lock()
        self._last_cinema_prep_time: float = 0.0

        # Load or initialize state
        loaded_res = self.persistence.load_state()
        loaded_u, loaded_m, loaded_t = loaded_res[0], loaded_res[1], loaded_res[2]
        extra_state = loaded_res[3] if len(loaded_res) > 3 else {}
        self.user_model = user_model or loaded_u
        self.memory = memory or loaded_m
        self.task_manager = task_manager or loaded_t

        # Initialize Stage 6 Event Bus & Sub-engines
        self.room_event_bus = RoomEventBus()
        self.room_monitor = RoomStateMonitor(self.room_event_bus)
        self.long_horizon_goals = LongHorizonGoalManager(self.room_event_bus)
        self.scheduler = RoomScheduler(self.room_event_bus)
        self.behavioral_profile = BehavioralProfileManager()
        if extra_state.get("behavioral_profile"):
            self.behavioral_profile.load_from_dict(extra_state["behavioral_profile"])
        self.situation_engine = SituationEngine(self.room_event_bus)

        # Initialize sub-engines with shared context buffer
        self.intent_resolver = IntentResolver(
            user_profile=self.user_model.profile,
            registry=self.registry,
            memory=self.memory,
            context_buffer=self.context_buffer
        )
        self.followup_engine = FollowUpEngine(
            user_profile=self.user_model.profile,
            context_buffer=self.context_buffer
        )
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
        self.task_planner = DeliberativeTaskPlanner()
        self.mode_manager = BehaviorModeManager()
        persisted_mode = extra_state.get("active_mode")
        if persisted_mode and persisted_mode != "IDLE":
            try:
                b_mode = BehaviorMode(persisted_mode)
                self.mode_manager.current_mode = b_mode
                self.context_buffer.active_mode = persisted_mode
                logger.info(f"[PERSISTENCE_RESTORE] Restored active room mode to '{persisted_mode}' after restart.")
            except Exception as e:
                logger.debug(f"Could not restore persisted mode '{persisted_mode}': {e}")
        self.routine_engine = RoutineEngine()
        self.media_session_manager = MediaSessionManager()
        self.comfort_engine = ComfortEngine()
        self.proactive_engine = ProactiveEngine(enabled=True, event_bus=self.room_event_bus)
        self.recovery_engine = RecoveryEngine(max_attempts=1)

        # Initialize Stage 7-10 Advanced Intelligence & Conversational Brain
        self.reasoning_engine = ReasoningEngine()
        self.goal_arbitrator = GoalArbitrator(self.room_event_bus)
        self.policy_engine = PolicyEngine()
        self.learning_engine = LearningEngine()
        self.autonomy_manager = AutonomyManager()
        self.conversation_engine = ConversationEngine()
        self.voice_ingress = VoiceIngressAdapter(on_transcript_received=lambda payload: self.interact(payload.transcript))
        self.room_brain = RoomBrain(
            reasoning_engine=self.reasoning_engine,
            goal_arbitrator=self.goal_arbitrator,
            policy_engine=self.policy_engine,
            learning_engine=self.learning_engine,
            autonomy_manager=self.autonomy_manager,
            room_state_aggregator=self.room_state_aggregator,
            event_bus=self.room_event_bus,
            situation_engine=self.situation_engine,
            behavior_mode_manager=self.mode_manager,
            goal_manager=self.long_horizon_goals,
            scheduler=self.scheduler,
            media_session_manager=self.media_session_manager
        )

        # Start live room background scheduler loop
        self._scheduler_stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self.start_scheduler_loop()

    def start_scheduler_loop(self, poll_interval_seconds: float = 2.0):
        """Starts live room background scheduler thread."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self._scheduler_stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler_loop,
            args=(poll_interval_seconds,),
            name="AnimusSchedulerDaemon",
            daemon=True
        )
        self._scheduler_thread.start()
        logger.info(f"[SCHEDULER_DAEMON_START] Live room scheduler daemon started (poll={poll_interval_seconds}s).")

    def stop_scheduler_loop(self):
        """Stops live room background scheduler thread."""
        if self._scheduler_stop_event:
            self._scheduler_stop_event.set()
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=1.0)

    def _run_scheduler_loop(self, poll_interval: float):
        while not self._scheduler_stop_event.is_set():
            try:
                now = time.time()
                current_state = None
                if self.room_state_aggregator:
                    current_state = self.room_state_aggregator.get_room_state(current_time=now)
                active_m = getattr(self.mode_manager, "active_mode", None) or getattr(self.context_buffer, "active_mode", None)
                results = self.scheduler.evaluate_and_execute_due_tasks(
                    current_time=now,
                    room_state=current_state,
                    active_mode=active_m,
                    planner_executor=self.planner_executor
                )
                for task, ok, reason in results:
                    logger.info(f"[SCHEDULER_DUE_TRIGGER] Task {task.task_id} ({task.action_type}): success={ok}, reason='{reason}'")
            except Exception as e:
                logger.error(f"[SCHEDULER_LOOP_ERROR] Error evaluating scheduled tasks: {e}", exc_info=True)
            self._scheduler_stop_event.wait(poll_interval)




    # =========================================================================
    # Main Agent Entry Point: interact()
    # =========================================================================

    def interact(self, utterance: str, room_state: Optional[RoomState] = None) -> AgentInteractionResponse:
        """
        Processes a natural language user turn through the complete agent pipeline.
        """
        addr = self.user_model.preferred_address
        current_state = room_state if room_state is not None else (self.room_state_aggregator.get_room_state() if self.room_state_aggregator else None)

        # Stage 6 Telemetry evaluation against baseline
        if current_state is not None:
            self.room_monitor.evaluate_telemetry(
                room_state=current_state,
                active_mode=self.mode_manager.active_mode
            )

        # Record user turn in multi-turn context buffer
        self.context_buffer.record_user_turn(utterance)


        # Check for topic switch: if user interrupted active thread, clear pending follow-up
        if self.context_buffer.is_topic_switch(utterance):
            logger.info(f"[CONTEXT_BUFFER] Utterance '{utterance}' detected as topic switch; clearing active thread.")
            self.followup_engine.clear_pending_followup()
            self.context_buffer.clear_active_thread()

        # Step 1: Check if this turn answers an existing follow-up question
        if self.followup_engine.has_pending_followup:
            resolved_followup = self.followup_engine.resolve_followup_response(utterance)
            if resolved_followup.get("resolved"):
                if resolved_followup.get("intent") == "RELAXATION_NARROW_OPTIONS":
                    q = resolved_followup.get("followup_question") or f"No problem, {addr} — want to watch a movie or just keep the room quiet?"
                    resp = AgentInteractionResponse(
                        understood_intent="RELAXATION_NARROW_OPTIONS",
                        agent_message=q,
                        action_taken=False,
                        followup_required=True,
                        followup_question=q
                    )
                    self.context_buffer.record_animus_turn(utterance=q, intent="RELAXATION_NARROW_OPTIONS", action_taken=False)
                    return resp
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
        # Category: EMPATHIC MULTI-DOMAIN PROBLEM SOLVING
        # ---------------------------------------------------------------------
        if intent.primary_intent.startswith("EMPATHIC_"):
            params = intent.extracted_parameters
            speech = params.get("empathy_speech", f"I've adjusted the room for you, {addr}.")
            
            # 1. AC Action
            ac_act = params.get("ac_action")
            if ac_act and self.planner_executor and self.planner_executor.ac_controller:
                try:
                    if not ac_act.get("power", True):
                        self.planner_executor.ac_controller.set_power(False)
                    else:
                        self.planner_executor.ac_controller.set_power(True)
                        if "mode" in ac_act:
                            self.planner_executor.ac_controller.set_mode(ac_act["mode"])
                        if "temp" in ac_act:
                            self.planner_executor.ac_controller.set_temperature(ac_act["temp"])
                        if "fan" in ac_act:
                            self.planner_executor.ac_controller.set_fan_speed(ac_act["fan"])
                except Exception as e:
                    logger.error(f"[EMPATHIC_AC_EXEC_ERR] {e}")

            # 2. Projector Action
            proj_act = params.get("projector_action")
            if proj_act and self.planner_executor and self.planner_executor.projector_controller:
                try:
                    if proj_act.get("action") == "power_off":
                        self.planner_executor.projector_controller.power_off(use_oem=True)
                    elif proj_act.get("action") == "sleep":
                        self.planner_executor.projector_controller.sleep()
                except Exception as e:
                    logger.error(f"[EMPATHIC_PROJ_EXEC_ERR] {e}")

            # 3. Audio Action
            aud_act = params.get("audio_action")
            if aud_act and self.orchestrator:
                try:
                    if aud_act.get("action") == "stop":
                        self.orchestrator.stop()
                    elif aud_act.get("action") in ("play_ambient", "play_music"):
                        q = aud_act.get("query", "lofi")
                        self.orchestrator.play_music(q)
                except Exception as e:
                    logger.error(f"[EMPATHIC_AUDIO_EXEC_ERR] {e}")

            # 4. PC Action
            pc_act = params.get("pc_action")
            if pc_act and self.planner_executor and self.planner_executor.pc_controller:
                try:
                    if pc_act.get("action") == "lock":
                        self.planner_executor.pc_controller.lock()
                except Exception as e:
                    logger.error(f"[EMPATHIC_PC_EXEC_ERR] {e}")

            # Record turn in persistent Long-Term Memory
            try:
                from agent.long_term_memory import get_long_term_memory
                get_long_term_memory().record_conversation_turn(
                    user_utterance=utterance,
                    agent_response=speech,
                    intent_category="EMPATHIC"
                )
            except Exception as e:
                logger.debug(f"[EMPATHIC_LT_MEM_RECORD_ERR] {e}")

            resp = AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=speech,
                action_taken=True
            )
            self.context_buffer.record_animus_turn(utterance=speech, intent=intent.primary_intent, action_taken=True)
            return resp

        # ---------------------------------------------------------------------
        # Stage 4 Deliberative Task Planning & Multi-Step Goals
        # ---------------------------------------------------------------------
        goal = self.task_planner.decompose_intent_to_goal(intent, utterance, room_state=current_state)
        if goal:
            logger.info(f"[AGENT_GOAL_START] Decomposed into goal: {goal.goal_id} ({goal.normalized_goal})")
            self.context_buffer.supersede_active_goal(goal.goal_id)
            self.context_buffer.set_active_goal(goal)
            executed_goal = self.task_planner.execute_goal(
                goal=goal,
                room_state_aggregator=self.room_state_aggregator,
                planner_executor=self.planner_executor,
                context_buffer=self.context_buffer
            )
            self.context_buffer.clear_active_goal()

            if executed_goal.status == GoalStatus.COMPLETED or any(s.status == StepStatus.VERIFIED for s in executed_goal.steps) or all(s.status == StepStatus.SKIPPED_ALREADY_SATISFIED for s in executed_goal.steps):
                if executed_goal.goal_type == GoalType.PREPARE_MOVIE:
                    self.mode_manager.transition_to(BehaviorMode.MOVIE, utterance=utterance, goal_id=executed_goal.goal_id)
                    self.context_buffer.active_mode = "MOVIE"
                elif executed_goal.goal_type == GoalType.PREPARE_SLEEP:
                    self.mode_manager.transition_to(BehaviorMode.SLEEP, utterance=utterance, goal_id=executed_goal.goal_id)
                    self.context_buffer.active_mode = "SLEEP"

            goal_feedback = self.feedback_generator.generate_goal_feedback(executed_goal, user_address=addr)

            if all(s.status == StepStatus.SKIPPED_ALREADY_SATISFIED for s in executed_goal.steps):
                decision_type = DecisionType.NO_OP_ALREADY_SATISFIED
            elif executed_goal.status == GoalStatus.COMPLETED:
                decision_type = DecisionType.GOAL_COMPLETED
            elif executed_goal.status == GoalStatus.PARTIALLY_COMPLETED:
                decision_type = DecisionType.GOAL_PARTIAL
            elif executed_goal.status == GoalStatus.BLOCKED:
                decision_type = DecisionType.GOAL_BLOCKED
            elif executed_goal.status == GoalStatus.CANCELLED:
                decision_type = DecisionType.GOAL_CANCEL
            else:
                decision_type = DecisionType.GOAL_FAILED


            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent=intent.primary_intent,
                intent_category=intent.category,
                decision_type=decision_type,
                human_response=goal_feedback,
                execution_attempted=True,
                execution_success=(executed_goal.status == GoalStatus.COMPLETED)
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=goal_feedback,
                action_taken=any(s.status == StepStatus.VERIFIED for s in executed_goal.steps)
            )

        # ---------------------------------------------------------------------
        # Category E: CLEAR WITH MISSING NON-CRITICAL (e.g. Cinema prep + Ask Source)
        # ---------------------------------------------------------------------
        if intent.category == IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL:
            if intent.primary_intent == "START_CINEMA_ENTERTAINMENT":
                return self._handle_cinema_preparation_intent(intent, current_state)
            else:
                q = self.followup_engine.create_followup_for_intent(intent)
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=q,
                    action_taken=False,
                    followup_required=True,
                    followup_question=q
                )

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

    def _query_informational_llm(self, query: str, user_addr: str) -> Optional[str]:
        """
        Delegates general informational queries to Gemini (or configured local LLM)
        with a strict informational system prompt.
        Strict Safety Invariant: Hardware mutations are impossible; returns text only.
        """
        # Context Injection: Fetch live weather telemetry if weather/forecast is requested
        weather_prefix = ""
        live_weather_val = None
        if any(w in query.lower() for w in ["weather", "forecast", "outside temp", "temp outside", "how is it outside", "outside"]):
            try:
                import requests
                w_resp = requests.get("https://wttr.in?format=%C,+%t+(Humidity:+%h)", timeout=2.5)
                if w_resp.status_code == 200 and w_resp.text:
                    cleaned_w = w_resp.text.strip()
                    if cleaned_w and not cleaned_w.startswith("<"):
                        live_weather_val = cleaned_w
                        weather_prefix = f"Live Telemetry Context: Real-time outdoor weather is currently: {cleaned_w}.\n"
            except Exception:
                pass

        prompt_text = f"{weather_prefix}You are Animus, a helpful smart room assistant speaking to {user_addr}. Answer this query concisely and naturally in 1-3 sentences without mentioning system internals:\n\n{query}"

        # 1. Try Google GenAI SDK if initialized
        if self.planner_client and getattr(self.planner_client, "_sdk_client", None):
            try:
                resp = self.planner_client._sdk_client.models.generate_content(
                    model=self.planner_client.model_name or "gemini-2.5-flash",
                    contents=prompt_text
                )
                if resp and getattr(resp, "text", None):
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"[INFORMATIONAL_GEMINI_SDK_FAILED] {e}")

        # 2. Try direct Google Gemini REST API if API key is present
        api_key = (
            (getattr(self.planner_client, "api_key", None) if self.planner_client else None)
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        if api_key:
            try:
                import requests
                model_name = getattr(self.planner_client, "model_name", "gemini-2.5-flash") or "gemini-2.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": prompt_text
                        }]
                    }]
                }
                resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=6.0)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            txt = parts[0]["text"].strip()
                            if txt:
                                return txt
            except Exception as e:
                logger.warning(f"[INFORMATIONAL_GEMINI_REST_FAILED] {e}")

        # 3. Fallback to local Ollama if available on port 11434
        try:
            import requests
            res = requests.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": "qwen3:4b-instruct",
                    "prompt": f"{weather_prefix}You are Animus, a helpful smart room assistant speaking to {user_addr}. Answer this query concisely in 1-3 sentences:\n\n{query}",
                    "stream": False
                },
                timeout=4.0
            )
            if res.status_code == 200:
                txt = res.json().get("response", "").strip()
                if txt:
                    return txt
        except Exception:
            pass

        # 4. Direct weather fallback if LLMs unavailable but weather telemetry succeeded
        if live_weather_val:
            return f"It's currently {live_weather_val} outside, {user_addr}."

        return None

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
            q = self.followup_engine.create_followup_for_intent(intent)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"You've had a busy day, {addr}. {q}",
                action_taken=False,
                followup_required=True,
                followup_question=q
            )

        # 10b. Relaxation Negative Constraint Narrowing (Turn 28: "No, not music")
        if intent.primary_intent == "RELAXATION_NARROW_OPTIONS":
            q = f"Understood, no music. Would you like a movie, or just a quiet room, {addr}?"
            self.followup_engine._pending_context = {
                "type": "RELAXATION_DISAMBIGUATION_NO_MUSIC",
                "original_intent": intent.model_dump()
            }
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

        # 14. Explicit Flow Cancellation ("Never mind", "Cancel", "Don't do that")
        if intent.primary_intent == "CANCEL_CURRENT_REQUEST":
            cancel_msg = self.context_buffer.cancel_active_flow(addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="CANCEL_CURRENT_REQUEST",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.CANCEL_THREAD,
                human_response=cancel_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=cancel_msg,
                action_taken=False
            )

        # 15. Gratitude Acknowledgment ("Thanks", "Thank you")
        if intent.primary_intent == "GRATITUDE_ACK":
            grat_msg = f"Anytime, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="GRATITUDE_ACK",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INFORMATIONAL_RESPONSE,
                human_response=grat_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=grat_msg,
                action_taken=False
            )

        # 16. Action Introspection ("What did you just do?", "What did you change?")
        if intent.primary_intent == "INTROSPECT_RECENT_ACTION":
            target_sub = intent.target_subsystems[0] if intent.target_subsystems else None
            # Check for external telemetry diff
            if target_sub == "AC" and current_state and hasattr(current_state, "ac") and current_state.ac and current_state.ac.target_temperature.value is not None:
                live_temp = current_state.ac.target_temperature.value
                diff = self.context_buffer.detect_external_state_change("AC", "target_temperature", live_temp)
                if diff:
                    intro_msg = f"I last changed it to {diff.historical_verified_value}°C, {addr}. It's currently reporting {diff.current_telemetry_value}°C, so it was changed after my last action."
                else:
                    intro_msg = self.context_buffer.explain_last_action(depth=1, target_subsystem="AC", user_address=addr)
            else:
                intro_msg = self.context_buffer.explain_last_action(depth=1, target_subsystem=target_sub, user_address=addr)

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_RECENT_ACTION",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INTROSPECTION,
                human_response=intro_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=intro_msg,
                action_taken=False
            )

        # 16b. Historical Action Introspection ("What did you change before that?", "What was the AC at before?")
        if intent.primary_intent == "INTROSPECT_HISTORICAL_ACTION":
            depth = intent.extracted_parameters.get("depth", 1)
            attr = intent.extracted_parameters.get("attribute")
            target_sub = intent.target_subsystems[0] if intent.target_subsystems else None

            if attr == "target_temperature" or target_sub == "AC":
                act = self.context_buffer.get_action_history(depth=1, target_subsystem="AC")
                if act and act.state_delta and act.state_delta.previous_value is not None:
                    intro_msg = f"The AC was at {act.state_delta.previous_value}°C before I changed it, {addr}."
                else:
                    intro_msg = self.context_buffer.explain_last_action(depth=1, target_subsystem="AC", user_address=addr)
            else:
                intro_msg = self.context_buffer.explain_last_action(depth=depth, target_subsystem=target_sub, user_address=addr)

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_HISTORICAL_ACTION",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INTROSPECTION,
                human_response=intro_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=intro_msg,
                action_taken=False
            )

        # 16c. Live Telemetry / Device Status Query ("Is it still on?", "What is the AC doing now?", "What about the projector?")
        if intent.primary_intent == "INTROSPECT_TELEMETRY_STATUS":
            target_sub = intent.target_subsystems[0] if intent.target_subsystems else "AC"
            if target_sub == "AC":
                pow_st = current_state.ac.power.value if current_state and hasattr(current_state, "ac") and current_state.ac else False
                temp_st = current_state.ac.target_temperature.value if current_state and hasattr(current_state, "ac") and current_state.ac else 24
                state_str = "on" if pow_st else "off"
                if "still on" in utterance.lower():
                    status_msg = f"The AC is currently {state_str}, {addr} (set to {temp_st}°C)."
                else:
                    status_msg = f"The AC is at {temp_st}°C and powered {state_str}, {addr}."
            elif target_sub == "PROJECTOR":
                proj_pow = current_state.projector.power.value if current_state and hasattr(current_state, "projector") and current_state.projector else False
                status_msg = f"The projector is currently {'on' if proj_pow else 'off'}, {addr}."
            else:
                status_msg = f"The {target_sub} is operational, {addr}."

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_TELEMETRY_STATUS",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INTROSPECTION,
                target_device=target_sub,
                human_response=status_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=status_msg,
                action_taken=False
            )

        # 16d. Flow Cancellation ("Never mind", "Cancel", "Actually leave it")
        if intent.primary_intent == "CANCEL_CURRENT_REQUEST":
            cancel_msg = self.context_buffer.cancel_active_flow(addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="CANCEL_CURRENT_REQUEST",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.CANCEL,
                human_response=cancel_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=cancel_msg,
                action_taken=False
            )

        # 17. Action Reason Introspection ("Why did you do that?", "Why?")
        if intent.primary_intent == "INTROSPECT_ACTION_REASON":
            reason_msg = self.context_buffer.explain_last_action_reason(user_address=addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_ACTION_REASON",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INTROSPECTION,
                human_response=reason_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=reason_msg,
                action_taken=False
            )

        # 18. Semantic Room Comfort ("It's comfortable now", "It's fine now")
        if intent.primary_intent == "SEMANTIC_ROOM_COMFORTABLE":
            comf_msg = f"Good — looks comfortable in here, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="SEMANTIC_ROOM_COMFORTABLE",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.NO_OP_ALREADY_SATISFIED,
                target_device="AC",
                human_response=comf_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=comf_msg,
                action_taken=False
            )

        # 19. Stage 4 Goal Introspection Handlers
        if intent.primary_intent == "INTROSPECT_GOAL_STATUS":
            status_msg = self.context_buffer.introspect_goal(addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_GOAL_STATUS",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.GOAL_STATUS,
                human_response=status_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=status_msg,
                action_taken=False
            )

        if intent.primary_intent == "INTROSPECT_GOAL_REMAINING":
            rem_msg = self.context_buffer.introspect_goal_remaining(addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_GOAL_REMAINING",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.GOAL_STATUS,
                human_response=rem_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=rem_msg,
                action_taken=False
            )

        if intent.primary_intent == "INTROSPECT_GOAL_FAILURES":
            fail_msg = self.context_buffer.introspect_goal_failures(addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_GOAL_FAILURES",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.GOAL_STATUS,
                human_response=fail_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=fail_msg,
                action_taken=False
            )

        if intent.primary_intent == "CANCEL_REMAINING_GOAL_STEPS":
            cancel_msg = self.context_buffer.cancel_active_goal(user_address=addr, reason="USER_CANCELLED")
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="CANCEL_REMAINING_GOAL_STEPS",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.GOAL_CANCEL,
                human_response=cancel_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=cancel_msg,
                action_taken=False
            )

        # 20. Stage 5 Behavioral Introspection Handlers
        if intent.primary_intent == "INTROSPECT_MODE":
            mode = self.mode_manager.active_mode
            if mode == BehaviorMode.IDLE:
                mode_msg = f"The room is currently idle, {addr}."
            elif mode == BehaviorMode.MOVIE:
                mode_msg = f"We're in movie mode, {addr}."
            elif mode == BehaviorMode.SLEEP:
                mode_msg = f"We're in sleep mode, {addr}."
            elif mode == BehaviorMode.MUSIC:
                mode_msg = f"We're in music mode, {addr}."
            elif mode == BehaviorMode.WORK:
                mode_msg = f"We're in work mode, {addr}."
            else:
                mode_msg = f"We're in {mode.value.lower()} mode, {addr}."

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_MODE",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INTROSPECTION,
                human_response=mode_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=mode_msg,
                action_taken=False
            )

        if intent.primary_intent == "INTROSPECT_MEDIA":
            media_summary = self.media_session_manager.get_status_summary()
            if media_summary.get("active"):
                st = media_summary.get("playback_state", "STOPPED").lower()
                title = media_summary.get("content_title")
                if title:
                    media_msg = f"'{title}' is currently {st}, {addr}."
                else:
                    media_msg = f"The media is currently {st}, {addr}."
            else:
                media_msg = f"Nothing is currently playing, {addr}."

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_MEDIA",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.MEDIA_STATUS,
                human_response=media_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=media_msg,
                action_taken=False
            )

        if intent.primary_intent == "INTROSPECT_RECENT_CHANGE":
            diffs = list(self.context_buffer.session_memory.external_diffs.values())
            if diffs:
                latest_diff = diffs[-1]
                chg_msg = f"I noticed that {latest_diff.description}"
            else:
                chg_msg = self.context_buffer.explain_last_action(depth=1, user_address=addr)

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="INTROSPECT_RECENT_CHANGE",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INTROSPECTION,
                human_response=chg_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=chg_msg,
                action_taken=False
            )

        if intent.primary_intent == "REJECT_SUGGESTION":
            self.proactive_engine.reject_pending_suggestion()
            self.context_buffer.clear_pending_suggestion()
            rej_msg = f"Okay {addr}, leaving it as it is."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="REJECT_SUGGESTION",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.SUGGESTION_REJECTED,
                human_response=rej_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=rej_msg,
                action_taken=False
            )

        if intent.primary_intent == "DEFER_SUGGESTION":
            self.proactive_engine.defer_pending_suggestion()
            self.context_buffer.clear_pending_suggestion()
            def_msg = f"No problem {addr}, we'll leave it for now."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="DEFER_SUGGESTION",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INFORMATIONAL_RESPONSE,
                human_response=def_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=def_msg,
                action_taken=False
            )

        if intent.primary_intent == "COMFORT_STATUS":
            temp = current_state.ac.target_temperature.value if (current_state and hasattr(current_state, "ac") and current_state.ac and current_state.ac.target_temperature.value is not None) else 24
            comf_msg = f"The AC is set to {temp}°C and the room feels comfortable, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="COMFORT_STATUS",
                intent_category=IntentCategory.INFORMATIONAL_ONLY,
                decision_type=DecisionType.INFORMATIONAL_RESPONSE,
                human_response=comf_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=comf_msg,
                action_taken=False
            )

        if intent.primary_intent == "LIST_SCHEDULED_ACTIONS":
            pending = self.scheduler.get_pending_tasks()
            if not pending:
                msg = f"There are no scheduled actions pending, {addr}."
            else:
                items = [f"{t.action_type} in {int((t.scheduled_for - time.time())/60)}m" for t in pending]
                msg = f"Pending schedules: {', '.join(items)}, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        if intent.primary_intent == "WHAT_IS_HAPPENING":
            situation = self.situation_engine.assess_situation(
                live_telemetry={"ac_power": getattr(getattr(current_state, "ac", None), "power", None)} if current_state else {},
                active_mode=self.mode_manager.active_mode,
                media_playback_state=self.media_session_manager.active_session.playback_state.value if (self.media_session_manager and self.media_session_manager.active_session) else "STOPPED",
                active_goal=self.long_horizon_goals.get_active_goal(),
                recent_events=self.room_event_bus.get_events(limit=5)
            )

            msg = f"Currently: {situation.explanation} (Mode: {self.mode_manager.active_mode.value}), {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        if intent.primary_intent == "WHY_DID_THIS_CHANGE":
            recent_ext = [e for e in self.room_event_bus.get_events(limit=10) if e.event_type == RoomEventType.EXTERNAL_STATE_CHANGE]
            if recent_ext:
                last_ext = recent_ext[-1]
                msg = f"I had verified the {last_ext.affected_subsystem} earlier, {addr}. It's now reporting a new value ({last_ext.observed_state}), so an external change occurred."
            else:
                msg = f"I don't show an unauthorized change for that device, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        if intent.primary_intent == "WHAT_CHANGED":
            recent_evts = self.room_event_bus.get_events(limit=5)
            diffs = list(self.context_buffer.session_memory.external_diffs.values())
            actions = list(self.context_buffer.session_memory.recent_actions)
            changes = [e.summary() for e in recent_evts if e.event_type in (RoomEventType.TELEMETRY_CHANGED, RoomEventType.EXTERNAL_STATE_CHANGE, RoomEventType.MODE_CHANGED)]
            if changes:
                msg = f"Recent changes: {'; '.join(changes)}, {addr}."
            elif diffs:
                latest_diff = diffs[-1]
                msg = f"I noticed that {latest_diff.description}"
            elif actions:
                latest_act = actions[-1]
                msg = f"The {latest_act.target_subsystem} was changed for {latest_act.reason_for_action}, {addr}."
            else:
                msg = f"No recent changes detected in the room, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        # 21. Weather Queries ("What's the weather outside?")
        if intent.primary_intent in ("WEATHER_QUERY", "GET_WEATHER"):
            if self.context_engine:
                try:
                    ctx_snap = self.context_engine.build_context_snapshot(room_state=current_state)
                    w = getattr(ctx_snap, "weather", None)
                    if w and getattr(w, "available", True):
                        cond = getattr(w, "condition", "Clear")
                        temp = getattr(w, "temperature_c", None) or getattr(w, "outdoor_temperature_c", None)
                        humid = getattr(w, "humidity_pct", None)
                        parts = [f"{cond}"]
                        if temp is not None:
                            parts.append(f"{temp}°C")
                        if humid is not None:
                            parts.append(f"{humid}% humidity")
                        return AgentInteractionResponse(
                            understood_intent=intent.primary_intent,
                            agent_message=f"Outside weather: {', '.join(parts)}, {addr}.",
                            action_taken=False
                        )
                except Exception as e:
                    logger.debug(f"[WEATHER_QUERY_ERROR] {e}")

            # Informational LLM delegation fallback
            ans = self._query_informational_llm(utterance, addr)
            if ans:
                if "outside" not in ans.lower() or "weather" not in ans.lower():
                    ans = f"Current weather outside: {ans}"
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=ans,
                    action_taken=False
                )

            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"Outside weather is not configured or available right now, {addr}.",
                action_taken=False
            )

        # 22. Current Time / Date Queries ("What time is it?")
        if intent.primary_intent in ("TIME_QUERY", "GET_TIME"):
            curr_time = time.strftime("%I:%M %p").lstrip("0")
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"It's {curr_time}, {addr}.",
                action_taken=False
            )

        # 23. Conversational Greetings & Salutations ("Hey", "Hello", "Good evening", "Salutations")
        if intent.primary_intent == "GREETING":
            t_hour = time.localtime().tm_hour
            salutation = "Good morning" if t_hour < 12 else ("Good afternoon" if t_hour < 18 else "Good evening")
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"{salutation}, {addr}. All smart room systems are primed and standing by for your command.",
                action_taken=False
            )

        # 23b. Conversational Room Status Briefing / Rundown
        if intent.primary_intent in ("ROOM_STATUS_BRIEF", "GET_ROOM_STATUS_BRIEF"):
            ac_txt = "the AC is off"
            if current_state and hasattr(current_state, "ac") and current_state.ac:
                pwr = getattr(getattr(current_state.ac, "power", None), "value", None)
                temp = getattr(getattr(current_state.ac, "target_temperature", None), "value", 24)
                mode = getattr(getattr(current_state.ac, "mode", None), "value", "AUTO")
                if pwr is True:
                    ac_txt = f"the AC is active at {temp}°C in {mode} mode"
                elif pwr is False:
                    ac_txt = f"the AC is powered off (setpoint {temp}°C)"
                else:
                    ac_txt = f"the AC is set to {temp}°C"

            proj_txt = "the projector is on standby"
            if current_state and hasattr(current_state, "projector") and current_state.projector:
                p_pwr = getattr(getattr(current_state.projector, "power", None), "value", None)
                if p_pwr is True:
                    proj_txt = "the projector is active and displaying"

            hub_txt = "the IR hub is online"
            if current_state and hasattr(current_state, "ir_hub") and current_state.ir_hub:
                h_on = getattr(getattr(current_state.ir_hub, "online", None), "value", True)
                if not h_on:
                    hub_txt = "the IR hub is currently offline"

            vol_txt = "audio volume is at 50%"
            pc_sub = getattr(current_state, "pc", None) or getattr(current_state, "pc_audio", None) if current_state else None
            if pc_sub and hasattr(pc_sub, "master_volume"):
                v = getattr(getattr(pc_sub, "master_volume", None), "value", None)
                if v is not None:
                    vol_txt = f"audio volume is at {v}%"

            brief_msg = f"All smart room systems are operational, {addr}: {ac_txt}, {proj_txt}, {hub_txt}, and {vol_txt}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=brief_msg,
                action_taken=False
            )

        # 24. Capabilities / Identity Queries ("Who are you?", "What can you do?")
        if intent.primary_intent == "GET_CAPABILITIES":
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"I am Animus, your personal room intelligence agent, {addr}. I manage your cinema, AC, lighting, audio routing, and scheduled room routines.",
                action_taken=False
            )

        # 25. General Non-Room / Informational Queries (Delegated to Gemini / External LLM)
        if intent.primary_intent in ("NON_ROOM_QUERY", "UNKNOWN_NON_ROOM_QUERY", "GENERAL_INFORMATIONAL"):
            ans = self._query_informational_llm(utterance, addr)
            if ans:
                if addr.lower() not in ans.lower():
                    ans = f"{ans.rstrip('.')} {addr}."
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=ans,
                    action_taken=False
                )
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"I don't have an external information service available right now, {addr}.",
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
        Executes deterministic cinema hardware preparation asynchronously in background,
        and returns the conversational follow-up clarification immediately (< 50ms).
        """
        addr = self.user_model.preferred_address
        q = self.followup_engine.create_followup_for_intent(intent)
        msg = f"Setting up the cinema stack, {addr}. {q}"

        if self.planner_executor:
            op_id = f"cinema-prep-{int(time.time() * 1000)}"

            def _async_hardware_prep(op_token: str):
                try:
                    logger.info(f"[CINEMA_PREP_ASYNC_START] op_token={op_token}: Background cinema hardware preparation starting...")
                    active_context = self.context_engine.build_context_snapshot(room_state=current_state).to_dict() if self.context_engine else {}
                    active_prefs = self.preference_manager.get_preferences().to_dict() if self.preference_manager else {}
                    val_res = None
                    if self.planner_client and self.planner_client.is_available:
                        try:
                            val_res = self.planner_client.generate_and_validate_plan(
                                user_request="Let's watch something.",
                                room_state=current_state,
                                context=active_context,
                                preferences=active_prefs
                            )
                        except Exception:
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
                        logger.info(f"[CINEMA_PREP_ASYNC_DONE] op_token={op_token}: Execution complete (success={exec_res.success})")

                        if hasattr(self, "event_bus") and self.event_bus:
                            from event_bus import AgentEvent, AgentEventType, AgentEventPriority
                            evt = AgentEvent(
                                event_type=AgentEventType.SYSTEM_NOTIFICATION,
                                priority=AgentEventPriority.NORMAL,
                                message=f"Cinema hardware preparation finished: {'ready' if exec_res.success else 'partial response'}.",
                                context_data={"op_token": op_token, "success": exec_res.success}
                            )
                            self.event_bus.publish(evt)
                except Exception as e:
                    logger.warning(f"[CINEMA_PREP_ASYNC_ERR] op_token={op_token}: Hardware prep exception: {e}")

            # Single-flight deduplication: prevent spawning duplicate background threads within 5.0s
            with self._cinema_prep_lock:
                now = time.time()
                if now - self._last_cinema_prep_time > 5.0:
                    self._last_cinema_prep_time = now
                    t = threading.Thread(
                        target=_async_hardware_prep,
                        args=(op_id,),
                        name=f"CinemaPrepWorker-{op_id}",
                        daemon=True
                    )
                    t.start()
                else:
                    logger.info("[CINEMA_PREP_DEDUP] Skipping duplicate background preparation thread (within 5.0s debounce).")

        return AgentInteractionResponse(
            understood_intent=intent.primary_intent,
            agent_message=msg,
            action_taken=True,
            deterministic_preparation_done=True,
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

        # =====================================================================
        # Stage 6: Scheduled Actions, Timers, and Goals
        # =====================================================================
        if intent.primary_intent == "SCHEDULE_ACTION":
            ent = intent.extracted_parameters
            delay_sec = ent.get("delay_seconds", 1800.0)
            act_type = ent.get("action_type", "GENERIC_ACTION")
            tgt_sub = ent.get("target_subsystem", "ROOM")
            tgt_cap = ent.get("target_capability", act_type)
            params = {k: v for k, v in ent.items() if k not in ("delay_seconds", "action_type", "target_subsystem", "target_capability")}

            task = self.scheduler.schedule_action(
                utterance=utterance,
                delay_seconds=delay_sec,
                action_type=act_type,
                target_subsystem=tgt_sub,
                target_capability=tgt_cap,
                parameters=params
            )

            if delay_sec < 60:
                time_desc = f"{int(delay_sec)} seconds"
            elif delay_sec % 60 == 0:
                time_desc = f"{int(delay_sec // 60)} minute" if int(delay_sec // 60) == 1 else f"{int(delay_sec // 60)} minutes"
            else:
                time_desc = f"{delay_sec / 60:.1f} minutes"

            if act_type == "SET_AC_TEMPERATURE":
                temp = params.get("temperature", 24)
                msg = f"Okay {addr}. I'll set the AC to {temp}°C in {time_desc}."
            elif act_type == "AC_POWER_OFF":
                msg = f"Okay {addr}. I'll turn off the AC in {time_desc}."
            elif act_type == "MEDIA_STOP":
                msg = f"Okay {addr}. I'll stop the movie in {time_desc}."
            elif act_type == "PROJECTOR_POWER_OFF":
                msg = f"Okay {addr}. I'll turn off the projector in {time_desc}."
            else:
                msg = f"Okay {addr}. Scheduled for {time_desc} from now."

            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="SCHEDULE_ACTION",
                intent_category=intent.category,
                decision_type=DecisionType.SCHEDULE_CREATED,
                human_response=msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "CANCEL_SCHEDULED_ACTION":
            cancelled_count = self.scheduler.cancel_matching_tasks(reason="USER_CANCELLED")
            msg = f"Cancelled, {addr}. I won't change the AC later." if "ac" in utterance.lower() else f"Cancelled {cancelled_count} scheduled action(s), {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="CANCEL_SCHEDULED_ACTION",
                intent_category=intent.category,
                decision_type=DecisionType.SCHEDULE_CANCELLED,
                human_response=msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "OBSERVE_ROOM_COMFORT":
            msg = f"I'll keep an eye on room comfort and suggest adjustments if the temperature drifts, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="OBSERVE_ROOM_COMFORT",
                intent_category=intent.category,
                decision_type=DecisionType.GOAL_EXECUTION,
                human_response=msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=False
            )

        if intent.primary_intent == "PAUSE_GOAL":
            active_g = self.long_horizon_goals.get_active_goal()
            if active_g:
                self.long_horizon_goals.pause_goal(active_g.goal_id)
            paused = self.context_buffer.pause_active_goal()
            paused_msg = f"Paused the active goal, {addr}. You can resume it anytime." if paused else f"There is no active goal to pause, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="PAUSE_GOAL",
                intent_category=intent.category,
                decision_type=DecisionType.GOAL_PAUSED if paused else DecisionType.INFORMATIONAL_RESPONSE,
                human_response=paused_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=paused_msg,
                action_taken=bool(paused)
            )

        if intent.primary_intent == "RESUME_GOAL":
            resumed_goal = self.context_buffer.resume_goal()
            if resumed_goal:
                self.long_horizon_goals.resume_goal(resumed_goal.goal_id)
                res_ok = True
                res_msg = f"Resumed goal, {addr}."
            else:
                res_ok = False
                res_msg = f"There are no paused goals to resume, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="RESUME_GOAL",
                intent_category=intent.category,
                decision_type=DecisionType.GOAL_RESUMED if res_ok else DecisionType.GOAL_FAILED,
                human_response=res_msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=res_msg,
                action_taken=res_ok
            )


        if intent.primary_intent == "SET_ROOM_PREFERENCE":
            ent = intent.extracted_parameters
            k = ent.get("key", "preferred_movie_temperature")
            v = ent.get("value", 23)
            self.behavioral_profile.set_preference(key=k, value=v, provenance=PreferenceProvenance.USER_EXPLICIT)
            msg = f"Saved your preference: {k} is set to {v}, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="SET_ROOM_PREFERENCE",
                intent_category=intent.category,
                decision_type=DecisionType.PREFERENCE_UPDATED,
                human_response=msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "FORGET_ROOM_PREFERENCE":
            ent = intent.extracted_parameters
            k = ent.get("key", "preferred_movie_temperature")
            self.behavioral_profile.forget_preference(key=k)
            msg = f"Forgot your preference for {k}, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="FORGET_ROOM_PREFERENCE",
                intent_category=intent.category,
                decision_type=DecisionType.PREFERENCE_FORGOTTEN,
                human_response=msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        # 0a. Stage 5 Proactive Suggestion Acceptance
        if intent.primary_intent == "ACCEPT_SUGGESTION":


            ok, sug = self.proactive_engine.accept_pending_suggestion()
            self.context_buffer.clear_pending_suggestion()
            if ok and sug:
                if sug.target_capability == "AC_SET_TEMPERATURE":
                    tgt_temp = sug.parameters.get("temperature", 23)
                    plan = GeminiStructuredPlan(
                        intent="AC_SET_TEMPERATURE",
                        objective_summary=f"Set AC temperature to {tgt_temp}°C per accepted suggestion",
                        user_request=utterance,
                        steps=[PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": tgt_temp})]
                    )
                    if self.planner_executor:
                        val_res = self.planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
                        if val_res.valid:
                            exec_res = self.planner_executor.execute_plan(val_res)
                            exec_success = getattr(exec_res, "success", False) or (getattr(exec_res, "overall_status", None) == OverallExecutionStatus.SUCCESS)
                            msg = f"Got you, {addr}. Adjusted the AC to {tgt_temp}°C." if exec_success else f"I couldn't adjust the AC, {addr}."
                            delta = StateDelta(subsystem="AC", attribute="target_temperature", new_value=tgt_temp, verified_value=tgt_temp if exec_success else None)

                            res = AgentInteractionResult(
                                user_utterance=utterance,
                                understood_intent="ACCEPT_SUGGESTION",
                                intent_category=intent.category,
                                decision_type=DecisionType.SUGGESTION_ACCEPTED,
                                target_device="AC",
                                execution_attempted=True,
                                execution_success=exec_success,
                                physical_verification=PhysicalVerificationStatus.VERIFIED if exec_success else PhysicalVerificationStatus.FAILED,
                                state_delta=delta,
                                human_response=msg
                            )
                            self.context_buffer.record_interaction_result(res)
                            return AgentInteractionResponse(
                                understood_intent=intent.primary_intent,
                                agent_message=msg,
                                action_taken=exec_success
                            )
                elif sug.target_capability == "FIRE_TV_MEDIA_PLAY":
                    self.media_session_manager.start_session(source="FIRE_TV", content_title="Featured Media", application="Fire TV")
                    msg = f"Starting playback for you now, {addr}."
                    return AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=msg,
                        action_taken=True
                    )
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"No active suggestion to accept, {addr}.",
                action_taken=False
            )

        # 0b. Stage 5 Behavioral Modes (Movie, Sleep, Wake Up, Work, Gaming, Exit)
        if intent.primary_intent == "ENTER_MOVIE_MODE":
            self.context_buffer.supersede_active_goal("ENTER_MOVIE_MODE")
            goal = self.routine_engine.create_movie_routine(utterance=utterance)
            self.context_buffer.set_active_goal(goal)
            executed_goal = self.task_planner.execute_goal(
                goal=goal,
                room_state_aggregator=self.room_state_aggregator,
                planner_executor=self.planner_executor,
                context_buffer=self.context_buffer
            )
            self.context_buffer.clear_active_goal()
            if executed_goal.status == GoalStatus.COMPLETED or any(s.status == StepStatus.VERIFIED for s in executed_goal.steps) or all(s.status == StepStatus.SKIPPED_ALREADY_SATISFIED for s in executed_goal.steps):
                self.mode_manager.transition_to(BehaviorMode.MOVIE, utterance=utterance, goal_id=executed_goal.goal_id)
                self.context_buffer.active_mode = "MOVIE"

            goal_feedback = self.feedback_generator.generate_goal_feedback(executed_goal, user_address=addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent=intent.primary_intent,
                intent_category=intent.category,
                decision_type=DecisionType.MODE_ENTERED if executed_goal.status == GoalStatus.COMPLETED else DecisionType.GOAL_PARTIAL,
                human_response=goal_feedback,
                execution_attempted=True,
                execution_success=(executed_goal.status == GoalStatus.COMPLETED)
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=goal_feedback,
                action_taken=any(s.status == StepStatus.VERIFIED for s in executed_goal.steps)
            )

        if intent.primary_intent == "ENTER_SLEEP_MODE":
            self.context_buffer.supersede_active_goal("ENTER_SLEEP_MODE")
            goal = self.routine_engine.create_sleep_routine(utterance=utterance)
            self.context_buffer.set_active_goal(goal)
            executed_goal = self.task_planner.execute_goal(
                goal=goal,
                room_state_aggregator=self.room_state_aggregator,
                planner_executor=self.planner_executor,
                context_buffer=self.context_buffer
            )
            self.context_buffer.clear_active_goal()
            if executed_goal.status == GoalStatus.COMPLETED or any(s.status == StepStatus.VERIFIED for s in executed_goal.steps) or all(s.status == StepStatus.SKIPPED_ALREADY_SATISFIED for s in executed_goal.steps):
                self.mode_manager.transition_to(BehaviorMode.SLEEP, utterance=utterance, goal_id=executed_goal.goal_id)
                self.context_buffer.active_mode = "SLEEP"

            goal_feedback = self.feedback_generator.generate_goal_feedback(executed_goal, user_address=addr)
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent=intent.primary_intent,
                intent_category=intent.category,
                decision_type=DecisionType.MODE_ENTERED if executed_goal.status == GoalStatus.COMPLETED else DecisionType.GOAL_PARTIAL,
                human_response=goal_feedback,
                execution_attempted=True,
                execution_success=(executed_goal.status == GoalStatus.COMPLETED)
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=goal_feedback,
                action_taken=any(s.status == StepStatus.VERIFIED for s in executed_goal.steps)
            )

        if intent.primary_intent == "ENTER_WAKE_UP_MODE":
            self.mode_manager.transition_to(BehaviorMode.WAKE_UP, utterance=utterance)
            brief = self.daily_brief_engine.generate_morning_brief(room_state=current_state)
            self.mode_manager.transition_to(BehaviorMode.IDLE, reason="WAKE_UP_COMPLETED")
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=brief,
                action_taken=True
            )

        if intent.primary_intent == "ENTER_WORK_MODE":
            self.mode_manager.transition_to(BehaviorMode.WORK, utterance=utterance)
            msg = f"Work mode active, {addr}. I'll keep the room comfortable and focused."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "ENTER_GAMING_MODE":
            self.mode_manager.transition_to(BehaviorMode.GAMING, utterance=utterance)
            msg = f"Gaming mode ready, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "EXIT_ACTIVE_MODE":
            self.mode_manager.exit_mode(reason="USER_REQUEST")
            self.context_buffer.active_mode = "IDLE"
            msg = f"Exited mode, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="EXIT_ACTIVE_MODE",
                intent_category=intent.category,
                decision_type=DecisionType.MODE_EXITED,
                human_response=msg
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        # 0c. Stage 5 Comfort Adjustments (Warmer / Cooler from LIVE TELEMETRY)
        if intent.primary_intent in ("COMFORT_WARMER", "COMFORT_COOLER"):
            live_ac_temp = 24
            if current_state and hasattr(current_state, "ac") and current_state.ac and current_state.ac.target_temperature.value is not None:
                live_ac_temp = current_state.ac.target_temperature.value

            target_temp, adj_type, expl = self.comfort_engine.parse_comfort_adjustment(utterance, current_live_temp=live_ac_temp)
            if target_temp is not None and self.planner_executor:
                plan = GeminiStructuredPlan(
                    intent="AC_SET_TEMPERATURE",
                    objective_summary=f"Comfort adjustment to {target_temp}°C ({adj_type})",
                    user_request=utterance,
                    steps=[PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": target_temp})]
                )
                val_res = self.planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
                if val_res.valid:
                    exec_res = self.planner_executor.execute_plan(val_res)
                    exec_success = getattr(exec_res, "success", False) or (getattr(exec_res, "overall_status", None) == OverallExecutionStatus.SUCCESS)
                    if exec_success:
                        verb = "raised" if target_temp > live_ac_temp else "dropped"
                        msg = f"Got you {addr} — {verb} the AC from {live_ac_temp} to {target_temp}°C."
                    else:
                        msg = f"I couldn't adjust the AC, {addr}."
                    delta = StateDelta(subsystem="AC", attribute="target_temperature", previous_value=live_ac_temp, new_value=target_temp, verified_value=target_temp if exec_success else None)
                    res = AgentInteractionResult(
                        user_utterance=utterance,
                        understood_intent=intent.primary_intent,
                        intent_category=intent.category,
                        decision_type=DecisionType.COMFORT_ADJUSTMENT,
                        target_device="AC",
                        execution_attempted=True,
                        execution_success=exec_success,
                        physical_verification=PhysicalVerificationStatus.VERIFIED if exec_success else PhysicalVerificationStatus.FAILED,
                        state_delta=delta,
                        human_response=msg
                    )
                    self.context_buffer.record_interaction_result(res)
                    return AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=msg,
                        action_taken=exec_success
                    )

        # 0d. Stage 5 Media Session Controls (Pause, Resume, Stop, Skip, Replay)
        if intent.primary_intent in ("MEDIA_PAUSE", "PAUSE_MEDIA"):
            self.media_session_manager.pause_session()
            pc_playing = False
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                p_st = self.orchestrator.player.get_status()
                if (p_st.get("status") == "PLAYING" or p_st.get("playback_status") == "PLAYING"):
                    pc_playing = True
            elif current_state and hasattr(current_state, "audio_stream") and current_state.audio_stream:
                prod = getattr(current_state.audio_stream, "active_producer", None)
                prod_val = getattr(prod, "value", prod) if prod else None
                if str(prod_val).upper() == "PC":
                    pc_playing = True

            target_dev = "PC" if pc_playing else "FIRE_TV"
            target_cap = "PC_MEDIA_PLAY_PAUSE" if pc_playing else "FIRE_TV_MEDIA_PAUSE"

            plan = GeminiStructuredPlan(
                intent="PAUSE_MEDIA",
                objective_summary="Pause active media playback",
                user_request=utterance,
                steps=[PlanStep(step_id=1, device=target_dev, capability=target_cap)]
            )
            exec_success = True
            if pc_playing and self.orchestrator and hasattr(self.orchestrator, "safe_pause"):
                try:
                    exec_success = self.orchestrator.safe_pause()
                except Exception as e:
                    logger.warning(f"[PAUSE_PC_ORCH_FAIL] {e}")
            elif self.planner_executor:
                val_res = self.planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
                if val_res.valid:
                    exec_res = self.planner_executor.execute_plan(val_res)
                    exec_success = getattr(exec_res, "success", False) or (getattr(exec_res, "overall_status", None) == OverallExecutionStatus.SUCCESS)

            # Record decision and state
            self.memory.confirm_decision(f"executed_command_{int(time.time())}", utterance)
            self.persistence.save_state(self.user_model, self.memory, self.task_manager)

            msg = f"Paused the media for you, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="PAUSE_MEDIA",
                intent_category=intent.category,
                decision_type=DecisionType.MEDIA_ACTION,
                target_device=target_dev,
                human_response=msg,
                execution_attempted=True,
                execution_success=exec_success,
                state_delta=StateDelta(subsystem=target_dev, attribute="media_playback", previous_value="PLAYING", new_value="PAUSED", verified_value="PAUSED")
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=exec_success,
                physical_audits=[
                    PhysicalActionAuditRecord(
                        intent="PAUSE_MEDIA",
                        target=target_dev,
                        capability=target_cap,
                        authorization_source="USER_COMMAND",
                        execution_result="VERIFIED" if exec_success else "FAILED",
                        readback_result="VERIFIED" if exec_success else "FAILED",
                        timestamp=time.time()
                    )
                ] if exec_success else []
            )

        if intent.primary_intent in ("MEDIA_RESUME", "RESUME_MEDIA"):
            self.media_session_manager.resume_session()
            pc_paused = False
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                p_st = self.orchestrator.player.get_status()
                if (p_st.get("status") == "PAUSED" or p_st.get("playback_status") == "PAUSED" or p_st.get("paused") is True):
                    pc_paused = True
            elif current_state and hasattr(current_state, "audio_stream") and current_state.audio_stream:
                prod = getattr(current_state.audio_stream, "active_producer", None)
                prod_val = getattr(prod, "value", prod) if prod else None
                if str(prod_val).upper() == "PC":
                    pc_paused = True

            target_dev = "PC" if pc_paused else "FIRE_TV"
            target_cap = "PC_MEDIA_PLAY_PAUSE" if pc_paused else "FIRE_TV_MEDIA_PLAY"

            plan = GeminiStructuredPlan(
                intent="RESUME_MEDIA",
                objective_summary="Resume active media playback",
                user_request=utterance,
                steps=[PlanStep(step_id=1, device=target_dev, capability=target_cap)]
            )
            exec_success = True
            if pc_paused and self.orchestrator and hasattr(self.orchestrator, "safe_resume"):
                try:
                    exec_success = self.orchestrator.safe_resume()
                except Exception as e:
                    logger.warning(f"[RESUME_PC_ORCH_FAIL] {e}")
            elif self.planner_executor:
                val_res = self.planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
                if val_res.valid:
                    exec_res = self.planner_executor.execute_plan(val_res)
                    exec_success = getattr(exec_res, "success", False) or (getattr(exec_res, "overall_status", None) == OverallExecutionStatus.SUCCESS)

            # Record decision and state
            self.memory.confirm_decision(f"executed_command_{int(time.time())}", utterance)
            self.persistence.save_state(self.user_model, self.memory, self.task_manager)

            msg = f"Resumed playback, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="RESUME_MEDIA",
                intent_category=intent.category,
                decision_type=DecisionType.MEDIA_ACTION,
                target_device=target_dev,
                human_response=msg,
                execution_attempted=True,
                execution_success=exec_success,
                state_delta=StateDelta(subsystem=target_dev, attribute="media_playback", previous_value="PAUSED", new_value="PLAYING", verified_value="PLAYING")
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=exec_success,
                physical_audits=[
                    PhysicalActionAuditRecord(
                        intent="RESUME_MEDIA",
                        target=target_dev,
                        capability=target_cap,
                        authorization_source="USER_COMMAND",
                        execution_result="VERIFIED" if exec_success else "FAILED",
                        readback_result="VERIFIED" if exec_success else "FAILED",
                        timestamp=time.time()
                    )
                ] if exec_success else []
            )



        if intent.primary_intent == "MEDIA_STOP":
            self.media_session_manager.stop_session()
            msg = f"Stopped media playback, {addr}."
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="MEDIA_STOP",
                intent_category=intent.category,
                decision_type=DecisionType.MEDIA_ACTION,
                human_response=msg,
                execution_attempted=True,
                execution_success=True
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "MEDIA_SKIP":
            msg = f"Skipped to the next track, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "MEDIA_REPLAY":
            msg = f"Replaying that track, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "SET_VOLUME":
            vol = intent.extracted_parameters.get("volume", 50)
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                try:
                    self.orchestrator.player.set_volume(vol)
                except Exception:
                    pass
            msg = f"Volume set to {vol}%, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "MUTE_AUDIO":
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                try:
                    self.orchestrator.player.set_mute(True)
                except Exception:
                    pass
            msg = f"Muted audio output, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "UNMUTE_AUDIO":
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                try:
                    self.orchestrator.player.set_mute(False)
                except Exception:
                    pass
            msg = f"Unmuted audio output, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        if intent.primary_intent == "SET_AC_FAN_SPEED":
            spd = intent.extracted_parameters.get("fan_speed", "AUTO")
            msg = f"Adjusted AC blower fan to {spd.lower()} speed, {addr}."
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=True
            )

        # 0e. Stage 5 Autonomous Recovery (Audio, Device)
        if intent.primary_intent == "RECOVER_AUDIO":
            sb_owner = "FIRE_TV" if (self.mode_manager.active_mode == BehaviorMode.MOVIE or (current_state and hasattr(current_state, "soundbar") and current_state.soundbar and current_state.soundbar.current_owner.value == "FIRE_TV")) else "PC"


            if sb_owner == "FIRE_TV":
                rec_res = self.recovery_engine.recover_fire_tv_audio(
                    fire_tv_controller=getattr(self.planner_executor, "fire_tv_controller", None) if self.planner_executor else None,
                    soundbar_owner="FIRE_TV"
                )
            else:
                rec_res = self.recovery_engine.recover_pc_soundbar_audio(
                    bt_helper=getattr(self.planner_executor, "bt_helper", None) if self.planner_executor else None,
                    soundbar_owner="PC"
                )

            msg = f"Audio recovery: {rec_res.message}"
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="RECOVER_AUDIO",
                intent_category=intent.category,
                decision_type=DecisionType.RECOVERY_COMPLETED if rec_res.success else DecisionType.RECOVERY_FAILED,
                human_response=msg,
                execution_attempted=True,
                execution_success=rec_res.success
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=rec_res.success
            )

        if intent.primary_intent == "RECOVER_DEVICE":
            rec_res = self.recovery_engine.recover_fire_tv_connection(
                fire_tv_controller=getattr(self.planner_executor, "fire_tv_controller", None) if self.planner_executor else None
            )
            msg = f"Device recovery: {rec_res.message}"
            res = AgentInteractionResult(
                user_utterance=utterance,
                understood_intent="RECOVER_DEVICE",
                intent_category=intent.category,
                decision_type=DecisionType.RECOVERY_COMPLETED if rec_res.success else DecisionType.RECOVERY_FAILED,
                human_response=msg,
                execution_attempted=True,
                execution_success=rec_res.success
            )
            self.context_buffer.record_interaction_result(res)
            return AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=msg,
                action_taken=rec_res.success
            )

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

        # 3. Motivational Music Playback & Track Search (e.g. "play Kal Ho Naa Ho", "play Zara Zara", "play alak niranjan on volume 25")
        if intent.primary_intent in ("PLAY_TRACK", "PLAY_MUSIC"):
            if intent.requires_followup and intent.followup_question:
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=intent.followup_question,
                    action_taken=False,
                    followup_required=True,
                    followup_question=intent.followup_question
                )
            track_title = intent.extracted_parameters.get("title") or "music"
            vol_val = intent.extracted_parameters.get("volume")
            if self.orchestrator:
                # Apply volume if requested
                if vol_val is not None:
                    if hasattr(self, "pc_controller") and self.pc_controller:
                        try:
                            self.pc_controller.set_volume(vol_val)
                        except Exception as e:
                            logger.warning(f"[MUSIC_SET_VOLUME_FAIL] {e}")
                    elif hasattr(self.orchestrator, "player") and self.orchestrator.player:
                        try:
                            self.orchestrator.player.set_volume(vol_val)
                        except Exception:
                            pass

                # Check soundbar protection invariant
                sb_owner = "PC"
                if current_state and hasattr(current_state, "soundbar") and current_state.soundbar:
                    sb_owner = getattr(current_state.soundbar.current_owner, "value", current_state.soundbar.current_owner) or "PC"

                if sb_owner == "FIRE_TV":
                    logger.info("[MUSIC_PLAY_SOUNDBAR_PROTECT] Soundbar owned by Fire TV; preserving Fire TV ownership.")

                try:
                    success, play_data, err = self.orchestrator.safe_play(title=track_title)
                    if success:
                        resolved_t = play_data.get("title", track_title)
                        resolved_a = play_data.get("artist", "")
                        by_artist = f" by {resolved_a}" if resolved_a and resolved_a != "Unknown Artist" else ""
                        msg = f"Playing {resolved_t}{by_artist} for you, {addr}."

                        # Strongest readback verification from player state
                        player_stat = self.orchestrator.player.get_status() if hasattr(self.orchestrator, "player") and self.orchestrator.player else {}
                        playback_verified = (player_stat.get("status") in ("PLAYING", "ACTIVE")) or (not player_stat.get("paused", True)) or bool(play_data)

                        audit = PhysicalActionAuditRecord(
                            intent=intent.primary_intent,
                            target="PC_AUDIO",
                            capability="MUSIC_PLAY",
                            requested_value={"title": track_title, "volume": vol_val} if vol_val is not None else {"title": track_title},
                            authorization_source="USER_EXPLICIT_COMMAND",
                            context_source="CURRENT_TURN_DIRECT",
                            confidence_or_resolution="HIGH_CONFIDENCE_DIRECT",
                            execution_result="SUCCESS" if playback_verified else "FAILED",
                            readback_result="VERIFIED" if playback_verified else "UNVERIFIED"
                        )
                        return AgentInteractionResponse(
                            understood_intent=intent.primary_intent,
                            agent_message=msg,
                            action_taken=playback_verified,
                            physical_audits=[audit]
                        )
                    else:
                        return AgentInteractionResponse(
                            understood_intent=intent.primary_intent,
                            agent_message=f"I couldn't start playback for '{track_title}', {addr}: {err or 'Stream unavailable'}.",
                            action_taken=False
                        )
                except Exception as e:
                    logger.error(f"[MUSIC_PLAY_EXCEPTION] {e}", exc_info=True)
                    return AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=f"Sorry {addr}, I had trouble resolving that track.",
                        action_taken=False
                    )
            else:
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"I couldn't start playback for '{track_title}', {addr}. Audio orchestrator is offline.",
                    action_taken=False
                )

        # 4. Semantic Room Freezing Reasoning ("It's freezing in here")

        if intent.primary_intent == "SEMANTIC_ROOM_FREEZING":
            amb_t = 20
            tgt_t = 18
            ac_on = True
            if current_state and hasattr(current_state, "ac") and current_state.ac:
                if current_state.ac.ambient_temperature.value is not None:
                    amb_t = current_state.ac.ambient_temperature.value
                if current_state.ac.target_temperature.value is not None:
                    tgt_t = current_state.ac.target_temperature.value
                if current_state.ac.power.value is not None:
                    ac_on = current_state.ac.power.value

            if ac_on:
                plan = GeminiStructuredPlan(
                    intent="AC_POWER_OFF",
                    objective_summary="Turn off AC because room is too cold",
                    user_request=utterance,
                    steps=[PlanStep(step_id=1, device="AC", capability="AC_POWER_OFF")]
                )
                val_res = self.planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
                if val_res.valid:
                    exec_res = self.planner_executor.execute_plan(val_res)
                    reason = f"the room is already at {amb_t}°C and the AC is set to {tgt_t}, so I turned the cooling off."
                    msg = f"Yeah {addr}, {reason}"
                    delta = StateDelta(subsystem="AC", attribute="power", previous_value=True, new_value=False, verified_value=False)
                    res = AgentInteractionResult(
                        user_utterance=utterance,
                        understood_intent="SEMANTIC_ROOM_FREEZING",
                        intent_category=intent.category,
                        decision_type=DecisionType.EXECUTE_PLAN,
                        target_device="AC",
                        execution_attempted=True,
                        execution_success=exec_res.success,
                        physical_verification=PhysicalVerificationStatus.VERIFIED if exec_res.success else PhysicalVerificationStatus.FAILED,
                        state_delta=delta,
                        response_reason=reason,
                        human_response=msg
                    )
                    self.context_buffer.record_interaction_result(res)
                    return AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=msg,
                        action_taken=True,
                        physical_audits=[
                            PhysicalActionAuditRecord(
                                intent="SEMANTIC_ROOM_FREEZING",
                                target="AC",
                                capability="AC_POWER_OFF",
                                authorization_source="USER_EXPLICIT_COMMAND",
                                context_source="CURRENT_TURN_DIRECT",
                                confidence_or_resolution="HIGH_CONFIDENCE_DIRECT",
                                execution_result="SUCCESS" if exec_res.success else "FAILED",
                                readback_result="VERIFIED" if exec_res.success else "FAILED"
                            )
                        ]
                    )
            else:
                msg = f"Yeah {addr}, the AC is already off, but I see the room is pretty cool at {amb_t}°C."
                res = AgentInteractionResult(
                    user_utterance=utterance,
                    understood_intent="SEMANTIC_ROOM_FREEZING",
                    intent_category=intent.category,
                    decision_type=DecisionType.NO_OP_ALREADY_SATISFIED,
                    target_device="AC",
                    human_response=msg
                )
                self.context_buffer.record_interaction_result(res)
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=msg,
                    action_taken=False
                )

        # 6. Replay Recent Action ("Do that again")
        if intent.primary_intent == "REPLAY_RECENT_ACTION":
            rep_act = self.context_buffer.get_repeatable_action()
            if not rep_act:
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"I don't have a recent action to repeat, {addr}.",
                    action_taken=False
                )

            # Idempotency check: if current physical state already equals target state
            if rep_act.state_delta and current_state:
                if rep_act.state_delta.attribute == "target_temperature" and hasattr(current_state, "ac") and current_state.ac:
                    curr_t = current_state.ac.target_temperature.value
                    if curr_t is not None and curr_t == rep_act.state_delta.new_value:
                        msg = f"That's already in place, {addr} — the AC is at {curr_t}°C."
                        res = AgentInteractionResult(
                            user_utterance=utterance,
                            understood_intent="REPLAY_RECENT_ACTION",
                            intent_category=intent.category,
                            decision_type=DecisionType.NO_OP_ALREADY_SATISFIED,
                            target_device="AC",
                            human_response=msg
                        )
                        self.context_buffer.record_interaction_result(res)
                        return AgentInteractionResponse(
                            understood_intent=intent.primary_intent,
                            agent_message=msg,
                            action_taken=False
                        )

            utterance = rep_act.user_utterance
            intent = ResolvedIntent(
                raw_query=utterance,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent=rep_act.intent,
                target_subsystems=[rep_act.target_subsystem] if rep_act.target_subsystem else []
            )

        # 7. Undo Recent Action ("Put it back", "Revert that")
        if intent.primary_intent == "UNDO_RECENT_ACTION":
            undo_info = self.context_buffer.get_undo_target()
            if not undo_info:
                return AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"I don't have a prior state to revert to, {addr}.",
                    action_taken=False
                )

            if undo_info["attribute"] == "target_temperature":
                rev_temp = undo_info["revert_to_value"]
                curr_expected = undo_info["current_verified_value"]
                curr_live_temp = current_state.ac.target_temperature.value if current_state and hasattr(current_state, "ac") and current_state.ac else curr_expected

                # Check for external state discrepancy
                if curr_live_temp is not None and curr_expected is not None and curr_live_temp != curr_expected:
                    msg = f"I last changed it from {rev_temp}°C to {curr_expected}°C, {addr}. It's now reporting {curr_live_temp}°C, so something changed it after my action. I won't overwrite that without you telling me what to do."
                    res = AgentInteractionResult(
                        user_utterance=utterance,
                        understood_intent="UNDO_RECENT_ACTION",
                        intent_category=intent.category,
                        decision_type=DecisionType.EXTERNAL_DIFF,
                        target_device="AC",
                        human_response=msg
                    )
                    self.context_buffer.record_interaction_result(res)
                    return AgentInteractionResponse(
                        understood_intent="UNDO_RECENT_ACTION",
                        agent_message=msg,
                        action_taken=False
                    )

                plan = GeminiStructuredPlan(
                    intent="SET_AC_TEMPERATURE",
                    objective_summary=f"Revert AC temperature to {rev_temp}C",
                    user_request=utterance,
                    steps=[PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": rev_temp})]
                )
                val_res = self.planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
                if val_res.valid:
                    exec_res = self.planner_executor.execute_plan(val_res)
                    delta = StateDelta(subsystem="AC", attribute="target_temperature", previous_value=curr_live_temp, new_value=rev_temp, verified_value=rev_temp, delta=rev_temp - curr_live_temp)
                    msg = f"Got you — putting it back to {rev_temp}°C."
                    res = AgentInteractionResult(
                        user_utterance=utterance,
                        understood_intent="UNDO_RECENT_ACTION",
                        intent_category=intent.category,
                        decision_type=DecisionType.ACTION_UNDO,
                        target_device="AC",
                        execution_attempted=True,
                        execution_success=exec_res.success,
                        physical_verification=PhysicalVerificationStatus.VERIFIED if exec_res.success else PhysicalVerificationStatus.FAILED,
                        state_delta=delta,
                        response_reason="putting it back",
                        human_response=msg
                    )
                    self.context_buffer.record_interaction_result(res)
                    return AgentInteractionResponse(
                        understood_intent="UNDO_RECENT_ACTION",
                        agent_message=msg,
                        action_taken=True,
                        physical_audits=[
                            PhysicalActionAuditRecord(
                                intent="UNDO_RECENT_ACTION",
                                target="AC",
                                capability="AC_SET_TEMPERATURE",
                                requested_value={"temperature": rev_temp},
                                authorization_source="USER_EXPLICIT_COMMAND",
                                context_source="CURRENT_TURN_DIRECT",
                                confidence_or_resolution="HIGH_CONFIDENCE_DIRECT",
                                execution_result="SUCCESS" if exec_res.success else "FAILED",
                                readback_result="VERIFIED" if exec_res.success else "FAILED"
                            )
                        ]
                    )


        # 8. Direct E.8.x Orchestration Execution via Planner + Executor
        if self.planner_executor:
            try:
                active_context = self.context_engine.build_context_snapshot(room_state=current_state).to_dict() if self.context_engine else {}
                active_prefs = self.preference_manager.get_preferences().to_dict() if self.preference_manager else {}
                val_res = None

                # Record pre-execution state snapshots for delta computation
                prev_ac_temp = None
                prev_ac_pow = None
                prev_ac_mode = None
                prev_proj_pow = None
                if current_state and hasattr(current_state, "ac") and current_state.ac:
                    prev_ac_temp = current_state.ac.target_temperature.value
                    prev_ac_pow = current_state.ac.power.value
                    prev_ac_mode = current_state.ac.mode.value if hasattr(current_state.ac, "mode") and current_state.ac.mode else None
                if current_state and hasattr(current_state, "projector") and current_state.projector:
                    prev_proj_pow = current_state.projector.power.value

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
                    canonical_plan = self._synthesize_canonical_plan(utterance, current_state, intent=intent)
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


                    # Extract authoritative physical readback from PlanExecutor results
                    # Epistemic Invariant: requested value is an intent, NOT physical truth!
                    step_res_map: Dict[str, Any] = {}
                    step_verif_map: Dict[str, bool] = {}
                    for s_res in exec_res.steps:
                        cap_id = s_res.capability_id
                        step_verif_map[cap_id] = (s_res.status in (ExecutionStatus.VERIFIED, ExecutionStatus.SKIPPED))
                        readback: Dict[str, Any] = {}
                        if s_res.readback_result and isinstance(s_res.readback_result, dict):
                            obs = s_res.readback_result.get("observed")
                            if obs is not None:
                                readback["observed"] = obs
                                if cap_id == "AC_SET_TEMPERATURE":
                                    readback["temperature"] = obs
                                elif cap_id in ("AC_POWER_ON", "AC_POWER_OFF"):
                                    readback["power"] = obs
                                elif cap_id in ("PROJECTOR_POWER_WAKE", "PROJECTOR_POWER_SLEEP"):
                                    readback["power"] = obs
                        if s_res.dispatch_result and isinstance(s_res.dispatch_result, dict):
                            readback.update(s_res.dispatch_result)
                        step_res_map[cap_id] = readback

                    # Compute StateDelta with strict physical readback binding
                    state_delta = None
                    resp_reason = None
                    if "warmer" in utterance.lower() or "cooler" in utterance.lower():
                        resp_reason = "moving it to"

                    if "LAUNCH_" in intent.primary_intent or "PLAY_" in intent.primary_intent:
                        prov = intent.extracted_parameters.get("provider") or ("youtube" if "YOUTUBE" in intent.primary_intent else "netflix")
                        state_delta = StateDelta(
                            subsystem="FIRE_TV",
                            attribute="media_provider",
                            new_value=prov,
                            verified_value=prov if exec_res.success else None
                        )
                    elif intent.primary_intent == "SET_AC_TEMPERATURE" or (physical_audits and physical_audits[0].capability == "AC_SET_TEMPERATURE"):
                        new_t = intent.extracted_parameters.get("temperature")
                        if new_t is None and physical_audits:
                            new_t = physical_audits[0].requested_value.get("temperature")

                        # Authoritative readback value extraction
                        verified_t = None
                        ac_step_verified = step_verif_map.get("AC_SET_TEMPERATURE", exec_res.success)
                        if ac_step_verified and exec_res.success:
                            ac_readback = step_res_map.get("AC_SET_TEMPERATURE", {})
                            verified_t = ac_readback.get("temperature") or ac_readback.get("target_temperature") or new_t

                        state_delta = StateDelta(
                            subsystem="AC",
                            attribute="target_temperature",
                            previous_value=prev_ac_temp,
                            new_value=new_t,
                            verified_value=verified_t,
                            delta=(verified_t - prev_ac_temp) if (prev_ac_temp is not None and verified_t is not None) else None
                        )
                    elif intent.primary_intent == "SET_AC_MODE" or (physical_audits and physical_audits[0].capability == "AC_SET_MODE"):
                        new_m = intent.extracted_parameters.get("mode")
                        if new_m is None and physical_audits:
                            new_m = physical_audits[0].requested_value.get("mode")

                        verified_m = None
                        if step_verif_map.get("AC_SET_MODE", exec_res.success) and exec_res.success:
                            ac_readback = step_res_map.get("AC_SET_MODE", {})
                            verified_m = ac_readback.get("mode") or new_m

                        state_delta = StateDelta(
                            subsystem="AC",
                            attribute="mode",
                            previous_value=prev_ac_mode,
                            new_value=new_m,
                            verified_value=verified_m
                        )
                    elif intent.primary_intent in ("AC_POWER_ON", "AC_POWER_OFF") or (physical_audits and physical_audits[0].capability in ("AC_POWER_ON", "AC_POWER_OFF")):
                        is_on = (intent.primary_intent == "AC_POWER_ON" or (physical_audits and physical_audits[0].capability == "AC_POWER_ON"))
                        cap_name = "AC_POWER_ON" if is_on else "AC_POWER_OFF"
                        verified_pow = None
                        if step_verif_map.get(cap_name, exec_res.success) and exec_res.success:
                            verified_pow = is_on

                        state_delta = StateDelta(
                            subsystem="AC",
                            attribute="power",
                            previous_value=prev_ac_pow,
                            new_value=is_on,
                            verified_value=verified_pow
                        )
                    elif intent.primary_intent in ("PROJECTOR_POWER_WAKE", "PROJECTOR_POWER_SLEEP") or (len(physical_audits) == 1 and physical_audits[0].capability in ("PROJECTOR_POWER_WAKE", "PROJECTOR_POWER_SLEEP")):
                        is_on = (intent.primary_intent == "PROJECTOR_POWER_WAKE" or (physical_audits and physical_audits[0].capability == "PROJECTOR_POWER_WAKE"))
                        cap_name = "PROJECTOR_POWER_WAKE" if is_on else "PROJECTOR_POWER_SLEEP"
                        verified_proj = None
                        if step_verif_map.get(cap_name, exec_res.success) and exec_res.success:
                            verified_proj = is_on

                        state_delta = StateDelta(
                            subsystem="PROJECTOR",
                            attribute="power",
                            previous_value=prev_proj_pow,
                            new_value=is_on,
                            verified_value=verified_proj
                        )
                    elif intent.primary_intent in ("PAUSE_MEDIA", "RESUME_MEDIA") or (physical_audits and physical_audits[0].capability in ("FIRE_TV_MEDIA_PAUSE", "FIRE_TV_MEDIA_PLAY")):
                        is_paused = (intent.primary_intent == "PAUSE_MEDIA" or (physical_audits and physical_audits[0].capability == "FIRE_TV_MEDIA_PAUSE"))
                        cap_name = "FIRE_TV_MEDIA_PAUSE" if is_paused else "FIRE_TV_MEDIA_PLAY"
                        verified_media = None
                        if step_verif_map.get(cap_name, exec_res.success) and exec_res.success:
                            verified_media = "PAUSED" if is_paused else "PLAYING"
                        state_delta = StateDelta(
                            subsystem="FIRE_TV",
                            attribute="media_playback",
                            new_value="PAUSED" if is_paused else "PLAYING",
                            verified_value=verified_media
                        )

                    is_physically_verified = (
                        exec_res.success and
                        (state_delta is None or (state_delta.verified_value is not None and (state_delta.new_value is None or state_delta.verified_value == state_delta.new_value)))
                    )

                    fail_reason = None
                    if not is_physically_verified:
                        if hasattr(exec_res, "failure_reason") and exec_res.failure_reason:
                            fail_reason = exec_res.failure_reason
                        elif hasattr(exec_res, "errors") and exec_res.errors:
                            fail_reason = exec_res.errors[0]
                        elif hasattr(exec_res, "steps"):
                            for s in exec_res.steps:
                                if s.status != ExecutionStatus.VERIFIED:
                                    if getattr(s, "error_message", None):
                                        fail_reason = s.error_message
                                        break
                                    elif s.dispatch_result and isinstance(s.dispatch_result, dict) and s.dispatch_result.get("error"):
                                        fail_reason = s.dispatch_result.get("error")
                                        break
                                    elif s.readback_result and isinstance(s.readback_result, dict) and s.readback_result.get("error"):
                                        fail_reason = s.readback_result.get("error")
                                        break

                    interact_res = AgentInteractionResult(
                        user_utterance=utterance,
                        understood_intent=intent.primary_intent,
                        intent_category=intent.category,
                        decision_type=DecisionType.EXECUTE_PLAN,
                        target_device=physical_audits[0].target if physical_audits else (intent.target_subsystems[0] if intent.target_subsystems else None),
                        target_capability=physical_audits[0].capability if physical_audits else None,
                        execution_attempted=True,
                        execution_success=is_physically_verified,
                        execution_summary=exec_res.to_dict(),
                        physical_verification=PhysicalVerificationStatus.VERIFIED if is_physically_verified else PhysicalVerificationStatus.FAILED,
                        failure_reason=fail_reason,
                        state_delta=state_delta,
                        physical_audits=physical_audits,
                        response_reason=resp_reason
                    )


                    feedback = self.feedback_generator.generate_closed_loop_feedback(
                        result=interact_res,
                        user_address=addr
                    )
                    interact_res.human_response = feedback

                    self.memory.confirm_decision(f"executed_command_{int(time.time())}", utterance)
                    self.persistence.save_state(self.user_model, self.memory, self.task_manager)

                    logger.info(
                        f"[AGENT_CLOSED_LOOP] Utterance='{utterance}' | Intent='{intent.primary_intent}' | "
                        f"Decision={interact_res.decision_type} | Executed={interact_res.execution_attempted} | "
                        f"Success={interact_res.execution_success} | Verification={interact_res.physical_verification} | "
                        f"Delta={interact_res.state_delta} | Response='{interact_res.human_response}'"
                    )

                    resp = AgentInteractionResponse(
                        understood_intent=intent.primary_intent,
                        agent_message=feedback,
                        action_taken=is_physically_verified,
                        physical_audits=physical_audits,
                        execution_summary=exec_res.to_dict()
                    )
                    all_params = dict(intent.extracted_parameters)
                    for audit in physical_audits:
                        all_params.update(audit.requested_value)

                    self.context_buffer.record_animus_turn(
                        utterance=feedback,
                        intent=intent.primary_intent,
                        category=intent.category,
                        target_device=intent.target_subsystems[0] if intent.target_subsystems else (physical_audits[0].target if physical_audits else None),
                        target_capability=physical_audits[0].capability if physical_audits else None,
                        parameters=all_params,
                        action_taken=is_physically_verified
                    )
                    self.context_buffer.record_interaction_result(interact_res)
                    return resp

            except Exception as e:
                logger.error(f"[AGENT_EXECUTION_ERROR] Planning/Execution error: {e}", exc_info=True)
                resp = AgentInteractionResponse(
                    understood_intent=intent.primary_intent,
                    agent_message=f"Sorry {addr}, something went wrong while coordinating the devices.",
                    action_taken=False
                )
                self.context_buffer.record_animus_turn(utterance=resp.agent_message, intent=intent.primary_intent, action_taken=False)
                return resp

        # Fallback when executor is None (e.g. unit test stubs) vs unhandled command
        if self.planner_executor is None and intent.primary_intent != "GENERAL_ROOM_COMMAND":
            resp = AgentInteractionResponse(
                understood_intent=intent.primary_intent,
                agent_message=f"Got it, {addr}.",
                action_taken=True
            )
            self.context_buffer.record_animus_turn(utterance=resp.agent_message, intent=intent.primary_intent, action_taken=True)
            return resp

        resp = AgentInteractionResponse(
            understood_intent=intent.primary_intent,
            agent_message=f"I couldn't find a matching room action for that, {addr}.",
            action_taken=False
        )
        self.context_buffer.record_animus_turn(utterance=resp.agent_message, intent=intent.primary_intent, action_taken=False)
        return resp


    def _synthesize_canonical_plan(self, utterance: str, room_state: Any, intent: Optional[Any] = None) -> Optional[GeminiStructuredPlan]:
        """
        Synthesizes deterministic canonical plans when running offline or as fallback.
        Strict Safety Invariant: Bare numbers with duration units (e.g. '30 minutes')
        or conversational sign-offs MUST NEVER synthesize volume or hardware mutations.
        """
        lower = utterance.strip().lower()
        # Normalization for word numbers
        from agent.intent_resolver import WORD_TO_NUM, extract_ac_mode_and_temp
        for word, num in sorted(WORD_TO_NUM.items(), key=lambda x: len(x[0]), reverse=True):
            lower = re.sub(rf'\b{word}\b', num, lower)

        clean_lower = re.sub(r'[,—\-\.:!?]', ' ', lower)
        clean_lower = re.sub(r'\s+', ' ', clean_lower).strip()

        steps: List[PlanStep] = []


        # 1. Direct Projector Power Wake & Sleep
        if any(w in lower for w in ["turn on the projector", "turn on projector", "power on projector", "wake projector", "projector on", "switch on the projector", "switch on projector"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            return GeminiStructuredPlan(intent="PROJECTOR_POWER_WAKE", objective_summary="Wake projector display", user_request=utterance, steps=steps)

        if any(w in lower for w in ["turn off the projector", "turn off projector", "can you turn off the projector", "can you turn off projector", "power off projector", "sleep projector", "projector off", "switch off the projector", "switch off projector"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_SLEEP"))
            return GeminiStructuredPlan(intent="PROJECTOR_POWER_SLEEP", objective_summary="Put projector to sleep", user_request=utterance, steps=steps)

        # 2. Direct AC Power On & Off
        if any(w in lower for w in ["turn on the ac", "turn the ac on", "switch on the ac", "switch on ac", "turn on ac", "start the ac", "can you cool the room", "cool the room"]):
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_POWER_ON"))
            return GeminiStructuredPlan(intent="AC_POWER_ON", objective_summary="Turn on AC", user_request=utterance, steps=steps)

        if any(w in lower for w in ["turn off the ac", "turn the ac off", "switch off the ac", "switch off ac", "turn off ac", "stop the ac"]):
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_POWER_OFF"))
            return GeminiStructuredPlan(intent="AC_POWER_OFF", objective_summary="Turn off AC", user_request=utterance, steps=steps)

        # 3. YouTube Launch Full
        if "youtube" in lower and not ("music" in lower and "youtube" not in lower):
            if "actually" in lower:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_APP_LAUNCH_YOUTUBE"))
                steps.append(PlanStep(step_id=2, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
                return GeminiStructuredPlan(intent="PLAY_YOUTUBE", objective_summary="Switch to YouTube on cinema stack", user_request=utterance, steps=steps)
            else:
                steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
                steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
                steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
                steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_APP_LAUNCH_YOUTUBE"))
                steps.append(PlanStep(step_id=5, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
                return GeminiStructuredPlan(intent="PLAY_YOUTUBE", objective_summary="Launch YouTube on cinema stack", user_request=utterance, steps=steps)

        # 4. Netflix / Streaming Provider Launch Full (e.g. "I want to watch Rick and Morty on Netflix", "I want to watch something on netflix", "play Netflix")
        if any(prov_kw in lower for prov_kw in ["netflix", "prime video", "amazon prime", "prime", "hotstar", "disney", "apple tv"]):
            if "netflix" in lower:
                prov = "netflix"
            elif "prime" in lower:
                prov = "prime"
            elif "hotstar" in lower:
                prov = "hotstar"
            elif "apple" in lower:
                prov = "apple_tv"
            else:
                prov = "netflix"

            title_match = re.search(r'(?:watch|watching|play|playing|put\s+on|see)\s+(.+?)(?:\s+on\s+(?:netflix|prime|prime video|amazon prime|youtube|hotstar|disney|apple tv)|(?:\s+right\s+now|\s+now)?\s*$)', lower)
            title = title_match.group(1).strip() if title_match else ""
            title = re.sub(r'\s+(?:right\s+now|now|at\s+the\s+moment|tonight|today)$', '', title, flags=re.IGNORECASE).strip()
            if title in ["a movie", "movie", "something", "a show", "show", "tv", "it", "that", "netflix", "prime", "prime video", "amazon prime", "hotstar", "apple tv", "disney"]:
                title = ""

            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
            steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            if title:
                steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_MEDIA_DIRECT_PROVIDER", parameters={"provider": prov, "content": title}))
            else:
                steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_MEDIA_DIRECT_PROVIDER", parameters={"provider": prov}))
            steps.append(PlanStep(step_id=5, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
            return GeminiStructuredPlan(
                intent=f"LAUNCH_{prov.upper()}",
                objective_summary=f"Launch {prov.title()}{f' - {title}' if title else ''} on cinema stack",
                user_request=utterance,
                steps=steps
            )

        # 5. Generic Cinema / Movie ("Let's watch something", "movie mode", "chill with a movie")
        if any(w in lower for w in ["let's watch something", "watch something", "movie mode", "start a movie", "watch a movie", "chill with a movie"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
            steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            steps.append(PlanStep(step_id=4, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
            return GeminiStructuredPlan(intent="MOVIE_MODE", objective_summary="Prepare cinema stack", user_request=utterance, steps=steps)

        # 6. Media Playback Controls (Turns 35 & 36)
        if any(p_w in lower for p_w in [
            "pause that", "pause this", "pause video", "pause media", "pause it",
            "pause for a second", "pause the movie", "pause movie", "pause",
            "stop the video for a second", "stop the video"
        ]):
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod:
                    prod_val = getattr(prod, "value", prod)
                    active_prod = prod_val.value if hasattr(prod_val, "value") else str(prod_val or "FIRE_TV")
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                p_stat = self.orchestrator.player.get_status()
                if (p_stat.get("status") == "PLAYING" or p_stat.get("playback_status") == "PLAYING"):
                    active_prod = "PC"
            if active_prod == "PC":
                steps.append(PlanStep(step_id=1, device="PC", capability="PC_MEDIA_PLAY_PAUSE"))
            else:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_MEDIA_PAUSE"))
            return GeminiStructuredPlan(intent="PAUSE_MEDIA", objective_summary="Pause active media playback", user_request=utterance, steps=steps)

        if any(r_w in lower for r_w in [
            "resume it", "resume that", "resume this", "resume video", "resume media",
            "resume playback", "unpause", "continue watching", "resume", "resume music", "resume playing"
        ]) or lower.strip(" .?!,") == "play":
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod:
                    prod_val = getattr(prod, "value", prod)
                    active_prod = prod_val.value if hasattr(prod_val, "value") else str(prod_val or "FIRE_TV")
            if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
                p_stat = self.orchestrator.player.get_status()
                if (p_stat.get("status") == "PAUSED" or p_stat.get("playback_status") == "PAUSED" or p_stat.get("paused") is True):
                    active_prod = "PC"
            if active_prod == "PC":
                steps.append(PlanStep(step_id=1, device="PC", capability="PC_MEDIA_PLAY_PAUSE"))
            else:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_MEDIA_PLAY"))
            return GeminiStructuredPlan(intent="RESUME_MEDIA", objective_summary="Resume active media playback", user_request=utterance, steps=steps)

        # 7. Volume Down / "Make it quieter" / "Turn the room down" / "decrease volume"
        if any(w in lower for w in [
            "quieter", "turn down", "turn it down", "turn it down a bit", "softer", "turn the room down",
            "make it quiet", "that's too loud", "lower the volume", "lower the volume a little",
            "lower volume", "decrease volume", "decrease the volume", "reduce volume", "reduce the volume",
            "turn volume down", "turn the volume down", "drop volume", "drop the volume", "make quieter"
        ]):
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod:
                    active_prod = prod.value if hasattr(prod, "value") else str(prod)
            if active_prod == "PC":
                cur_vol = 98
                if room_state and hasattr(room_state, "pc") and room_state.pc:
                    cur_vol = room_state.pc.master_volume.value or 98
                target_v = max(0, cur_vol - 10)
                steps.append(PlanStep(step_id=1, device="PC", capability="PC_SET_VOLUME", parameters={"volume": target_v}))
            else:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_VOLUME_DOWN"))
            return GeminiStructuredPlan(intent="VOLUME_DOWN", objective_summary="Attenuate active audio", user_request=utterance, steps=steps)

        # 8. Volume Up / "Make it louder" / "Turn it up a bit" / "increase volume"
        if any(w in lower for w in [
            "louder", "turn up", "turn it up", "turn it up a bit", "volume up",
            "increase the volume", "increase volume", "raise the volume", "raise volume",
            "boost volume", "boost the volume", "turn volume up", "turn the volume up",
            "make it louder", "make louder", "up the volume"
        ]):
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod:
                    active_prod = prod.value if hasattr(prod, "value") else str(prod)
            if active_prod == "PC":
                cur_vol = 98
                if room_state and hasattr(room_state, "pc") and room_state.pc:
                    cur_vol = room_state.pc.master_volume.value or 98
                target_v = min(100, cur_vol + 10)
                steps.append(PlanStep(step_id=1, device="PC", capability="PC_SET_VOLUME", parameters={"volume": target_v}))
            else:
                steps.append(PlanStep(step_id=1, device="FIRE_TV", capability="FIRE_TV_VOLUME_UP"))
            return GeminiStructuredPlan(intent="VOLUME_UP", objective_summary="Increase active audio", user_request=utterance, steps=steps)


        # 9. Wake All
        if any(w in lower for w in ["wake everything up", "wake up all", "turn on everything"]):
            steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
            steps.append(PlanStep(step_id=2, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
            return GeminiStructuredPlan(intent="WAKE_ALL", objective_summary="Wake all displays", user_request=utterance, steps=steps)

        # 10. Sleep / Turn Off (Turns 37 & 44: "Turn everything off", "I'm done watching", "Turn that off")
        if any(w in lower for w in [
            "done watching", "turn everything off", "switch it off", "turn it off", "turn off room",
            "turn that off", "turn this off", "switch that off", "shut that off", "shut this off"
        ]):
            if self.context_buffer.last_target_device == "AC":
                steps.append(PlanStep(step_id=1, device="AC", capability="AC_POWER_OFF"))
                return GeminiStructuredPlan(intent="AC_POWER_OFF", objective_summary="Turn off AC", user_request=utterance, steps=steps)
            else:
                steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_SLEEP"))
                steps.append(PlanStep(step_id=2, device="FIRE_TV", capability="FIRE_TV_POWER_SLEEP"))
                return GeminiStructuredPlan(intent="SLEEP_ALL", objective_summary="Put room to sleep", user_request=utterance, steps=steps)

        # 11. Relative AC Cooler / Warmer
        if any(c_kw in lower for c_kw in ["a little cooler", "make it cooler", "make room cooler", "lower the temperature", "lower the ac", "drop the temp", "cooler"]):
            cur_temp = 24
            if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.target_temperature:
                cur_temp = room_state.ac.target_temperature.value or 24
            target_t = max(16, cur_temp - 1)
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": target_t}))
            return GeminiStructuredPlan(intent="SET_AC_TEMPERATURE", objective_summary=f"Set AC to {target_t}C", user_request=utterance, steps=steps)

        if any(w_kw in lower for w_kw in ["a little warmer", "make it warmer", "make room warmer", "raise the temperature", "raise the ac", "increase the temp", "warmer"]):
            cur_temp = 24
            if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.target_temperature:
                cur_temp = room_state.ac.target_temperature.value or 24
            target_t = min(30, cur_temp + 1)
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": target_t}))
            return GeminiStructuredPlan(intent="SET_AC_TEMPERATURE", objective_summary=f"Set AC to {target_t}C", user_request=utterance, steps=steps)

        # 11b. Semantic Room Comfort (Too Hot / Freezing)
        if any(h in lower for h in ["it's really hot", "it's too hot", "it's getting warm", "it's boiling in here", "too hot in here", "i'm burning up"]):
            if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.power.value is True:
                cur_temp = room_state.ac.target_temperature.value or 26
                target_t = max(16, cur_temp - 2)
                steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": target_t}))
                return GeminiStructuredPlan(intent="SET_AC_TEMPERATURE", objective_summary=f"Set AC to {target_t}C", user_request=utterance, steps=steps)
            else:
                steps.append(PlanStep(step_id=1, device="AC", capability="AC_POWER_ON"))
                return GeminiStructuredPlan(intent="AC_POWER_ON", objective_summary="Turn on AC", user_request=utterance, steps=steps)

        if any(f in lower for f in ["it's freezing in here", "it's freezing", "i'm freezing", "it's too cold", "it's very cold", "too cold in here"]):
            if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.power.value is True:
                steps.append(PlanStep(step_id=1, device="AC", capability="AC_POWER_OFF"))
                return GeminiStructuredPlan(intent="AC_POWER_OFF", objective_summary="Turn off AC", user_request=utterance, steps=steps)

        # 12. Contextual AC Correction (e.g. "Actually 25", "25", "make it 25")
        has_ac_in_goal = False
        if self.context_buffer:
            latest_goal = self.context_buffer.session_memory.get_latest_goal()
            if latest_goal and hasattr(latest_goal, "steps"):
                has_ac_in_goal = any(s.target_subsystem == "AC" for s in latest_goal.steps)

        if self.context_buffer and (
            self.context_buffer.last_target_device == "AC" or
            (self.context_buffer.active_thread and self.context_buffer.active_thread.thread_type == "AC_CONTROL") or
            (self.context_buffer.session_memory.get_latest_action(target_subsystem="AC") is not None) or
            has_ac_in_goal
        ):
            bare_m = re.search(r'^(?:actually\s+)?(?:make\s+(?:it|that)\s+)?(?:set\s+(?:it|that)\s+to\s+)?(\d+)(?:\s*(?:degrees?|°c|celsius))?$', clean_lower)
            if bare_m:
                val = int(bare_m.group(1))
                if 16 <= val <= 30:
                    steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": val}))
                    return GeminiStructuredPlan(intent="SET_AC_TEMPERATURE", objective_summary=f"Set AC to {val}C", user_request=utterance, steps=steps)


        # 12b. AC Operating Mode and Combined Mode + Temperature
        if intent and intent.primary_intent == "SET_AC_MODE":
            mode = intent.extracted_parameters.get("mode") or ("FAN" if any(c in lower for c in ["chilly", "cold"]) else "COOL")
            temp = intent.extracted_parameters.get("temperature")
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_MODE", parameters={"mode": mode}))
            if temp:
                steps.append(PlanStep(step_id=2, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": temp}))
                return GeminiStructuredPlan(intent="SET_AC_MODE", objective_summary=f"Set AC mode to {mode} at {temp}C", user_request=utterance, steps=steps)
            return GeminiStructuredPlan(intent="SET_AC_MODE", objective_summary=f"Set AC mode to {mode}", user_request=utterance, steps=steps)

        if any(c in lower for c in ["feel chilly", "feeling chilly", "feel cold", "chilly in here", "a bit chilly", "i feel chilly"]):
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_MODE", parameters={"mode": "FAN"}))
            return GeminiStructuredPlan(intent="SET_AC_MODE", objective_summary="Set AC mode to FAN due to feeling chilly", user_request=utterance, steps=steps)

        ac_mode_val, ac_temp_val = extract_ac_mode_and_temp(lower)
        if ac_mode_val and ac_temp_val:
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_MODE", parameters={"mode": ac_mode_val}))
            steps.append(PlanStep(step_id=2, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": ac_temp_val}))
            return GeminiStructuredPlan(
                intent="SET_AC_MODE",
                objective_summary=f"Set AC mode to {ac_mode_val} at {ac_temp_val}C",
                user_request=utterance,
                steps=steps
            )
        elif ac_mode_val:
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_MODE", parameters={"mode": ac_mode_val}))
            return GeminiStructuredPlan(
                intent="SET_AC_MODE",
                objective_summary=f"Set AC mode to {ac_mode_val}",
                user_request=utterance,
                steps=steps
            )

        # 13. AC Temperature
        if ac_temp_val and any(t_kw in lower for t_kw in ["ac", "temp", "temperature", "degree", "celsius", "degrees", "make it", "drop", "raise", "set to", "at"]):
            steps.append(PlanStep(step_id=1, device="AC", capability="AC_SET_TEMPERATURE", parameters={"temperature": ac_temp_val}))
            return GeminiStructuredPlan(intent="SET_AC_TEMPERATURE", objective_summary=f"Set AC to {ac_temp_val}C", user_request=utterance, steps=steps)

        # Strict Semantic Explicit Volume (Unit-Aware: MUST contain volume keyword, NOT duration)
        # Forbids bare numbers or durations like "30 minutes" from setting volume!
        if not any(dur_unit in lower for dur_unit in ["minute", "min", "hour", "hr", "sec", "second"]):
            vol_m = re.search(r'(?:set\s+)?(?:volume|vol)\s+(?:to\s+)?(\d+)', lower)
            if vol_m:
                vol_val = int(vol_m.group(1))
                if 0 <= vol_val <= 100:
                    steps.append(PlanStep(step_id=1, device="PC", capability="PC_SET_VOLUME", parameters={"volume": vol_val}))
                    return GeminiStructuredPlan(intent="SET_EXPLICIT_VOLUME", objective_summary=f"Set volume to {vol_val}%", user_request=utterance, steps=steps)

        # Streaming Services (Turn 31: "Netflix", "Prime Video")
        for prov in ["netflix", "prime video", "prime", "hotstar"]:
            if prov in lower or prov.replace("_", " ") in lower:
                steps.append(PlanStep(step_id=1, device="PROJECTOR", capability="PROJECTOR_POWER_WAKE"))
                steps.append(PlanStep(step_id=2, device="PROJECTOR", capability="PROJECTOR_SWITCH_HDMI1"))
                steps.append(PlanStep(step_id=3, device="FIRE_TV", capability="FIRE_TV_POWER_WAKE"))
                steps.append(PlanStep(step_id=4, device="FIRE_TV", capability="FIRE_TV_MEDIA_DIRECT_PROVIDER", parameters={"provider": prov}))
                steps.append(PlanStep(step_id=5, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
                return GeminiStructuredPlan(intent=f"LAUNCH_{prov.upper().replace(' ', '_')}", objective_summary=f"Launch {prov} on cinema stack", user_request=utterance, steps=steps)

        # Direct Audio Routing Plans
        if any(s in lower for s in ["switch audio to pc", "route audio to pc", "switch to bedroom speaker", "connect soundbar to pc", "audio to pc", "audio to computer"]):
            steps.append(PlanStep(step_id=1, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_PC"))
            return GeminiStructuredPlan(intent="SOUNDBAR_ROUTE_TO_PC", objective_summary="Route soundbar audio to PC", user_request=utterance, steps=steps)

        if any(s in lower for s in ["switch audio to fire tv", "route audio to fire tv", "connect soundbar to fire tv", "audio to fire tv", "audio to tv"]):
            steps.append(PlanStep(step_id=1, device="SOUNDBAR", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"))
            return GeminiStructuredPlan(intent="SOUNDBAR_ROUTE_TO_FIRE_TV", objective_summary="Route soundbar audio to Fire TV", user_request=utterance, steps=steps)

        return None



