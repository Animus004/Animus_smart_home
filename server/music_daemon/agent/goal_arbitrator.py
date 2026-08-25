"""
Authoritative Goal Arbitrator for Phase 2 Stage 7 Animus Smart Room.
Resolves competing goals, schedule clashes, and mode transitions with explicit priority hierarchies.

EPISTEMIC & ARBITRATION INVARIANTS:
1. Explicit user commands strictly supersede obsolete goals or routine defaults.
2. Never silently destroy verified historical actions when superseding/cancelling.
3. Resuming goals requires live physical telemetry re-evaluation.
4. Explains arbitration rationale with deterministic provenance.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agent.task_models import AgentGoal, GoalStatus, StepStatus
from agent.behavior_modes import BehaviorMode
from agent.room_events import RoomEvent, RoomEventType

logger = logging.getLogger("music_daemon.agent.goal_arbitrator")


class ArbitrationOutcome(str, Enum):
    """Result of competing goal arbitration."""
    EXECUTE_NEW = "EXECUTE_NEW"
    SUPERSEDE_EXISTING = "SUPERSEDE_EXISTING"
    PAUSE_EXISTING = "PAUSE_EXISTING"
    REJECT_NEW = "REJECT_NEW"
    MERGE_GOALS = "MERGE_GOALS"
    NO_CONFLICT = "NO_CONFLICT"


class ArbitrationDecision(BaseModel):
    """Structured result of goal arbitration."""
    decision_id: str = Field(default_factory=lambda: f"arb_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    outcome: ArbitrationOutcome
    winning_goal_id: Optional[str] = None
    affected_goal_ids: List[str] = Field(default_factory=list)
    rationale: str = ""
    conflict_type: Optional[str] = None
    requires_user_confirmation: bool = False
    confirmation_prompt: Optional[str] = None


class GoalArbitrator:
    """
    Arbitrates conflicts between active goals, scheduled tasks, and incoming commands.
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self.event_bus = event_bus
        self.arbitration_history: List[ArbitrationDecision] = []

    def arbitrate(
        self,
        incoming_intent: str,
        incoming_goal: Optional[AgentGoal] = None,
        active_goals: Optional[List[AgentGoal]] = None,
        scheduled_tasks: Optional[List[Any]] = None,
        active_mode: BehaviorMode = BehaviorMode.IDLE,
        live_telemetry: Optional[Dict[str, Any]] = None
    ) -> ArbitrationDecision:
        """
        Evaluates potential conflicts between an incoming intent/goal and active room commitments.
        """
        current_active = [g for g in (active_goals or []) if g.status in (GoalStatus.PLANNING, GoalStatus.EXECUTING, GoalStatus.PENDING)]
        tasks = scheduled_tasks or []

        # 1. No active goals or tasks -> Clean execute
        if not current_active and not tasks:
            decision = ArbitrationDecision(
                outcome=ArbitrationOutcome.NO_CONFLICT,
                winning_goal_id=incoming_goal.goal_id if incoming_goal else None,
                rationale="No existing goals or schedules in progress; proceed cleanly."
            )
            self._archive(decision)
            return decision

        # 2. Incoming Sleep / Bed Command vs Active Movie Goal
        if any(w in incoming_intent.lower() for w in ["sleep", "bed", "goodnight"]):
            movie_goals = [g for g in current_active if "movie" in g.normalized_goal.lower()]
            if movie_goals:
                affected = [g.goal_id for g in movie_goals]
                decision = ArbitrationDecision(
                    outcome=ArbitrationOutcome.SUPERSEDE_EXISTING,
                    winning_goal_id=incoming_goal.goal_id if incoming_goal else None,
                    affected_goal_ids=affected,
                    conflict_type="MOVIE_VS_SLEEP",
                    rationale="Explicit user Sleep intent supersedes in-flight Cinema goal."
                )
                self._archive(decision)
                return decision

        # 3. Incoming User Wake Cancellation vs Scheduled Wake Routine
        if any(w in incoming_intent.lower() for w in ["don't wake", "dont wake", "cancel wake", "cancel alarm"]):
            wake_tasks = [t for t in tasks if getattr(t, "action_type", "") in ("WAKE_ROUTINE", "PROJECTOR_POWER_WAKE")]
            if wake_tasks:
                affected = [getattr(t, "task_id", str(t)) for t in wake_tasks]
                decision = ArbitrationDecision(
                    outcome=ArbitrationOutcome.SUPERSEDE_EXISTING,
                    winning_goal_id=None,
                    affected_goal_ids=affected,
                    conflict_type="WAKE_SCHEDULE_CANCELLATION",
                    rationale="Explicit user cancellation supersedes scheduled wake routine."
                )
                self._archive(decision)
                return decision

        # 4. Incoming Movie Goal vs Active Music Session
        if incoming_goal and "movie" in incoming_goal.normalized_goal.lower():
            music_goals = [g for g in current_active if "music" in g.normalized_goal.lower()]
            if music_goals:
                affected = [g.goal_id for g in music_goals]
                decision = ArbitrationDecision(
                    outcome=ArbitrationOutcome.SUPERSEDE_EXISTING,
                    winning_goal_id=incoming_goal.goal_id,
                    affected_goal_ids=affected,
                    conflict_type="MUSIC_VS_MOVIE",
                    rationale="Explicit Cinema request supersedes background music session."
                )
                self._archive(decision)
                return decision

        # 5. Default Priority Comparison if multiple goals
        if current_active and incoming_goal:
            # Explicit user command attached to incoming goal wins
            decision = ArbitrationDecision(
                outcome=ArbitrationOutcome.SUPERSEDE_EXISTING,
                winning_goal_id=incoming_goal.goal_id,
                affected_goal_ids=[g.goal_id for g in current_active],
                conflict_type="GENERAL_GOAL_PREEMPTION",
                rationale="New explicit user command takes precedence over active in-flight goals."
            )
            self._archive(decision)
            return decision

        decision = ArbitrationDecision(
            outcome=ArbitrationOutcome.EXECUTE_NEW,
            winning_goal_id=incoming_goal.goal_id if incoming_goal else None,
            rationale="Proceeding with requested intent."
        )
        self._archive(decision)
        return decision

    def supersede_goal(
        self,
        old_goal: AgentGoal,
        new_goal_id: str,
        reason: str = "SUPERSEDED_BY_NEW_USER_COMMAND"
    ) -> AgentGoal:
        """
        Marks an existing goal as SUPERSEDED, preserving verified step execution history.
        """
        old_goal.status = GoalStatus.SUPERSEDED
        old_goal.superseded_by = new_goal_id
        old_goal.completed_at = time.time()
        old_goal.failure_summary = reason

        # Cancel only pending/executing/blocked steps; preserve verified ones
        for step in old_goal.steps:
            if step.status in (StepStatus.PENDING, StepStatus.EXECUTING, StepStatus.BLOCKED, StepStatus.READY):
                step.status = StepStatus.CANCELLED

        logger.info(f"[GOAL_ARBITRATOR] Goal {old_goal.goal_id} SUPERSEDED by {new_goal_id}: {reason}")
        return old_goal

    def compare_priorities(self, goal_a: AgentGoal, goal_b: AgentGoal) -> int:
        """
        Returns -1 if goal_a has higher priority, 1 if goal_b has higher priority, 0 if equal.
        Explicit user commands always outrank background routine goals.
        """
        # User requested vs system/routine
        a_is_user = getattr(goal_a, "originating_command", None) is not None
        b_is_user = getattr(goal_b, "originating_command", None) is not None

        if a_is_user and not b_is_user:
            return -1
        if b_is_user and not a_is_user:
            return 1

        # Newer turn takes precedence
        if goal_a.created_at > goal_b.created_at:
            return -1
        elif goal_b.created_at > goal_a.created_at:
            return 1
        return 0

    def _archive(self, decision: ArbitrationDecision) -> None:
        self.arbitration_history.append(decision)
        if len(self.arbitration_history) > 100:
            self.arbitration_history.pop(0)
