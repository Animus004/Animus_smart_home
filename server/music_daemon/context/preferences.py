"""
Authoritative User & Room Preference Manager for Animus Smart Room.
Validates preference keys and values against the canonical Capability Registry,
enforcing physical bounds (e.g. AC 16-30°C, PC 0-100%) and strict typing.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from capability_registry import UnifiedCapabilityRegistry
from context.models import (
    UserPreferences,
    ComfortPreferences,
    AudioPreferences,
    EntertainmentPreferences,
    ProjectorPreferences,
    EnergyAndBehaviorPreferences
)
from context.errors import PreferenceValidationError

logger = logging.getLogger("music_daemon.context.preferences")


class PreferenceManager:
    """
    Manages active user and room configuration preferences with capability-bound validation.
    """

    def __init__(
        self,
        registry: Optional[UnifiedCapabilityRegistry] = None,
        initial_preferences: Optional[UserPreferences] = None
    ):
        self.registry = registry or UnifiedCapabilityRegistry()
        self._preferences = initial_preferences or UserPreferences()

    def get_preferences(self) -> UserPreferences:
        """Returns the current active UserPreferences snapshot."""
        return self._preferences

    def update_preferences(self, updates: Dict[str, Any]) -> UserPreferences:
        """
        Validates and merges partial preference updates into the active preferences profile.
        Fails deterministically on invalid keys, out-of-bounds numbers, or unsupported enums.
        """
        if not isinstance(updates, dict):
            raise PreferenceValidationError(f"Preference updates must be a dictionary, got {type(updates).__name__}.")

        current_dict = self._preferences.model_dump()

        # Handle flat or nested update dictionaries
        for key, val in updates.items():
            if key in ("comfort", "audio", "entertainment", "projector", "energy") and isinstance(val, dict):
                current_dict[key].update(val)
            elif key in current_dict["comfort"]:
                current_dict["comfort"][key] = val
            elif key in current_dict["audio"]:
                current_dict["audio"][key] = val
            elif key in current_dict["entertainment"]:
                current_dict["entertainment"][key] = val
            elif key in current_dict["projector"]:
                current_dict["projector"][key] = val
            elif key in current_dict["energy"]:
                current_dict["energy"][key] = val
            else:
                raise PreferenceValidationError(f"Unknown or unsupported preference key '{key}'.", field=key, invalid_value=val)

        # Validate through Capability Registry constraints & Pydantic models
        validated_prefs = self.validate_preferences(current_dict)
        self._preferences = validated_prefs
        logger.info("[PREFERENCE_MANAGER] Updated user preferences profile.")
        return self._preferences

    def validate_preferences(self, data: Dict[str, Any]) -> UserPreferences:
        """
        Enforces both Pydantic schema validation and authoritative Capability Registry physical bounds.
        """
        try:
            # 1. Pydantic Model Validation
            prefs = UserPreferences(**data)

            # 2. Canonical Registry Invariant Checks
            # Check AC Temperature against AC_SET_TEMPERATURE definition
            ac_cap = self.registry.get_capability("AC_SET_TEMPERATURE")
            if ac_cap and "temperature" in ac_cap.parameters:
                tc = ac_cap.parameters["temperature"]
                t_val = prefs.comfort.preferred_ac_temperature
                if tc.min_value is not None and t_val < tc.min_value:
                    raise PreferenceValidationError(f"preferred_ac_temperature ({t_val}) is below physical limit ({tc.min_value}).", field="preferred_ac_temperature", invalid_value=t_val)
                if tc.max_value is not None and t_val > tc.max_value:
                    raise PreferenceValidationError(f"preferred_ac_temperature ({t_val}) exceeds physical limit ({tc.max_value}).", field="preferred_ac_temperature", invalid_value=t_val)

            # Check PC Volume against PC_SET_VOLUME definition
            pc_cap = self.registry.get_capability("PC_SET_VOLUME")
            if pc_cap and "volume" in pc_cap.parameters:
                vc = pc_cap.parameters["volume"]
                v_val = prefs.audio.preferred_pc_volume
                if vc.min_value is not None and v_val < vc.min_value:
                    raise PreferenceValidationError(f"preferred_pc_volume ({v_val}) is below physical limit ({vc.min_value}).", field="preferred_pc_volume", invalid_value=v_val)
                if vc.max_value is not None and v_val > vc.max_value:
                    raise PreferenceValidationError(f"preferred_pc_volume ({v_val}) exceeds physical limit ({vc.max_value}).", field="preferred_pc_volume", invalid_value=v_val)

            # Check Projector Brightness against PROJECTOR_SET_BRIGHTNESS definition
            proj_cap = self.registry.get_capability("PROJECTOR_SET_BRIGHTNESS")
            if proj_cap and "brightness" in proj_cap.parameters:
                bc = proj_cap.parameters["brightness"]
                b_val = prefs.projector.preferred_brightness
                if bc.min_value is not None and b_val < bc.min_value:
                    raise PreferenceValidationError(f"preferred_brightness ({b_val}) is below physical limit ({bc.min_value}).", field="preferred_brightness", invalid_value=b_val)
                if bc.max_value is not None and b_val > bc.max_value:
                    raise PreferenceValidationError(f"preferred_brightness ({b_val}) exceeds physical limit ({bc.max_value}).", field="preferred_brightness", invalid_value=b_val)

            return prefs

        except PreferenceValidationError:
            raise
        except Exception as e:
            raise PreferenceValidationError(f"Preference validation failure: {e}")

    def export_prompt_dict(self) -> Dict[str, Any]:
        """Serializes preferences for inclusion in Gemini Planner prompt context."""
        return self._preferences.to_dict()
