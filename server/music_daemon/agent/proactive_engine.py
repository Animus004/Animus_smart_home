"""
Authoritative Proactive Intelligence Engine for Animus Smart Room.
Monitors room environment, mode baselines, and media sessions to generate non-intrusive suggestions.

EPISTEMIC & SAFETY INVARIANTS:
1. Proactive suggestions are strictly ASK / SUGGEST.
2. Animus NEVER executes hardware commands silently as part of a proactive suggestion.
3. Hardware execution requires explicit user acceptance, routing through the canonical PlanValidator/PlanExecutor pipeline.
4. Suggestion Invalidation: When physical conditions change such that a suggestion is no longer valid,
   it is immediately marked INVALIDATED and cleared.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agent.behavior_modes import BehaviorMode
from agent.room_events import RoomEvent, RoomEventType

logger = logging.getLogger("music_daemon.agent.proactive_engine")


class ProactiveSuggestionCategory(str, Enum):
    """Categorization of proactive suggestions."""
    ENVIRONMENTAL = "ENVIRONMENTAL"
    MEDIA_READINESS = "MEDIA_READINESS"
    RECOVERY = "RECOVERY"
    ROUTINE = "ROUTINE"


class ProactiveSuggestionStatus(str, Enum):
    """Lifecycle status of a proactive suggestion."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class ProactiveSuggestion(BaseModel):
    """Data model representing a non-intrusive agent suggestion."""
    suggestion_id: str = Field(default_factory=lambda: f"sug_{uuid.uuid4().hex[:8]}")
    category: ProactiveSuggestionCategory
    proposed_action: str
    target_subsystem: str
    target_capability: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    explanation: str
    prompt_question: str
    reason: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    expires_at: float = Field(default_factory=lambda: time.time() + 120.0)  # 2 minute TTL
    status: ProactiveSuggestionStatus = ProactiveSuggestionStatus.PENDING


class ProactiveEngine:
    """
    Evaluates room conditions and generates suggestions without silent hardware execution.
    Maintains cooldown deduplication, pending suggestion tracking, and automatic invalidation.
    """

    def __init__(self, enabled: bool = True, cooldown_seconds: float = 60.0, event_bus: Optional[Any] = None):
        self.enabled = enabled
        self.cooldown_seconds = cooldown_seconds
        self.event_bus = event_bus
        self.pending_suggestion: Optional[ProactiveSuggestion] = None
        self.suggestion_history: List[ProactiveSuggestion] = []
        self._last_suggestion_time: Dict[str, float] = {}

    def evaluate_room(
        self,
        live_telemetry: Dict[str, Any],
        active_mode: BehaviorMode,
        media_playback_state: str = "STOPPED"
    ) -> Optional[ProactiveSuggestion]:
        """
        Evaluates current room state against mode expectations to generate suggestions.
        Returns None if no suggestion is warranted, disabled, or in cooldown.
        """
        if not self.enabled:
            return None

        # Check if existing pending suggestion has become invalidated by room changes
        self.evaluate_invalidation(live_telemetry, active_mode, media_playback_state)

        # Check if there is an unexpired pending suggestion already
        if self.pending_suggestion and self.pending_suggestion.status == ProactiveSuggestionStatus.PENDING:
            if time.time() < self.pending_suggestion.expires_at:
                return None
            else:
                self.pending_suggestion.status = ProactiveSuggestionStatus.EXPIRED
                if self.event_bus:
                    self.event_bus.publish(
                        RoomEvent(
                            event_type=RoomEventType.PROACTIVE_SUGGESTION_EXPIRED,
                            source="PROACTIVE_ENGINE",
                            metadata={"suggestion_id": self.pending_suggestion.suggestion_id}
                        )
                    )
                self.pending_suggestion = None

        now = time.time()

        # 1. Environmental Drift in MOVIE Mode (e.g. AC set to 23, but ambient room temp >= 27)
        if active_mode == BehaviorMode.MOVIE:
            ambient_temp = live_telemetry.get("ambient_temperature") or live_telemetry.get("room_temperature")
            ac_target = live_telemetry.get("ac_target_temperature", 23)
            if ambient_temp and ambient_temp >= (ac_target + 3):
                key = "ENV_DRIFT_MOVIE"
                if (now - self._last_suggestion_time.get(key, 0)) >= self.cooldown_seconds:
                    suggestion = ProactiveSuggestion(
                        category=ProactiveSuggestionCategory.ENVIRONMENTAL,
                        proposed_action="LOWER_AC",
                        target_subsystem="ac",
                        target_capability="AC_SET_TEMPERATURE",
                        parameters={"temperature": ac_target - 1 if ac_target > 18 else 18},
                        explanation=f"The room has warmed to {ambient_temp}°C while in Movie Mode.",
                        prompt_question="The room is getting a bit warm. Want me to lower the AC?",
                        reason="Ambient temperature drifted above setpoint threshold",
                        evidence={"ambient_temp": ambient_temp, "ac_target": ac_target}
                    )
                    self._last_suggestion_time[key] = now
                    self.pending_suggestion = suggestion
                    if self.event_bus:
                        self.event_bus.publish(
                            RoomEvent(
                                event_type=RoomEventType.PROACTIVE_SUGGESTION_CREATED,
                                source="PROACTIVE_ENGINE",
                                affected_subsystem="AC",
                                observed_state={"suggestion_id": suggestion.suggestion_id, "category": suggestion.category.value},
                                metadata={"prompt_question": suggestion.prompt_question}
                            )
                        )
                    logger.info(f"[PROACTIVE_SUGGESTION] Generated environmental suggestion: {suggestion.prompt_question}")
                    return suggestion

        # 2. Media Readiness Suggestion (Room ready for movie, but media is STOPPED)
        if active_mode == BehaviorMode.MOVIE and media_playback_state in ("STOPPED", "UNKNOWN"):
            proj_on = live_telemetry.get("projector_power") is True
            sb_on_tv = live_telemetry.get("soundbar_owner") == "FIRE_TV"
            if proj_on and sb_on_tv:
                key = "MEDIA_READY_MOVIE"
                if (now - self._last_suggestion_time.get(key, 0)) >= self.cooldown_seconds:
                    suggestion = ProactiveSuggestion(
                        category=ProactiveSuggestionCategory.MEDIA_READINESS,
                        proposed_action="PROMPT_MEDIA_START",
                        target_subsystem="fire_tv",
                        target_capability="FIRE_TV_MEDIA_PLAY",
                        parameters={},
                        explanation="Movie room hardware is verified ready, but media playback is stopped.",
                        prompt_question="The room is ready. Want me to start something?",
                        reason="Hardware ready but playback inactive",
                        evidence={"projector_power": True, "soundbar_owner": "FIRE_TV"}
                    )
                    self._last_suggestion_time[key] = now
                    self.pending_suggestion = suggestion
                    if self.event_bus:
                        self.event_bus.publish(
                            RoomEvent(
                                event_type=RoomEventType.PROACTIVE_SUGGESTION_CREATED,
                                source="PROACTIVE_ENGINE",
                                affected_subsystem="FIRE_TV",
                                observed_state={"suggestion_id": suggestion.suggestion_id, "category": suggestion.category.value},
                                metadata={"prompt_question": suggestion.prompt_question}
                            )
                        )
                    logger.info(f"[PROACTIVE_SUGGESTION] Generated media readiness suggestion: {suggestion.prompt_question}")
                    return suggestion

        return None

    def evaluate_invalidation(
        self,
        live_telemetry: Dict[str, Any],
        active_mode: BehaviorMode,
        media_playback_state: str = "STOPPED"
    ) -> bool:
        """
        Checks if pending suggestion is no longer relevant due to physical room state transitions.
        """
        if not self.pending_suggestion or self.pending_suggestion.status != ProactiveSuggestionStatus.PENDING:
            return False

        sug = self.pending_suggestion

        # Environmental suggestion invalidation
        if sug.category == ProactiveSuggestionCategory.ENVIRONMENTAL:
            ambient_temp = live_telemetry.get("ambient_temperature") or live_telemetry.get("room_temperature")
            ac_target = live_telemetry.get("ac_target_temperature", 23)
            if ambient_temp and ambient_temp < (ac_target + 2):
                return self.invalidate_pending_suggestion("Room ambient temperature returned to nominal range")

        # Media readiness suggestion invalidation
        if sug.category == ProactiveSuggestionCategory.MEDIA_READINESS:
            if media_playback_state in ("PLAYING", "PAUSED"):
                return self.invalidate_pending_suggestion("Media playback is now active")
            if live_telemetry.get("projector_power") is False:
                return self.invalidate_pending_suggestion("Projector was turned off")

        return False

    def invalidate_pending_suggestion(self, reason: str) -> bool:
        """Marks active suggestion INVALIDATED and archives it."""
        if not self.pending_suggestion or self.pending_suggestion.status != ProactiveSuggestionStatus.PENDING:
            return False

        self.pending_suggestion.status = ProactiveSuggestionStatus.INVALIDATED
        invalidated = self.pending_suggestion
        self._archive_suggestion(invalidated)
        self.pending_suggestion = None

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.PROACTIVE_SUGGESTION_INVALIDATED,
                    source="PROACTIVE_ENGINE",
                    metadata={"suggestion_id": invalidated.suggestion_id, "reason": reason}
                )
            )

        logger.info(f"[PROACTIVE_INVALIDATED] Suggestion {invalidated.suggestion_id} invalidated: {reason}")
        return True

    def accept_pending_suggestion(self) -> Tuple[bool, Optional[ProactiveSuggestion]]:
        """Accepts the active pending suggestion."""
        if not self.pending_suggestion or self.pending_suggestion.status != ProactiveSuggestionStatus.PENDING:
            return False, None
        if time.time() > self.pending_suggestion.expires_at:
            self.pending_suggestion.status = ProactiveSuggestionStatus.EXPIRED
            return False, None

        self.pending_suggestion.status = ProactiveSuggestionStatus.ACCEPTED
        accepted = self.pending_suggestion
        self._archive_suggestion(accepted)
        self.pending_suggestion = None

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.PROACTIVE_SUGGESTION_ACCEPTED,
                    source="PROACTIVE_ENGINE",
                    metadata={"suggestion_id": accepted.suggestion_id}
                )
            )

        logger.info(f"[PROACTIVE_ACCEPT] User accepted suggestion: {accepted.suggestion_id}")
        return True, accepted

    def reject_pending_suggestion(self) -> Tuple[bool, Optional[ProactiveSuggestion]]:
        """Rejects the active pending suggestion."""
        if not self.pending_suggestion or self.pending_suggestion.status != ProactiveSuggestionStatus.PENDING:
            return False, None

        self.pending_suggestion.status = ProactiveSuggestionStatus.REJECTED
        rejected = self.pending_suggestion
        self._archive_suggestion(rejected)
        self.pending_suggestion = None

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.PROACTIVE_SUGGESTION_REJECTED,
                    source="PROACTIVE_ENGINE",
                    metadata={"suggestion_id": rejected.suggestion_id}
                )
            )

        logger.info(f"[PROACTIVE_REJECT] User rejected suggestion: {rejected.suggestion_id}")
        return True, rejected

    def defer_pending_suggestion(self) -> Tuple[bool, Optional[ProactiveSuggestion]]:
        """Defers the active pending suggestion."""
        if not self.pending_suggestion or self.pending_suggestion.status != ProactiveSuggestionStatus.PENDING:
            return False, None

        self.pending_suggestion.status = ProactiveSuggestionStatus.DEFERRED
        deferred = self.pending_suggestion
        self._archive_suggestion(deferred)
        self.pending_suggestion = None
        logger.info(f"[PROACTIVE_DEFER] User deferred suggestion: {deferred.suggestion_id}")
        return True, deferred

    def get_pending_suggestion(self) -> Optional[ProactiveSuggestion]:
        if self.pending_suggestion and self.pending_suggestion.status == ProactiveSuggestionStatus.PENDING:
            if time.time() < self.pending_suggestion.expires_at:
                return self.pending_suggestion
            else:
                self.pending_suggestion.status = ProactiveSuggestionStatus.EXPIRED
                self.pending_suggestion = None
        return None

    def clear_pending(self):
        self.pending_suggestion = None

    def _archive_suggestion(self, suggestion: ProactiveSuggestion):
        self.suggestion_history.append(suggestion)
        if len(self.suggestion_history) > 20:
            self.suggestion_history.pop(0)
