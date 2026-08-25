"""
Authoritative Persistent Behavioral Profile for Animus Smart Room Stage 6.
Maintains bounded, user-relevant behavioral preferences with explicit provenance and confidence scores.

EPISTEMIC & SAFETY INVARIANTS:
1. Behavioral preferences NEVER override explicit user commands.
2. Behavioral preferences NEVER override live physical telemetry.
3. Preferences provide defaults for canonical routines only when unconstrained by the user.
4. Preference storage is strictly bounded (max_preferences=20).
"""

from __future__ import annotations
import logging
import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.agent.behavioral_profile")


class PreferenceProvenance(str, Enum):
    USER_EXPLICIT = "USER_EXPLICIT"
    SESSION_INFERRED = "SESSION_INFERRED"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"


class BehavioralPreference(BaseModel):
    """A single bounded behavioral preference entry."""
    key: str
    value: Any
    provenance: PreferenceProvenance = PreferenceProvenance.USER_EXPLICIT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    observation_count: int = 1


class BehavioralProfileManager:
    """
    Manages bounded personal room preferences with conservative learning.
    """

    def __init__(self, max_preferences: int = 20):
        self.max_preferences = max_preferences
        self.preferences: Dict[str, BehavioralPreference] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Seeds default canonical preferences."""
        defaults = {
            "preferred_movie_temperature": 23,
            "preferred_sleep_temperature": 24,
            "preferred_work_temperature": 24,
            "preferred_music_volume": 40,
            "preferred_movie_volume": 40,
        }
        for k, v in defaults.items():
            self.preferences[k] = BehavioralPreference(
                key=k,
                value=v,
                provenance=PreferenceProvenance.SYSTEM_DEFAULT,
                confidence=0.5
            )

    def set_preference(
        self,
        key: str,
        value: Any,
        provenance: PreferenceProvenance = PreferenceProvenance.USER_EXPLICIT,
        confidence: float = 1.0
    ) -> BehavioralPreference:
        """Sets or updates an explicit user preference."""
        now = time.time()
        pref = BehavioralPreference(
            key=key,
            value=value,
            provenance=provenance,
            confidence=confidence,
            created_at=self.preferences[key].created_at if key in self.preferences else now,
            updated_at=now,
            observation_count=self.preferences[key].observation_count + 1 if key in self.preferences else 1
        )

        if len(self.preferences) >= self.max_preferences and key not in self.preferences:
            # Purge oldest system default or lowest confidence preference
            candidates = sorted(self.preferences.values(), key=lambda p: (p.provenance == PreferenceProvenance.USER_EXPLICIT, p.confidence, -p.updated_at))
            if candidates:
                del self.preferences[candidates[0].key]

        self.preferences[key] = pref
        logger.info(f"[BEHAVIORAL_PROFILE] Set {key} = {value} ({provenance.value}, conf={confidence:.2f})")
        return pref

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieves preference value if available."""
        pref = self.preferences.get(key)
        return pref.value if pref else default

    def forget_preference(self, key: str) -> bool:
        """Removes a preference from storage."""
        if key in self.preferences:
            del self.preferences[key]
            logger.info(f"[BEHAVIORAL_PROFILE] Forgot preference {key}")
            return True
        return False

    def learn_from_observation(self, key: str, value: Any) -> None:
        """
        Conservative preference learning from repeated explicit actions.
        Increments confidence without overriding explicit preferences arbitrarily.
        """
        existing = self.preferences.get(key)
        if existing:
            if existing.value == value:
                existing.observation_count += 1
                existing.confidence = min(1.0, existing.confidence + 0.1)
                existing.updated_at = time.time()
            elif existing.provenance != PreferenceProvenance.USER_EXPLICIT:
                # If non-explicit, allow update with moderate confidence
                self.set_preference(key, value, provenance=PreferenceProvenance.SESSION_INFERRED, confidence=0.7)
        else:
            self.set_preference(key, value, provenance=PreferenceProvenance.SESSION_INFERRED, confidence=0.6)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes preferences for bounded persistence."""
        return {k: p.model_dump() for k, p in self.preferences.items()}

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Loads preferences from saved dictionary."""
        for k, v in data.items():
            try:
                self.preferences[k] = BehavioralPreference(**v)
            except Exception as e:
                logger.warning(f"[BEHAVIORAL_PROFILE_LOAD] Error loading preference {k}: {e}")
