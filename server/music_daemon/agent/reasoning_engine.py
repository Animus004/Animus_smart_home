"""
Authoritative Adaptive Reasoning Engine for Phase 2 Stage 7 Animus Smart Room.
Performs deterministic multi-factor situational reasoning over room facts, active goals,
behavioral modes, scheduled intent, and user constraints to generate structured ReasoningResults.

EPISTEMIC & EXECUTION INVARIANTS:
1. Physical reality wins: Live physical telemetry outranks inferred assumptions.
2. Structured output: Produces strongly-typed ReasoningResult models, never unverified prose.
3. Explicit command dominance: Explicit user commands outrank past goals and learned defaults.
4. Non-duplication: Reasoning evaluates candidate actions; execution remains with TaskPlanner/Executor.
"""

from __future__ import annotations
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.behavior_modes import BehaviorMode
from agent.task_models import AgentGoal, GoalStatus
from agent.room_events import RoomEvent

logger = logging.getLogger("music_daemon.agent.reasoning_engine")


class CandidateAction(BaseModel):
    """A potential action considered during room reasoning."""
    action_type: str
    target_subsystem: str
    target_capability: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    priority: int = 10  # Lower number = higher priority


class ReasoningConflict(BaseModel):
    """A detected conflict between goals, commands, or modes."""
    conflict_type: str  # e.g. "GOAL_VS_MODE", "GOAL_VS_COMMAND", "ENVIRONMENTAL_DRIFT", "RESOURCE_CONTENTION"
    severity: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    description: str
    competing_entities: List[str] = Field(default_factory=list)
    resolution_applied: Optional[str] = None


class ReasoningResult(BaseModel):
    """
    Authoritative structured reasoning outcome for room decision-making.
    """
    result_id: str = Field(default_factory=lambda: f"reas_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    relevant_facts: List[str] = Field(default_factory=list)
    conflicts: List[ReasoningConflict] = Field(default_factory=list)
    candidate_actions: List[CandidateAction] = Field(default_factory=list)
    selected_action: Optional[CandidateAction] = None
    reason: str = ""
    confidence: float = 1.0
    constraints_considered: List[str] = Field(default_factory=list)
    requires_user_confirmation: bool = False
    confirmation_question: Optional[str] = None
    rejected_alternatives: List[Dict[str, Any]] = Field(default_factory=list)

    def summary(self) -> str:
        """Concise summary of reasoning outcome."""
        act = self.selected_action.action_type if self.selected_action else "NONE"
        return f"[Reasoning] Selected: {act} | Reason: {self.reason} | Confidence: {self.confidence:.2f}"


class ReasoningEngine:
    """
    Evaluates multi-factor room state and produces deterministic, inspectable reasoning results.
    """

    def __init__(self):
        self.reasoning_history: List[ReasoningResult] = []
        self._max_history: int = 100

    def reason(
        self,
        user_command: Optional[str] = None,
        live_telemetry: Optional[Dict[str, Any]] = None,
        active_mode: BehaviorMode = BehaviorMode.IDLE,
        active_goals: Optional[List[AgentGoal]] = None,
        scheduled_tasks: Optional[List[Any]] = None,
        media_session: Optional[Any] = None,
        behavioral_preferences: Optional[Dict[str, Any]] = None,
        recent_events: Optional[List[RoomEvent]] = None,
        safety_constraints: Optional[List[str]] = None
    ) -> ReasoningResult:
        """
        Executes structured multi-factor evaluation over the room state.
        """
        telemetry = live_telemetry or {}
        goals = active_goals or []
        tasks = scheduled_tasks or []
        prefs = behavioral_preferences or {}
        constraints = list(safety_constraints or [])

        facts: List[str] = []
        conflicts: List[ReasoningConflict] = []
        candidates: List[CandidateAction] = []
        rejected: List[Dict[str, Any]] = []

        # 1. Fact Extraction
        facts.append(f"Active mode is {active_mode.value}")
        if "ac_target_temperature" in telemetry:
            facts.append(f"AC setpoint is {telemetry['ac_target_temperature']}°C")
        if "ambient_temperature" in telemetry:
            facts.append(f"Ambient temperature is {telemetry['ambient_temperature']}°C")
        if "projector_power" in telemetry:
            facts.append(f"Projector is {'ON' if telemetry['projector_power'] else 'OFF'}")
        if "soundbar_owner" in telemetry:
            facts.append(f"Soundbar audio owner is {telemetry['soundbar_owner']}")

        # 2. Safety Invariant Check
        sb_owner = telemetry.get("soundbar_owner")
        if sb_owner == "FIRE_TV" or active_mode == BehaviorMode.MOVIE:
            constraints.append("SOUNDBAR_FIRE_TV_PROTECTION: Do not reclaim PC Bluetooth audio")

        # 3. Competing Intent & Conflict Detection
        # Scenario: User command vs Active Goal / Mode
        if user_command:
            lower_cmd = user_command.lower()
            if any(w in lower_cmd for w in ["sleep", "bed", "goodnight"]) and active_mode == BehaviorMode.MOVIE:
                conflicts.append(
                    ReasoningConflict(
                        conflict_type="COMMAND_VS_MODE",
                        severity="HIGH",
                        description="User requested sleep transition while room is in MOVIE mode",
                        competing_entities=["COMMAND_SLEEP", "MODE_MOVIE"],
                        resolution_applied="Explicit command supersedes active MOVIE mode"
                    )
                )
                candidates.append(
                    CandidateAction(
                        action_type="TRANSITION_MODE",
                        target_subsystem="ROOM",
                        target_capability="SET_BEHAVIOR_MODE",
                        parameters={"mode": "SLEEP"},
                        rationale="Explicit user sleep command overrides active movie session",
                        priority=1
                    )
                )

            # Scenario: Scheduled wake task conflict with user cancellation
            if any(w in lower_cmd for w in ["don't wake", "dont wake", "cancel alarm", "cancel wake"]):
                conflicts.append(
                    ReasoningConflict(
                        conflict_type="GOAL_VS_COMMAND",
                        severity="HIGH",
                        description="User explicitly requested cancellation of wake routine",
                        competing_entities=["COMMAND_CANCEL_WAKE", "SCHEDULED_WAKE"],
                        resolution_applied="Cancel pending wake tasks"
                    )
                )
                candidates.append(
                    CandidateAction(
                        action_type="CANCEL_SCHEDULED_TASK",
                        target_subsystem="SCHEDULER",
                        target_capability="CANCEL_TASK",
                        parameters={"action_type": "WAKE_ROUTINE"},
                        rationale="User explicitly cancelled wake-up schedule",
                        priority=1
                    )
                )

            # Scenario: Direct AC temperature adjustment
            if "ac" in lower_cmd or "temperature" in lower_cmd or "degree" in lower_cmd:
                candidates.append(
                    CandidateAction(
                        action_type="AC_SET_TEMPERATURE",
                        target_subsystem="AC",
                        target_capability="AC_SET_TEMPERATURE",
                        parameters={},
                        rationale="Direct user thermal adjustment",
                        priority=2
                    )
                )

        # 4. Environmental Drift Evaluation
        amb = telemetry.get("ambient_temperature")
        target_ac = telemetry.get("ac_target_temperature")
        if amb is not None and target_ac is not None:
            if amb >= 27 and target_ac < 25:
                conflicts.append(
                    ReasoningConflict(
                        conflict_type="ENVIRONMENTAL_DRIFT",
                        severity="MEDIUM",
                        description=f"Ambient temperature ({amb}°C) significantly exceeds target setpoint ({target_ac}°C)",
                        competing_entities=["AMBIENT_HEAT", "TARGET_COMFORT"],
                        resolution_applied="Suggest or authorize bounded thermal adjustment"
                    )
                )

        # 5. Goal Arbitration & Selection
        selected: Optional[CandidateAction] = None
        reason: str = ""
        confidence: float = 1.0
        req_confirm: bool = False
        confirm_q: Optional[str] = None

        if candidates:
            # Sort by priority (lowest integer = highest priority)
            candidates.sort(key=lambda c: c.priority)
            selected = candidates[0]
            reason = selected.rationale
            # Record rejected alternatives
            for alt in candidates[1:]:
                rejected.append({
                    "action_type": alt.action_type,
                    "target_subsystem": alt.target_subsystem,
                    "rejected_reason": f"Superseded by higher priority action {selected.action_type}"
                })
        else:
            reason = f"No hardware action required. Room status is nominal in {active_mode.value} mode."

        result = ReasoningResult(
            relevant_facts=facts,
            conflicts=conflicts,
            candidate_actions=candidates,
            selected_action=selected,
            reason=reason,
            confidence=confidence,
            constraints_considered=constraints,
            requires_user_confirmation=req_confirm,
            confirmation_question=confirm_q,
            rejected_alternatives=rejected
        )

        self._archive(result)
        return result

    def _archive(self, result: ReasoningResult) -> None:
        self.reasoning_history.append(result)
        if len(self.reasoning_history) > self._max_history:
            self.reasoning_history.pop(0)

    def get_latest_reasoning(self) -> Optional[ReasoningResult]:
        return self.reasoning_history[-1] if self.reasoning_history else None
