"""
Authoritative Autonomy Manager for Phase 2 Stage 9 Animus Smart Room.
Governs capability-scoped autonomy permissions, temporary leases, audit logging,
and conservative execution boundaries.

EPISTEMIC & SAFETY INVARIANTS:
1. Zero un-scoped autonomy: Authorizing AC comfort adjustments NEVER authorizes media playback, soundbar stealing, or projector control.
2. Temporary leases automatically expire and revert safely to ASK.
3. Soundbar Fire TV ownership is an absolute hard barrier: Audio autonomy can NEVER steal Bluetooth from Fire TV.
4. Comprehensive audit trail records every decision with clear rationale.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from agent.autonomy_policy import AutonomyCapability, AutonomyGrantLevel, AutonomyAuditRecord
from agent.behavior_modes import BehaviorMode

logger = logging.getLogger("music_daemon.agent.autonomy_manager")


class AutonomyGrantEntry:
    """Internal representation of a capability grant with optional expiration lease."""
    def __init__(self, level: AutonomyGrantLevel, expires_at: Optional[float] = None):
        self.level = level
        self.expires_at = expires_at

    def is_active(self, current_time: Optional[float] = None) -> bool:
        if self.expires_at is None:
            return True
        now = current_time or time.time()
        return now < self.expires_at


class AutonomyManager:
    """
    Evaluates and enforces scoped autonomous execution boundaries across all room capabilities.
    """

    def __init__(self, global_autonomy_enabled: bool = True):
        self.global_autonomy_enabled = global_autonomy_enabled
        self.grants: Dict[AutonomyCapability, AutonomyGrantEntry] = {}
        self.audit_log: List[AutonomyAuditRecord] = []
        self._max_audit_records: int = 200
        self._initialize_default_grants()

    def _initialize_default_grants(self) -> None:
        """Conservative baseline: Everything defaults to ASK, Audio routing to ASK."""
        for cap in AutonomyCapability:
            self.grants[cap] = AutonomyGrantEntry(level=AutonomyGrantLevel.ASK)

    def grant_autonomy(
        self,
        capability: AutonomyCapability,
        level: AutonomyGrantLevel = AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS,
        lease_seconds: Optional[float] = None
    ) -> None:
        """
        Grants an explicit authorization level to a specific capability, optionally bounded by a lease.
        """
        expires_at = (time.time() + lease_seconds) if lease_seconds is not None else None
        self.grants[capability] = AutonomyGrantEntry(level=level, expires_at=expires_at)
        logger.info(f"[AUTONOMY_MANAGER] Granted {capability.value} -> {level.value} (lease={lease_seconds}s)")

    def revoke_autonomy(self, capability: AutonomyCapability) -> None:
        """
        Revokes autonomy for a capability, resetting it safely to ASK.
        """
        self.grants[capability] = AutonomyGrantEntry(level=AutonomyGrantLevel.ASK)
        logger.info(f"[AUTONOMY_MANAGER] Revoked {capability.value} -> reset to ASK")

    def get_grant_level(self, capability: AutonomyCapability, current_time: Optional[float] = None) -> AutonomyGrantLevel:
        """
        Returns active grant level, checking lease expiration.
        """
        if not self.global_autonomy_enabled:
            return AutonomyGrantLevel.ASK

        entry = self.grants.get(capability)
        if not entry or not entry.is_active(current_time):
            return AutonomyGrantLevel.ASK
        return entry.level

    def evaluate_authorization(
        self,
        capability: AutonomyCapability,
        action_type: str,
        target_subsystem: str,
        parameters: Optional[Dict[str, Any]] = None,
        soundbar_owner: str = "PC",
        active_mode: BehaviorMode = BehaviorMode.IDLE,
        origin_trigger: str = "PROACTIVE_MONITOR"
    ) -> Tuple[bool, str, AutonomyGrantLevel]:
        """
        Evaluates whether an autonomous action is authorized to execute immediately.
        Returns: (is_authorized, reason, grant_level)
        """
        params = parameters or {}
        now = time.time()

        # 1. HARD SAFETY INVARIANT: Fire TV Soundbar Protection
        if capability == AutonomyCapability.AUDIO_ROUTING or target_subsystem == "SOUNDBAR":
            if action_type in ("RECLAIM_PC_BLUETOOTH", "CONNECT_PC_BT", "SET_PC_ENDPOINT"):
                if soundbar_owner == "FIRE_TV" or active_mode == BehaviorMode.MOVIE:
                    reason = "DENIED: Soundbar is owned by Fire TV. Autonomous Bluetooth stealing is strictly prohibited."
                    self._record_audit(capability, action_type, target_subsystem, AutonomyGrantLevel.DENIED, False, reason, params, origin_trigger)
                    return False, reason, AutonomyGrantLevel.DENIED

        # 2. Check Global Autonomy Switch
        if not self.global_autonomy_enabled:
            reason = "ASK: Global room autonomy is disabled."
            self._record_audit(capability, action_type, target_subsystem, AutonomyGrantLevel.ASK, False, reason, params, origin_trigger)
            return False, reason, AutonomyGrantLevel.ASK

        # 3. Check Capability Grant & Lease
        active_level = self.get_grant_level(capability, current_time=now)

        if active_level == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS:
            # AC bounds checking
            if capability == AutonomyCapability.AC_ADJUSTMENT and "temperature" in params:
                temp = params["temperature"]
                if temp < 16 or temp > 30:
                    reason = f"DENIED: Requested temperature {temp}°C violates physical limits (16-30°C)."
                    self._record_audit(capability, action_type, target_subsystem, AutonomyGrantLevel.DENIED, False, reason, params, origin_trigger)
                    return False, reason, AutonomyGrantLevel.DENIED

            reason = f"AUTHORIZED: Autonomous policy explicitly grants {capability.value}."
            self._record_audit(capability, action_type, target_subsystem, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS, True, reason, params, origin_trigger)
            return True, reason, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS

        elif active_level == AutonomyGrantLevel.DENIED:
            reason = f"DENIED: Capability {capability.value} is explicitly denied."
            self._record_audit(capability, action_type, target_subsystem, AutonomyGrantLevel.DENIED, False, reason, params, origin_trigger)
            return False, reason, AutonomyGrantLevel.DENIED

        else:
            reason = f"ASK: Autonomous execution for {capability.value} requires user confirmation."
            self._record_audit(capability, action_type, target_subsystem, AutonomyGrantLevel.ASK, False, reason, params, origin_trigger)
            return False, reason, AutonomyGrantLevel.ASK

    def evaluate_comfort_drift(
        self,
        ambient_temperature: float,
        target_temperature: float,
        tolerance_celsius: float = 1.5
    ) -> Optional[Dict[str, Any]]:
        """
        Determines bounded AC correction for environmental drift.
        """
        diff = ambient_temperature - target_temperature
        if diff >= tolerance_celsius:
            # Too hot: recommend lowering AC by 1 degree (bounded)
            bounded_target = max(18.0, target_temperature - 1.0)
            return {
                "action_type": "AC_SET_TEMPERATURE",
                "target_subsystem": "AC",
                "parameters": {"temperature": int(bounded_target)},
                "reason": f"Ambient temperature ({ambient_temperature}°C) exceeds target comfort ({target_temperature}°C) by {diff:.1f}°C"
            }
        elif diff <= -tolerance_celsius:
            # Too cold: recommend raising AC by 1 degree (bounded)
            bounded_target = min(28.0, target_temperature + 1.0)
            return {
                "action_type": "AC_SET_TEMPERATURE",
                "target_subsystem": "AC",
                "parameters": {"temperature": int(bounded_target)},
                "reason": f"Ambient temperature ({ambient_temperature}°C) is colder than target comfort ({target_temperature}°C) by {abs(diff):.1f}°C"
            }
        return None

    def _record_audit(
        self,
        capability: AutonomyCapability,
        action_type: str,
        target_subsystem: str,
        grant_level: AutonomyGrantLevel,
        is_authorized: bool,
        reason: str,
        parameters: Dict[str, Any],
        origin_trigger: str
    ) -> None:
        rec = AutonomyAuditRecord(
            capability=capability,
            action_type=action_type,
            target_subsystem=target_subsystem,
            grant_level=grant_level,
            is_authorized=is_authorized,
            reason=reason,
            parameters=parameters,
            origin_trigger=origin_trigger
        )
        self.audit_log.append(rec)
        if len(self.audit_log) > self._max_audit_records:
            self.audit_log.pop(0)

    def get_audit_log(self, limit: int = 20) -> List[AutonomyAuditRecord]:
        return self.audit_log[-limit:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global_autonomy_enabled": self.global_autonomy_enabled,
            "grants": {
                k.value: {
                    "level": v.level.value,
                    "expires_at": v.expires_at
                }
                for k, v in self.grants.items()
            }
        }

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        self.global_autonomy_enabled = data.get("global_autonomy_enabled", True)
        grants_data = data.get("grants", {})
        for k_str, v_dict in grants_data.items():
            try:
                cap = AutonomyCapability(k_str)
                lvl = AutonomyGrantLevel(v_dict["level"])
                exp = v_dict.get("expires_at")
                self.grants[cap] = AutonomyGrantEntry(level=lvl, expires_at=exp)
            except (ValueError, KeyError):
                continue
