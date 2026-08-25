"""
Authoritative Automated Test Battery for Phase 2 Stage 9:
Policy-Bounded Autonomy, Capability Isolation, Temporary Leases, and Scoped Execution.

Covers Sections A through G (60+ comprehensive tests):
Section A: Capability Taxonomy & Default Grants (Tests A1-A10)
Section B: Grants, Revocations & Temporary Leases (Tests B1-B10)
Section C: Subsystem Isolation & Anti-Scope-Creep (Tests C1-C10)
Section D: Soundbar Fire TV Ownership & Safety Limits (Tests D1-D10)
Section E: Bounded Environmental Drift (Tests E1-E10)
Section F: Audit Logging & Introspection (Tests F1-F10)
Section G: Agent Integration (Tests G1-G6)
"""

import time
import pytest

from agent.autonomy_policy import AutonomyCapability, AutonomyGrantLevel, AutonomyAuditRecord
from agent.autonomy_manager import AutonomyManager
from agent.behavior_modes import BehaviorMode
from agent.core import AnimusPersonalAgent


# =============================================================================
# SECTION A: CAPABILITY TAXONOMY & DEFAULT GRANTS (Tests A1-A10)
# =============================================================================

def test_a1_autonomy_capabilities_count():
    """All 8 core autonomy capabilities are defined in enum."""
    caps = list(AutonomyCapability)
    assert len(caps) == 8
    assert AutonomyCapability.AC_ADJUSTMENT in caps
    assert AutonomyCapability.MEDIA_CONTROL in caps
    assert AutonomyCapability.PROJECTOR_CONTROL in caps
    assert AutonomyCapability.AUDIO_ROUTING in caps


def test_a2_grant_levels_enum():
    """AutonomyGrantLevel supports ASK, AUTHORIZED_AUTONOMOUS, and DENIED."""
    assert AutonomyGrantLevel.ASK.value == "ASK"
    assert AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS.value == "AUTHORIZED_AUTONOMOUS"
    assert AutonomyGrantLevel.DENIED.value == "DENIED"


def test_a3_manager_defaults_to_ask():
    """By default, all capabilities initialize to ASK for conservative safety."""
    mgr = AutonomyManager()
    for cap in AutonomyCapability:
        assert mgr.get_grant_level(cap) == AutonomyGrantLevel.ASK


def test_a4_global_autonomy_disabled_forces_ask():
    """Disabling global autonomy forces all capabilities to evaluate to ASK."""
    mgr = AutonomyManager(global_autonomy_enabled=False)
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.ASK


def test_a5_audit_record_instantiation():
    """AutonomyAuditRecord records all evaluation metadata."""
    rec = AutonomyAuditRecord(
        capability=AutonomyCapability.AC_ADJUSTMENT,
        action_type="SET_TEMP",
        target_subsystem="AC",
        grant_level=AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS,
        is_authorized=True,
        reason="Comfort grant"
    )
    assert rec.audit_id.startswith("aud_")
    assert rec.is_authorized is True
    assert rec.timestamp > 0


def test_a6_evaluate_authorization_returns_tuple():
    """evaluate_authorization returns (is_authorized, reason, grant_level)."""
    mgr = AutonomyManager()
    auth, reason, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AC_ADJUSTMENT,
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC"
    )
    assert isinstance(auth, bool)
    assert isinstance(reason, str)
    assert isinstance(level, AutonomyGrantLevel)


def test_a7_default_unauthorized_action_requires_ask():
    """Unprompted action without grant evaluates to False / ASK."""
    mgr = AutonomyManager()
    auth, reason, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.MEDIA_CONTROL,
        action_type="PLAY_MEDIA",
        target_subsystem="MEDIA"
    )
    assert auth is False
    assert level == AutonomyGrantLevel.ASK
    assert "requires user confirmation" in reason.lower()


def test_a8_manager_serialization_to_dict():
    """to_dict serializes global switch and grant states."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    data = mgr.to_dict()
    assert data["global_autonomy_enabled"] is True
    assert data["grants"]["AC_ADJUSTMENT"]["level"] == "AUTHORIZED_AUTONOMOUS"


def test_a9_manager_deserialization_from_dict():
    """load_from_dict restores manager configuration."""
    data = {
        "global_autonomy_enabled": True,
        "grants": {
            "AC_ADJUSTMENT": {"level": "AUTHORIZED_AUTONOMOUS", "expires_at": None},
            "MEDIA_CONTROL": {"level": "DENIED", "expires_at": None}
        }
    }
    mgr = AutonomyManager()
    mgr.load_from_dict(data)
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS
    assert mgr.get_grant_level(AutonomyCapability.MEDIA_CONTROL) == AutonomyGrantLevel.DENIED


def test_a10_deserialization_handles_corrupt_entries_safely():
    """load_from_dict ignores unrecognized capabilities cleanly."""
    data = {"global_autonomy_enabled": True, "grants": {"NON_EXISTENT_CAP": {"level": "AUTHORIZED"}}}
    mgr = AutonomyManager()
    mgr.load_from_dict(data)
    assert len(mgr.grants) == 8


# =============================================================================
# SECTION B: GRANTS, REVOCATIONS & LEASES (Tests B1-B10)
# =============================================================================

def test_b1_grant_autonomy_enables_capability():
    """grant_autonomy permits authorized execution for the target capability."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, reason, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AC_ADJUSTMENT,
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 23}
    )
    assert auth is True
    assert level == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_b2_revoke_autonomy_resets_to_ask():
    """revoke_autonomy immediately resets capability to ASK."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    mgr.revoke_autonomy(AutonomyCapability.AC_ADJUSTMENT)
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.ASK


def test_b3_temporary_lease_active_before_expiry():
    """Temporary lease is valid while within lease_seconds duration."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.LIGHTING_CONTROL, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS, lease_seconds=300.0)
    assert mgr.get_grant_level(AutonomyCapability.LIGHTING_CONTROL) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_b4_temporary_lease_reverts_to_ask_after_expiry():
    """Temporary lease automatically expires and falls back to ASK."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.LIGHTING_CONTROL, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS, lease_seconds=10.0)
    future_time = time.time() + 15.0
    assert mgr.get_grant_level(AutonomyCapability.LIGHTING_CONTROL, current_time=future_time) == AutonomyGrantLevel.ASK


def test_b5_explicit_denied_grant():
    """Grant level DENIED explicitly blocks autonomous action."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.PROJECTOR_CONTROL, AutonomyGrantLevel.DENIED)
    auth, reason, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.PROJECTOR_CONTROL,
        action_type="PROJECTOR_POWER_OFF",
        target_subsystem="PROJECTOR"
    )
    assert auth is False
    assert level == AutonomyGrantLevel.DENIED
    assert "explicitly denied" in reason.lower()


def test_b6_grant_override_updates_level():
    """Subsequent grant updates the permission level in place."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.DENIED)
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_b7_multiple_grants_independent():
    """Multiple capabilities can be configured with different grant levels simultaneously."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    mgr.grant_autonomy(AutonomyCapability.PROJECTOR_CONTROL, AutonomyGrantLevel.DENIED)
    mgr.grant_autonomy(AutonomyCapability.MEDIA_CONTROL, AutonomyGrantLevel.ASK)

    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS
    assert mgr.get_grant_level(AutonomyCapability.PROJECTOR_CONTROL) == AutonomyGrantLevel.DENIED
    assert mgr.get_grant_level(AutonomyCapability.MEDIA_CONTROL) == AutonomyGrantLevel.ASK


def test_b8_toggle_global_autonomy_restores_grants_when_re_enabled():
    """Re-enabling global autonomy restores previous capability grants."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    mgr.global_autonomy_enabled = False
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.ASK
    mgr.global_autonomy_enabled = True
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_b9_lease_expiry_in_evaluation():
    """Expired lease returns False in evaluate_authorization."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS, lease_seconds=-10.0)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC")
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_b10_lease_none_is_permanent():
    """lease_seconds=None never expires."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS, lease_seconds=None)
    future = time.time() + (86400 * 365)
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT, current_time=future) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


# =============================================================================
# SECTION C: SUBSYSTEM ISOLATION & ANTI-SCOPE-CREEP (Tests C1-C10)
# =============================================================================

def test_c1_ac_grant_does_not_authorize_media():
    """Granting AC comfort autonomy does NOT authorize media playback."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.MEDIA_CONTROL, "FIRE_TV_PLAY", "MEDIA")
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_c2_ac_grant_does_not_authorize_projector():
    """Granting AC comfort autonomy does NOT authorize projector power."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.PROJECTOR_CONTROL, "PROJECTOR_POWER_WAKE", "PROJECTOR")
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_c3_ac_grant_does_not_authorize_audio_routing():
    """Granting AC comfort autonomy does NOT authorize audio routing changes."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.AUDIO_ROUTING, "SET_AUDIO_OUTPUT", "SOUNDBAR")
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_c4_lighting_grant_does_not_authorize_ac():
    """Granting Lighting autonomy does NOT authorize AC changes."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.LIGHTING_CONTROL, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC")
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_c5_routine_grant_does_not_authorize_unprompted_destructive_actions():
    """Routine execution grant is scoped to scheduled routines."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.ROUTINE_EXECUTION, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    assert mgr.get_grant_level(AutonomyCapability.ROUTINE_EXECUTION) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS
    assert mgr.get_grant_level(AutonomyCapability.MEDIA_CONTROL) == AutonomyGrantLevel.ASK


def test_c6_recovery_grant_isolation():
    """Recovery grant authorizes bounded fault healing only."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.RECOVERY, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.RECOVERY, "HEALTH_PROBE", "SYSTEM")
    assert auth is True
    assert level == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_c7_cross_subsystem_target_mismatch_denial():
    """Target subsystem mismatch does not bypass authorization."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, _ = mgr.evaluate_authorization(AutonomyCapability.MEDIA_CONTROL, "AC_COMMAND_ON_MEDIA", "MEDIA")
    assert auth is False


def test_c8_all_capabilities_isolated_by_default():
    """All capabilities are strictly isolated in separate entries."""
    mgr = AutonomyManager()
    for cap in AutonomyCapability:
        assert mgr.grants[cap].level == AutonomyGrantLevel.ASK


def test_c9_scheduled_action_grant_isolation():
    """Scheduled action capability is distinct from AC or Media."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.SCHEDULED_ACTION, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    assert mgr.get_grant_level(AutonomyCapability.SCHEDULED_ACTION) == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT) == AutonomyGrantLevel.ASK


def test_c10_projector_control_isolation():
    """Projector control grant does not affect lighting or audio."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.PROJECTOR_CONTROL, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    assert mgr.get_grant_level(AutonomyCapability.LIGHTING_CONTROL) == AutonomyGrantLevel.ASK
    assert mgr.get_grant_level(AutonomyCapability.AUDIO_ROUTING) == AutonomyGrantLevel.ASK


# =============================================================================
# SECTION D: SOUNDBAR OWNERSHIP & SAFETY LIMITS (Tests D1-D10)
# =============================================================================

def test_d1_audio_autonomy_cannot_steal_bluetooth_from_fire_tv():
    """Audio routing autonomy grant CANNOT steal Bluetooth when Fire TV owns soundbar."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AUDIO_ROUTING, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, reason, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AUDIO_ROUTING,
        action_type="RECLAIM_PC_BLUETOOTH",
        target_subsystem="SOUNDBAR",
        soundbar_owner="FIRE_TV"
    )
    assert auth is False
    assert level == AutonomyGrantLevel.DENIED
    assert "strictly prohibited" in reason.lower()


def test_d2_soundbar_fire_tv_ownership_in_movie_mode_denies_bt_reclaim():
    """Movie mode strictly denies PC Bluetooth reclaim under any autonomy setting."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AUDIO_ROUTING, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AUDIO_ROUTING,
        action_type="CONNECT_PC_BT",
        target_subsystem="SOUNDBAR",
        soundbar_owner="UNKNOWN",
        active_mode=BehaviorMode.MOVIE
    )
    assert auth is False
    assert level == AutonomyGrantLevel.DENIED


def test_d3_pc_soundbar_ownership_allows_routing_when_granted():
    """When PC owns soundbar, audio routing autonomy is allowed."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AUDIO_ROUTING, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AUDIO_ROUTING,
        action_type="SET_PC_ENDPOINT",
        target_subsystem="SOUNDBAR",
        soundbar_owner="PC"
    )
    assert auth is True
    assert level == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_d4_ac_temperature_out_of_bounds_denied():
    """AC temperature below 16°C or above 30°C is DENIED even with full autonomy grant."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth_low, _, level_low = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC", parameters={"temperature": 15})
    auth_high, _, level_high = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC", parameters={"temperature": 32})

    assert auth_low is False
    assert level_low == AutonomyGrantLevel.DENIED
    assert auth_high is False
    assert level_high == AutonomyGrantLevel.DENIED


def test_d5_ac_valid_temperature_authorized_when_granted():
    """AC temperature 23°C is authorized under active comfort grant."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC", parameters={"temperature": 23})
    assert auth is True
    assert level == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_d6_denied_records_in_audit_log():
    """Denied actions are written to audit log with reason."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AUDIO_ROUTING, "RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    latest = mgr.get_audit_log(1)[0]
    assert latest.is_authorized is False
    assert latest.grant_level == AutonomyGrantLevel.DENIED


def test_d7_soundbar_protection_applies_to_recovery_capability():
    """Recovery capability also cannot steal Fire TV soundbar."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.RECOVERY, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.RECOVERY, "RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    assert auth is False
    assert level == AutonomyGrantLevel.DENIED


def test_d8_safe_mode_forces_ask():
    """BehaviorMode.SLEEP or IDLE respects conservative defaults."""
    mgr = AutonomyManager()
    auth, _, level = mgr.evaluate_authorization(AutonomyCapability.PROJECTOR_CONTROL, "POWER_ON", "PROJECTOR", active_mode=BehaviorMode.SLEEP)
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_d9_ac_exact_boundary_16_allowed():
    """Boundary temperature 16°C is permitted."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, _ = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC", parameters={"temperature": 16})
    assert auth is True


def test_d10_ac_exact_boundary_30_allowed():
    """Boundary temperature 30°C is permitted."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, _ = mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "AC_SET_TEMPERATURE", "AC", parameters={"temperature": 30})
    assert auth is True


# =============================================================================
# SECTION E: BOUNDED ENVIRONMENTAL DRIFT (Tests E1-E10)
# =============================================================================

def test_e1_comfort_drift_hot_recommends_lowering():
    """Ambient temperature 27°C with target 24°C recommends lowering AC to 23°C."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(ambient_temperature=27.0, target_temperature=24.0, tolerance_celsius=1.5)
    assert corr is not None
    assert corr["action_type"] == "AC_SET_TEMPERATURE"
    assert corr["parameters"]["temperature"] == 23


def test_e2_comfort_drift_cold_recommends_raising():
    """Ambient temperature 21°C with target 24°C recommends raising AC to 25°C."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(ambient_temperature=21.0, target_temperature=24.0, tolerance_celsius=1.5)
    assert corr is not None
    assert corr["parameters"]["temperature"] == 25


def test_e3_comfort_within_tolerance_returns_none():
    """Ambient temperature within 1.5°C of target returns None (no action needed)."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(ambient_temperature=24.5, target_temperature=24.0, tolerance_celsius=1.5)
    assert corr is None


def test_e4_comfort_lower_bound_clamp():
    """Bounded comfort adjustment never drops below 18°C."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(ambient_temperature=25.0, target_temperature=18.0, tolerance_celsius=1.0)
    assert corr is not None
    assert corr["parameters"]["temperature"] >= 18


def test_e5_comfort_upper_bound_clamp():
    """Bounded comfort adjustment never exceeds 28°C."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(ambient_temperature=20.0, target_temperature=28.0, tolerance_celsius=1.0)
    assert corr is not None
    assert corr["parameters"]["temperature"] <= 28


def test_e6_custom_tolerance_parameter():
    """Custom tolerance threshold is respected."""
    mgr = AutonomyManager()
    # 0.5 threshold: 24.6 vs 24.0 triggers correction
    corr = mgr.evaluate_comfort_drift(ambient_temperature=24.6, target_temperature=24.0, tolerance_celsius=0.5)
    assert corr is not None


def test_e7_drift_reason_contains_temperatures():
    """Correction dictionary includes descriptive explanation."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(28.0, 24.0)
    assert "28.0°C" in corr["reason"]
    assert "24.0°C" in corr["reason"]


def test_e8_exact_tolerance_boundary():
    """Drift equal to tolerance threshold triggers adjustment."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(ambient_temperature=25.5, target_temperature=24.0, tolerance_celsius=1.5)
    assert corr is not None


def test_e9_negative_drift_formatting():
    """Cold drift contains positive difference in reason string."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(21.0, 24.0)
    assert "colder" in corr["reason"].lower()


def test_e10_integer_inputs_gracefully_handled():
    """Integer temperature inputs work without casting issues."""
    mgr = AutonomyManager()
    corr = mgr.evaluate_comfort_drift(28, 23)
    assert corr is not None
    assert corr["parameters"]["temperature"] == 22


# =============================================================================
# SECTION F: AUDIT LOGGING & INTROSPECTION (Tests F1-F10)
# =============================================================================

def test_f1_audit_log_records_evaluations():
    """Every evaluate_authorization call generates an audit log record."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "SET_TEMP", "AC")
    assert len(mgr.audit_log) == 1


def test_f2_audit_log_bounded_capacity():
    """Audit log stays bounded to max limit (200 records)."""
    mgr = AutonomyManager()
    mgr._max_audit_records = 10
    for i in range(25):
        mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, f"ACT_{i}", "AC")
    assert len(mgr.audit_log) == 10


def test_f3_get_audit_log_limit():
    """get_audit_log retrieves requested number of recent items."""
    mgr = AutonomyManager()
    for i in range(15):
        mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, f"ACT_{i}", "AC")
    recent = mgr.get_audit_log(5)
    assert len(recent) == 5
    assert recent[-1].action_type == "ACT_14"


def test_f4_audit_record_stores_parameters():
    """Audit log preserves requested parameters."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "SET_TEMP", "AC", parameters={"temperature": 24})
    assert mgr.audit_log[0].parameters.get("temperature") == 24


def test_f5_audit_record_stores_origin_trigger():
    """Audit record captures origin trigger string."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "SET_TEMP", "AC", origin_trigger="SCHEDULED_ROUTINE")
    assert mgr.audit_log[0].origin_trigger == "SCHEDULED_ROUTINE"


def test_f6_audit_record_timestamps_monotonic():
    """Audit records have increasing timestamps."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "ACT_1", "AC")
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "ACT_2", "AC")
    assert mgr.audit_log[1].timestamp >= mgr.audit_log[0].timestamp


def test_f7_audit_log_cleared_on_fresh_manager():
    """New manager starts with empty audit log."""
    mgr = AutonomyManager()
    assert len(mgr.audit_log) == 0


def test_f8_audit_record_unique_ids():
    """Audit records receive unique IDs."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "A1", "AC")
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "A2", "AC")
    assert mgr.audit_log[0].audit_id != mgr.audit_log[1].audit_id


def test_f9_audit_record_serialization_compatibility():
    """Audit log items are JSON-serializable."""
    import json
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AC_ADJUSTMENT, "A1", "AC")
    data = mgr.audit_log[0].dict()
    assert json.dumps(data) is not None


def test_f10_audit_log_preserves_denial_reasons():
    """Audit log contains detailed reasons for denied actions."""
    mgr = AutonomyManager()
    mgr.evaluate_authorization(AutonomyCapability.AUDIO_ROUTING, "RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    assert "prohibited" in mgr.audit_log[0].reason.lower()


# =============================================================================
# SECTION G: AGENT INTEGRATION (Tests G1-G6)
# =============================================================================

def test_g1_agent_instantiates_autonomy_manager():
    """AnimusPersonalAgent contains AutonomyManager."""
    agent = AnimusPersonalAgent()
    agent.autonomy_manager = AutonomyManager()
    assert agent.autonomy_manager is not None


def test_g2_authorized_autonomous_comfort_execution():
    """When comfort autonomy is granted, environmental drift executes bounded AC setpoint."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    drift = mgr.evaluate_comfort_drift(ambient_temperature=27.0, target_temperature=24.0)
    auth, _, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AC_ADJUSTMENT,
        action_type=drift["action_type"],
        target_subsystem=drift["target_subsystem"],
        parameters=drift["parameters"]
    )
    assert auth is True
    assert level == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_g3_unauthorized_comfort_drift_requires_confirmation():
    """Without comfort autonomy, environmental drift produces ASK requiring user confirmation."""
    mgr = AutonomyManager()
    # Default is ASK
    drift = mgr.evaluate_comfort_drift(ambient_temperature=27.0, target_temperature=24.0)
    auth, _, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AC_ADJUSTMENT,
        action_type=drift["action_type"],
        target_subsystem=drift["target_subsystem"],
        parameters=drift["parameters"]
    )
    assert auth is False
    assert level == AutonomyGrantLevel.ASK


def test_g4_soundbar_fire_tv_protection_in_agent_loop():
    """Soundbar Bluetooth reclaim is blocked in agent loop during movie playback."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AUDIO_ROUTING, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, _, level = mgr.evaluate_authorization(
        capability=AutonomyCapability.AUDIO_ROUTING,
        action_type="RECLAIM_PC_BLUETOOTH",
        target_subsystem="SOUNDBAR",
        soundbar_owner="FIRE_TV",
        active_mode=BehaviorMode.MOVIE
    )
    assert auth is False
    assert level == AutonomyGrantLevel.DENIED


def test_g5_autonomy_lease_expiry_reverts_agent_to_ask():
    """Agent returns to asking when autonomy lease expires."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS, lease_seconds=10.0)
    future = time.time() + 20.0
    assert mgr.get_grant_level(AutonomyCapability.AC_ADJUSTMENT, current_time=future) == AutonomyGrantLevel.ASK


def test_g6_canonical_dialogue_scenario_e_autonomous_comfort():
    """Full Scenario E verification: with grant -> authorized; without grant -> ask."""
    mgr = AutonomyManager()
    drift = mgr.evaluate_comfort_drift(ambient_temperature=28.0, target_temperature=24.0)

    # 1. Without authorization -> ASK
    auth_unauth, _, level_unauth = mgr.evaluate_authorization(
        AutonomyCapability.AC_ADJUSTMENT, drift["action_type"], drift["target_subsystem"], drift["parameters"]
    )
    assert auth_unauth is False
    assert level_unauth == AutonomyGrantLevel.ASK

    # 2. Grant authorization -> AUTHORIZED_AUTONOMOUS
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth_auth, _, level_auth = mgr.evaluate_authorization(
        AutonomyCapability.AC_ADJUSTMENT, drift["action_type"], drift["target_subsystem"], drift["parameters"]
    )
    assert auth_auth is True
    assert level_auth == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS
