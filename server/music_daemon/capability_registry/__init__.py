"""
Unified Capability Registry Module for Animus Smart Room.
Authoritative machine-readable catalog, canonical capability definitions,
and bidirectional translation tables.
"""

from capability_registry.models import (
    Subsystem,
    SafetyLevel,
    CapabilityStatus,
    ParameterType,
    ParameterConstraint,
    CapabilityDefinition
)
from capability_registry.catalog import AUTHORITATIVE_CAPABILITIES
from capability_registry.registry import (
    UnifiedCapabilityRegistry,
    RegistryValidationError
)

__all__ = [
    "Subsystem",
    "SafetyLevel",
    "CapabilityStatus",
    "ParameterType",
    "ParameterConstraint",
    "CapabilityDefinition",
    "AUTHORITATIVE_CAPABILITIES",
    "UnifiedCapabilityRegistry",
    "RegistryValidationError"
]
