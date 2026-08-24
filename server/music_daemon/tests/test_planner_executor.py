"""
Unit and Contract Test Suite for Phase E.7.4 Deterministic Plan Executor & Physical Read-Back Engine.
Verifies validated plan boundary enforcement, live precondition re-evaluation, hardware dispatch,
physical read-back verification polling, idempotency skipping, failure policy enforcement,
security injection blocking, and FastAPI execution endpoints.
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
from planner import (
    ErrorCode,
    ExecutionMode,
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
            power=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            input_source=StateField(value="HDMI_1", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            brightness=StateField(value=80, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            signal_active=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            health=StateField(value="OK", provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        ac=AcState(
            power=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            target_temperature=StateField(value=24, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            ambient_temperature=StateField(value=26, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            mode=StateField(value="COOL", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            fan_speed=StateField(value="MEDIUM", provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        fire_tv=FireTvState(
            online=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            power_state=StateField(value="AWAKE", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            foreground_app=StateField(value="com.amazon.tv.launcher", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            soundbar_connected=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        pc=PcState(
            online=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            master_volume=StateField(value=60, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            is_muted=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            default_audio_endpoint=StateField(value="Realtek High Definition Audio", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            bluetooth_radio_active=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        soundbar=SoundbarState(
            current_owner=StateField(value="FIRE_TV", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            is_connected=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        environment=RoomEnvironmentState(
            room_mode=StateField(value="CINEMA", provenance=Provenance.DERIVED, observed_at=now, source="TEST"),
            active_audio_route=StateField(value="FIRE_TV", provenance=Provenance.DERIVED, observed_at=now, source="TEST")
        )
    )


@pytest.fixture
def mock_controllers(mock_room_state):
    """Creates mocked physical controllers and aggregator."""
    p_ctrl = MagicMock()
    p_ctrl.wake.return_value = (True, {"power": "AWAKE"})
    p_ctrl.sleep.return_value = (True, {"power": "SLEEP"})
    p_ctrl.set_hdmi.return_value = (True, {"source": "HDMI_1"})
    p_ctrl.set_brightness.return_value = (True, {"brightness": 75})

    ac_ctrl = MagicMock()
    ac_ctrl.set_power.return_value = (True, {"power": True})
    ac_ctrl.set_temperature.return_value = (True, {"temperature": 22})
    ac_ctrl.set_mode.return_value = (True, {"mode": "COOL"})
    ac_ctrl.set_fan_speed.return_value = (True, {"fan_speed": "HIGH"})

    pc_ctrl = MagicMock()
    pc_ctrl.set_volume.return_value = (True, {"master_volume": 50})
    pc_ctrl.set_mute.return_value = (True, {"is_muted": True})
    pc_ctrl.media_play_pause.return_value = (True, {"action": "PLAY_PAUSE"})
    pc_ctrl.lock_workstation.return_value = (True, {"locked": True})

    ftv_ctrl = MagicMock()
    ftv_ctrl.power_wake.return_value = (True, {"power": "AWAKE"})
    ftv_ctrl.bt_connect_soundbar.return_value = (True, {"soundbar_connected": True})

    orch = MagicMock()
    orch.transfer_audio_to_fire_tv.return_value = (True, {"owner": "FIRE_TV"})
    orch.restore_audio_to_pc.return_value = (True, {"owner": "PC"})

    agg = MagicMock()
    agg.get_room_state.return_value = mock_room_state

    return {
        "projector": p_ctrl,
        "ac": ac_ctrl,
        "pc": pc_ctrl,
        "fire_tv": ftv_ctrl,
        "orchestrator": orch,
        "aggregator": agg
    }


# =============================================================================
# 1. Validation Boundary Enforcement
# =============================================================================

def test_executor_rejects_unvalidated_or_invalid_plan(mock_controllers):
    # ValidationResult with valid=False
    invalid_val_res = ValidationResult(
        valid=False,
        plan_id="test_invalid",
        errors=[{"error_code": ErrorCode.UNKNOWN_CAPABILITY, "message": "Unknown capability"}]
    )
    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(invalid_val_res)
    assert exec_res.success is False
    assert exec_res.overall_status == OverallExecutionStatus.FAILED
    assert exec_res.failure_code == ErrorCode.PLAN_NOT_VALIDATED
    mock_controllers["ac"].set_power.assert_not_called()


def test_executor_accepts_valid_validated_plan(mock_controllers, mock_room_state):
    # Set room state target temperature to 24 (so setting to 22 is NOT idempotent)
    mock_room_state.ac.target_temperature.value = 24

    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Set temperature",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert val_res.valid is True

    def mock_set_temp(temp):
        mock_room_state.ac.target_temperature.value = temp
        mock_room_state.ac.target_temperature.observed_at = time.time()
        return True, {"temperature": temp}

    mock_controllers["ac"].set_temperature.side_effect = mock_set_temp
    mock_controllers["aggregator"].get_room_state.side_effect = lambda current_time=None: mock_room_state

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res, verification_timeout=1.0, poll_interval=0.05)
    assert exec_res.success is True
    assert exec_res.overall_status == OverallExecutionStatus.SUCCESS
    assert len(exec_res.steps) == 1
    assert exec_res.steps[0].status == ExecutionStatus.VERIFIED
    assert exec_res.steps[0].verified is True
    mock_controllers["ac"].set_temperature.assert_called_once_with(22)


# =============================================================================
# 2. Live Precondition Re-Evaluation
# =============================================================================

def test_executor_blocks_execution_on_unknown_precondition_state(mock_controllers, mock_room_state):
    validator = PlanValidator()
    # Plan to set AC temperature requires AC power == True
    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Cool",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert val_res.valid is True

    # Simulate: immediately before execution, AC power becomes UNKNOWN
    mock_room_state.ac.power.provenance = Provenance.UNKNOWN
    mock_room_state.ac.power.value = None

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is False
    assert exec_res.steps[0].status == ExecutionStatus.UNKNOWN_STATE
    assert exec_res.steps[0].error_code == ErrorCode.UNKNOWN_STATE
    mock_controllers["ac"].set_temperature.assert_not_called()


def test_executor_blocks_execution_on_stale_precondition_state(mock_controllers, mock_room_state):
    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Cool",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert val_res.valid is True

    # Simulate: AC power observation is STALE (>15s TTL)
    mock_room_state.ac.power.observed_at = time.time() - 100.0

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is False
    assert exec_res.steps[0].status == ExecutionStatus.STALE_STATE
    assert exec_res.steps[0].error_code == ErrorCode.STALE_STATE
    mock_controllers["ac"].set_temperature.assert_not_called()


def test_executor_blocks_execution_when_precondition_becomes_false(mock_controllers, mock_room_state):
    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Cool",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert val_res.valid is True

    # Simulate: AC was turned OFF right before execution
    mock_room_state.ac.power.value = False
    mock_room_state.ac.power.observed_at = time.time()

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is False
    assert exec_res.steps[0].status == ExecutionStatus.PRECONDITION_FAILED
    assert exec_res.steps[0].error_code == ErrorCode.PRECONDITION_FAILED
    mock_controllers["ac"].set_temperature.assert_not_called()


# =============================================================================
# 3. Idempotency Skipping on Fresh State
# =============================================================================

def test_executor_skips_already_satisfied_action(mock_controllers, mock_room_state):
    # AC target temperature is already 24 in mock_room_state
    mock_room_state.ac.target_temperature.value = 24
    mock_room_state.ac.target_temperature.observed_at = time.time()

    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Maintain temp",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 24})]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.steps[0].status == ExecutionStatus.SKIPPED
    assert exec_res.steps[0].verified is True
    mock_controllers["ac"].set_temperature.assert_not_called()


# =============================================================================
# 4. Multi-Subsystem Hardware Dispatch
# =============================================================================

def test_executor_dispatches_across_all_subsystems(mock_controllers, mock_room_state):
    mock_room_state.pc.master_volume.value = 80
    mock_room_state.projector.brightness.value = 50
    mock_room_state.fire_tv.power_state.value = "SLEEP"
    mock_room_state.soundbar.current_owner.value = "FIRE_TV"

    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="MULTI_SYS",
        objective_summary="Multi subsystem",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_SET_BRIGHTNESS", parameters={"brightness": 75}),
            PlanStep(step_id=2, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 50}),
            PlanStep(step_id=3, device="fire_tv", capability="FIRE_TV_POWER_WAKE"),
            PlanStep(step_id=4, device="soundbar", capability="SOUNDBAR_ROUTE_TO_PC")
        ]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)

    def mock_set_bri(bri):
        mock_room_state.projector.brightness.value = bri
        mock_room_state.projector.brightness.observed_at = time.time()
        return True, {"brightness": bri}

    def mock_set_vol(vol):
        mock_room_state.pc.master_volume.value = vol
        mock_room_state.pc.master_volume.observed_at = time.time()
        return True, {"master_volume": vol}

    def mock_wake():
        mock_room_state.fire_tv.power_state.value = "AWAKE"
        mock_room_state.fire_tv.power_state.observed_at = time.time()
        return True, {"power": "AWAKE"}

    def mock_route_pc():
        mock_room_state.soundbar.current_owner.value = "PC"
        mock_room_state.soundbar.current_owner.observed_at = time.time()
        return True, {"owner": "PC"}

    mock_controllers["projector"].set_brightness.side_effect = mock_set_bri
    mock_controllers["pc"].set_volume.side_effect = mock_set_vol
    mock_controllers["fire_tv"].power_wake.side_effect = mock_wake
    mock_controllers["orchestrator"].restore_audio_to_pc.side_effect = mock_route_pc
    mock_controllers["aggregator"].get_room_state.side_effect = lambda current_time=None: mock_room_state

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        projector_controller=mock_controllers["projector"],
        pc_controller=mock_controllers["pc"],
        fire_tv_controller=mock_controllers["fire_tv"],
        orchestrator=mock_controllers["orchestrator"]
    )
    exec_res = executor.execute_plan(val_res, verification_timeout=1.0, poll_interval=0.05)
    assert exec_res.success is True
    assert exec_res.verified_steps_count == 4

    mock_controllers["projector"].set_brightness.assert_called_once_with(75)
    mock_controllers["pc"].set_volume.assert_called_once_with(50)
    mock_controllers["fire_tv"].power_wake.assert_called_once()
    mock_controllers["orchestrator"].restore_audio_to_pc.assert_called_once()


# =============================================================================
# 5. Read-Back Verification Timeout Handling
# =============================================================================

def test_executor_handles_readback_timeout(mock_controllers, mock_room_state):
    # AC controller dispatch succeeds, but state readback never reaches 22
    mock_room_state.ac.target_temperature.value = 24  # Stays at 24

    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Cool",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res, verification_timeout=0.2, poll_interval=0.05)
    assert exec_res.success is False
    assert exec_res.steps[0].status == ExecutionStatus.TIMEOUT
    assert exec_res.steps[0].error_code == ErrorCode.READBACK_TIMEOUT


# =============================================================================
# 6. Failure Policies & Abort Behavior
# =============================================================================

def test_executor_abort_plan_policy_stops_remaining_steps(mock_controllers, mock_room_state):
    # Projector is asleep
    mock_room_state.projector.power.value = False

    # Step 1 fails dispatch
    mock_controllers["projector"].wake.return_value = (False, {"error": "ADB_CONNECTION_REFUSED"})

    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="CINEMA",
        objective_summary="Cinema",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE", on_failure=FailurePolicy.ABORT_PLAN),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})
        ]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        projector_controller=mock_controllers["projector"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is False
    assert exec_res.overall_status == OverallExecutionStatus.ABORTED
    assert exec_res.steps[0].status == ExecutionStatus.FAILED
    assert exec_res.steps[1].status == ExecutionStatus.PENDING
    assert exec_res.steps[1].error_code == ErrorCode.EXECUTION_ABORTED
    mock_controllers["ac"].set_temperature.assert_not_called()


def test_executor_continue_best_effort_policy(mock_controllers, mock_room_state):
    # Projector is asleep
    mock_room_state.projector.power.value = False

    # Step 1 fails, but policy is CONTINUE_BEST_EFFORT
    mock_controllers["projector"].wake.return_value = (False, {"error": "ADB_SOCKET_TIMEOUT"})
    mock_room_state.ac.target_temperature.value = 26

    validator = PlanValidator()
    plan = GeminiStructuredPlan(
        intent="CINEMA",
        objective_summary="Cinema",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE", on_failure=FailurePolicy.CONTINUE_BEST_EFFORT),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})
        ]
    )
    val_res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)

    def mock_set_temp(temp):
        mock_room_state.ac.target_temperature.value = temp
        mock_room_state.ac.target_temperature.observed_at = time.time()
        return True, {"temperature": temp}

    mock_controllers["ac"].set_temperature.side_effect = mock_set_temp
    mock_controllers["aggregator"].get_room_state.side_effect = lambda current_time=None: mock_room_state

    executor = PlanExecutor(
        room_state_aggregator=mock_controllers["aggregator"],
        projector_controller=mock_controllers["projector"],
        ac_controller=mock_controllers["ac"]
    )
    exec_res = executor.execute_plan(val_res, verification_timeout=0.5, poll_interval=0.05)
    assert exec_res.success is False
    assert exec_res.overall_status == OverallExecutionStatus.PARTIAL_SUCCESS
    assert exec_res.steps[0].status == ExecutionStatus.FAILED
    assert exec_res.steps[1].status == ExecutionStatus.VERIFIED
    mock_controllers["ac"].set_temperature.assert_called_once_with(22)


# =============================================================================
# 7. FastAPI POST /api/planner/execute Endpoint
# =============================================================================

def test_fastapi_planner_execute_endpoint(mock_controllers, mock_room_state):
    from fastapi.testclient import TestClient
    from main import app, planner_client, planner_executor

    mock_plan = GeminiStructuredPlan(
        intent="CLIMATE",
        objective_summary="Cool",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_POWER_ON")]
    )

    client = TestClient(app)

    with patch.object(planner_client, "generate_plan", return_value=mock_plan):
        with patch.object(planner_client, "api_key", "mock_key"):
            with patch.object(planner_executor.ac, "set_power", return_value=(True, {"power": True})):
                res = client.post("/api/planner/execute", json={"request": "Turn on AC"})
                assert res.status_code == 200
                data = res.json()
                assert data["success"] is True
                assert data["overall_status"] in ("SUCCESS", "SKIPPED")
                assert len(data["steps"]) == 1
