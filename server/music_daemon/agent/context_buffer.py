"""
Authoritative Multi-Turn Conversation Context Buffer for Animus Smart Room.
Maintains rolling dialog history, active conversational threads, pending parameters,
negative constraints, historical target devices, and bounded AgentSessionMemory.

EPISTEMIC INVARIANT:
Memory records verified historical facts, but live telemetry is authoritative for current physical reality.
"""

from __future__ import annotations
import logging
import time
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.models import ResolvedIntent, IntentCategory
from agent.interaction_result import AgentInteractionResult, StateDelta, DecisionType, PhysicalVerificationStatus
from agent.state_memory import (
    AgentSessionMemory,
    RecentActionMemory,
    VerifiedRoomFact,
    FactProvenance,
    ReferenceType,
    ConversationReference,
    ExternalStateDiff
)

logger = logging.getLogger("music_daemon.agent.context_buffer")


class ConversationTurn(BaseModel):
    """Represents a single conversational turn in the rolling context buffer."""
    speaker: str  # "user" | "animus"
    utterance: str
    timestamp: float = Field(default_factory=time.time)
    intent: Optional[str] = None
    category: Optional[IntentCategory] = None
    target_device: Optional[str] = None
    target_capability: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    action_taken: bool = False
    interaction_result: Optional[AgentInteractionResult] = None


class ConversationThread(BaseModel):
    """Tracks an active multi-turn conversational objective."""
    thread_id: str
    thread_type: str  # "CINEMA_SETUP", "AC_CONTROL", "RELAXATION_FLOW", "TASK_MANAGEMENT", "AUDIO_ADJUSTMENT"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    original_intent: Optional[Dict[str, Any]] = None
    missing_parameters: List[str] = Field(default_factory=list)
    resolved_parameters: Dict[str, Any] = Field(default_factory=dict)
    negative_constraints: List[str] = Field(default_factory=list)
    step_index: int = 1
    completed: bool = False


class ConversationContextBuffer:
    """
    Generalized multi-turn conversational state engine.
    Maintains rolling history, active threads, in-flight corrections, and bounded session memory.
    """

    def __init__(self, max_history_turns: int = 10):
        self.max_history_turns = max_history_turns
        self.history: List[ConversationTurn] = []
        self.active_thread: Optional[ConversationThread] = None
        self.last_target_device: Optional[str] = None
        self.last_target_capability: Optional[str] = None
        self.last_target_parameters: Dict[str, Any] = {}
        self.last_media_provider: Optional[str] = None
        self.last_interaction_result: Optional[AgentInteractionResult] = None
        self.last_executed_action: Optional[AgentInteractionResult] = None
        self.last_state_delta: Optional[StateDelta] = None
        self.session_memory: AgentSessionMemory = AgentSessionMemory()
        self.active_goal: Optional[Any] = None
        self.paused_goals: List[Any] = []
        self.superseded_goals: List[Any] = []
        self.active_mode: Optional[str] = None
        self.active_media_session: Optional[Any] = None
        self.pending_suggestion: Optional[Any] = None
        self.turn_counter: int = 0



    def record_user_turn(self, utterance: str) -> None:
        """Records an incoming user utterance into the rolling buffer."""
        self.turn_counter += 1
        turn = ConversationTurn(speaker="user", utterance=utterance)
        self.history.append(turn)
        if len(self.history) > self.max_history_turns:
            self.history.pop(0)

    def record_animus_turn(
        self,
        utterance: str,
        intent: Optional[str] = None,
        category: Optional[IntentCategory] = None,
        target_device: Optional[str] = None,
        target_capability: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        action_taken: bool = False
    ) -> None:
        """Records an outgoing Animus response with structured execution context."""
        turn = ConversationTurn(
            speaker="animus",
            utterance=utterance,
            intent=intent,
            category=category,
            target_device=target_device,
            target_capability=target_capability,
            parameters=parameters or {},
            action_taken=action_taken
        )
        self.history.append(turn)
        if len(self.history) > self.max_history_turns:
            self.history.pop(0)

        if target_device:
            self.last_target_device = target_device
            self.session_memory.set_reference(
                ReferenceType.DEVICE, target_device, target_device, self.turn_counter
            )
        if target_capability:
            self.last_target_capability = target_capability
        if parameters:
            self.last_target_parameters = parameters
            if "provider" in parameters:
                self.last_media_provider = parameters["provider"]
                self.session_memory.set_reference(
                    ReferenceType.MEDIA, parameters["provider"], parameters["provider"], self.turn_counter
                )

    def get_last_agent_turn(self) -> Optional[ConversationTurn]:
        """Returns the most recent utterance and context spoken by the agent."""
        for turn in reversed(self.history):
            if turn.speaker == "animus":
                return turn
        return None

    def start_thread(
        self,
        thread_type: str,
        original_intent: Optional[ResolvedIntent] = None,
        missing_parameters: Optional[List[str]] = None
    ) -> ConversationThread:
        """Initializes a new active conversational thread."""
        thread = ConversationThread(
            thread_id=f"{thread_type}_{int(time.time()*1000)}",
            thread_type=thread_type,
            original_intent=original_intent.model_dump() if original_intent else None,
            missing_parameters=missing_parameters or (original_intent.missing_parameters if original_intent else [])
        )
        self.active_thread = thread
        logger.info(f"[CONTEXT_BUFFER] Started thread: {thread.thread_type} (id={thread.thread_id})")
        return thread

    def update_thread_parameters(self, key: str, value: Any) -> None:
        """Updates parameters in the active thread."""
        if self.active_thread:
            self.active_thread.resolved_parameters[key] = value
            if key in self.active_thread.missing_parameters:
                self.active_thread.missing_parameters.remove(key)
            self.active_thread.updated_at = time.time()
            self.active_thread.step_index += 1

    def add_negative_constraint(self, constraint: str) -> None:
        """Records a negative constraint (e.g. 'not music') in the active thread."""
        if self.active_thread:
            self.active_thread.negative_constraints.append(constraint.upper())
            self.active_thread.updated_at = time.time()

    def complete_thread(self) -> None:
        """Marks the active thread as completed."""
        if self.active_thread:
            logger.info(f"[CONTEXT_BUFFER] Completed thread: {self.active_thread.thread_type}")
            self.active_thread.completed = True
            self.active_thread = None

    def clear_active_thread(self) -> None:
        """Clears/supersedes the active thread."""
        if self.active_thread:
            logger.info(f"[CONTEXT_BUFFER] Cleared active thread: {self.active_thread.thread_type}")
            self.active_thread = None

    def is_topic_switch(self, utterance: str) -> bool:
        """
        Determines whether the incoming utterance interrupts the active thread with a new topic.
        Strict Invariant: An interrupted thread must NEVER execute an abandoned pending intent.
        """
        if not self.active_thread:
            return False

        lower = utterance.strip().lower()
        topic_switch_triggers = [
            "heading to", "going to", "at my desk", "moving to", "stepping to",
            "what is on", "what are my", "what do i have", "what's on my", "what did i",
            "good morning", "good night", "remind me", "add task", "create task",
            "mark ", "completed ", "done with", "set ac", "turn on ac", "turn off ac",
            "practicing guitar", "i had lunch", "just had lunch", "focus mode"
        ]
        return any(t in lower for t in topic_switch_triggers)

    def is_ac_correction(self, utterance: str) -> Optional[int]:
        """
        Checks if the utterance is a numeric correction for the AC (e.g. 'Actually 25', 'Actually, make that 25', 'Wait, no - 23').
        Returns the integer setpoint if previous turn or goal included an AC command, else None.
        """
        has_ac_in_goal = False
        latest_goal = self.session_memory.get_latest_goal()
        if latest_goal and hasattr(latest_goal, "steps"):
            has_ac_in_goal = any(s.target_subsystem == "AC" for s in latest_goal.steps)

        has_ac_in_history = any(
            t.target_device == "AC" or (t.intent and ("AC_" in t.intent or "SET_AC_" in t.intent))
            for t in self.history[-4:]
        )

        has_ac_context = (
            self.last_target_device == "AC" or
            (self.active_thread and self.active_thread.thread_type == "AC_CONTROL") or
            (self.session_memory.get_latest_action(target_subsystem="AC") is not None) or
            has_ac_in_goal or
            has_ac_in_history
        )
        if not has_ac_context:
            return None


        # Clean punctuation like commas, em-dashes, hyphens, periods
        cleaned = re.sub(r'[,—\-\.:!?]', ' ', utterance.strip().lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Check for numeric correction patterns
        match = re.search(
            r'^(?:actually|wait\s+no|no|wait|instead)?\s*(?:make\s+(?:it|that)\s+)?(?:set\s+(?:it|that)\s+to\s+)?(?:make\s+it\s+)?(\d+)(?:\s*(?:degrees?|°c|celsius|is\s+fine|is\s+good|percent|instead))?$',
            cleaned
        )
        if match:
            val = int(match.group(1))
            if 16 <= val <= 30:
                return val
        return None



    def is_provider_correction(self, utterance: str) -> Optional[str]:
        """
        Checks if the utterance is a provider switch during cinema/media context (e.g. 'Actually YouTube').
        """
        lower = utterance.strip().lower()
        for prov in ["netflix", "youtube", "prime video", "prime", "apple tv", "apple_tv", "hotstar", "smarttube", "vlc", "hulu", "disney"]:
            if prov in lower and ("actually" in lower or "switch to" in lower or "make it" in lower or "change to" in lower or self.active_thread is not None):
                return prov.replace(" ", "_").lower()
        return None

    def resolve_reference(self, phrase: str) -> Optional[str]:
        """
        Resolves pronouns or relative references ('it', 'that', 'this', 'them', 'there', 'too')
        to the appropriate active target device or subsystem.
        """
        lower = phrase.strip().lower()

        # Check explicit device keywords in phrase first
        if any(w in lower for w in ["ac", "air conditioner", "air conditioning", "cooling", "temperature"]):
            return "AC"
        if any(w in lower for w in ["projector", "screen", "display", "beam"]):
            return "PROJECTOR"
        if any(w in lower for w in ["music", "soundbar", "speaker", "song", "track", "volume"]):
            return "SOUNDBAR"
        if any(w in lower for w in ["tv", "fire tv", "firetv", "movie", "cinema", "stream"]):
            return "FIRE_TV"

        # If it's a pronoun reference ("it", "that", "this", "them", "there", "turn that off too")
        if any(p in lower for p in ["it", "that", "this", "them", "there", "too"]):
            # 1. Check active conversation thread target device
            if self.active_thread and self.active_thread.target_device:
                return self.active_thread.target_device

            # 2. Check session memory most recent referenced device
            ref = self.session_memory.get_most_recent_reference(ReferenceType.DEVICE)
            if ref and ref.name:
                return ref.name

            # 3. Fallback to last_target_device
            if self.last_target_device:
                return self.last_target_device

        return None

    def record_interaction_result(self, result: AgentInteractionResult) -> None:
        """Stores the authoritative structured interaction result in rolling state and session memory."""
        self.last_interaction_result = result
        if result.execution_attempted and result.execution_success:
            self.last_executed_action = result
            if result.state_delta:
                self.last_state_delta = result.state_delta

            # Create strongly typed RecentActionMemory entry
            action_mem = RecentActionMemory(
                turn_index=self.turn_counter,
                user_utterance=result.user_utterance,
                intent=result.understood_intent,
                target_subsystem=result.target_device or (result.state_delta.subsystem if result.state_delta else "ROOM"),
                target_capability=result.target_capability,
                requested_parameters=result.context_used.get("parameters", {}),
                validated_plan_summary=result.validated_plan,
                execution_success=result.execution_success,
                execution_status="VERIFIED" if result.physical_verification == PhysicalVerificationStatus.VERIFIED else "UNVERIFIED",
                readback_status=result.physical_verification.value,
                before_state=result.context_used.get("before_state", {}),
                after_state=result.context_used.get("after_state", {}),
                state_delta=result.state_delta,
                reason_for_action=result.response_reason or result.user_utterance
            )
            self.session_memory.record_action(action_mem)

            if result.state_delta and result.state_delta.verified_value is not None:
                self.session_memory.record_fact(
                    subsystem=result.state_delta.subsystem,
                    attribute=result.state_delta.attribute,
                    value=result.state_delta.verified_value,
                    provenance=FactProvenance.VERIFIED_EXECUTION,
                    source_tag=result.understood_intent
                )

    def get_action_history(self, depth: int = 1, target_subsystem: Optional[str] = None) -> Optional[RecentActionMemory]:
        """Retrieves historical action at specified depth (1 = most recent, 2 = one before that)."""
        return self.session_memory.get_action_history(depth=depth, target_subsystem=target_subsystem)

    def explain_last_action(self, depth: int = 1, target_subsystem: Optional[str] = None, user_address: str = "buddy") -> str:
        """Constructs an epistemologically verified explanation of a historical physical action."""
        act = self.get_action_history(depth=depth, target_subsystem=target_subsystem)
        if not act:
            target_str = f" to the {target_subsystem}" if target_subsystem else ""
            return f"I haven't changed anything{target_str} recently, {user_address}."

        delta = act.state_delta
        prefix = "Before that, I" if depth > 1 else "I"
        if delta:
            if delta.attribute == "target_temperature":
                prev_t = delta.previous_value
                new_t = delta.new_value or delta.verified_value
                if prev_t is not None and new_t is not None and prev_t != new_t:
                    verb = "raised" if new_t > prev_t else "lowered"
                    return f"{prefix} {verb} the AC from {prev_t} to {new_t}°C, {user_address}."
                return f"{prefix} set the AC to {new_t}°C, {user_address}."
            elif delta.attribute == "power":
                state_str = "on" if delta.new_value is True else "off"
                return f"{prefix} turned the {delta.subsystem} {state_str}, {user_address}."
            elif delta.attribute == "media_playback":
                return f"{prefix} {str(delta.new_value).lower()} the media playback, {user_address}."
            elif delta.attribute == "media_provider":
                return f"{prefix} switched the cinema stream to {str(delta.new_value).replace('_', ' ').title()}, {user_address}."
            elif delta.attribute == "master_volume":
                return f"{prefix} adjusted the volume to {delta.new_value}%, {user_address}."

        intent_name = act.intent.replace("_", " ").lower()
        return f"{prefix} executed {intent_name}, {user_address}."

    def explain_last_action_reason(self, depth: int = 1, user_address: str = "buddy") -> str:
        """Explains why an action was chosen based on observable context."""
        act = self.get_action_history(depth=depth)
        if not act:
            return f"I haven't executed any recent actions, {user_address}."

        if act.reason_for_action:
            return f"{act.reason_for_action}, {user_address}."

        return f"Because you asked me to '{act.user_utterance}', {user_address}."

    def get_repeatable_action(self) -> Optional[RecentActionMemory]:
        """Returns the most recent verified repeatable action for 'do that again'."""
        return self.session_memory.get_latest_action()

    def get_undo_target(self, device: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns reverse target parameters if the action has a verifiable previous state."""
        act = self.session_memory.get_latest_action(target_subsystem=device)
        if act and act.state_delta and act.state_delta.previous_value is not None:
            return {
                "subsystem": act.target_subsystem,
                "attribute": act.state_delta.attribute,
                "revert_to_value": act.state_delta.previous_value,
                "current_verified_value": act.state_delta.verified_value or act.state_delta.new_value,
                "action": act
            }
        return None

    def detect_external_state_change(
        self,
        subsystem: str,
        attribute: str,
        current_telemetry_value: Any
    ) -> Optional[ExternalStateDiff]:
        """Detects whether current physical telemetry diverges from verified memory."""
        return self.session_memory.reconcile_external_diff(subsystem, attribute, current_telemetry_value)

    def cancel_active_flow(self, user_address: str = "buddy") -> str:
        """Cancels active follow-up threads safely."""
        if self.active_thread:
            thread_name = self.active_thread.thread_type
            self.clear_active_thread()
            return f"Got you {user_address} — cancelled {thread_name.replace('_', ' ').lower()}."
        return f"Okay {user_address}, leaving it as it is."

    def set_active_goal(self, goal: Any) -> None:
        """Sets the currently orchestrating active goal."""
        self.active_goal = goal

    def get_active_goal(self) -> Optional[Any]:
        """Returns currently active goal if executing."""
        return self.active_goal

    def clear_active_goal(self) -> None:
        """Clears active goal reference."""
        self.active_goal = None

    def cancel_active_goal(self, user_address: str = "buddy") -> str:
        """Cancels any pending steps in the active goal while preserving completed actions."""
        if self.active_goal:
            from agent.task_models import GoalStatus, StepStatus
            self.active_goal.status = GoalStatus.CANCELLED
            completed = [s for s in self.active_goal.steps if s.status == StepStatus.VERIFIED]
            for s in self.active_goal.steps:
                if s.status in (StepStatus.PENDING, StepStatus.READY, StepStatus.EXECUTING):
                    s.status = StepStatus.CANCELLED

            self.session_memory.record_goal(self.active_goal)
            self.active_goal = None

            if completed:
                comp_names = ", ".join([f"the {s.target_subsystem.lower()}" for s in completed])
                return f"Okay {user_address}. I stopped the remaining steps. {comp_names.capitalize()} is already set, but I didn't continue with the rest."
            return f"Okay {user_address}. I stopped the remaining steps."
        return f"No active goal was running, {user_address}."

    def introspect_goal(self, user_address: str = "buddy") -> str:
        """Explains active or recent goal progression truthfully."""
        from agent.task_models import StepStatus
        goal = self.active_goal or self.session_memory.get_latest_goal()
        if not goal:
            return f"I don't have an active or recent goal on record, {user_address}."

        completed = [f"{s.capability.replace('_', ' ').lower()}" for s in goal.steps if s.status in (StepStatus.VERIFIED, StepStatus.SKIPPED_ALREADY_SATISFIED)]
        remaining = [f"{s.capability.replace('_', ' ').lower()}" for s in goal.steps if s.status in (StepStatus.PENDING, StepStatus.READY, StepStatus.EXECUTING)]

        res = f"Goal: {goal.normalized_goal} (Status: {goal.status.value}), {user_address}."
        if completed:
            res += f" Completed: {', '.join(completed)}."
        if remaining:
            res += f" Remaining: {', '.join(remaining)}."
        return res

    def introspect_goal_remaining(self, user_address: str = "buddy") -> str:
        """Reports remaining steps in active or latest goal."""
        from agent.task_models import StepStatus
        goal = self.active_goal or self.session_memory.get_latest_goal()
        if not goal:
            return f"No goal steps are currently pending, {user_address}."

        remaining = [f"{s.capability.replace('_', ' ').lower()}" for s in goal.steps if s.status in (StepStatus.PENDING, StepStatus.READY, StepStatus.EXECUTING)]
        if remaining:
            return f"Remaining steps for {goal.normalized_goal}: {', '.join(remaining)}, {user_address}."
        return f"All steps for {goal.normalized_goal} are finished, {user_address}."

    def introspect_goal_failures(self, user_address: str = "buddy") -> str:
        """Reports failed or blocked steps in active or latest goal."""
        from agent.task_models import StepStatus
        goal = self.active_goal or self.session_memory.get_latest_goal()
        if not goal:
            return f"I haven't encountered any goal failures, {user_address}."

        failed = [f"{s.capability.replace('_', ' ').lower()} ({s.failure_reason or 'failed'})" for s in goal.steps if s.status in (StepStatus.FAILED, StepStatus.BLOCKED)]
        if failed:
            return f"The following step(s) failed or were blocked: {', '.join(failed)}, {user_address}."
        return f"No steps failed in the last goal, {user_address}."

    def get_recent_history_summary(self) -> List[Dict[str, Any]]:
        """Returns a sanitized summary of recent conversation for context injection."""
        return [
            {
                "speaker": t.speaker,
                "text": t.utterance,
                "target_device": t.target_device,
                "action_taken": t.action_taken
            }
            for t in self.history[-6:]
        ]

    def set_active_goal(self, goal: Any) -> None:
        """Sets the currently orchestrating active goal."""
        self.active_goal = goal

    def get_active_goal(self) -> Optional[Any]:
        """Returns active goal if still in-flight."""
        from agent.task_models import GoalStatus
        if self.active_goal and self.active_goal.status in (GoalStatus.PLANNING, GoalStatus.EXECUTING, GoalStatus.PENDING):
            return self.active_goal
        return None

    def pause_active_goal(self) -> Optional[Any]:
        """Pauses in-flight goal, marking it PAUSED."""
        from agent.task_models import GoalStatus
        if self.active_goal:
            self.active_goal.status = GoalStatus.PAUSED
            self.active_goal.paused_at = time.time()
            self.paused_goals.append(self.active_goal)
            paused = self.active_goal
            self.active_goal = None
            logger.info(f"[CONTEXT_BUFFER] Paused goal {paused.goal_id}")
            return paused
        return None

    def resume_goal(self, goal_id: Optional[str] = None) -> Optional[Any]:
        """Finds and resumes a paused goal."""
        from agent.task_models import GoalStatus
        if self.paused_goals:
            if goal_id:
                for i, g in enumerate(self.paused_goals):
                    if g.goal_id == goal_id:
                        resumed = self.paused_goals.pop(i)
                        resumed.status = GoalStatus.RESUMABLE
                        self.active_goal = resumed
                        logger.info(f"[CONTEXT_BUFFER] Resumed goal {resumed.goal_id}")
                        return resumed
            else:
                resumed = self.paused_goals.pop(-1)
                resumed.status = GoalStatus.RESUMABLE
                self.active_goal = resumed
                logger.info(f"[CONTEXT_BUFFER] Resumed goal {resumed.goal_id}")
                return resumed
        return None



    def supersede_active_goal(self, new_goal_id: str) -> Optional[Any]:
        """Marks current in-flight goal as SUPERSEDED by new goal."""
        from agent.task_models import GoalStatus
        if self.active_goal:
            self.active_goal.status = GoalStatus.SUPERSEDED
            self.active_goal.superseded_by = new_goal_id
            self.active_goal.completed_at = time.time()
            self.superseded_goals.append(self.active_goal)
            superseded = self.active_goal
            self.active_goal = None
            logger.info(f"[CONTEXT_BUFFER] Goal {superseded.goal_id} SUPERSEDED by {new_goal_id}")
            return superseded
        return None

    def cancel_active_goal(self, user_address: str = "buddy", reason: str = "USER_CANCELLED") -> str:
        """Cancels current active goal."""
        from agent.task_models import GoalStatus, StepStatus
        if self.active_goal:
            self.active_goal.status = GoalStatus.CANCELLED
            self.active_goal.completed_at = time.time()
            self.active_goal.failure_summary = reason
            for s in self.active_goal.steps:
                if s.status in (StepStatus.PENDING, StepStatus.EXECUTING, StepStatus.BLOCKED):
                    s.status = StepStatus.CANCELLED
            verified = [s.target_subsystem.lower() for s in self.active_goal.steps if s.status == StepStatus.VERIFIED]
            cancelled = self.active_goal
            self.active_goal = None
            logger.info(f"[CONTEXT_BUFFER] Cancelled active goal {cancelled.goal_id}: {reason}")
            if verified:
                return f"I stopped the remaining steps, {user_address}. The completed steps ({', '.join(verified)}) will stay as they are."
            return f"I stopped the remaining steps, {user_address}. The completed steps will stay as they are."
        return f"There is no active goal in progress, {user_address}."





    def set_pending_suggestion(self, suggestion: Any) -> None:
        self.pending_suggestion = suggestion

    def get_pending_suggestion(self) -> Optional[Any]:
        return self.pending_suggestion

    def clear_pending_suggestion(self) -> None:
        self.pending_suggestion = None

    def get_user_context_summary(self, user_profile: Any) -> str:
        """
        Formats a concise, high-value user context summary for Brain reasoning prompts.
        """
        if not user_profile:
            return ""
        addr = getattr(getattr(user_profile, "identity", None), "preferred_address", "buddy")
        thermal = getattr(user_profile, "thermal", None)
        ac_str = f"Default Setpoint: {getattr(thermal, 'preferred_temp_set', 24)}°C, Mode: {getattr(thermal, 'preferred_mode', 'AUTO')}" if thermal else "24°C AUTO"
        ent = getattr(user_profile, "entertainment", None)
        stream_str = ", ".join([str(s).title() for s in getattr(ent, "preferred_streaming_services", [])[:3]]) if ent else "Netflix, YouTube"

        return (
            f"USER CONTEXT:\n"
            f"  - Preferred Address: {addr}\n"
            f"  - AC Preferences   : {ac_str}\n"
            f"  - Preferred Streams: {stream_str}\n"
            f"  - Active Mode      : {self.active_mode or 'IDLE'}"
        )

    def get_long_term_memory_summary(self, query: str = "") -> str:
        """
        Retrieves long-term episodic memory & confirmed facts prompt block.
        """
        try:
            from agent.long_term_memory import get_long_term_memory
            lt_mem = get_long_term_memory()
            return lt_mem.build_memory_context_prompt(query)
        except Exception as e:
            logger.debug(f"[CONTEXT_BUFFER_LT_MEM_ERR] {e}")
            return ""


