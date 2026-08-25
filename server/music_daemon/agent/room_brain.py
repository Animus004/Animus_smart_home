"""
Authoritative Unified Room Brain for Phase 2 Stage 10 Animus Smart Room.
Serves as the high-level world model and orchestration engine unifying physical telemetry,
events, situations, modes, goals, schedules, media, preferences, reasoning, and policies.

EPISTEMIC & ARCHITECTURAL INVARIANTS:
1. ZERO HARDWARE DUPLICATION: RoomBrain never executes hardware directly; it orchestrates
   the canonical TaskPlanner -> PlanValidator -> PlanExecutor pipeline.
2. PHYSICAL REALITY WINS: Fresh live physical telemetry is the absolute source of truth.
3. UNIFIED COGNITION: Models 'the room' as a cohesive physical environment.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.behavior_modes import BehaviorMode
from agent.room_events import RoomEvent, RoomEventType
from agent.task_models import AgentGoal, GoalStatus
from agent.reasoning_engine import ReasoningEngine, ReasoningResult
from agent.goal_arbitrator import GoalArbitrator, ArbitrationDecision, ArbitrationOutcome
from agent.policy_engine import PolicyEngine, PolicyAuthorization
from agent.learning_engine import LearningEngine
from agent.autonomy_manager import AutonomyManager, AutonomyCapability

logger = logging.getLogger("music_daemon.agent.room_brain")


class UnifiedRoomSummary(BaseModel):
    """Holistic representation of the room's current physical and operational state."""
    timestamp: float = Field(default_factory=time.time)
    active_mode: str
    situation: str
    ambient_temperature: Optional[float] = None
    target_temperature: Optional[int] = None
    projector_active: bool = False
    soundbar_owner: str = "PC"
    active_goal_summary: Optional[str] = None
    pending_scheduled_tasks_count: int = 0
    active_media_app: Optional[str] = None
    autonomy_enabled: bool = True
    recent_events_count: int = 0


class RoomBrain:
    """
    Unified cognitive layer synthesizing room subsystems into a single world model.
    """

    def __init__(
        self,
        reasoning_engine: Optional[ReasoningEngine] = None,
        goal_arbitrator: Optional[GoalArbitrator] = None,
        policy_engine: Optional[PolicyEngine] = None,
        learning_engine: Optional[LearningEngine] = None,
        autonomy_manager: Optional[AutonomyManager] = None,
        room_state_aggregator: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        situation_engine: Optional[Any] = None,
        behavior_mode_manager: Optional[Any] = None,
        goal_manager: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        media_session_manager: Optional[Any] = None
    ):
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.goal_arbitrator = goal_arbitrator or GoalArbitrator()
        self.policy_engine = policy_engine or PolicyEngine()
        self.learning_engine = learning_engine or LearningEngine()
        self.autonomy_manager = autonomy_manager or AutonomyManager()

        self.room_state_aggregator = room_state_aggregator
        self.event_bus = event_bus
        self.situation_engine = situation_engine
        self.behavior_mode_manager = behavior_mode_manager
        self.goal_manager = goal_manager
        self.scheduler = scheduler
        self.media_session_manager = media_session_manager

    def get_unified_summary(self) -> UnifiedRoomSummary:
        """
        Synthesizes the complete physical and logical state into a unified model.
        """
        telemetry = self._get_telemetry()
        mode_val = self.behavior_mode_manager.active_mode.value if self.behavior_mode_manager else BehaviorMode.IDLE.value
        sit_val = self.situation_engine.evaluate_situation().situation.value if self.situation_engine else "IDLE_ROOM"


        active_goal = None
        if self.goal_manager and hasattr(self.goal_manager, "active_goal"):
            ag = self.goal_manager.active_goal
            if ag and ag.status in (GoalStatus.PLANNING, GoalStatus.EXECUTING, GoalStatus.PENDING):
                active_goal = f"{ag.normalized_goal} ({ag.status.value})"


        sched_count = 0
        if self.scheduler:
            sched_count = len(self.scheduler.get_scheduled_tasks(include_completed=False))

        media_app = None
        if self.media_session_manager and getattr(self.media_session_manager, "active_session", None):
            media_app = self.media_session_manager.active_session.app_name

        events_count = len(self.event_bus.get_events(limit=50)) if self.event_bus else 0

        return UnifiedRoomSummary(
            active_mode=mode_val,
            situation=sit_val,
            ambient_temperature=telemetry.get("ambient_temperature"),
            target_temperature=telemetry.get("ac_target_temperature"),
            projector_active=bool(telemetry.get("projector_power", False)),
            soundbar_owner=telemetry.get("soundbar_owner", "PC"),
            active_goal_summary=active_goal,
            pending_scheduled_tasks_count=sched_count,
            active_media_app=media_app,
            autonomy_enabled=self.autonomy_manager.global_autonomy_enabled if self.autonomy_manager else True,
            recent_events_count=events_count
        )

    def explain_room_state(self) -> str:
        """
        Produces a truthful, human-readable narrative of room status grounded strictly in verified reality.
        """
        summary = self.get_unified_summary()
        parts: List[str] = []

        parts.append(f"You're in {summary.active_mode} mode.")

        # Projector & Fire TV
        if summary.projector_active:
            if summary.active_media_app:
                parts.append(f"The projector is on running {summary.active_media_app}.")
            else:
                parts.append("The projector is on.")
        else:
            parts.append("The projector is off.")

        # Soundbar
        parts.append(f"Soundbar audio is routed to {summary.soundbar_owner}.")

        # AC
        if summary.target_temperature is not None:
            parts.append(f"The AC is set to {summary.target_temperature}°C.")

        return " ".join(parts)

    def _get_telemetry(self) -> Dict[str, Any]:
        """Extracts sanitized telemetry map from aggregator."""
        if not self.room_state_aggregator:
            return {}
        try:
            state = self.room_state_aggregator.get_room_state(force_refresh=False)
            res = {}
            if hasattr(state, "ac") and state.ac:
                res["ac_target_temperature"] = getattr(state.ac, "target_temperature", None)
                res["ambient_temperature"] = getattr(state.ac, "current_temperature", None)
            if hasattr(state, "projector") and state.projector:
                res["projector_power"] = getattr(state.projector, "is_powered_on", False)
            if hasattr(state, "soundbar") and state.soundbar:
                res["soundbar_owner"] = getattr(state.soundbar, "current_owner", "PC")
            return res
        except Exception as e:
            logger.warning(f"[ROOM_BRAIN] Failed to read live telemetry: {e}")
            return {}
