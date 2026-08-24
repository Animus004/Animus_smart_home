"""
Error definitions and exception classes for Preferences & Context Engine.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
from pydantic import BaseModel


class ContextError(Exception):
    """Base exception for Context Engine and Preference errors."""
    pass


class PreferenceValidationError(ContextError):
    """Raised when user or system preferences violate capability constraints."""
    def __init__(self, message: str, field: Optional[str] = None, invalid_value: Any = None):
        super().__init__(message)
        self.field = field
        self.invalid_value = invalid_value


class ContextUnavailableError(ContextError):
    """Raised when a required environmental or hardware context provider is unreachable."""
    pass
