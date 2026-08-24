"""
Error definitions and deterministic error codes for Gemini Structured Planner & Plan Validator.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Authoritative deterministic error codes for plan validation failures."""
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    DEFERRED_CAPABILITY = "DEFERRED_CAPABILITY"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    MISSING_PARAMETER = "MISSING_PARAMETER"
    UNKNOWN_PARAMETER = "UNKNOWN_PARAMETER"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    INVALID_ENUM = "INVALID_ENUM"
    INVALID_PRECONDITION = "INVALID_PRECONDITION"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    UNKNOWN_STATE = "UNKNOWN_STATE"
    STALE_STATE = "STALE_STATE"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    DUPLICATE_STEP = "DUPLICATE_STEP"
    INVALID_PLAN_STRUCTURE = "INVALID_PLAN_STRUCTURE"
    IDEMPOTENT_ACTION = "IDEMPOTENT_ACTION"
    MALFORMED_JSON = "MALFORMED_JSON"
    GENAI_UNAVAILABLE = "GENAI_UNAVAILABLE"


class WarningCode(str, Enum):
    """Authoritative deterministic warning codes for non-fatal plan anomalies."""
    IDEMPOTENT_SKIPPED = "IDEMPOTENT_SKIPPED"
    PRECONDITION_UNCERTAIN_STALE = "PRECONDITION_UNCERTAIN_STALE"
    FALLBACK_CONFIGURED = "FALLBACK_CONFIGURED"


class PlanValidationErrorDetail(BaseModel):
    """Structured detail describing a single validation error in a plan."""
    error_code: ErrorCode
    step_id: Optional[int] = None
    capability: Optional[str] = None
    field: Optional[str] = None
    message: str


class PlanValidationWarningDetail(BaseModel):
    """Structured detail describing a single validation warning in a plan."""
    warning_code: WarningCode
    step_id: Optional[int] = None
    capability: Optional[str] = None
    message: str


class PlannerError(Exception):
    """Base exception for planner operations."""
    pass


class GeminiApiUnavailableError(PlannerError):
    """Raised when Gemini API key or SDK is not available."""
    pass


class GeminiResponseError(PlannerError):
    """Raised when Gemini returns an unparseable or malformed response."""
    pass


class PlanValidationError(PlannerError):
    """Raised when plan validation fails in strict mode."""
    def __init__(self, message: str, errors: list[PlanValidationErrorDetail]):
        super().__init__(message)
        self.errors = errors
