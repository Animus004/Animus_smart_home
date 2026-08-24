"""
Unit and Contract Test Suite for Phase E.7.3 Gemini Structured Planner & Plan Validator.
Verifies strongly typed plan models, deterministic capability validation, parameter bounds checking,
restricted AST precondition evaluation, UNKNOWN/STALE safety handling, idempotency filtering,
security injection blocking, and read-only FastAPI planning endpoints.
STRICTLY ZERO HARDWARE EXECUTION.
"""

import time
import pytest
from unittest.mock import patch

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
    WarningCode,
    ExecutionMode,
    FailurePolicy,
    FallbackStep,
    PlanStep,
    GeminiStructuredPlan,
    ValidatedStep,
    ValidationResult,
    PlanValidator,
    PreconditionStatus,
    RestrictedPreconditionEvaluator,
    GeminiPlannerClient,
    GeminiApiUnavailableError,
    GeminiResponseError,
    PLANNER_SYSTEM_INSTRUCTION
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


# =============================================================================
# 1. Plan Models Validation
# =============================================================================

def test_plan_model_instantiation():
    step = PlanStep(
        step_id=1,
        device="projector",
        capability="PROJECTOR_POWER_WAKE",
        parameters={},
        priority=1,
        execution_mode=ExecutionMode.PARALLEL,
        preconditions=["projector.health == 'OK'"],
        expected_state_transition="projector.power == true",
        on_failure=FailurePolicy.ABORT_PLAN
    )
    plan = GeminiStructuredPlan(
        intent="CINEMA_PLAYBACK",
        objective_summary="Prepare cinema mode",
        rationale="User wants to watch a movie",
        requires_user_confirmation=False,
        steps=[step]
    )
    assert plan.intent == "CINEMA_PLAYBACK"
    assert len(plan.steps) == 1
    assert plan.steps[0].capability == "PROJECTOR_POWER_WAKE"


def test_validator_rejects_duplicate_step_ids():
    step1 = PlanStep(step_id=1, device="ac", capability="AC_POWER_ON")
    step2 = PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 22})
    plan = GeminiStructuredPlan(
        intent="CLIMATE_CONTROL",
        objective_summary="Cool room",
        steps=[step1, step2]
    )
    validator = PlanValidator()
    res = validator.validate_plan(plan)
    assert res.valid is False
    err_codes = [e.error_code for e in res.errors]
    assert ErrorCode.DUPLICATE_STEP in err_codes


# =============================================================================
# 2. Capability Validation & Status Enforcement
# =============================================================================

def test_validator_accepts_valid_executable_capabilities():
    plan = GeminiStructuredPlan(
        intent="TEST_INTENT",
        objective_summary="Test execution",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE"),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 23}),
            PlanStep(step_id=3, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 50})
        ]
    )
    validator = PlanValidator()
    res = validator.validate_plan(plan)
    assert res.valid is True
    assert len(res.validated_steps) == 3
    assert len(res.errors) == 0


def test_validator_rejects_unknown_capability():
    plan = GeminiStructuredPlan(
        intent="MALICIOUS_INTENT",
        objective_summary="Unknown cap",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_TELEPORT_TO_MARS")]
    )
    validator = PlanValidator()
    res = validator.validate_plan(plan)
    assert res.valid is False
    assert any(e.error_code == ErrorCode.UNKNOWN_CAPABILITY for e in res.errors)


def test_validator_rejects_unsupported_hardware_capabilities():
    unsupported_steps = [
        PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_ON_COLD"),
        PlanStep(step_id=2, device="projector", capability="PROJECTOR_SWITCH_HDMI2"),
        PlanStep(step_id=3, device="ac", capability="AC_SET_HEAT"),
        PlanStep(step_id=4, device="ac", capability="AC_SET_SWING")
    ]
    validator = PlanValidator()
    for s in unsupported_steps:
        plan = GeminiStructuredPlan(intent="TEST", objective_summary="Test", steps=[s])
        res = validator.validate_plan(plan)
        assert res.valid is False
        assert any(e.error_code == ErrorCode.UNSUPPORTED_CAPABILITY for e in res.errors)


def test_validator_rejects_deferred_capabilities():
    plan = GeminiStructuredPlan(
        intent="TEST",
        objective_summary="Test",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_SET_CONTRAST", parameters={"contrast": 50})]
    )
    validator = PlanValidator()
    res = validator.validate_plan(plan)
    assert res.valid is False
    assert any(e.error_code == ErrorCode.DEFERRED_CAPABILITY for e in res.errors)


# =============================================================================
# 3. Parameter Safety & Physical Bounds
# =============================================================================

def test_parameter_bounds_ac_temperature():
    validator = PlanValidator()

    # 15°C (Below 16°C bound) -> FAIL
    p_low = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 15})
    ])
    assert validator.validate_plan(p_low).valid is False

    # 16°C (Valid lower bound) -> PASS
    p_min = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 16})
    ])
    assert validator.validate_plan(p_min).valid is True

    # 30°C (Valid upper bound) -> PASS
    p_max = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 30})
    ])
    assert validator.validate_plan(p_max).valid is True

    # 31°C (Above 30°C bound) -> FAIL
    p_high = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 31})
    ])
    assert validator.validate_plan(p_high).valid is False

    # String type instead of integer -> FAIL
    p_str = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": "24"})
    ])
    assert validator.validate_plan(p_str).valid is False


def test_parameter_bounds_pc_volume():
    validator = PlanValidator()

    # -1% -> FAIL
    p_neg = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": -1})
    ])
    assert validator.validate_plan(p_neg).valid is False

    # 0% -> PASS
    p_zero = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 0})
    ])
    assert validator.validate_plan(p_zero).valid is True

    # 100% -> PASS
    p_100 = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 100})
    ])
    assert validator.validate_plan(p_100).valid is True

    # 101% -> FAIL
    p_101 = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 101})
    ])
    assert validator.validate_plan(p_101).valid is False


def test_parameter_bounds_projector_brightness():
    validator = PlanValidator()

    # 0% -> FAIL (Min is 1%)
    p_0 = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="projector", capability="PROJECTOR_SET_BRIGHTNESS", parameters={"brightness": 0})
    ])
    assert validator.validate_plan(p_0).valid is False

    # 1% -> PASS
    p_1 = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="projector", capability="PROJECTOR_SET_BRIGHTNESS", parameters={"brightness": 1})
    ])
    assert validator.validate_plan(p_1).valid is True

    # 101% -> FAIL
    p_101 = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="projector", capability="PROJECTOR_SET_BRIGHTNESS", parameters={"brightness": 101})
    ])
    assert validator.validate_plan(p_101).valid is False


def test_parameter_enums_and_allowlists():
    validator = PlanValidator()

    # AC mode HEAT -> Rejected (only COOL, AUTO, DRY, FAN allowed)
    p_heat = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_MODE", parameters={"mode": "HEAT"})
    ])
    assert validator.validate_plan(p_heat).valid is False

    # PC Allowlisted App -> spotify accepted, cmd.exe rejected
    p_spotify = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="pc", capability="PC_LAUNCH_ALLOWLISTED_APP", parameters={"app_key": "spotify"})
    ])
    assert validator.validate_plan(p_spotify).valid is True

    p_malware = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="pc", capability="PC_LAUNCH_ALLOWLISTED_APP", parameters={"app_key": "powershell.exe"})
    ])
    assert validator.validate_plan(p_malware).valid is False


def test_missing_and_unknown_parameters():
    validator = PlanValidator()

    # Missing required parameter "temperature"
    p_missing = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_SET_TEMPERATURE", parameters={})
    ])
    res_m = validator.validate_plan(p_missing)
    assert res_m.valid is False
    assert any(e.error_code == ErrorCode.MISSING_PARAMETER for e in res_m.errors)

    # Unknown parameter "invalid_param"
    p_unknown = GeminiStructuredPlan(intent="T", objective_summary="T", steps=[
        PlanStep(step_id=1, device="ac", capability="AC_POWER_ON", parameters={"unsupported_field": True})
    ])
    res_u = validator.validate_plan(p_unknown)
    assert res_u.valid is False
    assert any(e.error_code == ErrorCode.UNKNOWN_PARAMETER for e in res_u.errors)


# =============================================================================
# 4. Restricted Precondition Evaluator
# =============================================================================

def test_precondition_evaluator_valid_expressions(mock_room_state):
    evaluator = RestrictedPreconditionEvaluator(current_time=mock_room_state.timestamp)

    # Satisfied Boolean
    res1 = evaluator.evaluate("projector.power == true", mock_room_state)
    assert res1.status == PreconditionStatus.SATISFIED

    # Satisfied Numeric
    res2 = evaluator.evaluate("ac.target_temperature == 24", mock_room_state)
    assert res2.status == PreconditionStatus.SATISFIED

    # Satisfied String (Case-Insensitive)
    res3 = evaluator.evaluate("projector.input_source == 'hdmi_1'", mock_room_state)
    assert res3.status == PreconditionStatus.SATISFIED

    # Satisfied List Membership
    res4 = evaluator.evaluate("fire_tv.power_state in ['AWAKE', 'ON']", mock_room_state)
    assert res4.status == PreconditionStatus.SATISFIED

    # Unsatisfied
    res5 = evaluator.evaluate("ac.target_temperature == 18", mock_room_state)
    assert res5.status == PreconditionStatus.NOT_SATISFIED

    # Logical AND
    res6 = evaluator.evaluate("projector.power == true and ac.power == true", mock_room_state)
    assert res6.status == PreconditionStatus.SATISFIED


def test_precondition_evaluator_unknown_and_stale_handling(mock_room_state):
    evaluator = RestrictedPreconditionEvaluator(current_time=mock_room_state.timestamp)

    # Set projector power to UNKNOWN
    mock_room_state.projector.power = StateField(value=None, provenance=Provenance.UNKNOWN, observed_at=mock_room_state.timestamp)
    res_unk = evaluator.evaluate("projector.power == true", mock_room_state)
    assert res_unk.status == PreconditionStatus.UNKNOWN_STATE

    # Set AC target temp to STALE (timestamp 100 seconds before evaluation time)
    old_time = mock_room_state.timestamp - 100.0
    mock_room_state.ac.target_temperature = StateField(value=24, provenance=Provenance.OBSERVED, observed_at=old_time)
    res_stale = evaluator.evaluate("ac.target_temperature == 24", mock_room_state)
    assert res_stale.status == PreconditionStatus.STALE_STATE


def test_precondition_evaluator_blocks_malicious_syntax(mock_room_state):
    evaluator = RestrictedPreconditionEvaluator(current_time=mock_room_state.timestamp)

    # Function call attempt -> Rejection
    res_call = evaluator.evaluate("__import__('os').system('calc')", mock_room_state)
    assert res_call.status == PreconditionStatus.INVALID_PRECONDITION

    # Subscript indexing -> Rejection
    res_sub = evaluator.evaluate("projector['power'] == true", mock_room_state)
    assert res_sub.status == PreconditionStatus.INVALID_PRECONDITION

    # Lambda / eval injection -> Rejection
    res_eval = evaluator.evaluate("eval('1 + 1') == 2", mock_room_state)
    assert res_eval.status == PreconditionStatus.INVALID_PRECONDITION


# =============================================================================
# 5. Idempotency Filtering
# =============================================================================

def test_idempotency_filtering_skips_already_observed_state(mock_room_state):
    validator = PlanValidator()

    # Projector is already awake (OBSERVED True) in mock_room_state
    plan = GeminiStructuredPlan(
        intent="CINEMA",
        objective_summary="Start cinema",
        steps=[
            PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE"),
            PlanStep(step_id=2, device="projector", capability="PROJECTOR_SWITCH_HDMI1")
        ]
    )
    res = validator.validate_plan(plan, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert res.valid is True
    # Both step 1 (wake) and step 2 (HDMI 1) are already satisfied in mock_room_state
    assert 1 in res.idempotent_step_ids
    assert 2 in res.idempotent_step_ids
    assert any(w.warning_code == WarningCode.IDEMPOTENT_SKIPPED for w in res.warnings)


def test_idempotency_does_not_skip_unknown_or_stale_state(mock_room_state):
    validator = PlanValidator()

    # Case A: AC_POWER_ON has no preconditions. With UNKNOWN state, it is validated but NOT marked idempotent.
    mock_room_state.ac.power = StateField(value=None, provenance=Provenance.UNKNOWN, observed_at=mock_room_state.timestamp)

    plan_ac = GeminiStructuredPlan(
        intent="COOL",
        objective_summary="Turn on AC",
        steps=[PlanStep(step_id=1, device="ac", capability="AC_POWER_ON")]
    )
    res_ac = validator.validate_plan(plan_ac, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert res_ac.valid is True
    assert 1 not in res_ac.idempotent_step_ids  # Must NOT be marked idempotent when state is UNKNOWN

    # Case B: PROJECTOR_POWER_WAKE has precondition projector.reachable. With UNKNOWN state, it fails closed.
    mock_room_state.projector.power = StateField(value=None, provenance=Provenance.UNKNOWN, observed_at=mock_room_state.timestamp)
    plan_proj = GeminiStructuredPlan(
        intent="WAKE",
        objective_summary="Wake",
        steps=[PlanStep(step_id=1, device="projector", capability="PROJECTOR_POWER_WAKE")]
    )
    res_proj = validator.validate_plan(plan_proj, room_state=mock_room_state, current_time=mock_room_state.timestamp)
    assert res_proj.valid is False
    assert any(e.error_code == ErrorCode.UNKNOWN_STATE for e in res_proj.errors)
    assert 1 not in res_proj.idempotent_step_ids


# =============================================================================
# 6. Gemini Client Structured Generation & Prompts
# =============================================================================

def test_gemini_client_missing_key_fails_safely(mock_room_state):
    client = GeminiPlannerClient(api_key="")
    with pytest.raises(GeminiApiUnavailableError):
        client.generate_plan("Make it chilly", mock_room_state)


def test_gemini_client_prompt_assembly_contains_no_secrets(mock_room_state):
    client = GeminiPlannerClient(api_key="mock_key")
    prompt_str = client.build_prompt_payload("Turn on movie mode", mock_room_state)
    assert "Turn on movie mode" in prompt_str
    assert "room_state" in prompt_str
    assert "available_capabilities" in prompt_str
    assert "PROJECTOR_POWER_WAKE" in prompt_str
    # Must NOT contain raw credentials
    assert "mock_key" not in prompt_str
    assert "password" not in prompt_str.lower()


# =============================================================================
# 7. FastAPI Endpoint Contract Tests
# =============================================================================

def test_capabilities_and_room_state_endpoints():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # 1. GET /api/capabilities
    res_cap = client.get("/api/capabilities")
    assert res_cap.status_code == 200
    data_cap = res_cap.json()
    assert data_cap["version"] == "1.0.0"
    assert "subsystems" in data_cap

    # 2. GET /api/room/state
    res_state = client.get("/api/room/state")
    assert res_state.status_code == 200
    data_state = res_state.json()
    assert "projector" in data_state
    assert "ac" in data_state


def test_planner_plan_endpoint_without_key_returns_503():
    from fastapi.testclient import TestClient
    from main import app, planner_client

    client = TestClient(app)

    # Temporarily ensure api key is unset on planner_client
    with patch.object(planner_client, "api_key", None):
        res = client.post("/api/planner/plan", json={"request": "Turn on movie mode"})
        assert res.status_code == 503
        data = res.json()
        assert data["detail"]["status"] == "GEMINI_UNAVAILABLE"


def test_planner_plan_endpoint_with_mocked_plan(mock_room_state):
    from fastapi.testclient import TestClient
    from main import app, planner_client

    mock_plan = GeminiStructuredPlan(
        intent="CINEMA_PLAYBACK",
        objective_summary="Prepare movie mode",
        steps=[
            PlanStep(step_id=1, device="ac", capability="AC_POWER_ON"),
            PlanStep(step_id=2, device="ac", capability="AC_SET_TEMPERATURE", parameters={"temperature": 23})
        ]
    )

    client = TestClient(app)

    with patch.object(planner_client, "generate_plan", return_value=mock_plan):
        with patch.object(planner_client, "api_key", "test_mock_key"):
            res = client.post("/api/planner/plan", json={"request": "Watch a movie"})
            assert res.status_code == 200
            data = res.json()
            assert data["valid"] is True
            assert data["intent"] == "CINEMA_PLAYBACK"
            assert len(data["validated_steps"]) == 2
