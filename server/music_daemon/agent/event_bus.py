"""
Authoritative In-Process Deterministic Event Bus for Animus Smart Room.
Provides thread-safe publish-subscribe, bounded memory history, duplicate suppression,
correlation tracking, and fault-isolated subscriber execution.

EPISTEMIC & SAFETY INVARIANTS:
1. Event dispatch never creates infinite feedback loops (guarded by correlation ID and depth bounds).
2. Subscriber exceptions are strictly isolated to prevent bus corruption.
3. Event history is strictly bounded (max_history=500) to prevent unbounded memory growth.
"""

from __future__ import annotations
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set
from agent.room_events import RoomEvent, RoomEventType

logger = logging.getLogger("music_daemon.agent.event_bus")


class RoomEventBus:
    """
    Deterministic In-Process Event Bus.
    Delivers strongly typed RoomEvents synchronously and ordered to registered subscribers.
    """

    def __init__(self, max_history: int = 500, deduplication_window_seconds: float = 1.0):
        self.max_history = max_history
        self.deduplication_window_seconds = deduplication_window_seconds
        self._subscribers: List[Dict[str, Any]] = []
        self._history: List[RoomEvent] = []
        self._recent_signatures: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._max_cascade_depth = 4

    def subscribe(
        self,
        callback: Callable[[RoomEvent], Any],
        event_types: Optional[Set[RoomEventType]] = None,
        subscriber_id: Optional[str] = None
    ) -> str:
        """
        Registers a callback handler for events.
        If event_types is provided, filters delivery strictly to matching categories.
        """
        sub_id = subscriber_id or f"sub_{len(self._subscribers) + 1}_{int(time.time()*1000)}"
        with self._lock:
            self._subscribers.append({
                "id": sub_id,
                "callback": callback,
                "event_types": set(event_types) if event_types else None
            })
            logger.info(f"[EVENT_BUS_SUB] Subscribed {sub_id} (filter: {event_types or 'ALL'})")
        return sub_id

    def unsubscribe(self, subscriber_id_or_callback: Any) -> bool:
        """Unregisters an active subscriber by ID or callback reference."""
        with self._lock:
            initial_count = len(self._subscribers)
            self._subscribers = [
                s for s in self._subscribers
                if s["id"] != subscriber_id_or_callback and s["callback"] != subscriber_id_or_callback
            ]
            removed = len(self._subscribers) < initial_count
            if removed:
                logger.info(f"[EVENT_BUS_UNSUB] Removed subscriber {subscriber_id_or_callback}")
            return removed

    def publish(self, event: RoomEvent, cascade_depth: int = 0) -> Optional[RoomEvent]:
        """
        Publishes a RoomEvent to matching subscribers with duplicate suppression
        and cascade loop prevention.
        """
        if cascade_depth > self._max_cascade_depth:
            logger.warning(f"[EVENT_BUS_LOOP_PREVENT] Discarding event {event.event_type.value}: cascade depth {cascade_depth} exceeded max {self._max_cascade_depth}")
            return None

        now = time.time()
        sig = self._compute_signature(event)

        with self._lock:
            # 1. Duplicate event suppression
            last_seen = self._recent_signatures.get(sig, 0.0)
            if (now - last_seen) < self.deduplication_window_seconds:
                logger.debug(f"[EVENT_BUS_DEDUP] Suppressing duplicate event: {sig}")
                return None
            self._recent_signatures[sig] = now
            self._prune_signatures(now)

            # 2. Append to bounded history
            self._history.append(event)
            if len(self._history) > self.max_history:
                self._history.pop(0)

            # 3. Snapshot active subscribers
            current_subscribers = list(self._subscribers)

        # 4. Dispatch to subscribers outside lock for fault isolation
        for sub in current_subscribers:
            filter_types = sub.get("event_types")
            if filter_types is None or event.event_type in filter_types:
                try:
                    cb = sub["callback"]
                    cb(event)
                except Exception as e:
                    logger.error(f"[EVENT_BUS_DISPATCH_ERROR] Subscriber {sub.get('id')} failed handling {event.event_type.value}: {e}", exc_info=True)

        logger.debug(f"[EVENT_BUS_PUBLISHED] {event.summary()}")
        return event

    def get_events(
        self,
        limit: int = 50,
        event_type: Optional[RoomEventType] = None,
        subsystem: Optional[str] = None
    ) -> List[RoomEvent]:
        """Queries recent bounded event history with optional type/subsystem filtering."""
        with self._lock:
            events = list(self._history)

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if subsystem:
            events = [e for e in events if e.affected_subsystem == subsystem]

        return events[-limit:]

    def clear_history(self) -> None:
        """Clears bounded event history buffer (for test isolation)."""
        with self._lock:
            self._history.clear()
            self._recent_signatures.clear()

    def _compute_signature(self, event: RoomEvent) -> str:
        """Computes a lightweight deduplication signature."""
        return f"{event.event_type.value}_{event.affected_subsystem}_{event.observed_state}_{event.correlation_id}"

    def _prune_signatures(self, now: float) -> None:
        """Purges old deduplication signatures."""
        cutoff = now - (self.deduplication_window_seconds * 5)
        stale_keys = [k for k, ts in self._recent_signatures.items() if ts < cutoff]
        for k in stale_keys:
            del self._recent_signatures[k]
