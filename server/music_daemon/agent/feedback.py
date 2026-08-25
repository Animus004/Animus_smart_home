"""
Agent Feedback Engine for Animus Personal Agent.
Generates concise, human-like feedback based on actual physical execution read-backs.
Reports what was understood, what was executed, what was already satisfied, and what failed.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from planner.models import ExecutionResult, ExecutionStatus, OverallExecutionStatus
from agent.models import UserProfile

logger = logging.getLogger("music_daemon.agent.feedback")


class AgentFeedbackGenerator:
    """
    Constructs truthful, transparent conversational feedback from physical execution traces.
    """

    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile

    def format_execution_feedback(
        self,
        command: str,
        exec_result: ExecutionResult,
        followup_question: Optional[str] = None
    ) -> str:
        """
        Synthesizes human-readable feedback from an ExecutionResult.
        """
        addr = self.user_profile.identity.preferred_address
        status = exec_result.overall_status

        executed_steps: List[str] = []
        skipped_steps: List[str] = []
        failed_steps: List[str] = []

        for step in exec_result.steps:
            cap = step.capability_id
            human_name = self._humanize_capability(cap, step.requested_parameters)
            if step.status == ExecutionStatus.VERIFIED:
                executed_steps.append(human_name)
            elif step.status == ExecutionStatus.SKIPPED:
                skipped_steps.append(human_name)
            elif step.status in (ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT):
                failed_steps.append(human_name)

        # 1. Total Idempotent Skip (Everything was already ready)
        if status == OverallExecutionStatus.SKIPPED or (len(skipped_steps) > 0 and len(executed_steps) == 0 and len(failed_steps) == 0):
            feedback = f"Everything is already set up and ready, {addr}."
            if followup_question:
                feedback += f" {followup_question}"
            return feedback

        # 2. Complete Execution Success
        if status == OverallExecutionStatus.SUCCESS and len(failed_steps) == 0:
            if executed_steps:
                actions_str = ", ".join(executed_steps)
                feedback = f"All set, {addr} — I've prepared {actions_str}."
            else:
                feedback = f"All done, {addr}."

            if skipped_steps:
                skipped_str = ", ".join(skipped_steps)
                feedback += f" ({skipped_str} was already in place)."

            if followup_question:
                feedback += f" {followup_question}"
            return feedback

        # 3. Partial Execution
        if status == OverallExecutionStatus.PARTIAL_SUCCESS or (len(executed_steps) > 0 and len(failed_steps) > 0):
            done_str = ", ".join(executed_steps) if executed_steps else "some initial setup"
            fail_str = ", ".join(failed_steps)
            return f"I got {done_str} ready, {addr}, but {fail_str} didn't respond as expected."

        # 4. Total Failure
        if status in (OverallExecutionStatus.FAILED, OverallExecutionStatus.ABORTED) or len(failed_steps) > 0:
            fail_str = ", ".join(failed_steps) if failed_steps else "the requested action"
            return f"Sorry {addr}, I wasn't able to complete {fail_str} for '{command}'. I've left the room safely as-is."

        return f"Done, {addr}."

    def _humanize_capability(self, cap_id: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Converts canonical capability IDs into natural English phrases with parameter context."""
        params = params or {}
        if cap_id == "AC_SET_TEMPERATURE":
            temp = params.get("temperature")
            return f"the AC to {temp}°C" if temp is not None else "the AC temperature"
        if cap_id == "FIRE_TV_MEDIA_DIRECT_PROVIDER":
            prov = params.get("provider", "streaming app")
            return f"{prov.title()} on Fire TV"
        if cap_id == "FIRE_TV_MEDIA_PLAY":
            return "resumed media on Fire TV"
        if cap_id == "FIRE_TV_MEDIA_PAUSE":
            return "paused media on Fire TV"
        if cap_id == "FIRE_TV_APP_LAUNCH_YOUTUBE":
            return "YouTube on Fire TV"

        mapping = {
            "PROJECTOR_POWER_WAKE": "the projector",
            "PROJECTOR_POWER_SLEEP": "putting projector to sleep",
            "PROJECTOR_SWITCH_HDMI1": "the Fire TV HDMI display",
            "PROJECTOR_SWITCH_ANDROID": "the Android home screen",
            "PROJECTOR_SET_BRIGHTNESS": "projector brightness",
            "FIRE_TV_POWER_WAKE": "Fire TV",
            "FIRE_TV_POWER_SLEEP": "Fire TV sleep",
            "FIRE_TV_LAUNCH_APP": "the streaming app",
            "FIRE_TV_VOLUME_DOWN": "Fire TV volume",
            "FIRE_TV_VOLUME_UP": "Fire TV volume",
            "FIRE_TV_MUTE": "Fire TV mute",
            "SOUNDBAR_ROUTE_TO_FIRE_TV": "soundbar routed to Fire TV",
            "SOUNDBAR_ROUTE_TO_PC": "soundbar connected to PC",
            "SOUNDBAR_DISCONNECT": "soundbar disconnected",
            "PC_SET_VOLUME": "PC volume",
            "PC_SET_MUTE": "PC mute",
            "AC_POWER_ON": "AC power on",
            "AC_POWER_OFF": "AC power off",
            "AC_SET_POWER": "AC power",
            "AC_SET_MODE": "AC mode",
        }
        return mapping.get(cap_id, cap_id.lower().replace("_", " "))

