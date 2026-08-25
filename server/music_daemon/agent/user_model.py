"""
Authoritative User Profile & Preference Manager for Animus Personal Agent.
Encapsulates user identity, behavioral routines, thermal preferences with explicit AC semantics,
entertainment devices, notification quiet hours, and privacy constraints.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from agent.models import (
    UserProfile,
    UserIdentity,
    AcPreferenceModel,
    EntertainmentPreferencesModel,
    NotificationPreferencesModel,
    DailyRoutines
)

logger = logging.getLogger("music_daemon.agent.user_model")


class UserModel:
    """
    Authoritative stateful manager for the user's profile and behavioral preferences.
    """

    def __init__(self, profile: Optional[UserProfile] = None):
        self._profile: UserProfile = profile or UserProfile()

    @property
    def profile(self) -> UserProfile:
        return self._profile

    @property
    def identity(self) -> UserIdentity:
        return self._profile.identity

    @property
    def preferred_address(self) -> str:
        """Returns preferred conversational form of address ('buddy')."""
        return self._profile.identity.preferred_address

    @property
    def routines(self) -> DailyRoutines:
        return self._profile.routines

    @property
    def thermal(self) -> AcPreferenceModel:
        return self._profile.thermal

    @property
    def entertainment(self) -> EntertainmentPreferencesModel:
        return self._profile.entertainment

    @property
    def notifications(self) -> NotificationPreferencesModel:
        return self._profile.notifications

    # =========================================================================
    # Routine & Trigger Evaluation
    # =========================================================================

    def is_lunch_trigger(self, utterance: str) -> bool:
        """
        Determines whether the user's statement represents a lunch-completion routine transition.
        Matches phrases such as 'I had lunch', 'Just had lunch', 'I have lunch', 'finished lunch'.
        """
        lower = utterance.strip().lower()
        return any(trigger in lower for trigger in self._profile.routines.lunch_trigger_keywords)

    def is_in_quiet_hours(self, current_time_str: Optional[str] = None) -> bool:
        """
        Evaluates whether the current local time falls within configured quiet hours (e.g. 11:00 to 17:00).
        During quiet hours, unnecessary conversational interruptions are avoided, while critical alerts remain enabled.
        """
        if not self._profile.notifications.quiet_hours_enabled:
            return False

        if current_time_str is None:
            current_time_str = time.strftime("%H:%M")

        start = self._profile.notifications.quiet_hours_start
        end = self._profile.notifications.quiet_hours_end

        if start <= end:
            return start <= current_time_str < end
        else:
            # Over midnight span
            return current_time_str >= start or current_time_str < end

    # =========================================================================
    # Thermal Policy & AC Disambiguation
    # =========================================================================

    def evaluate_ac_policy_for_work(self, current_ac_on: bool, current_ac_temp: Optional[int] = None) -> Dict[str, Any]:
        """
        Evaluates whether AC should be adjusted for work mode.
        STRICT PRINCIPLE: AC is an independent controllable subsystem.
        Never blindly set temperature without evaluating policy or explicit command.
        """
        policy = self._profile.thermal.work_mode_ac_policy
        setpoint = self._profile.thermal.preferred_ac_setpoint
        mode = self._profile.thermal.comfort_preference

        if policy == "MANUAL_ONLY":
            return {"action_required": False, "reason": "Work AC policy is MANUAL_ONLY"}

        if not current_ac_on:
            # If AC is currently OFF, do not forcefully power on unless policy mandates MAINTAIN_COMFORT
            return {
                "action_required": False,
                "target_temperature": setpoint,
                "target_mode": mode,
                "reason": "AC currently OFF; leaving untouched under standard work policy."
            }

        # If already ON, check if temperature adjustment is needed
        if current_ac_temp is not None and current_ac_temp == setpoint:
            return {
                "action_required": False,
                "target_temperature": setpoint,
                "target_mode": mode,
                "reason": f"AC already at preferred setpoint {setpoint}°C."
            }

        return {
            "action_required": True,
            "target_temperature": setpoint,
            "target_mode": mode,
            "reason": f"Adjusting AC to preferred setpoint {setpoint}°C ({mode}) for work."
        }

    # =========================================================================
    # Serialization & Updates
    # =========================================================================

    def update_profile(self, data: Dict[str, Any]) -> UserProfile:
        """Updates user profile fields."""
        current_dict = self._profile.model_dump()
        for k, v in data.items():
            if k in current_dict and isinstance(v, dict):
                current_dict[k].update(v)
            elif k in current_dict:
                current_dict[k] = v
        self._profile = UserProfile(**current_dict)
        logger.info("[USER_MODEL] User profile updated.")
        return self._profile

    def to_dict(self) -> Dict[str, Any]:
        """Exports clean dictionary representation."""
        return self._profile.model_dump()
