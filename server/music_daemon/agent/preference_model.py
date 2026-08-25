"""
Authoritative Learned Preference Model for Phase 2 Stage 8 Animus Smart Room.
Provides strongly-typed behavioral preferences with explicit provenance,
confidence scoring, observation counting, and mathematical decay/reinforcement.

EPISTEMIC INVARIANTS:
1. Learned preferences NEVER override explicit user commands, safety rules, or live physical readback.
2. Provenance is strictly preserved (USER_EXPLICIT > SESSION_INFERRED > OBSERVED_PATTERN > SYSTEM_DEFAULT).
3. Confidence decays over time if unconfirmed and reinforces upon repeated consistent observations.
"""

from __future__ import annotations
import math
import time
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PreferenceProvenance(str, Enum):
    """Authoritative source tracking for behavioral preferences."""
    USER_EXPLICIT = "USER_EXPLICIT"         # Explicitly told: "Remember I like 23 degrees" (Confidence 1.0)
    SESSION_INFERRED = "SESSION_INFERRED"   # Inferred within active multi-turn thread (Confidence 0.75)
    OBSERVED_PATTERN = "OBSERVED_PATTERN"   # Observed across multiple turns/sessions (Confidence 0.50 -> 0.90)
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"       # Built-in room defaults (Confidence 0.40)


class LearnedPreference(BaseModel):
    """
    A single learned personal preference with statistical provenance.
    """
    key: str
    value: Any
    provenance: PreferenceProvenance = PreferenceProvenance.SYSTEM_DEFAULT
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    observation_count: int = 1
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_confirmed_at: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def reinforce(self, observed_value: Any, boost: float = 0.15) -> None:
        """
        Reinforces confidence when an identical value is observed again.
        """
        now = time.time()
        if self.value == observed_value:
            self.observation_count += 1
            # Diminishing returns asymptotic boost towards 1.0
            self.confidence = min(0.95, self.confidence + boost * (1.0 - self.confidence))
            self.updated_at = now
            if self.provenance == PreferenceProvenance.SYSTEM_DEFAULT:
                self.provenance = PreferenceProvenance.OBSERVED_PATTERN
        else:
            # Contradiction observed: decrease confidence
            self.confidence = max(0.2, self.confidence - 0.20)
            self.updated_at = now

    def apply_decay(self, current_time: Optional[float] = None, half_life_days: float = 14.0) -> None:
        """
        Applies exponential time decay to unreinforced non-explicit preferences.
        Explicit user preferences do NOT decay.
        """
        if self.provenance == PreferenceProvenance.USER_EXPLICIT:
            return

        now = current_time or time.time()
        elapsed_days = (now - self.updated_at) / 86400.0
        if elapsed_days > 0:
            decay_factor = math.exp(-math.log(2) * (elapsed_days / half_life_days))
            self.confidence = max(0.1, self.confidence * decay_factor)

    def update_explicit(self, new_value: Any) -> None:
        """
        Direct explicit user correction or setting.
        Immediately elevates confidence to 1.0 and sets provenance to USER_EXPLICIT.
        """
        now = time.time()
        self.value = new_value
        self.provenance = PreferenceProvenance.USER_EXPLICIT
        self.confidence = 1.0
        self.observation_count += 1
        self.updated_at = now
        self.last_confirmed_at = now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "provenance": self.provenance.value,
            "confidence": float(self.confidence),
            "observation_count": self.observation_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_confirmed_at": self.last_confirmed_at,
            "metadata": self.metadata
        }


    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> LearnedPreference:
        return cls(
            key=d["key"],
            value=d["value"],
            provenance=PreferenceProvenance(d.get("provenance", PreferenceProvenance.SYSTEM_DEFAULT)),
            confidence=float(d.get("confidence", 0.5)),
            observation_count=int(d.get("observation_count", 1)),
            created_at=float(d.get("created_at", time.time())),
            updated_at=float(d.get("updated_at", time.time())),
            last_confirmed_at=d.get("last_confirmed_at"),
            metadata=d.get("metadata", {})
        )
