"""
Authoritative 9-Category Agent Memory Store for Animus Smart Room.
Enforces strict taxonomy boundaries: facts, preferences, routines, tasks, reminders,
temporary context, observations, assumptions, and confirmed decisions.
CRITICAL INVARIANT: Zero silent promotion of assumptions into facts.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from agent.models import MemoryCategory, MemoryItem

logger = logging.getLogger("music_daemon.agent.memory")


class AgentMemoryStore:
    """
    In-memory and persistent structured memory store with taxonomy enforcement.
    """

    def __init__(self, initial_items: Optional[List[MemoryItem]] = None):
        self._items: Dict[str, MemoryItem] = {}
        if initial_items:
            for item in initial_items:
                self._items[item.id] = item
        else:
            self._initialize_default_knowledge()

    def _initialize_default_knowledge(self) -> None:
        """Populates baseline authoritative facts and preferences."""
        self.record_fact("preferred_address", "Sir", source="USER_EXPLICIT_SPECIFICATION")
        self.record_fact("user_full_name", "Sayan Halder", source="USER_EXPLICIT_SPECIFICATION")
        self.record_fact("location_pin", "741235", source="USER_EXPLICIT_SPECIFICATION")

        self.record_preference(
            "preferred_movie_devices",
            ["PROJECTOR", "FIRE_TV", "LG_SOUNDBAR"],
            source="USER_EXPLICIT_SPECIFICATION"
        )
        self.record_preference(
            "preferred_streaming_services",
            ["netflix", "apple_tv", "prime_video", "youtube"],
            source="USER_EXPLICIT_SPECIFICATION"
        )
        self.record_preference("preferred_volume", 30, source="USER_EXPLICIT_SPECIFICATION")

        self.record_routine("morning_wake_routine", "Wake up -> Morning summary -> Motivation tune -> Start day")
        self.record_routine("work_routine", "Work & Learn SQL starts generally after 11:00 AM")
        self.record_routine("guitar_routine", "Guitar practice preferred around 17:00 or after lunch")

    # =========================================================================
    # Explicit Taxonomy Adders
    # =========================================================================

    def record_fact(self, key: str, content: Any, source: str = "USER_CONFIRMED") -> MemoryItem:
        """Records a permanent stable fact about the user."""
        item = MemoryItem(
            category=MemoryCategory.STABLE_USER_FACT,
            key=key,
            content=content,
            confidence=1.0,
            source=source,
            user_confirmed=True
        )
        self._items[item.id] = item
        logger.debug(f"[MEMORY] Recorded stable fact: {key} = {content}")
        return item

    def record_preference(self, key: str, content: Any, source: str = "USER_PREFERENCES") -> MemoryItem:
        """Records a user preference."""
        item = MemoryItem(
            category=MemoryCategory.USER_PREFERENCE,
            key=key,
            content=content,
            confidence=1.0,
            source=source,
            user_confirmed=True
        )
        self._items[item.id] = item
        logger.debug(f"[MEMORY] Recorded preference: {key} = {content}")
        return item

    def record_routine(self, key: str, content: Any) -> MemoryItem:
        """Records a behavioral routine hint."""
        item = MemoryItem(
            category=MemoryCategory.ROUTINE,
            key=key,
            content=content,
            confidence=0.9,
            source="USER_ROUTINE_PROFILE",
            user_confirmed=True
        )
        self._items[item.id] = item
        return item

    def record_observation(self, key: str, content: Any, source: str = "USER_STATEMENT") -> MemoryItem:
        """Records an empirical observation (e.g. user said 'I had lunch')."""
        item = MemoryItem(
            category=MemoryCategory.OBSERVATION,
            key=key,
            content=content,
            confidence=1.0,
            source=source,
            user_confirmed=True
        )
        self._items[item.id] = item
        logger.info(f"[MEMORY] Observation recorded: {key} = {content}")
        return item

    def record_temporary_context(self, key: str, content: Any, ttl_seconds: float = 3600.0) -> MemoryItem:
        """Records a temporary context with explicit expiration TTL."""
        item = MemoryItem(
            category=MemoryCategory.TEMPORARY_CONTEXT,
            key=key,
            content=content,
            confidence=1.0,
            source="AGENT_INFERENCE",
            expires_at=time.time() + ttl_seconds
        )
        self._items[item.id] = item
        return item

    def record_assumption(self, key: str, content: Any, confidence: float = 0.6) -> MemoryItem:
        """
        Records an AGENT_ASSUMPTION.
        CRITICAL RULE: Assumptions remain unconfirmed until explicitly verified by the user.
        """
        item = MemoryItem(
            category=MemoryCategory.AGENT_ASSUMPTION,
            key=key,
            content=content,
            confidence=confidence,
            source="AGENT_HYPOTHESIS",
            user_confirmed=False
        )
        self._items[item.id] = item
        logger.info(f"[MEMORY_ASSUMPTION] Recorded assumption (unconfirmed): {key} = {content}")
        return item

    def confirm_decision(self, key: str, content: Any, assumption_id: Optional[str] = None) -> MemoryItem:
        """
        Converts an assumption or user response into a USER_CONFIRMED_DECISION.
        """
        if assumption_id and assumption_id in self._items:
            # Delete or supersede the unconfirmed assumption
            del self._items[assumption_id]

        item = MemoryItem(
            category=MemoryCategory.USER_CONFIRMED_DECISION,
            key=key,
            content=content,
            confidence=1.0,
            source="USER_EXPLICIT_CONFIRMATION",
            user_confirmed=True
        )
        self._items[item.id] = item
        logger.info(f"[MEMORY_DECISION] Recorded user-confirmed decision: {key} = {content}")
        return item

    # =========================================================================
    # Retrieval & Inspection
    # =========================================================================

    def get_by_category(self, category: MemoryCategory, include_expired: bool = False) -> List[MemoryItem]:
        """Returns all memory items for a specific taxonomy category."""
        res: List[MemoryItem] = []
        for item in self._items.values():
            if item.category == category:
                if not include_expired and item.is_expired():
                    continue
                res.append(item)
        return res

    def get_latest_by_key(self, key: str, category: Optional[MemoryCategory] = None) -> Optional[MemoryItem]:
        """Finds the most recent memory item for a key."""
        candidates = [
            item for item in self._items.values()
            if item.key == key and (category is None or item.category == category) and not item.is_expired()
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x.updated_at, reverse=True)
        return candidates[0]

    def get_all_active(self) -> List[MemoryItem]:
        """Returns all non-expired memory items across all categories."""
        return [item for item in self._items.values() if not item.is_expired()]

    def to_dict_summary(self) -> Dict[str, Any]:
        """Exports a clean structured summary grouped by memory taxonomy category."""
        summary: Dict[str, List[Dict[str, Any]]] = {cat.value: [] for cat in MemoryCategory}
        for item in self.get_all_active():
            summary[item.category.value].append({
                "id": item.id,
                "key": item.key,
                "content": item.content,
                "confidence": item.confidence,
                "source": item.source,
                "user_confirmed": item.user_confirmed,
                "created_at": item.created_at
            })
        return summary
