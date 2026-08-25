"""
Authoritative RoomEvent Data Model for Animus Smart Room Stage 6 Event-Driven Awareness.
Defines strongly typed, immutable room events, event categories, and lightweight provenance metadata.

EPISTEMIC INVARIANT:
Events record what was observed, transitioned, or scheduled at a point in time.
Events are immutable fact records, not live physical telemetry.
"""

from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class RoomEventType(str, Enum):
    """Authoritative event taxonomy for the Animus in-process EventBus."""
    TELEMETRY_CHANGED = "TELEMETRY_CHANGED"
    DEVICE_CONNECTED = "DEVICE_CONNECTED"
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"
    MEDIA_STARTED = "MEDIA_STARTED"
    MEDIA_STOPPED = "MEDIA_STOPPED"
    MEDIA_PAUSED = "MEDIA_PAUSED"
    MEDIA_RESUMED = "MEDIA_RESUMED"
    MODE_CHANGED = "MODE_CHANGED"
    MODE_DIVERGENCE_DETECTED = "MODE_DIVERGENCE_DETECTED"
    GOAL_STARTED = "GOAL_STARTED"
    GOAL_COMPLETED = "GOAL_COMPLETED"
    GOAL_FAILED = "GOAL_FAILED"
    GOAL_PAUSED = "GOAL_PAUSED"
    GOAL_SUPERSEDED = "GOAL_SUPERSEDED"
    GOAL_RESUMED = "GOAL_RESUMED"
    GOAL_EXPIRED = "GOAL_EXPIRED"
    EXTERNAL_STATE_CHANGE = "EXTERNAL_STATE_CHANGE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    PROACTIVE_SUGGESTION_CREATED = "PROACTIVE_SUGGESTION_CREATED"
    PROACTIVE_SUGGESTION_EXPIRED = "PROACTIVE_SUGGESTION_EXPIRED"
    PROACTIVE_SUGGESTION_INVALIDATED = "PROACTIVE_SUGGESTION_INVALIDATED"
    PROACTIVE_SUGGESTION_ACCEPTED = "PROACTIVE_SUGGESTION_ACCEPTED"
    PROACTIVE_SUGGESTION_REJECTED = "PROACTIVE_SUGGESTION_REJECTED"
    TIMER_FIRED = "TIMER_FIRED"
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_CANCELLED = "SCHEDULE_CANCELLED"
    SCHEDULE_EXPIRED = "SCHEDULE_EXPIRED"
    SCHEDULE_EXECUTED = "SCHEDULE_EXECUTED"
    USER_COMMAND = "USER_COMMAND"
    SYSTEM_STARTUP = "SYSTEM_STARTUP"
    SITUATION_CHANGED = "SITUATION_CHANGED"


class RoomEvent(BaseModel):
    """
    Immutable structured event emitted through the RoomEventBus.
    Contains lightweight sanitized metadata to prevent large memory retention.
    """
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    event_type: RoomEventType
    timestamp: float = Field(default_factory=time.time)
    source: str = "ROOM_MONITOR"
    affected_subsystem: Optional[str] = None
    previous_state: Dict[str, Any] = Field(default_factory=dict)
    observed_state: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = "LIVE_TELEMETRY"
    correlation_id: Optional[str] = None
    goal_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def summary(self) -> str:
        """Returns a concise 1-line event summary."""
        sub = f" [{self.affected_subsystem}]" if self.affected_subsystem else ""
        return f"[{self.event_type.value}]{sub} at {self.timestamp:.2f}: {self.observed_state or self.metadata}"
