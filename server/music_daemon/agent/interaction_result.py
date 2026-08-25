"""
Authoritative AgentInteractionResult Data Contract for Animus Smart Room.
Captures the complete closed-loop lifecycle of an interaction:
Meaning -> Decision -> Action -> Observation -> Interpretation -> Human Feedback.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from agent.models import IntentCategory, PhysicalActionAuditRecord


class DecisionType(str, Enum):
    """Authoritative decision classification for agent actions."""
    EXECUTE_PLAN = "EXECUTE_PLAN"
    NO_OP_ALREADY_SATISFIED = "NO_OP_ALREADY_SATISFIED"
    INFORMATIONAL_RESPONSE = "INFORMATIONAL_RESPONSE"
    CLARIFY_FOLLOWUP = "CLARIFY_FOLLOWUP"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    REJECT_UNSAFE = "REJECT_UNSAFE"
    REJECT_UNSUPPORTED = "REJECT_UNSUPPORTED"
    CANCEL_THREAD = "CANCEL_THREAD"
    CANCEL = "CANCEL"
    INTROSPECTION = "INTROSPECTION"
    ACTION_REPLAY = "ACTION_REPLAY"
    REPLAY = "REPLAY"
    ACTION_UNDO = "ACTION_UNDO"
    UNDO = "UNDO"
    EXTERNAL_DIFF = "EXTERNAL_DIFF"
    GOAL_EXECUTION = "GOAL_EXECUTION"
    GOAL_STATUS = "GOAL_STATUS"
    GOAL_CANCEL = "GOAL_CANCEL"
    GOAL_PARTIAL = "GOAL_PARTIAL"
    GOAL_BLOCKED = "GOAL_BLOCKED"
    GOAL_FAILED = "GOAL_FAILED"
    GOAL_COMPLETED = "GOAL_COMPLETED"
    GOAL_SUPERSEDED = "GOAL_SUPERSEDED"
    GOAL_PAUSED = "GOAL_PAUSED"
    GOAL_RESUMED = "GOAL_RESUMED"
    MODE_ENTERED = "MODE_ENTERED"
    MODE_EXITED = "MODE_EXITED"
    MODE_TRANSITIONED = "MODE_TRANSITIONED"
    MEDIA_ACTION = "MEDIA_ACTION"
    MEDIA_STATUS = "MEDIA_STATUS"
    COMFORT_ADJUSTMENT = "COMFORT_ADJUSTMENT"
    COMFORT_SUGGESTION = "COMFORT_SUGGESTION"
    PROACTIVE_SUGGESTION = "PROACTIVE_SUGGESTION"
    SUGGESTION_ACCEPTED = "SUGGESTION_ACCEPTED"
    SUGGESTION_REJECTED = "SUGGESTION_REJECTED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    EVENT_DETECTED = "EVENT_DETECTED"
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_CANCELLED = "SCHEDULE_CANCELLED"
    SCHEDULE_EXPIRED = "SCHEDULE_EXPIRED"
    GOAL_DEFERRED = "GOAL_DEFERRED"
    SITUATION_CHANGED = "SITUATION_CHANGED"
    EXTERNAL_CHANGE_DETECTED = "EXTERNAL_CHANGE_DETECTED"
    MODE_DIVERGENCE = "MODE_DIVERGENCE"
    PROACTIVE_INVALIDATED = "PROACTIVE_INVALIDATED"
    PREFERENCE_UPDATED = "PREFERENCE_UPDATED"
    PREFERENCE_FORGOTTEN = "PREFERENCE_FORGOTTEN"
    ROOM_STATUS = "ROOM_STATUS"






class PhysicalVerificationStatus(str, Enum):
    """Authoritative verification status of hardware execution."""
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class StateDelta(BaseModel):
    """Explicit before/after hardware state transition."""
    subsystem: str
    attribute: str
    previous_value: Any = None
    new_value: Any = None
    verified_value: Any = None
    delta: Optional[Any] = None


class AgentInteractionResult(BaseModel):
    """
    Epistemologically grounded structured interaction record.
    Provides the response layer with complete facts to distinguish:
    - 'I tried to do X'
    - 'I successfully did X and observed state Y'
    - 'X was already satisfied, so no action was needed'
    - 'I couldn't do X because of Z'
    """
    interaction_id: str = Field(default_factory=lambda: f"act_{int(time.time()*1000)}")
    timestamp: float = Field(default_factory=time.time)
    user_utterance: str
    understood_intent: str
    intent_category: IntentCategory = IntentCategory.CLEAR_EXECUTABLE
    decision_type: DecisionType = DecisionType.EXECUTE_PLAN
    confidence: float = 1.0
    context_used: Dict[str, Any] = Field(default_factory=dict)
    target_device: Optional[str] = None
    target_capability: Optional[str] = None
    proposed_action: Optional[str] = None
    validated_plan: Optional[Dict[str, Any]] = None
    execution_attempted: bool = False
    execution_success: bool = False
    execution_summary: Optional[Dict[str, Any]] = None
    physical_verification: PhysicalVerificationStatus = PhysicalVerificationStatus.NOT_APPLICABLE
    state_delta: Optional[StateDelta] = None
    physical_audits: List[PhysicalActionAuditRecord] = Field(default_factory=list)
    memory_updates: List[Dict[str, Any]] = Field(default_factory=list)
    task_updates: List[Dict[str, Any]] = Field(default_factory=list)
    followup_required: bool = False
    followup_question: Optional[str] = None
    response_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    human_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
