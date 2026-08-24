"""
ANIMUS SMART HOME — PHASE E.8.1 REAL-ROOM PHYSICAL VALIDATION PYTEST SUITE
Guarded by ANIMUS_PHYSICAL_E2E=1 environment variable.
Without explicit opt-in, all tests in this suite skip safely to prevent accidental hardware mutation.
When enabled, executes true end-to-end cognitive chain against physical devices:
Natural Language -> PlanValidator -> PlanExecutor -> Hardware -> Physical Readback.
"""

from __future__ import annotations

import os
import time
import pytest
from typing import Dict, Any

from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState
from room_state.aggregator import RoomStateAggregator
from planner import (
    ErrorCode,
    FailurePolicy,
    PlanStep,
    GeminiStructuredPlan,
    PlanValidator,
    ExecutionStatus,
    OverallExecutionStatus,
    PlanExecutor
)
from projector_controller import ProjectorController, ProjectorPowerState, ProjectorSource
from ac_controller import AcController
from pc_controller import PcController
from fire_tv_controller import FireTvController
from fire_tv_capabilities import FireTVCapabilityRegistry

# Strict Environment Separation Guard
PHYSICAL_E2E_OPT_IN = os.environ.get("ANIMUS_PHYSICAL_E2E") == "1"
pytestmark = pytest.mark.skipif(
    not PHYSICAL_E2E_OPT_IN,
    reason="Physical Hardware tests require explicit ANIMUS_PHYSICAL_E2E=1 opt-in."
)


@pytest.fixture(scope="module")
def physical_system():
    """Initializes authoritative physical hardware stack."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    proj = ProjectorController(target="192.168.1.11:5555")
    ac = AcController()
    pc = PcController()
    ftv_ctrl = FireTvController(target="192.168.1.5:5555")
    ftv_reg = FireTVCapabilityRegistry(fire_tv=ftv_ctrl)

    agg = RoomStateAggregator(
        projector_controller=proj,
        ac_controller=ac,
        fire_tv_controller=ftv_reg,
        pc_controller=pc
    )

    executor = PlanExecutor(
        registry=registry,
        validator=validator,
        room_state_aggregator=agg,
        projector_controller=proj,
        ac_controller=ac,
        pc_controller=pc,
        fire_tv_controller=ftv_reg
    )

    # Capture baseline
    rs_init = agg.get_room_state()
    baseline = {
        "ac_temp": rs_init.ac.target_temperature.value or 24,
        "ac_mode": rs_init.ac.mode.value or "COOL",
        "ac_fan": rs_init.ac.fan_speed.value or "LOW",
        "ac_power": rs_init.ac.power.value or True,
        "pc_volume": rs_init.pc.master_volume.value or 50,
        "pc_muted": rs_init.pc.is_muted.value or False,
        "proj_source": rs_init.projector.input_source.value or "ANDROID_HOME",
        "proj_bri": rs_init.projector.brightness.value or 40
    }

    yield {
        "registry": registry,
        "validator": validator,
        "aggregator": agg,
        "executor": executor,
        "controllers": {
            "projector": proj,
            "ac": ac,
            "pc": pc,
            "fire_tv": ftv_ctrl,
            "fire_tv_reg": ftv_reg
        },
        "baseline": baseline
    }

    # Safe Restoration Teardown
    try:
        if baseline["ac_temp"]:
            ac.set_temperature(int(baseline["ac_temp"]))
        if baseline["ac_mode"]:
            ac.set_mode(baseline["ac_mode"])
        if baseline["ac_fan"]:
            ac.set_fan_speed(baseline["ac_fan"])
        if baseline["pc_volume"] is not None:
            pc.set_volume(int(baseline["pc_volume"]))
        if baseline["pc_muted"] is not None:
            pc.set_mute(bool(baseline["pc_muted"]))
        ftv_ctrl.home()
        if baseline["proj_source"] == "ANDROID_HOME":
            proj.home()
    except Exception:
        pass


# =============================================================================
# Level 1: Read-Only Physical Discovery
# =============================================================================

def test_p81_l1_ac_discovery(physical_system):
    ac_st = physical_system["controllers"]["ac"].get_status()
    assert ac_st.get("verified") is True
    assert ac_st.get("power") is True
    assert 16 <= int(ac_st.get("target_temperature", 24)) <= 30


def test_p81_l1_pc_discovery(physical_system):
    pc_st = physical_system["controllers"]["pc"].get_power_state()
    assert pc_st.get("verified") is True
    assert pc_st.get("power_state") == "AWAKE_AND_RUNNING"
    vol = physical_system["controllers"]["pc"].get_volume()
    assert 0 <= vol <= 100


def test_p81_l1_projector_discovery(physical_system):
    p_conn, _ = physical_system["controllers"]["projector"].is_connected(auto_connect=True)
    assert p_conn is True
    p_pwr = physical_system["controllers"]["projector"].get_power_state()
    assert p_pwr.get("verified") is True
    assert p_pwr.get("connected") is True


def test_p81_l1_fire_tv_discovery(physical_system):
    ftv_conn, _ = physical_system["controllers"]["fire_tv"].is_connected(auto_connect=True)
    assert ftv_conn is True
    ftv_st = physical_system["controllers"]["fire_tv_reg"].get_state()
    assert ftv_st.reachable is True


def test_p81_l1_room_state_consistency(physical_system):
    rs = physical_system["aggregator"].get_room_state()
    assert rs.is_consistent is True
    assert rs.ac.power.provenance.value == "OBSERVED"
    assert rs.pc.online.provenance.value == "OBSERVED"


# =============================================================================
# Level 2: Safe Individual Actions
# =============================================================================

def test_p81_l2_ac_temperature_mutation(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    curr_temp = rs_pre.ac.target_temperature.value or 24
    target_temp = 25 if curr_temp == 24 else 24

    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary=f"Set AC to {target_temp}°C",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": target_temp})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True

    rs_post = sys["aggregator"].get_room_state()
    assert rs_post.ac.target_temperature.value == target_temp


def test_p81_l2_pc_volume_mutation(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    curr_vol = rs_pre.pc.master_volume.value or 50
    target_vol = 45 if curr_vol != 45 else 55

    plan = GeminiStructuredPlan(
        intent="AUDIO_VOLUME",
        objective_summary=f"Set PC volume to {target_vol}%",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": target_vol})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True

    rs_post = sys["aggregator"].get_room_state()
    assert rs_post.pc.master_volume.value == target_vol


def test_p81_l2_projector_wake_and_hdmi1(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="DISPLAY_CONTROL",
        objective_summary="Wake projector and switch to HDMI 1",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE"),
            PlanStep(step_id=2, device="projector", capability="PROJECTOR_SWITCH_HDMI1")
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True


def test_p81_l2_fire_tv_wake_and_home(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="NAVIGATION",
        objective_summary="Wake Fire TV and go Home",
        steps=[
            PlanStep(step_id=1, device="fire_tv", capability="FIRE_TV_POWER_WAKE"),
            PlanStep(step_id=2, device="fire_tv", capability="FIRE_TV_NAV_HOME")
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True


# =============================================================================
# Level 3: Multi-Step Real Room Scenarios
# =============================================================================

def test_p81_l3_scenario_comfort_room(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Make room comfortable: AC ON, 23°C, COOL",
        steps=[
            PlanStep(step_id=1, device="ac", capability="AC_POWER_ON"),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 23}),
            PlanStep(step_id=3, device="ac", capability="AC_SET_MODE", parameters={"mode": "COOL"})
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.failed_steps_count == 0

    rs_post = sys["aggregator"].get_room_state()
    assert rs_post.ac.target_temperature.value == 23


def test_p81_l3_scenario_watch_youtube(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="ENTERTAINMENT",
        objective_summary="Put on YouTube: wake Fire TV, launch YouTube",
        steps=[
            PlanStep(step_id=1, device="fire_tv", capability="FIRE_TV_POWER_WAKE"),
            PlanStep(step_id=2, device="fire_tv", capability="FIRE_TV_APP_LAUNCH_YOUTUBE")
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True


def test_p81_l3_scenario_restore_room(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="ROOM_RESTORE",
        objective_summary="Done watching: Fire TV home, Projector home, AC 24°C",
        steps=[
            PlanStep(step_id=1, device="fire_tv", capability="FIRE_TV_NAV_HOME"),
            PlanStep(step_id=2, device="projector", capability="PROJECTOR_SWITCH_ANDROID_HOME"),
            PlanStep(step_id=3, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 24})
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True


# =============================================================================
# Level 4: Idempotency & State-Drift Protection
# =============================================================================

def test_p81_l4_physical_idempotency(physical_system):
    sys = physical_system
    rs_pre = sys["aggregator"].get_room_state()
    curr_temp = rs_pre.ac.target_temperature.value or 24

    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary=f"Set AC to {curr_temp}°C (Already satisfied)",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": curr_temp})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_pre)
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.skipped_steps_count == 1
    assert exec_res.verified_steps_count == 0


def test_p81_l4_state_drift_protection(physical_system):
    sys = physical_system
    rs_stale = sys["aggregator"].get_room_state()

    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Set AC to 25°C",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 25})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs_stale)

    # Modify hardware externally
    sys["controllers"]["ac"].set_temperature(25)
    time.sleep(1.0)

    # Execute validated plan
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.skipped_steps_count == 1


# =============================================================================
# Level 5: Safe Failure Handling & Invariants
# =============================================================================

def test_p81_l5_reject_oob_temperature(physical_system):
    sys = physical_system
    rs = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Set AC to 40°C",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 40})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs)
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.OUT_OF_RANGE for e in val_res.errors)


def test_p81_l5_reject_unsupported_hdmi3(physical_system):
    sys = physical_system
    rs = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="DISPLAY_INPUT",
        objective_summary="Switch Projector to HDMI 3",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_SWITCH_HDMI3")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs)
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.UNSUPPORTED_CAPABILITY for e in val_res.errors)


def test_p81_l5_reject_ac_heat_mode(physical_system):
    sys = physical_system
    rs = sys["aggregator"].get_room_state()
    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Turn on heat mode",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_MODE", parameters={"mode": "HEAT"})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=rs)
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.INVALID_ENUM for e in val_res.errors)
