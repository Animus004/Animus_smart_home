"""
Authoritative Situation Engine for Animus Smart Room Stage 6.
Classifies high-level operational situations from live physical telemetry, active modes,
media playback sessions, goals, and recent room events.

EPISTEMIC INVARIANT:
Situations reflect current observable physical reality combined with active agent intent.
Inference is never treated as verified physical readback.
"""

from __future__ import annotations
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.room_events import RoomEvent, RoomEventType
from agent.event_bus import RoomEventBus
from agent.behavior_modes import BehaviorMode

logger = logging.getLogger("music_daemon.agent.situation_engine")


class RoomSituation(str, Enum):
    """High-level contextual situation of the smart room."""
    ROOM_IDLE = "ROOM_IDLE"
    MOVIE_ACTIVE = "MOVIE_ACTIVE"
    MUSIC_ACTIVE = "MUSIC_ACTIVE"
    SLEEP_ACTIVE = "SLEEP_ACTIVE"
    WORK_ACTIVE = "WORK_ACTIVE"
    COMFORT_REQUIRED = "COMFORT_REQUIRED"
    MEDIA_READY = "MEDIA_READY"
    MEDIA_INTERRUPTED = "MEDIA_INTERRUPTED"
    DEVICE_DEGRADED = "DEVICE_DEGRADED"
    EXTERNAL_CHANGE_DETECTED = "EXTERNAL_CHANGE_DETECTED"
    GOAL_WAITING = "GOAL_WAITING"
    GOAL_BLOCKED = "GOAL_BLOCKED"
    MODE_DIVERGENCE = "MODE_DIVERGENCE"


class SituationAssessment(BaseModel):
    """Structured assessment of current room situation."""
    situation: RoomSituation = RoomSituation.ROOM_IDLE
    confidence: float = 1.0
    active_mode: str = "IDLE"
    media_state: str = "STOPPED"
    evidence: Dict[str, Any] = Field(default_factory=dict)
    explanation: str = "Room is in nominal idle state."
    timestamp: float = Field(default_factory=time.time)


class SituationEngine:
    """
    Synthesizes multi-subsystem room telemetry into an authoritative situation assessment.
    """

    def __init__(self, event_bus: Optional[RoomEventBus] = None):
        self.event_bus = event_bus
        self.current_assessment = SituationAssessment()

    def assess_situation(
        self,
        live_telemetry: Dict[str, Any],
        active_mode: BehaviorMode = BehaviorMode.IDLE,
        media_playback_state: str = "STOPPED",
        active_goal: Optional[Any] = None,
        recent_events: Optional[List[RoomEvent]] = None
    ) -> SituationAssessment:
        """
        Classifies the room situation with epistemic priority ordering.
        """
        prev_situation = self.current_assessment.situation
        evidence: Dict[str, Any] = {
            "mode": active_mode.value,
            "media": media_playback_state,
            "telemetry": live_telemetry
        }

        # 1. Goal Blocked
        if active_goal and getattr(active_goal, "status", None) == "BLOCKED":
            assessment = SituationAssessment(
                situation=RoomSituation.GOAL_BLOCKED,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation=f"Goal {active_goal.goal_id} is blocked on dependencies."
            )
        # 2. Goal Waiting / Paused
        elif active_goal and getattr(active_goal, "status", None) == "PAUSED":
            assessment = SituationAssessment(
                situation=RoomSituation.GOAL_WAITING,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation=f"Goal {active_goal.goal_id} is paused waiting to resume."
            )
        # 3. Recent Mode Divergence
        elif recent_events and any(e.event_type == RoomEventType.MODE_DIVERGENCE_DETECTED for e in recent_events[-3:]):
            assessment = SituationAssessment(
                situation=RoomSituation.MODE_DIVERGENCE,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation=f"Physical telemetry diverges from {active_mode.value} mode expectations."
            )
        # 4. Recent External Change Detected
        elif recent_events and any(e.event_type == RoomEventType.EXTERNAL_STATE_CHANGE for e in recent_events[-3:]):
            assessment = SituationAssessment(
                situation=RoomSituation.EXTERNAL_CHANGE_DETECTED,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="External physical state change was detected."
            )
        # 5. Media Interrupted (Paused during active movie mode)
        elif active_mode == BehaviorMode.MOVIE and media_playback_state == "PAUSED":
            assessment = SituationAssessment(
                situation=RoomSituation.MEDIA_INTERRUPTED,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Media playback is temporarily paused during movie mode."
            )
        # 6. Media Ready (Movie hardware online, but media stopped)
        elif active_mode == BehaviorMode.MOVIE and media_playback_state in ("STOPPED", "UNKNOWN") and live_telemetry.get("projector_power") is True:
            assessment = SituationAssessment(
                situation=RoomSituation.MEDIA_READY,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Movie equipment is ready, waiting for media playback to start."
            )
        # 7. Active Modes
        elif active_mode == BehaviorMode.MOVIE:
            assessment = SituationAssessment(
                situation=RoomSituation.MOVIE_ACTIVE,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Movie mode is actively running."
            )
        elif active_mode == BehaviorMode.MUSIC:
            assessment = SituationAssessment(
                situation=RoomSituation.MUSIC_ACTIVE,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Music playback is active."
            )
        elif active_mode == BehaviorMode.SLEEP:
            assessment = SituationAssessment(
                situation=RoomSituation.SLEEP_ACTIVE,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Sleep mode is active."
            )
        elif active_mode == BehaviorMode.WORK:
            assessment = SituationAssessment(
                situation=RoomSituation.WORK_ACTIVE,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Work/Focus mode is active."
            )
        # 8. Environmental Comfort Required
        elif self._is_comfort_required(live_telemetry):
            assessment = SituationAssessment(
                situation=RoomSituation.COMFORT_REQUIRED,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Room ambient temperature significantly diverges from setpoint."
            )
        # 9. Nominal Idle
        else:
            assessment = SituationAssessment(
                situation=RoomSituation.ROOM_IDLE,
                active_mode=active_mode.value,
                media_state=media_playback_state,
                evidence=evidence,
                explanation="Room is nominal and idle."
            )

        self.current_assessment = assessment

        if self.event_bus and assessment.situation != prev_situation:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.SITUATION_CHANGED,
                    source="SITUATION_ENGINE",
                    previous_state={"situation": prev_situation.value},
                    observed_state={"situation": assessment.situation.value},
                    metadata={"explanation": assessment.explanation}
                )
            )
            logger.info(f"[SITUATION_ENGINE] Situation transitioned: {prev_situation.value} -> {assessment.situation.value}")

        return assessment

    def _is_comfort_required(self, live_telemetry: Dict[str, Any]) -> bool:
        amb = live_telemetry.get("ambient_temperature") or live_telemetry.get("room_temperature")
        target = live_telemetry.get("ac_target_temperature") or live_telemetry.get("target_temperature")
        if amb is not None and target is not None:
            return abs(amb - target) >= 3
        return False
