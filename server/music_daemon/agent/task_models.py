"""
Strongly typed models for Deliberative Task Planning, Multi-Step Goals, and Step-level Orchestration.
Follows strict non-negotiable physical-truth invariant:
Planned state != physical state. Only fresh physical telemetry establishes verified completion.
"""

from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GoalStatus(str, Enum):
    """Lifecycle status of a multi-step AgentGoal."""
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    PAUSED = "PAUSED"
    RESUMABLE = "RESUMABLE"
    RECOVERING = "RECOVERING"
    EXPIRED = "EXPIRED"



class StepStatus(str, Enum):
    """Physical execution and verification status of an individual TaskStep."""
    PENDING = "PENDING"
    SKIPPED_ALREADY_SATISFIED = "SKIPPED_ALREADY_SATISFIED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class GoalType(str, Enum):
    """Categorization of deliberative goals."""
    PREPARE_MOVIE = "PREPARE_MOVIE"
    PREPARE_SLEEP = "PREPARE_SLEEP"
    COOL_AND_PROJECTOR = "COOL_AND_PROJECTOR"
    COMFORT_SETPOINT = "COMFORT_SETPOINT"
    MULTI_DEVICE_CONTROL = "MULTI_DEVICE_CONTROL"
    CONDITIONAL_CONTROL = "CONDITIONAL_CONTROL"
    CUSTOM_GOAL = "CUSTOM_GOAL"


class TaskStep(BaseModel):
    """
    Individual atomic step within a deliberative AgentGoal.
    Defaults are conservative to prevent unsafe execution:
    - retry_safe = False
    - max_retries = 0
    - is_required = True
    """
    step_id: int
    target_subsystem: str
    capability: str
    requested_parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[int] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    expected_postcondition: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    execution_result: Optional[Dict[str, Any]] = None
    physical_readback: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    is_required: bool = True
    is_reversible: bool = True
    retry_safe: bool = False
    max_retries: int = 0
    retries_attempted: int = 0
    condition_expr: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


    def is_dependency_satisfied(self, step_status_map: Dict[int, StepStatus]) -> bool:
        """
        Returns True if all prerequisite dependencies are in a terminal non-blocking state:
        VERIFIED or SKIPPED_ALREADY_SATISFIED.
        """
        for dep_id in self.dependencies:
            dep_status = step_status_map.get(dep_id, StepStatus.PENDING)
            if dep_status not in (StepStatus.VERIFIED, StepStatus.SKIPPED_ALREADY_SATISFIED):
                return False
        return True


class AgentGoal(BaseModel):
    """
    High-level deliberative goal composed of structured, dependency-linked TaskSteps.
    Preserves full step-level execution and readback provenance for truthful reporting.
    """
    goal_id: str = Field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    user_utterance: str
    normalized_goal: str
    goal_type: GoalType
    steps: List[TaskStep] = Field(default_factory=list)
    current_step_index: int = 0
    status: GoalStatus = GoalStatus.PENDING
    completion_summary: Optional[str] = None
    failure_summary: Optional[str] = None
    superseded_by: Optional[str] = None
    paused_at: Optional[float] = None
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    last_verified_at: Optional[float] = None
    lease_seconds: Optional[float] = 300.0
    originating_command: Optional[str] = None
    authorization_context: Dict[str, Any] = Field(default_factory=dict)
    conversation_turn: int = 0



    def get_step(self, step_id: int) -> Optional[TaskStep]:
        """Retrieves step by step_id."""
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def get_step_status_map(self) -> Dict[int, StepStatus]:
        """Returns map of step_id to StepStatus."""
        return {s.step_id: s.status for s in self.steps}

    def update_overall_status(self) -> GoalStatus:
        """
        Reconciles overall goal status based on individual step outcomes.
        Invariant: Never report COMPLETED if any required step failed or is blocked.
        """
        if self.status == GoalStatus.CANCELLED:
            return GoalStatus.CANCELLED

        statuses = [s.status for s in self.steps]
        if not statuses:
            self.status = GoalStatus.COMPLETED
            return self.status

        has_failed = any(st in (StepStatus.FAILED, StepStatus.BLOCKED) for st in statuses)
        has_verified = any(st == StepStatus.VERIFIED for st in statuses)
        all_resolved = all(st in (StepStatus.VERIFIED, StepStatus.SKIPPED_ALREADY_SATISFIED) for st in statuses)

        if all_resolved:
            self.status = GoalStatus.COMPLETED
            self.completed_at = time.time()
        elif has_failed and has_verified:
            self.status = GoalStatus.PARTIALLY_COMPLETED
            self.completed_at = time.time()
        elif has_failed and not has_verified:
            # Check if all steps were blocked/failed
            self.status = GoalStatus.FAILED
            self.completed_at = time.time()
        elif any(st == StepStatus.EXECUTING for st in statuses):
            self.status = GoalStatus.EXECUTING
        else:
            self.status = GoalStatus.PLANNING

        return self.status
