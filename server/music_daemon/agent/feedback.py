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
from agent.interaction_result import AgentInteractionResult, DecisionType, PhysicalVerificationStatus

logger = logging.getLogger("music_daemon.agent.feedback")


class AgentFeedbackGenerator:
    """
    Constructs truthful, transparent conversational feedback from physical execution traces.
    """

    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile

    def generate_closed_loop_feedback(
        self,
        result: AgentInteractionResult,
        user_address: Optional[str] = None
    ) -> str:
        """
        Synthesizes an epistemologically grounded natural response directly from verified state transitions,
        physical readback verifications, or explicit failure reasons.
        """
        addr = user_address or self.user_profile.identity.preferred_address

        # 1. No-Op / Already Satisfied
        if result.decision_type in (DecisionType.NO_OP_ALREADY_SATISFIED, "NO_OP_ALREADY_SATISFIED"):
            if result.human_response:
                return result.human_response
            if result.response_reason:
                return f"{result.response_reason}"
            if result.target_device == "PROJECTOR":
                return f"It's already on, {addr}."
            if result.target_device == "AC":
                return f"Good — looks comfortable in here, {addr}."
            return f"That's already set up, {addr}."

        # 2. Safety / Unsupported Device Rejection
        if result.decision_type in (DecisionType.REJECT_UNSAFE, "REJECT_UNSAFE"):
            return f"That's outside safe operating bounds, {addr}."

        if result.decision_type in (DecisionType.REJECT_UNSUPPORTED, "REJECT_UNSUPPORTED"):
            return f"I don't have control over that device in this room, {addr}."

        # 3. Cancellation & Rejection
        if result.decision_type in (DecisionType.CANCEL_THREAD, DecisionType.CANCEL, "CANCEL_THREAD", "CANCEL"):
            return result.human_response or f"Okay {addr}, leaving it as it is."

        if result.decision_type in (DecisionType.SUGGESTION_REJECTED, "SUGGESTION_REJECTED"):
            return result.human_response or f"Okay {addr}, leaving it as it is."

        # 4. Proactive Suggestion
        if result.decision_type in (DecisionType.PROACTIVE_SUGGESTION, "PROACTIVE_SUGGESTION"):
            return result.human_response or f"The room is getting warmer. Want me to adjust the AC, {addr}?"

        # 5. Modes & Transitions
        if result.decision_type in (DecisionType.MODE_ENTERED, "MODE_ENTERED"):
            return result.human_response or f"We're in mode, {addr}."

        if result.decision_type in (DecisionType.MODE_EXITED, "MODE_EXITED"):
            return result.human_response or f"Exited mode, {addr}."

        # 6. Media & Comfort
        if result.decision_type in (DecisionType.MEDIA_ACTION, DecisionType.MEDIA_STATUS, "MEDIA_ACTION", "MEDIA_STATUS"):
            return result.human_response or f"Media updated, {addr}."

        if result.decision_type in (DecisionType.COMFORT_ADJUSTMENT, "COMFORT_ADJUSTMENT"):
            return result.human_response or f"Adjusted comfort, {addr}."

        # 7. Recovery
        if result.decision_type in (DecisionType.RECOVERY_STARTED, DecisionType.RECOVERY_COMPLETED, DecisionType.RECOVERY_FAILED, "RECOVERY_STARTED", "RECOVERY_COMPLETED", "RECOVERY_FAILED"):
            return result.human_response or f"Recovery status updated, {addr}."

        # 8. Introspection / External Diff / Goal Superseded / Schedules / Situations
        if result.decision_type in (
            DecisionType.INTROSPECTION, DecisionType.EXTERNAL_DIFF, DecisionType.GOAL_SUPERSEDED,
            DecisionType.GOAL_PAUSED, DecisionType.GOAL_RESUMED, DecisionType.GOAL_DEFERRED,
            DecisionType.SCHEDULE_CREATED, DecisionType.SCHEDULE_CANCELLED, DecisionType.SCHEDULE_EXPIRED,
            DecisionType.MODE_DIVERGENCE, DecisionType.EXTERNAL_CHANGE_DETECTED, DecisionType.SITUATION_CHANGED,
            DecisionType.PREFERENCE_UPDATED, DecisionType.PREFERENCE_FORGOTTEN, DecisionType.ROOM_STATUS,
            "INTROSPECTION", "EXTERNAL_DIFF", "GOAL_SUPERSEDED", "GOAL_PAUSED", "GOAL_RESUMED",
            "SCHEDULE_CREATED", "SCHEDULE_CANCELLED", "SCHEDULE_EXPIRED", "MODE_DIVERGENCE",
            "EXTERNAL_CHANGE_DETECTED", "SITUATION_CHANGED", "PREFERENCE_UPDATED", "PREFERENCE_FORGOTTEN", "ROOM_STATUS"
        ):
            return result.human_response or f"All set, {addr}."




        # 5. Physical Execution Attempted
        if result.execution_attempted:
            # A. Failure Handling
            if not result.execution_success or result.physical_verification == PhysicalVerificationStatus.FAILED:
                if result.failure_reason:
                    return f"I couldn't complete that, {addr}: {result.failure_reason}"
                if result.target_device == "PROJECTOR" or "PROJECTOR" in (result.understood_intent or ""):
                    return f"The projector is still starting up and hasn't become reachable yet, {addr}."
                if result.target_device == "AC":
                    if result.understood_intent == "SET_AC_MODE" or result.target_capability == "AC_SET_MODE":
                        return f"I couldn't change the AC mode, {addr}. The requested mode is unavailable."
                    if result.understood_intent == "SET_AC_TEMPERATURE" or result.target_capability == "AC_SET_TEMPERATURE":
                        return f"I couldn't adjust the AC temperature, {addr}. The controller didn't confirm the change."
                    return f"I couldn't turn the AC on, {addr}. The controller didn't confirm the change."
                return f"I couldn't complete that, {addr}. The hardware didn't confirm the change."

            # B. Success Handling from State Delta
            delta = result.state_delta
            if delta:
                if delta.attribute == "target_temperature":
                    prev_v = delta.previous_value
                    new_v = delta.new_value or delta.verified_value
                    if result.response_reason and "moving it to" in result.response_reason.lower():
                        return f"Sure {addr} — moving it to {new_v}°C."
                    if result.response_reason and "putting it back" in result.response_reason.lower():
                        return f"Got you — putting it back to {new_v}°C."
                    if prev_v is not None and new_v is not None and prev_v != new_v:
                        verb = "dropped" if new_v < prev_v else "raised"
                        return f"Got you {addr} — {verb} the AC from {prev_v} to {new_v}°C."
                    return f"Done {addr} — the AC is at {new_v}°C."

                if delta.attribute == "power":
                    if delta.subsystem == "AC":
                        if delta.new_value is True:
                            return f"Done {addr} — the AC is on."
                        else:
                            if result.response_reason:
                                return f"Yeah {addr}, {result.response_reason}"
                            return f"Done {addr} — turned the AC off."
                    if delta.subsystem == "PROJECTOR":
                        return f"Projector's on, {addr}." if delta.new_value else f"Projector is off, {addr}."

                if delta.attribute == "mode":
                    m_val = str(delta.new_value or delta.verified_value).upper()
                    if result.physical_audits:
                        for pa in result.physical_audits:
                            if pa.capability == "AC_SET_TEMPERATURE" and pa.requested_value and "temperature" in pa.requested_value:
                                t_val = pa.requested_value["temperature"]
                                return f"Switched the AC mode to {m_val} at {t_val}°C, {addr}."
                    return f"Switched the AC mode to {m_val}, {addr}."

                if delta.attribute == "fan_speed":
                    f_val = str(delta.new_value or delta.verified_value).upper()
                    return f"Set the AC fan speed to {f_val}, {addr}."

                if delta.attribute == "media_playback":
                    return f"Paused the media for you, {addr}." if delta.new_value == "PAUSED" else f"Resumed playback, {addr}."

                if delta.attribute == "media_provider":
                    prov_title = str(delta.new_value).replace("_", " ").title()
                    content_name = None
                    if result.physical_audits:
                        for pa in result.physical_audits:
                            if pa.requested_value and isinstance(pa.requested_value, dict) and pa.requested_value.get("content"):
                                content_name = str(pa.requested_value["content"]).title()
                                break
                    if content_name:
                        return f"Putting on {content_name} on {prov_title} for you now, {addr}."
                    return f"Opening {prov_title} on the cinema screen for you, {addr}."

        # Fallback to execution result formatter if execution summary available
        if result.execution_summary and "steps" in result.execution_summary:
            pass

        return result.human_response or f"Done, {addr}."

    def generate_goal_feedback(
        self,
        goal: Any,
        user_address: Optional[str] = None
    ) -> str:
        """
        Synthesizes truthful human-readable feedback from an orchestrated AgentGoal.
        Follows strict epistemic invariants:
        - Never claim completion if steps failed or were blocked.
        - Accurately report partial completion with specific verified and failed steps.
        - Distinguish idempotent skips from actual hardware changes.
        """
        from agent.task_models import GoalStatus, StepStatus, GoalType
        addr = user_address or self.user_profile.identity.preferred_address

        # 1. Total Idempotent Skip (All steps already satisfied)
        if all(s.status == StepStatus.SKIPPED_ALREADY_SATISFIED for s in goal.steps):
            if goal.goal_type == GoalType.PREPARE_MOVIE:
                return f"Everything is already set for the movie, {addr}."
            return f"Everything is already set up, {addr}."

        # 2. Complete Goal Success
        if goal.status == GoalStatus.COMPLETED:
            verified_steps = [s for s in goal.steps if s.status == StepStatus.VERIFIED]
            proj_verified = any(s.target_subsystem == "PROJECTOR" for s in verified_steps)
            ac_step = next((s for s in verified_steps if s.target_subsystem == "AC"), None)
            ac_temp = ac_step.requested_parameters.get("temperature", 24) if ac_step else None

            if proj_verified and ac_temp is not None:
                return f"All set, {addr}. The projector is on and the AC is at {ac_temp}°C."
            elif proj_verified:
                return f"All set, {addr}. The projector is on."
            elif ac_temp is not None:
                return f"All set, {addr}. The AC is at {ac_temp}°C."
            return f"All set, {addr}."

        # 3. Partial Completion
        if goal.status == GoalStatus.PARTIALLY_COMPLETED:
            verified_parts = []
            if any(s.status == StepStatus.VERIFIED and s.target_subsystem == "PROJECTOR" for s in goal.steps):
                verified_parts.append("the projector is on")
            ac_step = next((s for s in goal.steps if s.target_subsystem == "AC" and s.status == StepStatus.VERIFIED), None)
            if ac_step and "temperature" in ac_step.requested_parameters:
                verified_parts.append(f"the AC is at {ac_step.requested_parameters['temperature']}°C")

            failed_step = next((s for s in goal.steps if s.status in (StepStatus.FAILED, StepStatus.BLOCKED)), None)
            fail_str = "I couldn't complete the remaining steps"
            if failed_step:
                if failed_step.capability in ("MEDIA_PLAY", "CINEMA_START", "FIRE_TV_MEDIA_PLAY"):
                    fail_str = "I couldn't start the movie"
                elif failed_step.target_subsystem == "PROJECTOR":
                    fail_str = "I couldn't start the projector"
                elif failed_step.target_subsystem == "AC":
                    fail_str = "I couldn't adjust the AC"

            if verified_parts:
                return f"{' and '.join(verified_parts).capitalize()}, {addr}, but {fail_str}."
            return f"I couldn't complete the goal, {addr}: {fail_str}."

        # 4. Dependency Blocked / Upstream Failure
        if goal.status == GoalStatus.BLOCKED or any(s.status == StepStatus.BLOCKED for s in goal.steps):
            first_fail = next((s for s in goal.steps if s.status == StepStatus.FAILED), None)
            blocked_step = next((s for s in goal.steps if s.status == StepStatus.BLOCKED), None)
            if first_fail and blocked_step:
                if first_fail.target_subsystem == "PROJECTOR" and blocked_step.capability in ("MEDIA_PLAY", "CINEMA_START", "FIRE_TV_MEDIA_PLAY"):
                    return f"I couldn't start the projector, {addr}, so I couldn't start the movie either."
                return f"I couldn't complete {first_fail.capability.replace('_', ' ').lower()}, {addr}, so subsequent steps were blocked."
            return f"I couldn't complete that goal, {addr}."


        # 5. Cancelled / Superseded / Paused
        if goal.status == GoalStatus.SUPERSEDED:
            return f"Got it, {addr}. I stopped the remaining steps and switched tasks."

        if goal.status == GoalStatus.PAUSED:
            return f"Paused {goal.normalized_goal}, {addr}."

        if goal.status == GoalStatus.CANCELLED:
            completed_steps = [s for s in goal.steps if s.status == StepStatus.VERIFIED]
            if completed_steps:
                comp_desc = ", ".join([f"the {s.target_subsystem.lower()} is already on" if s.target_subsystem == "PROJECTOR" else f"the {s.target_subsystem.lower()} was set" for s in completed_steps])
                return f"Okay {addr}. I stopped the remaining steps. {comp_desc.capitalize()}, but I didn't continue with the rest."
            return f"Okay {addr}. I stopped the remaining steps."


        # 6. Total Failure
        if goal.status == GoalStatus.FAILED:
            first_fail = next((s for s in goal.steps if s.status == StepStatus.FAILED), None)
            if first_fail:
                if first_fail.target_subsystem == "PROJECTOR":
                    return f"The projector is still starting up and hasn't become reachable yet, {addr}."
                if first_fail.target_subsystem == "AC":
                    return f"I couldn't adjust the AC, {addr}. The hardware didn't confirm the change."
            return f"I couldn't complete that goal, {addr}."

        return f"Done, {addr}."


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


