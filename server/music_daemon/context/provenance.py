"""
Provenance and freshness tracking for Context and Preferences in Animus Smart Room.
Follows canonical RoomState provenance conventions with deterministic status transitions.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ContextProvenanceStatus(str, Enum):
    """Authoritative provenance statuses for context telemetry and preference records."""
    KNOWN = "KNOWN"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class ContextProvenance(BaseModel):
    """
    Provenance metadata tracking the origin, freshness, and epistemic certainty of a context item.
    """
    source: str
    observed_at: float = Field(default_factory=time.time)
    status: ContextProvenanceStatus = ContextProvenanceStatus.KNOWN
    ttl_seconds: Optional[float] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def is_fresh(self, current_time: Optional[float] = None) -> bool:
        """Evaluates whether the context value is within its validity TTL."""
        if self.ttl_seconds is None:
            return True
        now = current_time if current_time is not None else time.time()
        return (now - self.observed_at) <= self.ttl_seconds

    def effective_status(self, current_time: Optional[float] = None) -> ContextProvenanceStatus:
        """Returns the current effective status, degrading KNOWN/DERIVED to STALE if TTL expired."""
        if self.status in (ContextProvenanceStatus.UNKNOWN, ContextProvenanceStatus.UNAVAILABLE):
            return self.status
        if not self.is_fresh(current_time):
            return ContextProvenanceStatus.STALE
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dictionary serialization."""
        now = time.time()
        return {
            "source": self.source,
            "observed_at": self.observed_at,
            "age_seconds": round(now - self.observed_at, 2),
            "status": self.effective_status(now).value,
            "ttl_seconds": self.ttl_seconds,
            "confidence": self.confidence,
            "is_fresh": self.is_fresh(now)
        }
