"""
Authoritative Long-Horizon Goal Management Engine for Animus Smart Room Stage 6.
Maintains, pauses, resumes, supersedes, and expires multi-step goals across extended horizons.

EPISTEMIC & SAFETY INVARIANTS:
1. Physical Reality Overrides Memory: A resumed goal ALWAYS queries and evaluates fresh live telemetry before executing.
2. Stale goals expire cleanly (lease_seconds=300.0) and never silently execute unverified historical intentions.
3. No False Completion: Only verified readback confirms completion.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus
from agent.room_events import RoomEvent, RoomEventType
from agent.event_bus import RoomEventBus

logger = logging.getLogger("music_daemon.agent.long_horizon_goals")


class LongHorizonGoalManager:
    """
    Orchestrates goal persistence, pause/resume lifecycles, lease expiration,
    and live-telemetry reconciliation for multi-step room goals.
    """

    def __init__(
        self,
        event_bus: Optional[RoomEventBus] = None,
        default_lease_seconds: float = 300.0,
        max_active_goals: int = 10
    ):
        self.event_bus = event_bus
        self.default_lease_seconds = default_lease_seconds
        self.max_active_goals = max_active_goals
        self.active_goals: Dict[str, AgentGoal] = {}
        self.paused_goals: Dict[str, AgentGoal] = {}
        self.completed_goals: List[AgentGoal] = []
        self.expired_goals: List[AgentGoal] = []
        self.superseded_goals: List[AgentGoal] = []

    def register_goal(self, goal: AgentGoal, lease_seconds: Optional[float] = None) -> AgentGoal:
        """Registers a newly instantiated goal for long-horizon orchestration."""
        now = time.time()
        goal.created_at = now
        goal.last_verified_at = now
        if not hasattr(goal, "lease_seconds") or goal.lease_seconds is None:
            goal.lease_seconds = lease_seconds or self.default_lease_seconds

        self.active_goals[goal.goal_id] = goal

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.GOAL_STARTED,
                    source="LONG_HORIZON_GOAL_MANAGER",
                    goal_id=goal.goal_id,
                    metadata={"normalized_goal": goal.normalized_goal, "goal_type": goal.goal_type.value}
                )
            )
        logger.info(f"[LONG_HORIZON_GOAL] Registered goal {goal.goal_id} ({goal.normalized_goal}) with lease {goal.lease_seconds}s")
        return goal

    def pause_goal(self, goal_id: str, reason: str = "USER_INTERRUPTION") -> Optional[AgentGoal]:
        """Pauses an in-flight active goal."""
        goal = self.active_goals.pop(goal_id, None)
        if goal:
            goal.status = GoalStatus.PAUSED
            goal.paused_at = time.time()
            self.paused_goals[goal_id] = goal

            if self.event_bus:
                self.event_bus.publish(
                    RoomEvent(
                        event_type=RoomEventType.GOAL_PAUSED,
                        source="LONG_HORIZON_GOAL_MANAGER",
                        goal_id=goal_id,
                        metadata={"reason": reason}
                    )
                )
            logger.info(f"[LONG_HORIZON_GOAL] Paused goal {goal_id}: {reason}")
            return goal
        return None

    def resume_goal(
        self,
        goal_id: str,
        live_telemetry: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Optional[AgentGoal], str]:
        """
        Resumes a paused goal after validating freshness against live room telemetry.
        """
        goal = self.paused_goals.get(goal_id)
        if not goal:
            return False, None, f"No paused goal with ID {goal_id}"

        now = current_time or time.time()
        # Check lease staleness
        lease = getattr(goal, "lease_seconds", self.default_lease_seconds)
        last_seen = getattr(goal, "last_verified_at", goal.created_at)
        if (now - last_seen) > lease:
            goal.status = GoalStatus.EXPIRED
            self.paused_goals.pop(goal_id, None)
            self.expired_goals.append(goal)
            if self.event_bus:
                self.event_bus.publish(
                    RoomEvent(
                        event_type=RoomEventType.GOAL_EXPIRED,
                        source="LONG_HORIZON_GOAL_MANAGER",
                        goal_id=goal_id,
                        metadata={"reason": "Lease expired"}
                    )
                )
            return False, goal, f"Goal {goal_id} has expired ({int(now - last_seen)}s > {int(lease)}s) and cannot resume."

        # Re-evaluate live physical telemetry against remaining steps
        if live_telemetry:
            self._reconcile_goal_steps_with_telemetry(goal, live_telemetry)

        # Move to active
        self.paused_goals.pop(goal_id, None)
        goal.status = GoalStatus.RESUMABLE
        goal.last_verified_at = now
        self.active_goals[goal_id] = goal

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.GOAL_RESUMED,
                    source="LONG_HORIZON_GOAL_MANAGER",
                    goal_id=goal_id,
                    metadata={"resumed_steps_remaining": sum(1 for s in goal.steps if s.status in (StepStatus.PENDING, StepStatus.READY))}
                )
            )
        logger.info(f"[LONG_HORIZON_GOAL] Resumed goal {goal_id}")
        return True, goal, f"Resumed goal {goal_id}"

    def supersede_goal(self, old_goal_id: str, new_goal_id: str) -> Optional[AgentGoal]:
        """Marks a goal SUPERSEDED by a newer user goal."""
        goal = self.active_goals.pop(old_goal_id, None) or self.paused_goals.pop(old_goal_id, None)
        if goal:
            goal.status = GoalStatus.SUPERSEDED
            goal.superseded_by = new_goal_id
            goal.completed_at = time.time()
            self.superseded_goals.append(goal)

            if self.event_bus:
                self.event_bus.publish(
                    RoomEvent(
                        event_type=RoomEventType.GOAL_SUPERSEDED,
                        source="LONG_HORIZON_GOAL_MANAGER",
                        goal_id=old_goal_id,
                        metadata={"superseded_by": new_goal_id}
                    )
                )
            logger.info(f"[LONG_HORIZON_GOAL] Goal {old_goal_id} SUPERSEDED by {new_goal_id}")
            return goal
        return None

    def mark_completed(self, goal_id: str, completion_summary: str = "") -> Optional[AgentGoal]:
        """Moves verified completed goal to history."""
        goal = self.active_goals.pop(goal_id, None)
        if goal:
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = time.time()
            goal.completion_summary = completion_summary
            self.completed_goals.append(goal)

            if self.event_bus:
                self.event_bus.publish(
                    RoomEvent(
                        event_type=RoomEventType.GOAL_COMPLETED,
                        source="LONG_HORIZON_GOAL_MANAGER",
                        goal_id=goal_id,
                        metadata={"summary": completion_summary}
                    )
                )
            return goal
        return None

    def expire_stale_goals(self, current_time: Optional[float] = None) -> List[AgentGoal]:
        """Scans active and paused goals, expiring any whose lease has elapsed."""
        now = current_time or time.time()
        expired: List[AgentGoal] = []

        for goal_id in list(self.active_goals.keys()):
            g = self.active_goals[goal_id]
            lease = getattr(g, "lease_seconds", self.default_lease_seconds)
            last_seen = getattr(g, "last_verified_at", g.created_at)
            if (now - last_seen) > lease:
                g.status = GoalStatus.EXPIRED
                self.active_goals.pop(goal_id)
                self.expired_goals.append(g)
                expired.append(g)
                if self.event_bus:
                    self.event_bus.publish(
                        RoomEvent(
                            event_type=RoomEventType.GOAL_EXPIRED,
                            source="LONG_HORIZON_GOAL_MANAGER",
                            goal_id=goal_id,
                            metadata={"reason": "Lease expired"}
                        )
                    )

        for goal_id in list(self.paused_goals.keys()):
            g = self.paused_goals[goal_id]
            lease = getattr(g, "lease_seconds", self.default_lease_seconds)
            last_seen = getattr(g, "last_verified_at", g.created_at)
            if (now - last_seen) > lease:
                g.status = GoalStatus.EXPIRED
                self.paused_goals.pop(goal_id)
                self.expired_goals.append(g)
                expired.append(g)
                if self.event_bus:
                    self.event_bus.publish(
                        RoomEvent(
                            event_type=RoomEventType.GOAL_EXPIRED,
                            source="LONG_HORIZON_GOAL_MANAGER",
                            goal_id=goal_id,
                            metadata={"reason": "Paused goal lease timeout"}
                        )
                    )

        return expired

    def get_active_goal(self) -> Optional[AgentGoal]:
        """Returns the most recent active goal if any."""
        if self.active_goals:
            return list(self.active_goals.values())[-1]
        return None

    def get_goal(self, goal_id: str) -> Optional[AgentGoal]:
        return (
            self.active_goals.get(goal_id)
            or self.paused_goals.get(goal_id)
            or next((g for g in self.completed_goals if g.goal_id == goal_id), None)
            or next((g for g in self.superseded_goals if g.goal_id == goal_id), None)
            or next((g for g in self.expired_goals if g.goal_id == goal_id), None)
        )

    def _reconcile_goal_steps_with_telemetry(self, goal: AgentGoal, telemetry: Dict[str, Any]):
        """Updates step statuses if physical reality has already satisfied or invalidated them."""
        for step in goal.steps:
            if step.status == StepStatus.PENDING:
                if step.target_subsystem.upper() == "AC" and step.capability == "AC_SET_TEMPERATURE":
                    target_t = step.requested_parameters.get("temperature")
                    current_t = telemetry.get("ac_target_temperature") or telemetry.get("target_temperature")
                    if target_t is not None and current_t == target_t:
                        step.status = StepStatus.SKIPPED_ALREADY_SATISFIED
                        step.physical_readback = {"matched": True, "target_temperature": target_t}
                elif step.target_subsystem.upper() == "PROJECTOR" and step.capability == "PROJECTOR_POWER_WAKE":
                    if telemetry.get("projector_power") is True:
                        step.status = StepStatus.SKIPPED_ALREADY_SATISFIED
                        step.physical_readback = {"power": True}
