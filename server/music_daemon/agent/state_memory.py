"""
Authoritative Strongly Typed Session & Behavioral Memory Model for Animus Smart Room.
Maintains bounded verified action history, session facts with explicit provenance,
conversational reference tracking, thread states, and external state change reconciliation.

EPISTEMIC INVARIANT:
Memory is NOT a source of physical truth.
Live telemetry is authoritative for current physical reality.
Memory is authoritative for what Animus attempted, executed, and verified historically.
"""

from __future__ import annotations
import time
import uuid
import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.interaction_result import StateDelta

logger = logging.getLogger("music_daemon.agent.state_memory")


class FactProvenance(str, Enum):
    """Authoritative source classification for stored room and session facts."""
    LIVE_TELEMETRY = "LIVE_TELEMETRY"
    VERIFIED_EXECUTION = "VERIFIED_EXECUTION"
    CONVERSATIONAL_ONLY = "CONVERSATIONAL_ONLY"
    CONVERSATIONAL_PREFERENCE = "CONVERSATIONAL_PREFERENCE"
    UNKNOWN = "UNKNOWN"


class ConversationalPreference(BaseModel):
    """
    Bounded session-scoped conversational preference (e.g. 'Keep room around 24').
    EPISTEMIC INVARIANT:
    Preferences never override live physical telemetry, safety rules, or explicit user commands.
    """
    preference_id: str = Field(default_factory=lambda: f"pref_{uuid.uuid4().hex[:8]}")
    key: str
    value: Any
    provenance: FactProvenance = FactProvenance.CONVERSATIONAL_PREFERENCE
    created_at: float = Field(default_factory=time.time)
    confidence: float = 1.0
    user_utterance: Optional[str] = None



class ReferenceType(str, Enum):
    """Categorization for conversational reference targets."""
    DEVICE = "DEVICE"
    ATTRIBUTE = "ATTRIBUTE"
    MEDIA = "MEDIA"
    TOPIC = "TOPIC"


class VerifiedRoomFact(BaseModel):
    """
    Represents a specific known fact about the room or session,
    preserving exact provenance so conversational assumptions are never confused with telemetry.
    """
    subsystem: str
    attribute: str
    value: Any
    provenance: FactProvenance
    timestamp: float = Field(default_factory=time.time)
    source_tag: str = ""


class RecentActionMemory(BaseModel):
    """
    A single bounded verified action entry in the agent's short-term behavioral history.
    """
    action_id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    turn_index: int = 0
    user_utterance: str
    intent: str
    target_subsystem: str
    target_capability: Optional[str] = None
    requested_parameters: Dict[str, Any] = Field(default_factory=dict)
    validated_plan_summary: Optional[Dict[str, Any]] = None
    execution_success: bool = True
    execution_status: str = "VERIFIED"
    readback_status: str = "VERIFIED"
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Dict[str, Any] = Field(default_factory=dict)
    state_delta: Optional[StateDelta] = None
    reason_for_action: Optional[str] = None


class ConversationReference(BaseModel):
    """Tracks the most recently referenced entity in conversation for pronoun/reference resolution."""
    entity_type: ReferenceType
    name: str
    value: Any = None
    last_referenced_timestamp: float = Field(default_factory=time.time)
    turn_index: int = 0


class ConversationThreadState(BaseModel):
    """Tracks multi-turn workflow progression."""
    thread_id: str
    thread_type: str
    target_device: Optional[str] = None
    missing_parameters: List[str] = Field(default_factory=list)
    resolved_parameters: Dict[str, Any] = Field(default_factory=dict)
    negative_constraints: List[str] = Field(default_factory=list)
    completion_status: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ExternalStateDiff(BaseModel):
    """Tracks detected out-of-band physical changes between verified memory and live telemetry."""
    subsystem: str
    attribute: str
    historical_verified_value: Any
    current_telemetry_value: Any
    detected_at: float = Field(default_factory=time.time)
    description: str = ""


class AgentSessionMemory(BaseModel):
    """
    Bounded session-scoped memory store.
    Guarantees:
    - Bounded to 10 verified recent actions (FIFO eviction).
    - Session-scoped: no unbounded personal profiling.
    - Preserves provenance for every fact.
    - Explicitly tracks external changes when telemetry diverges from verified memory.
    """
    session_id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    started_at: float = Field(default_factory=time.time)
    last_active_at: float = Field(default_factory=time.time)
    max_recent_actions: int = 10
    recent_actions: List[RecentActionMemory] = Field(default_factory=list)
    max_recent_goals: int = 5
    recent_goals: List[Any] = Field(default_factory=list)
    max_preferences: int = 5
    preferences: List[ConversationalPreference] = Field(default_factory=list)
    session_facts: Dict[str, VerifiedRoomFact] = Field(default_factory=dict)
    active_references: Dict[str, ConversationReference] = Field(default_factory=dict)
    active_threads: Dict[str, ConversationThreadState] = Field(default_factory=dict)
    external_diffs: Dict[str, ExternalStateDiff] = Field(default_factory=dict)

    def record_preference(self, pref: ConversationalPreference) -> None:
        """Stores a conversational preference in bounded FIFO memory (max 5)."""
        # Remove any existing preference with identical key
        self.preferences = [p for p in self.preferences if p.key.lower() != pref.key.lower()]
        self.preferences.append(pref)
        if len(self.preferences) > self.max_preferences:
            self.preferences.pop(0)
        self.last_active_at = time.time()
        logger.info(f"[SESSION_MEMORY] Recorded preference '{pref.key}' = {pref.value}")

    def get_preference(self, key: str) -> Optional[ConversationalPreference]:
        """Retrieves most recent preference for key, or None."""
        for p in reversed(self.preferences):
            if p.key.lower() == key.lower():
                return p
        return None

    def get_all_preferences(self) -> List[ConversationalPreference]:
        """Returns list of active session preferences."""
        return list(self.preferences)


    def record_action(self, action: RecentActionMemory) -> None:
        """Appends a verified action to rolling bounded history (max 10 entries)."""
        self.recent_actions.append(action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions.pop(0)
        self.last_active_at = time.time()

        # Update active references for the target subsystem and capability
        if action.target_subsystem:
            self.set_reference(
                ReferenceType.DEVICE,
                action.target_subsystem,
                action.target_subsystem,
                action.turn_index
            )
        if action.state_delta and action.state_delta.attribute:
            self.set_reference(
                ReferenceType.ATTRIBUTE,
                action.state_delta.attribute,
                action.state_delta.verified_value or action.state_delta.new_value,
                action.turn_index
            )

    def record_goal(self, goal: Any) -> None:
        """Appends a completed/orchestrated AgentGoal to rolling bounded history (max 5 entries)."""
        self.recent_goals.append(goal)
        if len(self.recent_goals) > self.max_recent_goals:
            self.recent_goals.pop(0)
        self.last_active_at = time.time()

    def get_latest_goal(self) -> Optional[Any]:
        """Retrieves the most recent deliberative AgentGoal."""
        return self.recent_goals[-1] if self.recent_goals else None

    def get_latest_action(self, target_subsystem: Optional[str] = None) -> Optional[RecentActionMemory]:
        """Retrieves the most recent verified action, optionally filtered by subsystem."""
        if not self.recent_actions:
            return None
        if not target_subsystem:
            return self.recent_actions[-1]
        for act in reversed(self.recent_actions):
            if act.target_subsystem.upper() == target_subsystem.upper():
                return act
        return None


    def get_action_history(self, depth: int = 1, target_subsystem: Optional[str] = None) -> Optional[RecentActionMemory]:
        """
        Retrieves historical action at specified depth (1 = most recent, 2 = one before that, etc.).
        """
        actions = self.recent_actions
        if target_subsystem:
            actions = [a for a in actions if a.target_subsystem.upper() == target_subsystem.upper()]
        if not actions or depth < 1 or depth > len(actions):
            return None
        return actions[-depth]

    def set_reference(self, ref_type: ReferenceType, name: str, value: Any = None, turn_index: int = 0) -> None:
        """Updates or registers a conversational reference."""
        key = f"{ref_type.value}:{name.upper()}"
        self.active_references[key] = ConversationReference(
            entity_type=ref_type,
            name=name.upper(),
            value=value,
            last_referenced_timestamp=time.time(),
            turn_index=turn_index
        )
        self.last_active_at = time.time()

    def get_most_recent_reference(self, ref_type: Optional[ReferenceType] = None) -> Optional[ConversationReference]:
        """Retrieves the most recently referenced entity of a given type."""
        candidates = list(self.active_references.values())
        if ref_type:
            candidates = [c for c in candidates if c.entity_type == ref_type]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.last_referenced_timestamp)

    def record_fact(
        self,
        subsystem: str,
        attribute: str,
        value: Any,
        provenance: FactProvenance,
        source_tag: str = ""
    ) -> None:
        """Stores a verified or conversational fact with strict provenance."""
        key = f"{subsystem.upper()}.{attribute.lower()}"
        self.session_facts[key] = VerifiedRoomFact(
            subsystem=subsystem.upper(),
            attribute=attribute.lower(),
            value=value,
            provenance=provenance,
            timestamp=time.time(),
            source_tag=source_tag
        )
        self.last_active_at = time.time()

    def get_fact(self, subsystem: str, attribute: str) -> Optional[VerifiedRoomFact]:
        """Retrieves a known fact by subsystem and attribute."""
        key = f"{subsystem.upper()}.{attribute.lower()}"
        return self.session_facts.get(key)

    def reconcile_external_diff(
        self,
        subsystem: str,
        attribute: str,
        current_telemetry_value: Any
    ) -> Optional[ExternalStateDiff]:
        """
        Checks if current live telemetry contradicts the most recent verified memory.
        If a mismatch is detected, records an ExternalStateDiff.
        """
        latest = self.get_latest_action(target_subsystem=subsystem)
        if not latest or not latest.state_delta or latest.state_delta.attribute != attribute:
            return None

        historical_val = latest.state_delta.verified_value
        if historical_val is None:
            historical_val = latest.state_delta.new_value

        if historical_val is not None and current_telemetry_value is not None:
            if str(historical_val).lower() != str(current_telemetry_value).lower():
                diff = ExternalStateDiff(
                    subsystem=subsystem.upper(),
                    attribute=attribute,
                    historical_verified_value=historical_val,
                    current_telemetry_value=current_telemetry_value,
                    description=f"{subsystem} {attribute} was verified at {historical_val}, but live telemetry reports {current_telemetry_value}."
                )
                key = f"{subsystem.upper()}.{attribute}"
                self.external_diffs[key] = diff
                return diff
        return None
