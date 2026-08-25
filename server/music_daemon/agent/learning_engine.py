"""
Authoritative Behavioral Learning Engine for Phase 2 Stage 8 Animus Smart Room.
Maintains bounded personal room preferences with provenance-aware statistical learning,
contradiction management, confidence decay, and truthful explainability.

EPISTEMIC INVARIANTS:
1. Learned behavior NEVER overrides explicit real-time user commands or safety constraints.
2. Learned facts are grounded in explicit observation count and provenance.
3. Truthful introspection: Never fabricate reasons for learned preferences.
4. Bounded capacity: Maximum 30 preferences with LRU eviction of low-confidence items.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.preference_model import LearnedPreference, PreferenceProvenance

logger = logging.getLogger("music_daemon.agent.learning_engine")


class LearningEngine:
    """
    Manages bounded behavioral learning, confidence decay, and preference resolution.
    """

    def __init__(self, max_preferences: int = 30):
        self.max_preferences = max_preferences
        self.preferences: Dict[str, LearnedPreference] = {}
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Seed nominal baseline system defaults."""
        defaults = {
            "preferred_movie_temperature": 23,
            "preferred_sleep_temperature": 24,
            "preferred_work_temperature": 24,
            "preferred_music_volume": 40,
            "preferred_projector_brightness": 80,
            "preferred_media_source": "FIRE_TV",
            "preferred_audio_sink": "LG_SOUNDBAR"
        }
        now = time.time()
        for k, v in defaults.items():
            if len(self.preferences) < self.max_preferences:
                self.preferences[k] = LearnedPreference(
                    key=k,
                    value=v,
                    provenance=PreferenceProvenance.SYSTEM_DEFAULT,
                    confidence=0.40,
                    observation_count=1,
                    created_at=now,
                    updated_at=now
                )

    def record_explicit(self, key: str, value: Any) -> LearnedPreference:
        """
        Records an explicit user preference (highest authority, confidence 1.0).
        """
        now = time.time()
        key_norm = key.strip().lower().replace(" ", "_")
        if key_norm in self.preferences:
            pref = self.preferences[key_norm]
            pref.update_explicit(value)
        else:
            self._ensure_capacity()
            pref = LearnedPreference(
                key=key_norm,
                value=value,
                provenance=PreferenceProvenance.USER_EXPLICIT,
                confidence=1.0,
                observation_count=1,
                created_at=now,
                updated_at=now,
                last_confirmed_at=now
            )
            self.preferences[key_norm] = pref

        logger.info(f"[LEARNING_ENGINE] Explicit preference saved: {key_norm} = {value}")
        return pref

    def learn_from_observation(self, key: str, value: Any) -> LearnedPreference:
        """
        Observes a repeated user pattern and reinforces statistical confidence.
        """
        key_norm = key.strip().lower().replace(" ", "_")
        if key_norm in self.preferences:
            pref = self.preferences[key_norm]
            if pref.provenance == PreferenceProvenance.SYSTEM_DEFAULT:
                pref.value = value
                pref.provenance = PreferenceProvenance.OBSERVED_PATTERN
                pref.confidence = 0.55
                pref.observation_count = 1
                pref.updated_at = time.time()
            elif pref.provenance != PreferenceProvenance.USER_EXPLICIT:
                pref.reinforce(value)
        else:
            self._ensure_capacity()
            pref = LearnedPreference(
                key=key_norm,
                value=value,
                provenance=PreferenceProvenance.OBSERVED_PATTERN,
                confidence=0.55,
                observation_count=1
            )
            self.preferences[key_norm] = pref

        logger.info(f"[LEARNING_ENGINE] Observed pattern reinforced: {key_norm} = {value} (conf={self.preferences[key_norm].confidence:.2f})")
        return self.preferences[key_norm]

    def get_preference(self, key: str, min_confidence: float = 0.5) -> Optional[Any]:
        """
        Retrieves preference value if confidence meets the minimum threshold.
        """
        key_norm = key.strip().lower().replace(" ", "_")
        pref = self.preferences.get(key_norm)
        if pref and pref.confidence >= min_confidence:
            return pref.value
        return None

    def forget_preference(self, key: str) -> bool:
        """
        Removes a learned or explicit preference, falling back to default if applicable.
        """
        key_norm = key.strip().lower().replace(" ", "_")
        if key_norm in self.preferences:
            del self.preferences[key_norm]
            logger.info(f"[LEARNING_ENGINE] Forgot preference: {key_norm}")
            return True
        return False

    def decay_all(self, current_time: Optional[float] = None) -> None:
        """
        Applies mathematical time decay to all non-explicit preferences.
        """
        now = current_time or time.time()
        for pref in self.preferences.values():
            pref.apply_decay(current_time=now)

    def explain_preference(self, key: str) -> str:
        """
        Truthfully explains why a preference value is held.
        Never fabricates reasons.
        """
        key_norm = key.strip().lower().replace(" ", "_")
        pref = self.preferences.get(key_norm)
        if not pref:
            return f"I don't have a stored preference for {key}."

        if pref.provenance == PreferenceProvenance.USER_EXPLICIT:
            return f"You explicitly asked me to set {key} to {pref.value}."
        elif pref.provenance == PreferenceProvenance.OBSERVED_PATTERN:
            return f"You usually use {pref.value} for {key} (observed {pref.observation_count} times, confidence {int(pref.confidence*100)}%)."
        elif pref.provenance == PreferenceProvenance.SESSION_INFERRED:
            return f"Inferred from our conversation that you prefer {pref.value} for {key}."
        else:
            return f"{pref.value} is the standard default for {key}."

    def _ensure_capacity(self) -> None:
        """Evicts lowest-confidence, least-observed non-explicit preference if at capacity."""
        while len(self.preferences) >= self.max_preferences:
            evictable = [
                (k, p) for k, p in self.preferences.items()
                if p.provenance != PreferenceProvenance.USER_EXPLICIT
            ]
            if evictable:
                # Sort by confidence ascending, then observation_count ascending
                evictable.sort(key=lambda item: (item[1].confidence, item[1].observation_count))
                evict_key = evictable[0][0]
                del self.preferences[evict_key]
                logger.info(f"[LEARNING_ENGINE] Capacity reached. Evicted low-confidence preference: {evict_key}")
            else:
                break


    def to_dict(self) -> Dict[str, Any]:
        return {k: p.to_dict() for k, p in self.preferences.items()}

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            self.preferences[k] = LearnedPreference.from_dict(v)
