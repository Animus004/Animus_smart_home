"""
Gemini Structured Planner and Deterministic Plan Validator Module for Animus Smart Room.
Authoritative models, restricted precondition evaluator, deterministic validator,
and structured generation client.
"""

from planner.errors import (
    ErrorCode,
    WarningCode,
    PlanValidationErrorDetail,
    PlanValidationWarningDetail,
    PlannerError,
    GeminiApiUnavailableError,
    GeminiResponseError,
    PlanValidationError
)
from planner.models import (
    ExecutionMode,
    FailurePolicy,
    FallbackStep,
    PlanStep,
    GeminiStructuredPlan,
    ValidatedStep,
    ValidationResult
)
from planner.preconditions import (
    PreconditionStatus,
    PreconditionEvaluationResult,
    RestrictedPreconditionEvaluator
)
from planner.validator import PlanValidator
from planner.gemini_client import (
    GeminiPlannerClient,
    PLANNER_SYSTEM_INSTRUCTION
)

__all__ = [
    "ErrorCode",
    "WarningCode",
    "PlanValidationErrorDetail",
    "PlanValidationWarningDetail",
    "PlannerError",
    "GeminiApiUnavailableError",
    "GeminiResponseError",
    "PlanValidationError",
    "ExecutionMode",
    "FailurePolicy",
    "FallbackStep",
    "PlanStep",
    "GeminiStructuredPlan",
    "ValidatedStep",
    "ValidationResult",
    "PreconditionStatus",
    "PreconditionEvaluationResult",
    "RestrictedPreconditionEvaluator",
    "PlanValidator",
    "GeminiPlannerClient",
    "PLANNER_SYSTEM_INSTRUCTION"
]
