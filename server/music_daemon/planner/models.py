"""
Strongly typed Pydantic models for Gemini Structured Plans, Plan Steps,
and Validation Results in Animus Smart Room.
Contains data definitions ONLY — zero executable hardware functions.
"""

from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from capability_registry.models import SafetyLevel, OperationType
from planner.errors import (
    PlanValidationErrorDetail,
    PlanValidationWarningDetail,
    ErrorCode
)


class ExecutionMode(str, Enum):
    """Step execution coordination mode."""
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"


class FailurePolicy(str, Enum):
    """Step failure recovery behavior."""
    ABORT_PLAN = "ABORT_PLAN"
    CONTINUE_BEST_EFFORT = "CONTINUE_BEST_EFFORT"
    EXECUTE_FALLBACK = "EXECUTE_FALLBACK"


class FallbackStep(BaseModel):
    """Fallback step definition invoked when a primary step fails."""
    device: Optional[str] = None
    capability: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """
    Individual step in a Gemini Structured Plan.
    Represents an atomic declarative intent step before validation and routing.
    """
    step_id: int
    device: str
    capability: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 1
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    preconditions: List[str] = Field(default_factory=list)
    expected_state_transition: Optional[str] = None
    on_failure: FailurePolicy = FailurePolicy.CONTINUE_BEST_EFFORT
    fallback_step: Optional[FallbackStep] = None


class GeminiStructuredPlan(BaseModel):
    """
    Canonical Structured Plan produced by Gemini Structured Planner.
    Strict JSON data contract conforming to E.6 architecture specifications.
    """
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "1.0.0"
    generated_at: float = Field(default_factory=time.time)
    user_request: Optional[str] = None
    intent: str
    objective_summary: str
    rationale: str = ""
    requires_user_confirmation: bool = False
    steps: List[PlanStep] = Field(default_factory=list)


class ValidatedStep(BaseModel):
    """Enriched, validated plan step metadata ready for downstream routing."""
    step_id: int
    device: str
    canonical_capability_id: str
    underlying_capability_name: str
    underlying_controller: str
    operation_type: OperationType
    safety_level: SafetyLevel
    parameters: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 1
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    preconditions: List[str] = Field(default_factory=list)
    expected_state_transition: Optional[str] = None
    on_failure: FailurePolicy = FailurePolicy.CONTINUE_BEST_EFFORT
    fallback_step: Optional[FallbackStep] = None
    is_idempotent_no_op: bool = False


class ValidationResult(BaseModel):
    """
    Authoritative result of the Deterministic Plan Validator.
    Conveys whether a plan is safe and valid without executing any commands.
    """
    valid: bool
    plan_id: Optional[str] = None
    schema_version: str = "1.0.0"
    user_request: Optional[str] = None
    intent: Optional[str] = None
    objective_summary: Optional[str] = None
    requires_user_confirmation: bool = False
    validated_steps: List[ValidatedStep] = Field(default_factory=list)
    rejected_steps: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[PlanValidationErrorDetail] = Field(default_factory=list)
    warnings: List[PlanValidationWarningDetail] = Field(default_factory=list)
    idempotent_step_ids: List[int] = Field(default_factory=list)
    validated_at: float = Field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dictionary representation."""
        return {
            "valid": self.valid,
            "plan_id": self.plan_id,
            "schema_version": self.schema_version,
            "user_request": self.user_request,
            "intent": self.intent,
            "objective_summary": self.objective_summary,
            "requires_user_confirmation": self.requires_user_confirmation,
            "total_steps": len(self.validated_steps) + len(self.rejected_steps),
            "validated_steps_count": len(self.validated_steps),
            "rejected_steps_count": len(self.rejected_steps),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "validated_steps": [s.model_dump() for s in self.validated_steps],
            "rejected_steps": self.rejected_steps,
            "errors": [e.model_dump() for e in self.errors],
            "warnings": [w.model_dump() for w in self.warnings],
            "idempotent_step_ids": self.idempotent_step_ids,
            "validated_at": self.validated_at
        }


class ExecutionStatus(str, Enum):
    """Execution status for an individual step."""
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    UNKNOWN_STATE = "UNKNOWN_STATE"
    STALE_STATE = "STALE_STATE"
    DISPATCHED = "DISPATCHED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class OverallExecutionStatus(str, Enum):
    """Overall plan execution status."""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    SKIPPED = "SKIPPED"


class StepExecutionResult(BaseModel):
    """Detailed execution result for an individual plan step."""
    step_id: int
    device: str
    capability_id: str
    requested_parameters: Dict[str, Any] = Field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: float = Field(default_factory=time.time)
    completed_at: float = Field(default_factory=time.time)
    precondition_result: Optional[Dict[str, Any]] = None
    dispatch_result: Optional[Dict[str, Any]] = None
    readback_result: Optional[Dict[str, Any]] = None
    verified: bool = False
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None


class ExecutionResult(BaseModel):
    """
    Authoritative, deterministic result of physical plan execution.
    Contains complete step-level audit trail, physical read-back evidence, and timing.
    """
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: Optional[str] = None
    user_request: Optional[str] = None
    intent: Optional[str] = None
    started_at: float = Field(default_factory=time.time)
    completed_at: float = Field(default_factory=time.time)
    success: bool = False
    overall_status: OverallExecutionStatus = OverallExecutionStatus.PENDING
    steps: List[StepExecutionResult] = Field(default_factory=list)
    total_steps: int = 0
    verified_steps_count: int = 0
    skipped_steps_count: int = 0
    failed_steps_count: int = 0
    failure_code: Optional[ErrorCode] = None
    warnings: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic JSON dictionary representation."""
        return {
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "user_request": self.user_request,
            "intent": self.intent,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": round((self.completed_at - self.started_at) * 1000, 2),
            "success": self.success,
            "overall_status": self.overall_status.value,
            "total_steps": self.total_steps,
            "verified_steps_count": self.verified_steps_count,
            "skipped_steps_count": self.skipped_steps_count,
            "failed_steps_count": self.failed_steps_count,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "warnings": self.warnings,
            "steps": [s.model_dump() for s in self.steps]
        }


# Rebuild models to resolve forward annotations
StepExecutionResult.model_rebuild()
ExecutionResult.model_rebuild()
ValidationResult.model_rebuild()
GeminiStructuredPlan.model_rebuild()
