"""
Authoritative Unified Capability Registry for Animus Smart Room.
Provides metadata, bidirectional canonical translation, safety boundary enforcement,
operation type filtering, and deterministic catalog serialization without executing hardware commands.
"""

import json
from typing import Dict, List, Optional, Tuple, Any, Union

from capability_registry.models import (
    Subsystem,
    OperationType,
    SafetyLevel,
    CapabilityStatus,
    CapabilityDefinition
)
from capability_registry.catalog import AUTHORITATIVE_CAPABILITIES


class RegistryValidationError(Exception):
    """Raised when capability definitions fail closed during validation."""
    pass


class UnifiedCapabilityRegistry:
    """
    Central machine-readable capability registry for Animus Smart Room.
    Maintains an authoritative catalog of physical device capabilities,
    deterministic bidirectional translation tables, and validation guarantees.
    """
    def __init__(self, custom_capabilities: Optional[List[CapabilityDefinition]] = None):
        self._capabilities_by_id: Dict[str, CapabilityDefinition] = {}
        self._underlying_to_canonical: Dict[Tuple[Subsystem, str], str] = {}
        
        raw_list = custom_capabilities if custom_capabilities is not None else AUTHORITATIVE_CAPABILITIES
        self._load_and_validate(raw_list)

    def _load_and_validate(self, capabilities: List[CapabilityDefinition]) -> None:
        """
        Validates catalog integrity and populates fast lookup indices.
        Fails closed on any inconsistency, duplicate, or unsafe definition.
        """
        for cap in capabilities:
            # 1. Canonical ID validation
            cid = cap.canonical_id.strip()
            if not cid:
                raise RegistryValidationError("Capability canonical_id cannot be empty.")
            if cid in self._capabilities_by_id:
                raise RegistryValidationError(f"Duplicate canonical_id detected: '{cid}'")
            
            # 2. Underlying name validation
            uname = cap.underlying_capability_name.strip()
            if not uname:
                raise RegistryValidationError(f"Capability '{cid}' has empty underlying_capability_name.")
            
            mapping_key = (cap.subsystem, uname)
            if mapping_key in self._underlying_to_canonical:
                prev_cid = self._underlying_to_canonical[mapping_key]
                raise RegistryValidationError(
                    f"Duplicate underlying mapping detected for subsystem {cap.subsystem.value} and "
                    f"name '{uname}': '{prev_cid}' vs '{cid}'"
                )

            # 3. Unsupported capability safety invariant
            if cap.status in (CapabilityStatus.UNSUPPORTED_HARDWARE, CapabilityStatus.DEFERRED_PENDING_IMPLEMENTATION):
                if cap.is_executable:
                    raise RegistryValidationError(
                        f"Unsupported/deferred capability '{cid}' cannot be marked executable."
                    )

            # 4. Parameter bounds validation
            for pname, pcon in cap.parameters.items():
                if pcon.min_value is not None and pcon.max_value is not None:
                    if pcon.min_value > pcon.max_value:
                        raise RegistryValidationError(
                            f"Capability '{cid}' parameter '{pname}' has invalid range: min {pcon.min_value} > max {pcon.max_value}"
                        )

            # Populate lookup indices
            self._capabilities_by_id[cid] = cap
            self._underlying_to_canonical[mapping_key] = cid

    # =========================================================================
    # Lookup & Translation API
    # =========================================================================

    def get_capability(self, canonical_id: str) -> Optional[CapabilityDefinition]:
        """Looks up a capability definition by its canonical ID."""
        if not canonical_id:
            return None
        return self._capabilities_by_id.get(canonical_id.strip())

    def get_canonical_id_for_underlying(self, subsystem: Union[Subsystem, str], underlying_name: str) -> Optional[str]:
        """Translates an underlying controller capability name into its canonical ID."""
        if not underlying_name or not subsystem:
            return None
        sub_enum = subsystem if isinstance(subsystem, Subsystem) else Subsystem(subsystem.upper())
        return self._underlying_to_canonical.get((sub_enum, underlying_name.strip()))

    def get_underlying_name(self, canonical_id: str) -> Optional[str]:
        """Translates a canonical ID into its underlying controller capability name."""
        cap = self.get_capability(canonical_id)
        return cap.underlying_capability_name if cap else None

    # =========================================================================
    # Filtering API
    # =========================================================================

    def get_all_capabilities(self) -> List[CapabilityDefinition]:
        """Returns all registered capabilities sorted deterministically by canonical_id."""
        return [self._capabilities_by_id[cid] for cid in sorted(self._capabilities_by_id.keys())]

    def get_executable_capabilities(self) -> List[CapabilityDefinition]:
        """Returns only verified, executable capabilities available for physical dispatch."""
        return [cap for cap in self.get_all_capabilities() if cap.is_executable]

    def get_capabilities_by_subsystem(self, subsystem: Union[Subsystem, str]) -> List[CapabilityDefinition]:
        """Returns all capabilities belonging to a specific subsystem."""
        sub_enum = subsystem if isinstance(subsystem, Subsystem) else Subsystem(subsystem.upper())
        return [cap for cap in self.get_all_capabilities() if cap.subsystem == sub_enum]

    def get_unsupported_capabilities(self) -> List[CapabilityDefinition]:
        """Returns all unsupported or deferred capabilities."""
        return [cap for cap in self.get_all_capabilities() if not cap.is_executable]

    def get_queries(self) -> List[CapabilityDefinition]:
        """Returns all read-only query/telemetry capabilities."""
        return [cap for cap in self.get_all_capabilities() if cap.operation_type == OperationType.QUERY]

    def get_actions(self) -> List[CapabilityDefinition]:
        """Returns all atomic action/mutation capabilities."""
        return [cap for cap in self.get_all_capabilities() if cap.operation_type == OperationType.ACTION]

    def get_automations(self) -> List[CapabilityDefinition]:
        """Returns all multi-step composed automation workflows."""
        return [cap for cap in self.get_all_capabilities() if cap.operation_type == OperationType.AUTOMATION]

    # =========================================================================
    # Deterministic Serialization & Prompt Catalog Export
    # =========================================================================

    def export_catalog_dict(self) -> Dict[str, Any]:
        """Exports complete catalog as a deterministic dictionary."""
        caps = self.get_all_capabilities()
        by_sub: Dict[str, List[Dict[str, Any]]] = {}
        for c in caps:
            sub_key = c.subsystem.value.lower()
            if sub_key not in by_sub:
                by_sub[sub_key] = []
            by_sub[sub_key].append(c.to_dict())

        return {
            "version": "1.0.0",
            "total_capabilities": len(caps),
            "executable_capabilities": len(self.get_executable_capabilities()),
            "unsupported_capabilities": len(self.get_unsupported_capabilities()),
            "queries": len(self.get_queries()),
            "actions": len(self.get_actions()),
            "automations": len(self.get_automations()),
            "subsystems": {k: by_sub[k] for k in sorted(by_sub.keys())}
        }

    def export_catalog_json(self) -> str:
        """Exports catalog as a deterministic, indented JSON string."""
        return json.dumps(self.export_catalog_dict(), indent=2, sort_keys=True)

    def export_prompt_schema_dict(self) -> Dict[str, Any]:
        """
        Exports a compact, sanitized capability catalog formatted specifically for injection
        into Gemini Structured Planner system instructions. Only includes executable capabilities.
        """
        executable_caps = self.get_executable_capabilities()
        prompt_catalog: Dict[str, Any] = {}

        for cap in executable_caps:
            sub = cap.subsystem.value.lower()
            if sub not in prompt_catalog:
                prompt_catalog[sub] = []

            param_meta = {}
            for pname, pcon in sorted(cap.parameters.items()):
                pdict: Dict[str, Any] = {
                    "type": pcon.param_type.value,
                    "required": pcon.required
                }
                if pcon.min_value is not None:
                    pdict["min"] = pcon.min_value
                if pcon.max_value is not None:
                    pdict["max"] = pcon.max_value
                if pcon.allowed_values:
                    pdict["allowed_values"] = pcon.allowed_values
                param_meta[pname] = pdict

            prompt_catalog[sub].append({
                "capability": cap.canonical_id,
                "operation_type": cap.operation_type.value,
                "description": cap.description,
                "parameters": param_meta,
                "idempotent": cap.idempotent,
                "preconditions": cap.preconditions,
                "safety_level": cap.safety_level.value
            })

        return prompt_catalog
