"""
Authoritative Autonomy Policy Model for Phase 2 Stage 9 Animus Smart Room.
Defines explicit autonomy capabilities, permission tiers, and audit models.

EPISTEMIC & AUTONOMY INVARIANTS:
1. Conservative default: Every capability defaults to ASK or DENIED unless explicitly granted.
2. Capability isolation: Granting autonomy for one subsystem (e.g. AC) never authorizes other subsystems (e.g. Media or Soundbar).
3. Audit integrity: Every autonomous evaluation produces a structured audit log record.
"""

from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AutonomyCapability(str, Enum):
    """Subsystems and operations subject to autonomy policies."""
    AC_ADJUSTMENT = "AC_ADJUSTMENT"
    MEDIA_CONTROL = "MEDIA_CONTROL"
    PROJECTOR_CONTROL = "PROJECTOR_CONTROL"
    LIGHTING_CONTROL = "LIGHTING_CONTROL"
    AUDIO_ROUTING = "AUDIO_ROUTING"
    ROUTINE_EXECUTION = "ROUTINE_EXECUTION"
    SCHEDULED_ACTION = "SCHEDULED_ACTION"
    RECOVERY = "RECOVERY"


class AutonomyGrantLevel(str, Enum):
    """Authorization tiers for autonomous actions."""
    ASK = "ASK"                                     # User confirmation required
    AUTHORIZED_AUTONOMOUS = "AUTHORIZED_AUTONOMOUS" # Bounded autonomous execution permitted
    DENIED = "DENIED"                               # Action strictly prohibited


class AutonomyAuditRecord(BaseModel):
    """Immutable audit trail entry for autonomous policy evaluations."""
    audit_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    capability: AutonomyCapability
    action_type: str
    target_subsystem: str
    grant_level: AutonomyGrantLevel
    is_authorized: bool
    reason: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    origin_trigger: str = "PROACTIVE_MONITOR"  # e.g. "PROACTIVE_MONITOR", "SCHEDULED_TRIGGER", "RECOVERY_FAULT"
