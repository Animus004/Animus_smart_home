"""
Strongly-Typed Capability Registry Models for Animus Smart Room.
Defines machine-readable capability contracts, safety levels, and parameter schemas
for authoritative capability translation without hardware execution.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field


class Subsystem(str, Enum):
    """Subsystem device classification."""
    PROJECTOR = "PROJECTOR"
    AC = "AC"
    FIRE_TV = "FIRE_TV"
    PC = "PC"
    SOUNDBAR = "SOUNDBAR"
    ENVIRONMENT = "ENVIRONMENT"


class SafetyLevel(str, Enum):
    """Safety classification for capability execution."""
    SAFE = "SAFE"                 # Read-only or cosmetic
    LOW_RISK = "LOW_RISK"         # Standard reversible action (e.g. volume change, pause)
    MEDIUM_RISK = "MEDIUM_RISK"   # Mode changes, power standby toggles
    HIGH_RISK = "HIGH_RISK"       # System shutdown, hardware reset
    RESTRICTED = "RESTRICTED"     # Must not be executed autonomously without human consent


class CapabilityStatus(str, Enum):
    """Lifecycle and support status of a capability."""
    VERIFIED_EXECUTABLE = "VERIFIED_EXECUTABLE"
    DEFERRED_PENDING_HARDWARE = "DEFERRED_PENDING_HARDWARE"
    UNSUPPORTED_HARDWARE = "UNSUPPORTED_HARDWARE"


class ParameterType(str, Enum):
    """Supported parameter data types."""
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"


class ParameterConstraint(BaseModel):
    """Specification and safety bounds for a capability parameter."""
    name: str
    param_type: ParameterType
    required: bool = True
    default: Optional[Any] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    description: str = ""

    def validate_value(self, val: Any) -> bool:
        """Validates a candidate value against parameter constraints."""
        if val is None:
            return not self.required

        if self.param_type == ParameterType.INTEGER:
            if not isinstance(val, int) or isinstance(val, bool):
                return False
            if self.min_value is not None and val < self.min_value:
                return False
            if self.max_value is not None and val > self.max_value:
                return False

        elif self.param_type == ParameterType.FLOAT:
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                return False
            if self.min_value is not None and val < self.min_value:
                return False
            if self.max_value is not None and val > self.max_value:
                return False

        elif self.param_type == ParameterType.STRING:
            if not isinstance(val, str):
                return False
            if self.allowed_values and val not in self.allowed_values:
                return False

        elif self.param_type == ParameterType.BOOLEAN:
            if not isinstance(val, bool):
                return False

        elif self.param_type == ParameterType.ENUM:
            if self.allowed_values and val not in self.allowed_values:
                return False

        return True


class CapabilityDefinition(BaseModel):
    """
    Authoritative, machine-readable declaration of an individual physical capability.
    Contains complete metadata needed for deterministic validation and translation.
    """
    canonical_id: str
    subsystem: Subsystem
    description: str
    underlying_controller: str
    underlying_capability_name: str
    parameters: Dict[str, ParameterConstraint] = Field(default_factory=dict)
    idempotent: bool = False
    requires_device_online: bool = True
    readback_verification_expected: bool = True
    safety_level: SafetyLevel = SafetyLevel.LOW_RISK
    status: CapabilityStatus = CapabilityStatus.VERIFIED_EXECUTABLE
    preconditions: List[str] = Field(default_factory=list)
    expected_state_transition: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_executable(self) -> bool:
        """Returns True if the capability is fully verified and available for hardware dispatch."""
        return self.status == CapabilityStatus.VERIFIED_EXECUTABLE

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dictionary serialization."""
        return {
            "canonical_id": self.canonical_id,
            "subsystem": self.subsystem.value,
            "description": self.description,
            "underlying_controller": self.underlying_controller,
            "underlying_capability_name": self.underlying_capability_name,
            "parameters": {
                k: {
                    "name": v.name,
                    "param_type": v.param_type.value,
                    "required": v.required,
                    "default": v.default,
                    "min_value": v.min_value,
                    "max_value": v.max_value,
                    "allowed_values": v.allowed_values,
                    "description": v.description
                }
                for k, v in sorted(self.parameters.items())
            },
            "idempotent": self.idempotent,
            "requires_device_online": self.requires_device_online,
            "readback_verification_expected": self.readback_verification_expected,
            "safety_level": self.safety_level.value,
            "status": self.status.value,
            "is_executable": self.is_executable,
            "preconditions": sorted(self.preconditions),
            "expected_state_transition": self.expected_state_transition
        }
