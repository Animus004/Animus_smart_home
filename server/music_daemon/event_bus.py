"""
Authoritative Event Bus and Event Models for Animus Smart Room Proactive Async Messaging.
Provides bounded in-memory event queues, thread-safe publish-subscribe, event acknowledgement,
TTL-based retention, and fault-isolated dispatch to WebSocket clients.
"""

from __future__ import annotations
from enum import Enum
import logging
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.event_bus")


class AgentEventType(str, Enum):
    REMINDER_DUE = "REMINDER_DUE"
    FOLLOWUP_REQUIRED = "FOLLOWUP_REQUIRED"
    TASK_DUE = "TASK_DUE"
    SYSTEM_NOTIFICATION = "SYSTEM_NOTIFICATION"
    AGENT_PROACTIVE_MESSAGE = "AGENT_PROACTIVE_MESSAGE"
    DESK_USER_ARRIVED = "DESK_USER_ARRIVED"
    DESK_USER_DEPARTED = "DESK_USER_DEPARTED"


class AgentEventPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class AgentEvent(BaseModel):
    """Immutable structured Agent Event."""
    event_id: str = Field(default_factory=lambda: f"evt-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}")
    event_type: AgentEventType
    timestamp: float = Field(default_factory=time.time)
    priority: AgentEventPriority = AgentEventPriority.NORMAL
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class AgentEventBus:
    """
    In-process Thread-Safe & Asyncio-Safe Event Broker.
    Manages active subscriber queues, event acknowledgement, and bounded history buffer.
    """
    def __init__(self, max_history: int = 100, default_ttl_seconds: float = 3600.0):
        self.max_history = max_history
        self.default_ttl_seconds = default_ttl_seconds
        self._subscribers: Set[Any] = set()
        self._history: List[AgentEvent] = []
        self._acknowledged_event_ids: Set[str] = set()
        self._lock = threading.RLock()
        logger.info(f"[EVENT_BUS] Initialized with max_history={max_history}, ttl={default_ttl_seconds}s")

    def publish(self, event: AgentEvent) -> AgentEvent:
        """
        Publishes an event to all active subscriber queues and records to history.
        Sanitizes sensitive data before dispatch.
        """
        sanitized_event = self._sanitize_event(event)
        with self._lock:
            # 1. Append to bounded history
            self._history.append(sanitized_event)
            self._purge_stale_history()

            # 2. Dispatch to subscribers
            dead_subs = []
            for sub_queue in list(self._subscribers):
                try:
                    if hasattr(sub_queue, "put_nowait"):
                        sub_queue.put_nowait(sanitized_event)
                    elif hasattr(sub_queue, "put"):
                        sub_queue.put(sanitized_event)
                except Exception as e:
                    logger.debug(f"[EVENT_BUS] Subscriber queue full/error: {e}")
                    dead_subs.append(sub_queue)

            for dead in dead_subs:
                self._subscribers.discard(dead)

        logger.info(f"[EVENT_BUS_PUBLISH] Published [{sanitized_event.event_type.value}] id={sanitized_event.event_id}: '{sanitized_event.message[:50]}...'")
        return sanitized_event

    def subscribe(self, subscriber_queue: Any):
        """Registers a queue (asyncio.Queue or queue.Queue) as an active event subscriber."""
        with self._lock:
            self._subscribers.add(subscriber_queue)
            logger.info(f"[EVENT_BUS_SUB] Subscriber added. Total active: {len(self._subscribers)}")

    def unsubscribe(self, subscriber_queue: Any):
        """Unregisters an event subscriber queue."""
        with self._lock:
            self._subscribers.discard(subscriber_queue)
            logger.info(f"[EVENT_BUS_UNSUB] Subscriber removed. Remaining: {len(self._subscribers)}")

    def acknowledge(self, event_id: str) -> bool:
        """Records client acknowledgement for a delivered event."""
        with self._lock:
            self._acknowledged_event_ids.add(event_id)
            logger.info(f"[EVENT_BUS_ACK] Event acknowledged: {event_id}")
            return True

    def is_acknowledged(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._acknowledged_event_ids

    def get_unacknowledged_events(self, max_count: int = 20) -> List[AgentEvent]:
        """Returns unacknowledged events that are still within their TTL window."""
        now = time.time()
        with self._lock:
            unacked = [
                evt for evt in self._history
                if evt.event_id not in self._acknowledged_event_ids
                and (now - evt.timestamp) <= self.default_ttl_seconds
            ]
            return unacked[:max_count]

    def _purge_stale_history(self):
        """Enforces max_history buffer limit and purges events older than TTL."""
        now = time.time()
        # Keep within max_history
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
        # Remove expired
        self._history = [
            evt for evt in self._history
            if (now - evt.timestamp) <= self.default_ttl_seconds
        ]

    def _sanitize_event(self, event: AgentEvent) -> AgentEvent:
        """Ensures secrets, access tokens, and stack traces never leak in event payloads."""
        sensitive_patterns = [
            r"local_key",
            r"access_id",
            r"access_secret",
            r"Traceback \(most recent call last\)",
            r'File "[^"]+", line \d+',
            r"Exception:"
        ]
        sanitized_msg = event.message
        for pat in sensitive_patterns:
            if re.search(pat, sanitized_msg, re.IGNORECASE):
                logger.warning(f"[EVENT_BUS_SECURITY] Sanitized sensitive token from event message: '{pat}'")
                sanitized_msg = "An internal smart room event occurred."
                break

        # Sanitize payload dictionary
        sanitized_payload = {}
        for k, v in event.payload.items():
            if any(re.search(pat, str(k), re.IGNORECASE) for pat in ["key", "secret", "token", "password"]):
                continue
            if any(re.search(pat, str(v), re.IGNORECASE) for pat in ["Traceback", "Exception:"]):
                continue
            sanitized_payload[k] = v

        return AgentEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            priority=event.priority,
            message=sanitized_msg,
            payload=sanitized_payload
        )

    def clear(self):
        with self._lock:
            self._history.clear()
            self._acknowledged_event_ids.clear()
            self._subscribers.clear()
