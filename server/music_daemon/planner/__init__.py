"""
Gemini Structured Planner, Deterministic Plan Validator & Plan Executor Module for Animus Smart Room.
Authoritative models, restricted precondition evaluator, deterministic validator,
structured generation client, and verified physical execution engine.
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
    ValidationResult,
    ExecutionStatus,
    OverallExecutionStatus,
    StepExecutionResult,
    ExecutionResult
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
from planner.executor import PlanExecutor

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
    "ExecutionStatus",
    "OverallExecutionStatus",
    "StepExecutionResult",
    "ExecutionResult",
    "PreconditionStatus",
    "PreconditionEvaluationResult",
    "RestrictedPreconditionEvaluator",
    "PlanValidator",
    "GeminiPlannerClient",
    "PLANNER_SYSTEM_INSTRUCTION",
    "PlanExecutor"
]
