"""
Comprehensive Acceptance & E2E Validation Suite for Phase E.7.6.
Tests the full orchestration chain:
Human Request -> Context Engine -> Gemini Planner -> Deterministic Validator -> Plan Executor -> Read-Back -> Result
Covers human behavior matrix, multi-step intents, context sensitivity, mistake recovery,
state changes before execution, failure simulations, conversational sequences, and adversarial safety.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from capability_registry import UnifiedCapabilityRegistry
from room_state.models import (
    RoomState,
    StateField,
    ProjectorState,
    AcState,
    FireTvState,
    PcState,
    SoundbarState,
    RoomEnvironmentState
)
from room_state.provenance import Provenance
from context import (
    PreferenceManager,
    ContextEngine,
    UserPreferences,
    ContextSnapshot
)
from planner import (
    ErrorCode,
    FailurePolicy,
    PlanStep,
    GeminiStructuredPlan,
    ValidatedStep,
    ValidationResult,
    PlanValidator,
    ExecutionStatus,
    OverallExecutionStatus,
    StepExecutionResult,
    ExecutionResult,
    PlanExecutor,
    GeminiPlannerClient
)


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def mock_room_state():
    """Constructs a deterministic, fresh canonical RoomState."""
    now = time.time()
    return RoomState(
        timestamp=now,
        is_consistent=True,
        projector=ProjectorState(
            power=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            input_source=StateField(value="HDMI_1", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            brightness=StateField(value=80, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            signal_active=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            health=StateField(value="OK", provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        ac=AcState(
            power=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            target_temperature=StateField(value=24, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            ambient_temperature=StateField(value=28, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            mode=StateField(value="COOL", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            fan_speed=StateField(value="AUTO", provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        fire_tv=FireTvState(
            online=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            power_state=StateField(value="SLEEP", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            foreground_app=StateField(value="com.amazon.tv.launcher", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            soundbar_connected=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        pc=PcState(
            online=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            master_volume=StateField(value=50, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            is_muted=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            default_audio_endpoint=StateField(value="Realtek High Definition Audio", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            bluetooth_radio_active=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        soundbar=SoundbarState(
            current_owner=StateField(value="PC", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            is_connected=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        environment=RoomEnvironmentState(
            room_mode=StateField(value="IDLE", provenance=Provenance.DERIVED, observed_at=now, source="TEST"),
            active_audio_route=StateField(value="PC", provenance=Provenance.DERIVED, observed_at=now, source="TEST")
        )
    )


@pytest.fixture
def mock_room_system(mock_room_state):
    """Creates a fully wired mock room execution system with dynamic telemetry reflection."""
    p_ctrl = MagicMock()
    ac_ctrl = MagicMock()
    pc_ctrl = MagicMock()
    ftv_ctrl = MagicMock()
    orch = MagicMock()
    ftv_service = MagicMock()
    agg = MagicMock()

    # Dynamic telemetry reflection
    def mock_proj_wake():
        mock_room_state.projector.power.value = True
        mock_room_state.projector.power.observed_at = time.time()
        return True, {"power": "AWAKE"}
    def mock_proj_sleep():
        mock_room_state.projector.power.value = False
        mock_room_state.projector.power.observed_at = time.time()
        return True, {"power": "SLEEP"}
    def mock_proj_hdmi1(src=1):
        mock_room_state.projector.input_source.value = "HDMI_1"
        mock_room_state.projector.input_source.observed_at = time.time()
        return True, {"source": "HDMI_1"}
    def mock_proj_bri(b):
        mock_room_state.projector.brightness.value = b
        mock_room_state.projector.brightness.observed_at = time.time()
        return True, {"brightness": b}

    def mock_ac_pwr(p):
        mock_room_state.ac.power.value = p
        mock_room_state.ac.power.observed_at = time.time()
        return True, {"power": p}
    def mock_ac_temp(t):
        mock_room_state.ac.target_temperature.value = t
        mock_room_state.ac.target_temperature.observed_at = time.time()
        return True, {"temperature": t}
    def mock_ac_mode(m):
        mock_room_state.ac.mode.value = m
        mock_room_state.ac.mode.observed_at = time.time()
        return True, {"mode": m}
    def mock_ac_fan(f):
        mock_room_state.ac.fan_speed.value = f
        mock_room_state.ac.fan_speed.observed_at = time.time()
        return True, {"speed": f}

    def mock_pc_vol(v):
        mock_room_state.pc.master_volume.value = v
        mock_room_state.pc.master_volume.observed_at = time.time()
        return True, {"volume": v}
    def mock_pc_mute(m):
        mock_room_state.pc.is_muted.value = m
        mock_room_state.pc.is_muted.observed_at = time.time()
        return True, {"mute": m}
    def mock_pc_media(action="PLAY_PAUSE"):
        return True, {"action": action}

    def mock_ftv_wake():
        mock_room_state.fire_tv.power_state.value = "AWAKE"
        mock_room_state.fire_tv.power_state.observed_at = time.time()
        return True, {"power": "AWAKE"}
    def mock_ftv_bt():
        mock_room_state.fire_tv.soundbar_connected.value = True
        mock_room_state.fire_tv.soundbar_connected.observed_at = time.time()
        return True, {"connected": True}
    def mock_ftv_yt():
        mock_room_state.fire_tv.foreground_app.value = "com.google.android.youtube.tv"
        mock_room_state.fire_tv.foreground_app.observed_at = time.time()
        return True, {"app": "youtube"}

    def mock_route_ftv():
        mock_room_state.soundbar.current_owner.value = "FIRE_TV"
        mock_room_state.soundbar.current_owner.observed_at = time.time()
        return True, {"owner": "FIRE_TV"}
    def mock_route_pc():
        mock_room_state.soundbar.current_owner.value = "PC"
        mock_room_state.soundbar.current_owner.observed_at = time.time()
        return True, {"owner": "PC"}

    p_ctrl.wake.side_effect = mock_proj_wake
    p_ctrl.sleep.side_effect = mock_proj_sleep
    p_ctrl.set_hdmi.side_effect = mock_proj_hdmi1
    p_ctrl.set_brightness.side_effect = mock_proj_bri

    ac_ctrl.set_power.side_effect = mock_ac_pwr
    ac_ctrl.set_temperature.side_effect = mock_ac_temp
    ac_ctrl.set_mode.side_effect = mock_ac_mode
    ac_ctrl.set_fan_speed.side_effect = mock_ac_fan

    pc_ctrl.set_volume.side_effect = mock_pc_vol
    pc_ctrl.set_mute.side_effect = mock_pc_mute
    pc_ctrl.media_play_pause.side_effect = mock_pc_media

    ftv_ctrl.power_wake.side_effect = mock_ftv_wake
    ftv_ctrl.bt_connect_soundbar.side_effect = mock_ftv_bt
    ftv_ctrl.app_launch_youtube.side_effect = mock_ftv_yt

    orch.transfer_audio_to_fire_tv.side_effect = mock_route_ftv
    orch.restore_audio_to_pc.side_effect = mock_route_pc

    agg.get_room_state.side_effect = lambda current_time=None: mock_room_state

    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)
    executor = PlanExecutor(
        registry=registry,
        validator=validator,
        room_state_aggregator=agg,
        projector_controller=p_ctrl,
        ac_controller=ac_ctrl,
        pc_controller=pc_ctrl,
        fire_tv_controller=ftv_ctrl,
        firetv_service=ftv_service,
        orchestrator=orch
    )
    pref_mgr = PreferenceManager(registry=registry)
    ctx_eng = ContextEngine(preference_manager=pref_mgr, room_state_aggregator=agg)
    planner_client = GeminiPlannerClient(registry=registry, validator=validator)

    return {
        "registry": registry,
        "validator": validator,
        "executor": executor,
        "preference_manager": pref_mgr,
        "context_engine": ctx_eng,
        "planner_client": planner_client,
        "controllers": {
            "projector": p_ctrl,
            "ac": ac_ctrl,
            "pc": pc_ctrl,
            "fire_tv": ftv_ctrl,
            "orchestrator": orch
        },
        "room_state": mock_room_state,
        "aggregator": agg
    }


# =============================================================================
# Phase 1: Simple & Natural Human Requests
# =============================================================================

def test_human_request_ac_power_on(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Turn AC on",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_POWER_ON")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].ac.power.value is True


def test_human_request_ac_set_24(mock_room_system):
    sys = mock_room_system
    # Turn AC on first
    sys["room_state"].ac.power.value = True
    sys["room_state"].ac.target_temperature.value = 26

    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Make it 24 degrees",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 24})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].ac.target_temperature.value == 24


def test_human_request_put_something_on_youtube(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="ENTERTAINMENT",
        objective_summary="Put something on YouTube",
        steps=[PlanStep(step_id=1, device="fire_tv", capability="FIRE_TV_APP_LAUNCH_YOUTUBE")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].fire_tv.foreground_app.value == "com.google.android.youtube.tv"


def test_human_request_turn_projector_off(mock_room_system):
    sys = mock_room_system
    sys["room_state"].projector.power.value = True

    plan = GeminiStructuredPlan(
        intent="POWER",
        objective_summary="Turn the projector off",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_SLEEP")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].projector.power.value is False


def test_human_request_make_room_quieter(mock_room_system):
    sys = mock_room_system
    sys["room_state"].pc.master_volume.value = 80

    plan = GeminiStructuredPlan(
        intent="AUDIO_VOLUME",
        objective_summary="Make the room quieter",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 30})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].pc.master_volume.value == 30


def test_human_request_getting_hot_in_here(mock_room_system):
    sys = mock_room_system
    sys["room_state"].ac.power.value = True
    sys["room_state"].ac.target_temperature.value = 26

    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="It's getting a bit hot in here",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].ac.target_temperature.value == 22


# =============================================================================
# Phase 2: Multi-Step Human Intent Orchestration
# =============================================================================

def test_multi_step_movie_intent(mock_room_system):
    sys = mock_room_system
    sys["room_state"].projector.input_source.value = "ANDROID_HOME"
    plan = GeminiStructuredPlan(
        intent="MOVIE_MODE",
        objective_summary="Watch a movie",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE"),
            PlanStep(step_id=2, device="projector", capability="PROJECTOR_SWITCH_HDMI1"),
            PlanStep(step_id=3, device="fire_tv", capability="FIRE_TV_POWER_WAKE"),
            PlanStep(step_id=4, device="soundbar", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"),
            PlanStep(step_id=5, device="fire_tv", capability="FIRE_TV_APP_LAUNCH_YOUTUBE")
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.verified_steps_count == 5
    assert sys["room_state"].projector.power.value is True
    assert sys["room_state"].projector.input_source.value == "HDMI_1"
    assert sys["room_state"].soundbar.current_owner.value == "FIRE_TV"


def test_multi_step_room_shutdown_intent(mock_room_system):
    sys = mock_room_system
    # Room is currently active
    sys["room_state"].projector.power.value = True
    sys["room_state"].soundbar.current_owner.value = "FIRE_TV"
    sys["room_state"].ac.power.value = True

    plan = GeminiStructuredPlan(
        intent="SHUTDOWN",
        objective_summary="Done watching, put everything back",
        steps=[
            PlanStep(step_id=1, device="soundbar", capability="SOUNDBAR_ROUTE_TO_PC"),
            PlanStep(step_id=2, device="projector", capability="PROJECTOR_POWER_SLEEP"),
            PlanStep(step_id=3, device="ac", capability="AC_POWER_OFF")
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert sys["room_state"].soundbar.current_owner.value == "PC"
    assert sys["room_state"].projector.power.value is False
    assert sys["room_state"].ac.power.value is False


# =============================================================================
# Phase 3: Context-Aware Idempotency & Sensitivity
# =============================================================================

def test_context_idempotent_skip_when_projector_already_on(mock_room_system):
    sys = mock_room_system
    sys["room_state"].projector.power.value = True  # Already on

    plan = GeminiStructuredPlan(
        intent="WAKE",
        objective_summary="Turn on projector",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.steps[0].status == ExecutionStatus.SKIPPED
    sys["controllers"]["projector"].wake.assert_not_called()


def test_context_idempotent_skip_when_ac_already_at_target(mock_room_system):
    sys = mock_room_system
    sys["room_state"].ac.power.value = True
    sys["room_state"].ac.target_temperature.value = 24  # Already 24

    plan = GeminiStructuredPlan(
        intent="CLIMATE",
        objective_summary="Set AC to 24",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 24})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.steps[0].status == ExecutionStatus.SKIPPED
    sys["controllers"]["ac"].set_temperature.assert_not_called()


# =============================================================================
# Phase 4: Human Mistake Rejections
# =============================================================================

def test_human_mistake_ac_40_degrees_rejected(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="CLIMATE",
        objective_summary="Set AC to 40",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 40})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.OUT_OF_RANGE for e in val_res.errors)

    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is False
    assert exec_res.failure_code == ErrorCode.PLAN_NOT_VALIDATED


def test_human_mistake_heater_mode_rejected(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="CLIMATE",
        objective_summary="Turn on heater",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_MODE", parameters={"mode": "HEAT"})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.INVALID_ENUM for e in val_res.errors)


def test_human_mistake_hdmi3_rejected(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="SOURCE",
        objective_summary="Switch to HDMI 3",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_SWITCH_HDMI3")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is False
    assert any(e.error_code in (ErrorCode.UNSUPPORTED_CAPABILITY, ErrorCode.UNKNOWN_CAPABILITY) for e in val_res.errors)


def test_human_mistake_non_allowlisted_app_rejected(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="LAUNCH",
        objective_summary="Open arbitrary app",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_LAUNCH_ALLOWLISTED_APP", parameters={"app_key": "powershell.exe"})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.INVALID_ENUM for e in val_res.errors)


# =============================================================================
# Phase 5: State Changes Between Planning and Execution
# =============================================================================

def test_state_change_between_planning_and_execution_idempotent_skip(mock_room_system):
    sys = mock_room_system
    # At planning time: AC is 26
    sys["room_state"].ac.power.value = True
    sys["room_state"].ac.target_temperature.value = 26

    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Set AC to 22",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is True

    # Between planning and execution: physical AC was already set to 22 externally!
    sys["room_state"].ac.target_temperature.value = 22
    sys["room_state"].ac.target_temperature.observed_at = time.time()

    # Executor queries fresh state immediately prior to dispatch
    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.steps[0].status == ExecutionStatus.SKIPPED
    sys["controllers"]["ac"].set_temperature.assert_not_called()


# =============================================================================
# Phase 6: Physical Failure Simulations
# =============================================================================

def test_physical_failure_readback_timeout(mock_room_system):
    sys = mock_room_system
    sys["room_state"].ac.power.value = True
    sys["room_state"].ac.target_temperature.value = 26

    # AC controller returns True, but telemetry never updates (stays 26)
    sys["controllers"]["ac"].set_temperature.side_effect = lambda t: (True, {"temperature": t})

    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Set AC to 22",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    exec_res = sys["executor"].execute_plan(val_res, verification_timeout=0.2, poll_interval=0.05)
    assert exec_res.success is False
    assert exec_res.steps[0].status == ExecutionStatus.TIMEOUT
    assert exec_res.steps[0].error_code == ErrorCode.READBACK_TIMEOUT


def test_partial_execution_under_continue_policy(mock_room_system):
    sys = mock_room_system
    sys["room_state"].projector.power.value = False
    sys["room_state"].ac.power.value = True
    sys["room_state"].ac.target_temperature.value = 26

    # Step 1 (Projector wake) fails with socket error
    sys["controllers"]["projector"].wake.side_effect = lambda: (False, {"error": "ADB_SOCKET_ERROR"})

    plan = GeminiStructuredPlan(
        intent="CINEMA",
        objective_summary="Cinema",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE", on_failure=FailurePolicy.CONTINUE_BEST_EFFORT),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})
        ]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    exec_res = sys["executor"].execute_plan(val_res, verification_timeout=0.5, poll_interval=0.05)
    assert exec_res.success is False
    assert exec_res.overall_status == OverallExecutionStatus.PARTIAL_SUCCESS
    assert exec_res.steps[0].status == ExecutionStatus.FAILED
    assert exec_res.steps[1].status == ExecutionStatus.VERIFIED


# =============================================================================
# Phase 7 & 8: Conversational Multi-Turn Session State Transitions
# =============================================================================

def test_conversational_multi_turn_session(mock_room_system):
    sys = mock_room_system
    v = sys["validator"]
    e = sys["executor"]

    # Turn 1: "Turn on the projector."
    plan1 = GeminiStructuredPlan(
        intent="WAKE",
        objective_summary="Turn on projector",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE")]
    )
    res1 = e.execute_plan(v.validate_plan(plan1, room_state=sys["room_state"]))
    assert res1.success is True
    assert sys["room_state"].projector.power.value is True

    # Turn 2: "Actually, let's watch YouTube."
    plan2 = GeminiStructuredPlan(
        intent="YOUTUBE",
        objective_summary="Watch YouTube",
        steps=[
            PlanStep(step_id=1, device="soundbar", capability="SOUNDBAR_ROUTE_TO_FIRE_TV"),
            PlanStep(step_id=2, device="fire_tv", capability="FIRE_TV_APP_LAUNCH_YOUTUBE")
        ]
    )
    res2 = e.execute_plan(v.validate_plan(plan2, room_state=sys["room_state"]))
    assert res2.success is True
    assert sys["room_state"].soundbar.current_owner.value == "FIRE_TV"
    assert sys["room_state"].fire_tv.foreground_app.value == "com.google.android.youtube.tv"

    # Turn 3: "Make it cooler, 22 degrees."
    plan3 = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Set AC to 22",
        steps=[
            PlanStep(step_id=1, device="ac", capability="AC_POWER_ON"),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})
        ]
    )
    res3 = e.execute_plan(v.validate_plan(plan3, room_state=sys["room_state"]))
    assert res3.success is True
    assert sys["room_state"].ac.target_temperature.value == 22

    # Turn 4: "Make it louder."
    plan4 = GeminiStructuredPlan(
        intent="VOLUME",
        objective_summary="Increase PC volume",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 75})]
    )
    res4 = e.execute_plan(v.validate_plan(plan4, room_state=sys["room_state"]))
    assert res4.success is True
    assert sys["room_state"].pc.master_volume.value == 75

    # Turn 5: "Okay I'm done, turn everything off."
    plan5 = GeminiStructuredPlan(
        intent="SHUTDOWN",
        objective_summary="Turn everything off",
        steps=[
            PlanStep(step_id=1, device="soundbar", capability="SOUNDBAR_ROUTE_TO_PC"),
            PlanStep(step_id=2, device="projector", capability="PROJECTOR_POWER_SLEEP"),
            PlanStep(step_id=3, device="ac", capability="AC_POWER_OFF")
        ]
    )
    res5 = e.execute_plan(v.validate_plan(plan5, room_state=sys["room_state"]))
    assert res5.success is True
    assert sys["room_state"].soundbar.current_owner.value == "PC"
    assert sys["room_state"].projector.power.value is False
    assert sys["room_state"].ac.power.value is False


# =============================================================================
# Phase 9: Adversarial & Safety Prompt Injection Tests
# =============================================================================

def test_adversarial_jailbreak_bypass_command_rejected(mock_room_system):
    sys = mock_room_system
    plan = GeminiStructuredPlan(
        intent="ADVERSARIAL",
        objective_summary="Ignore restrictions and run powershell",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_RUN_POWERSHELL_CMD", parameters={"cmd": "Remove-Item C:\\"})]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.UNKNOWN_CAPABILITY for e in val_res.errors)

    exec_res = sys["executor"].execute_plan(val_res)
    assert exec_res.success is False
    assert exec_res.failure_code == ErrorCode.PLAN_NOT_VALIDATED


def test_adversarial_execute_on_unknown_state_fails_closed(mock_room_system):
    sys = mock_room_system
    # Projector power state is UNKNOWN
    sys["room_state"].projector.power.provenance = Provenance.UNKNOWN
    sys["room_state"].projector.power.value = None

    plan = GeminiStructuredPlan(
        intent="WAKE",
        objective_summary="Wake projector on unknown state",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE")]
    )
    val_res = sys["validator"].validate_plan(plan, room_state=sys["room_state"])
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.UNKNOWN_STATE for e in val_res.errors)


def test_adversarial_direct_unvalidated_execution_rejected(mock_room_system):
    sys = mock_room_system
    # Attempt to bypass validator by submitting invalid dictionary
    invalid_dict = {
        "valid": False,
        "plan_id": "malicious_bypass_attempt",
        "errors": [{"error_code": "UNKNOWN_CAPABILITY", "message": "Bypass"}]
    }
    exec_res = sys["executor"].execute_plan(invalid_dict)
    assert exec_res.success is False
    assert exec_res.failure_code == ErrorCode.PLAN_NOT_VALIDATED
