"""
Authoritative Policy Engine for Phase 2 Stage 7 Animus Smart Room.
Enforces deterministic authorization boundaries on physical hardware actions.

EPISTEMIC & POLICY INVARIANTS:
1. Every candidate hardware mutation must receive an explicit authorization decision:
   - OBSERVE: Monitoring only; physical execution prohibited.
   - ASK: User confirmation required prior to execution.
   - AUTHORIZED_AUTONOMOUS: Bounded execution permitted under verified policy grant.
   - DENIED: Hard invariant violation; execution strictly forbidden.
2. The LLM cannot bypass or weaken policy decisions.
3. Provides explainable rationale for all allowed, asked, or denied actions.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent.behavior_modes import BehaviorMode

logger = logging.getLogger("music_daemon.agent.policy_engine")


class PolicyAuthorization(str, Enum):
    """Authoritative decision levels for physical actions."""
    OBSERVE = "OBSERVE"
    ASK = "ASK"
    AUTHORIZED_AUTONOMOUS = "AUTHORIZED_AUTONOMOUS"
    DENIED = "DENIED"


class PolicyEvaluationResult(BaseModel):
    """Structured result of a policy evaluation."""
    evaluation_id: str = Field(default_factory=lambda: f"pol_{uuid.uuid4().hex[:8]}")
    timestamp: float = Field(default_factory=time.time)
    action_type: str
    target_subsystem: str
    authorization: PolicyAuthorization
    reason: str
    violates_hard_constraint: bool = False
    requires_confirmation_prompt: Optional[str] = None
    applied_rules: List[str] = Field(default_factory=list)

    def is_permitted(self) -> bool:
        """True if action can proceed to execution immediately."""
        return self.authorization == PolicyAuthorization.AUTHORIZED_AUTONOMOUS

    def requires_ask(self) -> bool:
        """True if confirmation prompt must be presented to user."""
        return self.authorization == PolicyAuthorization.ASK

    def is_denied(self) -> bool:
        """True if action is strictly forbidden."""
        return self.authorization == PolicyAuthorization.DENIED


class PolicyEngine:
    """
    Evaluates proposed room actions against safety constraints, soundbar boundaries, and autonomy grants.
    """

    def __init__(self):
        self.evaluation_history: List[PolicyEvaluationResult] = []
        self._max_history: int = 100

    def evaluate_action(
        self,
        action_type: str,
        target_subsystem: str,
        parameters: Optional[Dict[str, Any]] = None,
        is_user_explicit: bool = True,
        is_autonomous_granted: bool = False,
        soundbar_owner: str = "PC",
        active_mode: BehaviorMode = BehaviorMode.IDLE,
        live_telemetry: Optional[Dict[str, Any]] = None
    ) -> PolicyEvaluationResult:
        """
        Evaluates a candidate action and produces an authoritative PolicyEvaluationResult.
        """
        params = parameters or {}
        rules: List[str] = []

        # ---------------------------------------------------------------------
        # Rule 1: HARD SAFETY INVARIANT - Fire TV Soundbar Ownership
        # ---------------------------------------------------------------------
        if target_subsystem == "SOUNDBAR" and action_type in ("RECLAIM_PC_BLUETOOTH", "CONNECT_PC_BT", "SET_PC_ENDPOINT"):
            if soundbar_owner == "FIRE_TV" or active_mode == BehaviorMode.MOVIE:
                res = PolicyEvaluationResult(
                    action_type=action_type,
                    target_subsystem=target_subsystem,
                    authorization=PolicyAuthorization.DENIED,
                    reason="Prohibited: Soundbar is owned by Fire TV. PC Bluetooth reclaim is forbidden.",
                    violates_hard_constraint=True,
                    applied_rules=["RULE_SOUNDBAR_FIRE_TV_PROTECTION"]
                )
                self._archive(res)
                return res

        # ---------------------------------------------------------------------
        # Rule 2: HARD SAFETY INVARIANT - Temperature Limits
        # ---------------------------------------------------------------------
        if target_subsystem == "AC" and "temperature" in params:
            temp = params["temperature"]
            if temp < 16 or temp > 30:
                res = PolicyEvaluationResult(
                    action_type=action_type,
                    target_subsystem=target_subsystem,
                    authorization=PolicyAuthorization.DENIED,
                    reason=f"Prohibited: Requested temperature {temp}°C is outside safe physical limits (16-30°C).",
                    violates_hard_constraint=True,
                    applied_rules=["RULE_AC_TEMPERATURE_BOUNDS"]
                )
                self._archive(res)
                return res

        # ---------------------------------------------------------------------
        # Rule 3: Explicit User Commands Are Authorized
        # ---------------------------------------------------------------------
        if is_user_explicit:
            rules.append("RULE_USER_EXPLICIT_AUTHORIZATION")
            res = PolicyEvaluationResult(
                action_type=action_type,
                target_subsystem=target_subsystem,
                authorization=PolicyAuthorization.AUTHORIZED_AUTONOMOUS,
                reason="Action explicitly authorized by direct user command.",
                applied_rules=rules
            )
            self._archive(res)
            return res

        # ---------------------------------------------------------------------
        # Rule 4: Autonomous Grants for Bounded Subsystems
        # ---------------------------------------------------------------------
        if is_autonomous_granted:
            # AC adjustments under autonomous comfort policy
            if target_subsystem == "AC" and action_type in ("AC_SET_TEMPERATURE", "LOWER_AC", "RAISE_AC"):
                rules.append("RULE_AUTONOMOUS_COMFORT_GRANT")
                res = PolicyEvaluationResult(
                    action_type=action_type,
                    target_subsystem=target_subsystem,
                    authorization=PolicyAuthorization.AUTHORIZED_AUTONOMOUS,
                    reason="Autonomous comfort policy is active; bounded AC adjustment permitted.",
                    applied_rules=rules
                )
                self._archive(res)
                return res

            # Prohibit autonomous media or projector mutations without explicit user prompt
            if target_subsystem in ("PROJECTOR", "FIRE_TV", "MEDIA"):
                rules.append("RULE_AUTONOMY_EXCLUSION_MEDIA")
                res = PolicyEvaluationResult(
                    action_type=action_type,
                    target_subsystem=target_subsystem,
                    authorization=PolicyAuthorization.ASK,
                    reason="Autonomous media/projector changes require user confirmation.",
                    requires_confirmation_prompt=f"Would you like me to adjust {target_subsystem.lower()}?",
                    applied_rules=rules
                )
                self._archive(res)
                return res

        # ---------------------------------------------------------------------
        # Rule 5: Default Un-authorized Proactive Action -> ASK
        # ---------------------------------------------------------------------
        rules.append("RULE_DEFAULT_PROACTIVE_CONFIRMATION")
        confirm_q = f"Would you like me to adjust the {target_subsystem.lower()}?"
        if target_subsystem == "AC" and "temperature" in params:
            confirm_q = f"Want me to set the AC to {params['temperature']}°C?"

        res = PolicyEvaluationResult(
            action_type=action_type,
            target_subsystem=target_subsystem,
            authorization=PolicyAuthorization.ASK,
            reason="Proactive action requires explicit user confirmation before execution.",
            requires_confirmation_prompt=confirm_q,
            applied_rules=rules
        )
        self._archive(res)
        return res

    def _archive(self, res: PolicyEvaluationResult) -> None:
        self.evaluation_history.append(res)
        if len(self.evaluation_history) > self._max_history:
            self.evaluation_history.pop(0)

    def explain_decision(self, evaluation_id: str) -> str:
        """Provides an explainable report for a past policy evaluation."""
        for r in reversed(self.evaluation_history):
            if r.evaluation_id == evaluation_id:
                if r.is_permitted():
                    return f"I allowed {r.action_type} because: {r.reason}"
                elif r.is_denied():
                    return f"I denied {r.action_type} because: {r.reason}"
                else:
                    return f"I asked for confirmation on {r.action_type} because: {r.reason}"
        return "No evaluation record found."
