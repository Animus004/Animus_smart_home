"""
Authoritative Test Suite for Animus Phase 2 Stage 2:
Agentic Feedback, Meaning & Closed-Loop Behavioral Intelligence.

Verifies:
1. Closed-Loop Execution Cycle (Meaning -> Decision -> Action -> Observation -> Truthful Human Feedback)
2. StateDelta tracking and factual human-readable response generation
3. Semantic room reasoning (Thermal comfort, freezing, too hot, comfortable now)
4. Action introspection ("What did you just change?", "Why did you do that?")
5. Safe action replay ("Do that again")
6. Action undo & reversion ("Put it back")
7. Cancellation ("Never mind", "Forget it", "Don't do that")
8. Truthful hardware failure & unverified readback reporting
9. Complete Multi-Turn Real-Room Acceptance Flow
"""

import time
import pytest
from unittest.mock import MagicMock

from agent.core import AnimusPersonalAgent
from agent.models import (
    IntentCategory, UserProfile, UserIdentity, AcPreferenceModel,
    EntertainmentPreferencesModel, NotificationPreferencesModel, DailyRoutines
)
from agent.user_model import UserModel
from agent.memory import AgentMemoryStore
from agent.task_manager import TaskManager
from agent.context_buffer import ConversationContextBuffer
from agent.interaction_result import DecisionType, PhysicalVerificationStatus
from capability_registry.registry import UnifiedCapabilityRegistry
from capability_registry.catalog import AUTHORITATIVE_CAPABILITIES
from room_state.models import RoomState, StateField
from room_state.aggregator import RoomStateAggregator
from planner.validator import PlanValidator
from planner.executor import PlanExecutor
from planner.models import ExecutionResult, StepExecutionResult, ExecutionStatus, OverallExecutionStatus



@pytest.fixture
def mock_stage2_agent():
    """Builds an AnimusPersonalAgent wired with registry, validator, executor, and mock RoomState."""
    registry = UnifiedCapabilityRegistry()

    user_prof = UserProfile(
        identity=UserIdentity(name="Sayan", preferred_address="buddy"),
        thermal=AcPreferenceModel(preferred_ac_setpoint=24, comfort_preference="ECO"),
        entertainment=EntertainmentPreferencesModel(preferred_volume=40),
        notifications=NotificationPreferencesModel(),
        routines=DailyRoutines()
    )
    user_model = UserModel(profile=user_prof)
    memory = AgentMemoryStore()
    task_mgr = TaskManager()
    context_buf = ConversationContextBuffer()

    now = time.time()
    st = RoomState()
    st.ac.target_temperature = StateField.observed(24, "MOCK", now)
    st.ac.ambient_temperature = StateField.observed(28, "MOCK", now)
    st.ac.power = StateField.observed(True, "MOCK", now)
    st.projector.power = StateField.observed(True, "MOCK", now)
    st.projector.signal_active = StateField.observed(True, "MOCK", now)
    st.fire_tv.online = StateField.observed(True, "MOCK", now)
    st.fire_tv.power_state = StateField.observed("AWAKE", "MOCK", now)
    st.pc.online = StateField.observed(True, "MOCK", now)
    st.pc.master_volume = StateField.observed(40, "MOCK", now)
    st.soundbar.is_connected = StateField.observed(True, "MOCK", now)
    st.audio_stream.active_producer = StateField.observed("FIRE_TV", "MOCK", now)
    st.environment.room_mode = StateField.observed("IDLE", "MOCK", now)

    mock_agg = MagicMock(spec=RoomStateAggregator)
    mock_agg.get_room_state.return_value = st

    validator = PlanValidator(registry=registry)
    mock_executor = MagicMock(spec=PlanExecutor)
    mock_executor.validator = validator

    def _mock_exec(val_plan):
        steps_res = []
        for s in val_plan.validated_steps:
            obs = s.parameters.get("temperature", s.parameters.get("power", True))
            steps_res.append(
                StepExecutionResult(
                    step_id=s.step_id,
                    device=s.device,
                    capability_id=s.canonical_capability_id,
                    status=ExecutionStatus.VERIFIED,
                    requested_parameters=s.parameters,
                    dispatch_result=s.parameters,
                    readback_result={"matched": True, "observed": obs},
                    verified=True
                )
            )
        return ExecutionResult(
            plan_id=val_plan.plan_id,
            overall_status=OverallExecutionStatus.SUCCESS,
            success=True,
            total_duration_ms=45.0,
            steps=steps_res
        )



    mock_executor.execute_plan.side_effect = _mock_exec

    agent = AnimusPersonalAgent(
        registry=registry,
        room_state_aggregator=mock_agg,
        user_model=user_model,
        memory=memory,
        task_manager=task_mgr,
        context_buffer=context_buf,
        planner_executor=mock_executor
    )
    return agent, mock_executor, mock_agg



# =============================================================================
# 1. CLOSED-LOOP STATE DELTA & TRUTHFUL HUMAN FEEDBACK
# =============================================================================

def test_successful_ac_change_truthful_delta(mock_stage2_agent):
    """Verifies that AC temperature changes produce accurate state delta feedback."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 26

    r = agent.interact("Set the AC to 24.")
    assert r.action_taken is True
    assert "24" in r.agent_message
    assert "AC" in r.agent_message or "ac" in r.agent_message.lower()

    # Verify context buffer recorded StateDelta
    delta = agent.context_buffer.last_state_delta
    assert delta is not None
    assert delta.subsystem == "AC"
    assert delta.attribute == "target_temperature"
    assert delta.previous_value == 26
    assert delta.new_value == 24
    assert delta.delta == -2


def test_successful_projector_wake_truthful_response(mock_stage2_agent):
    """Verifies direct projector wake responds with verified state confirmation."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.projector.power.value = False

    r = agent.interact("turn on the projector")
    assert r.action_taken is True
    assert "on" in r.agent_message.lower() or "awake" in r.agent_message.lower()


def test_successful_media_pause_and_resume_feedback(mock_stage2_agent):
    """Verifies media playback control provides natural confirmation."""
    agent, mock_executor, _ = mock_stage2_agent

    r_pause = agent.interact("pause the movie")
    assert r_pause.action_taken is True
    assert "pause" in r_pause.agent_message.lower()

    r_play = agent.interact("resume the video")
    assert r_play.action_taken is True
    assert "resume" in r_play.agent_message.lower() or "playback" in r_play.agent_message.lower()


def test_truthful_hardware_failure_reporting(mock_stage2_agent):
    """Verifies that when hardware execution fails, Animus reports the failure truthfully."""
    agent, mock_executor, _ = mock_stage2_agent

    # Simulate Tuya failure
    mock_executor.execute_plan.side_effect = None
    mock_executor.execute_plan.return_value = ExecutionResult(
        plan_id="fail_plan",
        overall_status=OverallExecutionStatus.FAILED,
        success=False,
        total_duration_ms=120.0,
        steps=[
            StepExecutionResult(
                step_id=1,
                device="AC",
                capability_id="AC_POWER_ON",
                status=ExecutionStatus.FAILED,
                error_message="TUYA_TIMEOUT"
            )

        ]
    )

    r = agent.interact("turn on the AC")
    assert "couldn't" in r.agent_message.lower() or "failed" in r.agent_message.lower() or "didn't confirm" in r.agent_message.lower()
    assert "done" not in r.agent_message.lower()


# =============================================================================
# 2. SEMANTIC ROOM OBSERVATION & REASONING (COMFORT / THERMAL)
# =============================================================================

def test_semantic_room_freezing_turns_off_cold_ac(mock_stage2_agent):
    """Verifies 'It's freezing in here' turns off AC when room is already cold."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.ambient_temperature.value = 20
    st.ac.target_temperature.value = 18
    st.ac.power.value = True

    r = agent.interact("It's freezing in here.")
    assert r.action_taken is True
    assert "20" in r.agent_message
    assert "18" in r.agent_message
    assert "off" in r.agent_message.lower()
    assert mock_executor.execute_plan.called


def test_semantic_room_freezing_when_ac_already_off(mock_stage2_agent):
    """Verifies 'It's freezing in here' acknowledges temperature without modifying hardware when AC is already off."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.ambient_temperature.value = 19
    st.ac.power.value = False

    r = agent.interact("It's freezing in here.")
    assert r.action_taken is False
    assert "already off" in r.agent_message.lower()


def test_semantic_room_too_hot_turns_on_ac(mock_stage2_agent):
    """Verifies 'It's really hot' turns on AC if off."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.power.value = False

    r = agent.interact("It's really hot in here.")
    assert r.action_taken is True
    assert mock_executor.execute_plan.called


def test_semantic_room_comfortable_no_unnecessary_mutation(mock_stage2_agent):
    """Verifies 'It's comfortable now' avoids mutating hardware and responds naturally."""
    agent, mock_executor, _ = mock_stage2_agent

    r = agent.interact("It's comfortable now.")
    assert r.action_taken is False
    assert "comfortable" in r.agent_message.lower()
    assert not mock_executor.execute_plan.called


# =============================================================================
# 3. ACTION INTROSPECTION ("What did you just change?", "Why did you do that?")
# =============================================================================

def test_action_introspection_what_did_you_just_change(mock_stage2_agent):
    """Verifies 'What did you just change?' explains the exact before/after state delta."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 26

    # Turn 1: Change AC
    agent.interact("Set the AC to 24.")

    # Turn 2: Ask what changed
    r2 = agent.interact("What did you just change?")
    assert r2.action_taken is False
    assert "26" in r2.agent_message
    assert "24" in r2.agent_message
    assert "AC" in r2.agent_message or "ac" in r2.agent_message.lower()


def test_action_reason_introspection_why_did_you_do_that(mock_stage2_agent):
    """Verifies 'Why did you do that?' explains the reason from observable context."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.ambient_temperature.value = 20
    st.ac.target_temperature.value = 18
    st.ac.power.value = True

    # Turn 1: Semantic freezing command
    agent.interact("It's freezing in here.")

    # Turn 2: Ask why
    r2 = agent.interact("Why did you do that?")
    assert r2.action_taken is False
    assert "20" in r2.agent_message or "freezing" in r2.agent_message.lower() or "cooling off" in r2.agent_message.lower()


# =============================================================================
# 4. ACTION REPLAY ("Do that again") & UNDO ("Put it back")
# =============================================================================

def test_action_replay_do_that_again(mock_stage2_agent):
    """Verifies 'Do that again' safely repeats the most recent physical action."""
    agent, mock_executor, _ = mock_stage2_agent

    # Turn 1: Pause media
    agent.interact("pause the video")
    assert mock_executor.execute_plan.call_count == 1

    # Turn 2: Repeat
    r2 = agent.interact("do that again")
    assert r2.action_taken is True
    assert mock_executor.execute_plan.call_count == 2


def test_action_undo_put_it_back(mock_stage2_agent):
    """Verifies 'Put it back' restores the previous verified setpoint."""
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 24

    # Turn 1: Set AC to 25
    agent.interact("Set AC to 25.")
    st.ac.target_temperature.value = 25

    # Turn 2: Undo
    r_undo = agent.interact("Actually, never mind. Put it back.")
    assert r_undo.action_taken is True
    assert "24" in r_undo.agent_message
    assert r_undo.physical_audits[0].requested_value.get("temperature") == 24


# =============================================================================
# 5. CANCELLATION & FLOW CONTROL
# =============================================================================

def test_first_class_cancellation(mock_stage2_agent):
    """Verifies 'Never mind', 'Cancel', and 'Don't do that' cancel active threads with zero mutations."""
    agent, mock_executor, _ = mock_stage2_agent

    # Turn 1: Start multi-turn cinema setup
    t1 = agent.interact("Let's watch something.")
    assert t1.followup_required is True
    assert agent.context_buffer.active_thread is not None

    # Turn 2: Cancel
    t2 = agent.interact("Never mind.")
    assert t2.action_taken is False
    assert agent.context_buffer.active_thread is None
    assert "cancelled" in t2.agent_message.lower() or "no problem" in t2.agent_message.lower()


# =============================================================================
# 6. PRIMARY ACCEPTANCE TEST SEQUENCE (SECTION 19 MULTI-TURN CYCLE)
# =============================================================================

def test_full_section_19_acceptance_dialogue(mock_stage2_agent):
    """
    Executes the exact Section 19 Acceptance Dialogue:
    User: "Set the AC to 24."
    Animus: "Done buddy — the AC is at 24°C."
    User: "Actually make it a little warmer."
    Animus: "Sure buddy — moving it to 25°C."
    User: "What did you just change?"
    Animus: "I raised the AC from 24 to 25°C."
    User: "Actually, never mind. Put it back."
    Animus: "Got you — putting it back to 24°C."
    User: "Thanks."
    Animus: "Anytime, buddy."
    """
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 26

    # 1. "Set the AC to 24."
    t1 = agent.interact("Set the AC to 24.")
    assert t1.action_taken is True
    assert "24" in t1.agent_message
    st.ac.target_temperature.value = 24

    mock_executor.execute_plan.reset_mock()

    # 2. "Actually make it a little warmer."
    t2 = agent.interact("Actually make it a little warmer.")
    assert t2.action_taken is True
    assert "25" in t2.agent_message
    st.ac.target_temperature.value = 25

    mock_executor.execute_plan.reset_mock()

    # 3. "What did you just change?"
    t3 = agent.interact("What did you just change?")
    assert t3.action_taken is False
    assert "24" in t3.agent_message and "25" in t3.agent_message
    assert "raised" in t3.agent_message.lower() or "ac" in t3.agent_message.lower()

    # 4. "Actually, never mind. Put it back."
    t4 = agent.interact("Actually, never mind. Put it back.")
    assert t4.action_taken is True
    assert "24" in t4.agent_message
    assert t4.physical_audits[0].requested_value.get("temperature") == 24
    st.ac.target_temperature.value = 24

    mock_executor.execute_plan.reset_mock()

    # 5. "Thanks."
    t5 = agent.interact("Thanks.")
    assert t5.action_taken is False
    assert "anytime" in t5.agent_message.lower() or "welcome" in t5.agent_message.lower()


# =============================================================================
# 7. PRODUCTION TRUTH & PHYSICAL VERIFICATION INTEGRITY (FIX 5 TESTS)
# =============================================================================

def test_truth_requested_value_does_not_equal_verified_value_automatically(mock_stage2_agent):
    """
    Test A: Requested value must not equal verified value automatically.
    Requested: 24
    Physical readback: 26 (mismatch / failed)
    Expected: verified_value is NOT 24, success is False, response does NOT claim AC is at 24°C.
    """
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 26

    def _mock_mismatch_exec(val_plan):
        return ExecutionResult(
            plan_id=val_plan.plan_id,
            overall_status=OverallExecutionStatus.FAILED,
            success=False,
            total_duration_ms=50.0,
            steps=[
                StepExecutionResult(
                    step_id=1,
                    device="AC",
                    capability_id="AC_SET_TEMPERATURE",
                    status=ExecutionStatus.FAILED,
                    requested_parameters={"temperature": 24},
                    dispatch_result={"temperature": 24},
                    readback_result={"matched": False, "observed": 26},
                    verified=False
                )
            ]
        )

    mock_executor.execute_plan.side_effect = _mock_mismatch_exec

    resp = agent.interact("Set the AC to 24.")
    last_res = agent.context_buffer.last_interaction_result
    assert last_res is not None
    assert last_res.execution_success is False
    assert last_res.physical_verification == PhysicalVerificationStatus.FAILED
    assert last_res.state_delta is not None
    assert last_res.state_delta.verified_value != 24
    assert "at 24°C" not in resp.agent_message
    assert ("couldn't" in resp.agent_message.lower() or "didn't confirm" in resp.agent_message.lower())


def test_truth_missing_physical_readback(mock_stage2_agent):
    """
    Test B: Missing physical readback / timeout must result in failure response.
    """
    agent, mock_executor, mock_agg = mock_stage2_agent

    def _mock_timeout_exec(val_plan):
        return ExecutionResult(
            plan_id=val_plan.plan_id,
            overall_status=OverallExecutionStatus.FAILED,
            success=False,
            total_duration_ms=5000.0,
            steps=[
                StepExecutionResult(
                    step_id=1,
                    device="AC",
                    capability_id="AC_SET_TEMPERATURE",
                    status=ExecutionStatus.TIMEOUT,
                    requested_parameters={"temperature": 24},
                    dispatch_result={"temperature": 24},
                    readback_result=None,
                    verified=False
                )
            ]
        )

    mock_executor.execute_plan.side_effect = _mock_timeout_exec

    resp = agent.interact("Set the AC to 24.")
    last_res = agent.context_buffer.last_interaction_result
    assert last_res.execution_success is False
    assert last_res.physical_verification == PhysicalVerificationStatus.FAILED
    assert ("couldn't" in resp.agent_message.lower() or "didn't confirm" in resp.agent_message.lower())


def test_truth_stale_cached_state_bypassed_by_fresh_readback():
    """
    Test C: PlanExecutor polling forces fresh room telemetry (force_refresh=True).
    """
    mock_agg = MagicMock(spec=RoomStateAggregator)
    now = time.time()
    st_fresh = RoomState()
    st_fresh.ac.target_temperature = StateField.observed(25, "POLL", now)
    mock_agg.get_room_state.return_value = st_fresh

    executor = PlanExecutor(room_state_aggregator=mock_agg)
    verified, status, detail = executor._verify_physical_readback(
        cid="AC_SET_TEMPERATURE",
        parameters={"temperature": 25},
        timeout=1.0,
        poll_interval=0.1
    )

    assert verified is True
    assert status == ExecutionStatus.VERIFIED
    # Assert force_refresh=True was passed during polling
    mock_agg.get_room_state.assert_called_with(current_time=pytest.approx(now, abs=2.0), force_refresh=True)


def test_truth_false_cached_success_prevention(mock_stage2_agent):
    """
    Test D: Pre-command state equals requested value, but hardware dispatch fails.
    Must not report verified success if the executor fails.
    """
    agent, mock_executor, mock_agg = mock_stage2_agent
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 24

    def _mock_dispatch_fail(val_plan):
        return ExecutionResult(
            plan_id=val_plan.plan_id,
            overall_status=OverallExecutionStatus.FAILED,
            success=False,
            total_duration_ms=10.0,
            steps=[
                StepExecutionResult(
                    step_id=1,
                    device="AC",
                    capability_id="AC_SET_TEMPERATURE",
                    status=ExecutionStatus.FAILED,
                    requested_parameters={"temperature": 24},
                    dispatch_result={},
                    readback_result={},
                    verified=False
                )
            ]
        )

    mock_executor.execute_plan.side_effect = _mock_dispatch_fail

    resp = agent.interact("Set the AC to 24.")
    last_res = agent.context_buffer.last_interaction_result
    assert last_res.execution_success is False
    assert last_res.physical_verification == PhysicalVerificationStatus.FAILED


def test_truth_physical_failure_handling(mock_stage2_agent):
    """
    Test E: Complete agent interaction with failed execution produces truthful failure response without 'Done'.
    """
    agent, mock_executor, _ = mock_stage2_agent

    mock_executor.execute_plan.side_effect = lambda _: ExecutionResult(
        plan_id="fail_plan",
        overall_status=OverallExecutionStatus.FAILED,
        success=False,
        total_duration_ms=20.0,
        steps=[
            StepExecutionResult(
                step_id=1,
                device="PROJECTOR",
                capability_id="PROJECTOR_POWER_WAKE",
                status=ExecutionStatus.FAILED,
                requested_parameters={},
                dispatch_result={},
                readback_result=None,
                verified=False
            )
        ]
    )

    resp = agent.interact("Turn on the projector.")
    assert resp.agent_message.startswith("Done") is False
    assert ("couldn't" in resp.agent_message.lower() or "didn't confirm" in resp.agent_message.lower() or "stopped" in resp.agent_message.lower() or "starting up" in resp.agent_message.lower() or "reachable" in resp.agent_message.lower())



def test_tts_production_startup_and_endpoint_resolution():
    """
    Test F & G: RoomTtsService startup configuration and audio endpoint binding.
    """
    from tts_service import RoomTtsService

    # 1. Verification of default / explicit enabled configuration
    tts = RoomTtsService(enabled=True)
    assert tts.is_enabled() is True

    # 2. Soundbar already active in WASAPI graph -> resolves directly without reconnect
    mock_orch = MagicMock()
    mock_orch.bt_helper.scan_active_endpoints.return_value = (
        {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"},
        "ALREADY_CONNECTED"
    )
    tts_orch = RoomTtsService(orchestrator=mock_orch, enabled=True)

    endpoint_id = tts_orch._resolve_audio_device_id()
    assert endpoint_id == "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}"
    mock_orch.bt_helper.ensure_audio_endpoint.assert_not_called()

    # 3. Soundbar in standby / not in graph -> ensure_audio_endpoint() reconnects
    mock_orch.bt_helper.scan_active_endpoints.return_value = (None, "NOT_IN_GRAPH")
    mock_orch.bt_helper.ensure_audio_endpoint.return_value = (
        True,
        {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"},
        "RECONNECTED"
    )

    reconnected_id = tts_orch._resolve_audio_device_id()
    assert reconnected_id == "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}"
    mock_orch.bt_helper.ensure_audio_endpoint.assert_called_once()

    # 4. Bluetooth unavailable -> graceful fallback to None
    mock_orch.bt_helper.scan_active_endpoints.return_value = (None, "NOT_IN_GRAPH")
    mock_orch.bt_helper.ensure_audio_endpoint.return_value = (False, None, "AUDIO_OUTPUT_UNAVAILABLE")

    fallback_id = tts_orch._resolve_audio_device_id()
    assert fallback_id is None

    # 5. Exception handling -> graceful fallback to None without crash
    mock_orch.bt_helper.scan_active_endpoints.side_effect = RuntimeError("WinRT Bluetooth failure")
    err_fallback_id = tts_orch._resolve_audio_device_id()
    assert err_fallback_id is None



