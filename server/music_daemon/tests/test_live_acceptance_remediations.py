"""
Unit and Integration Regression Test Suite for Phase 2 Live Acceptance Remediation:
1. AC Mode Control (COOL, AUTO, DRY, FAN, and HEAT rejection)
2. Music / PC Audio Playback & Soundbar Protection Invariant
3. Background Real Scheduler Loop Execution
4. Non-Room / Informational Queries Fast-path (action_taken=False)
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from capability_registry import UnifiedCapabilityRegistry
from agent.models import (
    IntentCategory,
    UserProfile
)
from agent.interaction_result import PhysicalVerificationStatus
from planner.models import OverallExecutionStatus
from agent.memory import AgentMemoryStore
from agent.context_buffer import ConversationContextBuffer
from agent.intent_resolver import IntentResolver
from agent.core import AnimusPersonalAgent
from agent.feedback import AgentFeedbackGenerator
from agent.scheduler import RoomScheduler, ScheduledTaskStatus
from planner.models import GeminiStructuredPlan, PlanStep
from room_state.models import RoomState, AcState, AudioStreamState, SoundbarState, StateField, Provenance


@pytest.fixture
def mock_profile():
    return UserProfile(identity={"user_name": "Sayan", "preferred_address": "buddy"})


@pytest.fixture
def mock_registry():
    return UnifiedCapabilityRegistry()


@pytest.fixture
def mock_memory():
    return AgentMemoryStore()


@pytest.fixture
def mock_context_buffer():
    return ConversationContextBuffer()


@pytest.fixture
def intent_resolver(mock_profile, mock_registry, mock_memory, mock_context_buffer):
    return IntentResolver(
        user_profile=mock_profile,
        registry=mock_registry,
        memory=mock_memory,
        context_buffer=mock_context_buffer
    )


# =========================================================================
# 1. AC Mode Control Intent & Plan Tests
# =========================================================================

def test_intent_resolver_ac_mode_auto(intent_resolver):
    for utt in ["put to auto", "change ac mode to auto", "set ac mode to auto", "put ac in auto mode", "ac mode auto"]:
        res = intent_resolver.resolve_intent(utt)
        assert res.category == IntentCategory.CLEAR_EXECUTABLE
        assert res.primary_intent == "SET_AC_MODE"
        assert res.extracted_parameters.get("mode") == "AUTO"
        assert "AC" in res.target_subsystems


def test_intent_resolver_ac_mode_cool_dry_fan(intent_resolver):
    res_cool = intent_resolver.resolve_intent("set ac mode to cool")
    assert res_cool.primary_intent == "SET_AC_MODE"
    assert res_cool.extracted_parameters.get("mode") == "COOL"

    res_dry = intent_resolver.resolve_intent("switch ac to dry mode")
    assert res_dry.primary_intent == "SET_AC_MODE"
    assert res_dry.extracted_parameters.get("mode") == "DRY"

    res_fan = intent_resolver.resolve_intent("change mode to fan")
    assert res_fan.primary_intent == "SET_AC_MODE"
    assert res_fan.extracted_parameters.get("mode") == "FAN"


def test_intent_resolver_ac_mode_missing_param(intent_resolver):
    res = intent_resolver.resolve_intent("change mode")
    assert res.category == IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL
    assert res.primary_intent == "SET_AC_MODE"
    assert res.missing_parameters == ["mode"]
    assert res.requires_followup is True


def test_ac_mode_canonical_plan_synthesis():
    agent = AnimusPersonalAgent()
    try:
        plan = agent._synthesize_canonical_plan("put to auto", None)
        assert plan is not None
        assert plan.intent == "SET_AC_MODE"
        assert len(plan.steps) == 1
        assert plan.steps[0].capability == "AC_SET_MODE"
        assert plan.steps[0].parameters.get("mode") == "AUTO"
    finally:
        agent.stop_scheduler_loop()


# =========================================================================
# 2. Music / Track Playback Intent & Soundbar Protection Invariant Tests
# =========================================================================

def test_intent_resolver_play_specific_tracks(intent_resolver):
    res1 = intent_resolver.resolve_intent("play Kal Ho Naa Ho")
    assert res1.category == IntentCategory.CLEAR_EXECUTABLE
    assert res1.primary_intent == "PLAY_TRACK"
    assert res1.extracted_parameters.get("title") == "kal ho naa ho"

    res2 = intent_resolver.resolve_intent("play Zara Zara")
    assert res2.primary_intent == "PLAY_TRACK"
    assert res2.extracted_parameters.get("title") == "zara zara"

    # Conversational prefixes (e.g. "first play...", "can you play...")
    res3 = intent_resolver.resolve_intent("first play kal ho na ho")
    assert res3.primary_intent == "PLAY_TRACK"
    assert res3.extracted_parameters.get("title") == "kal ho na ho"

    res4 = intent_resolver.resolve_intent("can you play Kesariya")
    assert res4.primary_intent == "PLAY_TRACK"
    assert res4.extracted_parameters.get("title") == "kesariya"


def test_intent_resolver_direct_power_intents(intent_resolver):
    res_p_on = intent_resolver.resolve_intent("turn on the projector")
    assert res_p_on.primary_intent == "PROJECTOR_POWER_WAKE"
    assert "PROJECTOR" in res_p_on.target_subsystems

    res_p_off = intent_resolver.resolve_intent("can you turn off the projector")
    assert res_p_off.primary_intent == "PROJECTOR_POWER_SLEEP"

    res_ac_on = intent_resolver.resolve_intent("turn on the ac")
    assert res_ac_on.primary_intent == "AC_POWER_ON"

    res_ac_off = intent_resolver.resolve_intent("turn off ac")
    assert res_ac_off.primary_intent == "AC_POWER_OFF"


def test_music_playback_soundbar_protection_and_audit():
    mock_orchestrator = MagicMock()
    mock_orchestrator.player.get_status.return_value = {"status": "PLAYING", "paused": False}
    mock_orchestrator.safe_play.return_value = (True, {"title": "Kal Ho Naa Ho", "artist": "Sonu Nigam"}, None)

    # Room state where Fire TV owns the soundbar
    st = RoomState(
        soundbar=SoundbarState(current_owner=StateField(value="FIRE_TV", provenance=Provenance.OBSERVED))
    )

    mock_aggregator = MagicMock()
    mock_aggregator.get_room_state.return_value = st

    agent = AnimusPersonalAgent(
        room_state_aggregator=mock_aggregator,
        orchestrator=mock_orchestrator
    )
    try:
        resp = agent.interact("first play kal ho na ho", room_state=st)
        assert resp.action_taken is True
        assert "Kal Ho Naa Ho" in resp.agent_message
        assert resp.physical_audits is not None
        assert len(resp.physical_audits) == 1
        assert resp.physical_audits[0].readback_result == "VERIFIED"
        mock_orchestrator.safe_play.assert_called_once_with(title="kal ho na ho")
    finally:
        agent.stop_scheduler_loop()


def test_unhandled_command_never_claims_false_action_taken():
    agent = AnimusPersonalAgent()
    try:
        resp = agent.interact("random unhandled command without hardware plan")
        assert resp.action_taken is False
        assert "Got it" not in resp.agent_message
    finally:
        agent.stop_scheduler_loop()


# =========================================================================
# 3. Scheduled Commands & Background Real Scheduler Tests
# =========================================================================

def test_intent_resolver_schedule_actions(intent_resolver):
    res = intent_resolver.resolve_intent("turn the AC to 23 in 2 minutes")
    assert res.category == IntentCategory.CLEAR_EXECUTABLE
    assert res.primary_intent == "SCHEDULE_ACTION"
    assert res.extracted_parameters.get("delay_seconds") == 120.0
    assert res.extracted_parameters.get("temperature") == 23

    res_cancel = intent_resolver.resolve_intent("cancel scheduled ac")
    assert res_cancel.primary_intent == "CANCEL_SCHEDULED_ACTION"


def test_background_scheduler_evaluates_and_executes():
    mock_executor = MagicMock()
    mock_executor.validator.validate_plan.return_value = MagicMock(valid=True)
    mock_executor.execute_plan.return_value = MagicMock(success=True)

    sched = RoomScheduler()
    t_now = 1000.0

    # Schedule a task for t = 1010.0 (10s in future)
    task = sched.schedule_action(
        utterance="Turn AC to 23 in 10 seconds",
        delay_seconds=10.0,
        action_type="SET_AC_TEMPERATURE",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 23},
        current_time=t_now
    )
    assert task.status == ScheduledTaskStatus.SCHEDULED

    # Tick at t = 1005 (not due)
    res_early = sched.evaluate_and_execute_due_tasks(
        current_time=1005.0,
        room_state=None,
        planner_executor=mock_executor
    )
    assert len(res_early) == 0
    assert task.status == ScheduledTaskStatus.SCHEDULED

    # Tick at t = 1011 (due)
    res_due = sched.evaluate_and_execute_due_tasks(
        current_time=1011.0,
        room_state=None,
        planner_executor=mock_executor
    )
    assert len(res_due) == 1
    t_executed, ok, reason = res_due[0]
    assert ok is True
    assert t_executed.status == ScheduledTaskStatus.EXECUTED
    mock_executor.execute_plan.assert_called_once()


# =========================================================================
# 4. AC Mode Comprehensive Variation & Combined Mode+Temp Tests
# =========================================================================

def test_all_ac_mode_natural_variations(intent_resolver):
    cases = [
        ("set AC to auto", "AUTO", None),
        ("put AC on auto", "AUTO", None),
        ("change AC mode to auto", "AUTO", None),
        ("AC auto mode", "AUTO", None),
        ("switch AC to auto mode", "AUTO", None),
        ("put to auto", "AUTO", None),
        ("set AC to cool", "COOL", None),
        ("set AC to dry", "DRY", None),
        ("set AC to fan", "FAN", None),
        ("set AC to fan mode", "FAN", None),
        ("change AC mode to cool", "COOL", None),
        ("change AC mode to dry", "DRY", None),
        ("change AC mode to fan", "FAN", None),
        ("change AC mode to cold", "COOL", None),
        ("cool mode on AC", "COOL", None),
        ("dry mode on AC", "DRY", None),
        # Combined Mode + Temperature
        ("set the AC to fan mode at 28", "FAN", 28),
        ("put the AC on dry at 24", "DRY", 24),
        ("switch the AC to cool and make it 25", "COOL", 25),
        ("set AC to fan mode at 26", "FAN", 26),
        ("switch to dry mode at 28", "DRY", 28),
    ]

    for utt, expected_mode, expected_temp in cases:
        res = intent_resolver.resolve_intent(utt)
        assert res.primary_intent == "SET_AC_MODE", f"Failed intent for '{utt}', got {res.primary_intent}"
        assert res.extracted_parameters.get("mode") == expected_mode, f"Failed mode for '{utt}', expected {expected_mode}, got {res.extracted_parameters.get('mode')}"
        if expected_temp is not None:
            assert res.extracted_parameters.get("temperature") == expected_temp, f"Failed temp for '{utt}', expected {expected_temp}, got {res.extracted_parameters.get('temperature')}"


def test_ac_combined_canonical_plan_synthesis():
    agent = AnimusPersonalAgent()
    try:
        plan = agent._synthesize_canonical_plan("set the AC to fan mode at 28", None)
        assert plan is not None
        assert plan.intent == "SET_AC_MODE"
        assert len(plan.steps) == 2
        assert plan.steps[0].capability == "AC_SET_MODE"
        assert plan.steps[0].parameters.get("mode") == "FAN"
        assert plan.steps[1].capability == "AC_SET_TEMPERATURE"
        assert plan.steps[1].parameters.get("temperature") == 28
    finally:
        agent.stop_scheduler_loop()


# =========================================================================
# 5. Projector Startup & Readiness Polling Tests
# =========================================================================

def test_projector_wake_tolerates_startup_latency():
    from projector_controller import ProjectorController, ProjectorPowerState
    from unittest.mock import MagicMock, patch

    mock_ir = MagicMock()
    ctrl = ProjectorController(use_ir_power=True, ir_transport=mock_ir)

    # Simulate: first 3 polls fail/disconnected, 4th poll succeeds
    connection_attempts = [False, False, False, True]
    def mock_is_connected(*args, **kwargs):
        if connection_attempts:
            return connection_attempts.pop(0), "192.168.1.11:5555"
        return True, "192.168.1.11:5555"

    with patch.object(ctrl, "is_connected", side_effect=mock_is_connected):
        with patch.object(ctrl, "get_power_state", return_value={"power_state": ProjectorPowerState.ON.value, "interactive": True}):
            with patch("time.sleep", return_value=None):
                success = ctrl.wake(timeout_seconds=60.0)
                assert success is True
                mock_ir.send_power_wake.assert_called_once()


def test_projector_wake_timeout_truthful_failure():
    from projector_controller import ProjectorController
    from unittest.mock import MagicMock, patch

    mock_ir = MagicMock()
    ctrl = ProjectorController(use_ir_power=True, ir_transport=mock_ir)

    with patch.object(ctrl, "is_connected", return_value=(False, None)):
        with patch("time.sleep", return_value=None):
            with patch("time.time", side_effect=[0, 10, 30, 50, 70]):
                success = ctrl.wake(timeout_seconds=60.0)
                assert success is False


# =========================================================================
# 6. Informational Queries & Gemini / External Fallback Tests
# =========================================================================

def test_informational_queries_never_take_hardware_action():
    agent = AnimusPersonalAgent()
    try:
        # Mock the external LLM call so test is fast & offline
        with patch.object(agent, "_query_informational_llm", return_value="Here is an external informational answer."):
            queries = [
                "what's the weather outside?",
                "what time is it?",
                "tell me a joke",
                "who is Elon Musk?",
                "who are you?"
            ]
            for q in queries:
                resp = agent.interact(q)
                assert resp.action_taken is False, f"Action taken should be False for '{q}', got {resp.action_taken}"
                assert resp.agent_message is not None and len(resp.agent_message) > 0
                assert resp.physical_audits is None or len(resp.physical_audits) == 0
    finally:
        agent.stop_scheduler_loop()


def test_music_and_streaming_playback_intents(intent_resolver):
    # 1. "play Kal Ho Naa Ho"
    res1 = intent_resolver.resolve_intent("play Kal Ho Naa Ho")
    assert res1.primary_intent == "PLAY_TRACK"
    assert res1.extracted_parameters.get("title") == "kal ho naa ho"
    assert res1.extracted_parameters.get("volume") is None

    # 2. Clean compound commands with volume: "play alak niranjan on volume 25"
    res_vol1 = intent_resolver.resolve_intent("play alak niranjan on volume 25")
    assert res_vol1.primary_intent == "PLAY_TRACK"
    assert res_vol1.extracted_parameters.get("title") == "alak niranjan"
    assert res_vol1.extracted_parameters.get("volume") == 25

    # 3. "play kal ho naa ho on volume 25"
    res_vol2 = intent_resolver.resolve_intent("play kal ho naa ho on volume 25")
    assert res_vol2.primary_intent == "PLAY_TRACK"
    assert res_vol2.extracted_parameters.get("title") == "kal ho naa ho"
    assert res_vol2.extracted_parameters.get("volume") == 25

    # 4. "play sunday suspense on volume 30"
    res_vol3 = intent_resolver.resolve_intent("play sunday suspense on volume 30")
    assert res_vol3.primary_intent == "PLAY_TRACK"
    assert res_vol3.extracted_parameters.get("title") == "sunday suspense"
    assert res_vol3.extracted_parameters.get("volume") == 30

    # 5. "I want to watch Rick and Morty on Netflix"
    res2 = intent_resolver.resolve_intent("I want to watch Rick and Morty on Netflix")
    assert res2.primary_intent == "LAUNCH_NETFLIX"
    assert res2.extracted_parameters.get("provider") == "netflix"


def test_ac_temperature_control_variations(intent_resolver):
    # "change the temperature to 28"
    res1 = intent_resolver.resolve_intent("change the temperature to 28")
    assert res1.primary_intent == "SET_AC_TEMPERATURE"
    assert res1.extracted_parameters.get("temperature") == 28

    # "temperature 28"
    res2 = intent_resolver.resolve_intent("temperature 28")
    assert res2.primary_intent == "SET_AC_TEMPERATURE"
    assert res2.extracted_parameters.get("temperature") == 28

    # "AC on chill mode temperature 26"
    res3 = intent_resolver.resolve_intent("AC on chill mode temperature 26")
    assert res3.primary_intent == "SET_AC_MODE"
    assert res3.extracted_parameters.get("mode") == "COOL"
    assert res3.extracted_parameters.get("temperature") == 26


def test_ac_heat_mode_truthful_rejection():
    from ac_controller import AcController
    ac = AcController()
    ok, details = ac.set_mode("HEAT")
    assert ok is False
    assert "cooling-only" in details.get("error", "")


def test_projector_startup_failure_truthful_feedback(mock_profile):
    from agent.feedback import AgentFeedbackGenerator
    from agent.interaction_result import AgentInteractionResult, PhysicalVerificationStatus, DecisionType

    gen = AgentFeedbackGenerator(user_profile=mock_profile)
    res = AgentInteractionResult(
        user_utterance="movie time",
        understood_intent="PROJECTOR_POWER_WAKE",
        decision_type=DecisionType.EXECUTE_PLAN,
        target_device="PROJECTOR",
        execution_attempted=True,
        execution_success=False,
        physical_verification=PhysicalVerificationStatus.FAILED
    )
    feedback = gen.generate_closed_loop_feedback(res, user_address="buddy")
    assert "still starting up" in feedback or "couldn't" in feedback


def test_physical_reality_invariant_unverified_action_never_claims_true():
    """
    PHYSICAL REALITY WINS:
    Proves that if physical readback is FAILED or unverified,
    action_taken MUST be False and the agent response must report failure.
    """
    from unittest.mock import MagicMock
    mock_executor = MagicMock()
    mock_exec_res = MagicMock()
    mock_exec_res.success = False
    mock_exec_res.failure_reason = "Physical read-back verification failed."
    mock_exec_res.to_dict.return_value = {"success": False, "status": "FAILED"}
    mock_exec_res.steps = []
    mock_executor.execute_plan.return_value = mock_exec_res
    mock_executor.validator.validate_plan.return_value = MagicMock(valid=True, errors=[])

    agent = AnimusPersonalAgent(planner_executor=mock_executor)
    try:
        # When physical readback is unverified / failed, action_taken must be False
        resp = agent.interact("set the AC to fan mode at 28")
        assert resp.action_taken is False
        assert "couldn't" in resp.agent_message.lower() or "failed" in resp.agent_message.lower()
    finally:
        agent.stop_scheduler_loop()


def test_netflix_canonical_plan_synthesis():
    agent = AnimusPersonalAgent()
    try:
        plan = agent._synthesize_canonical_plan("I want to watch Rick and Morty on Netflix", None)
        assert plan is not None
        assert plan.intent == "LAUNCH_NETFLIX"
        assert len(plan.steps) == 5
        assert plan.steps[0].capability == "PROJECTOR_POWER_WAKE"
        assert plan.steps[1].capability == "PROJECTOR_SWITCH_HDMI1"
        assert plan.steps[2].capability == "FIRE_TV_POWER_WAKE"
        assert plan.steps[3].capability == "FIRE_TV_MEDIA_DIRECT_PROVIDER"
        assert plan.steps[3].parameters.get("provider") == "netflix"
        assert plan.steps[3].parameters.get("content").lower() == "rick and morty"
        assert plan.steps[4].capability == "SOUNDBAR_ROUTE_TO_FIRE_TV"

        # Also test with spelling variation "rik and morty"
        plan_var = agent._synthesize_canonical_plan("play rik and morty on netflix", None)
        assert plan_var is not None
        assert plan_var.intent == "LAUNCH_NETFLIX"
        assert plan_var.steps[3].parameters.get("content").lower() == "rik and morty"
    finally:
        agent.stop_scheduler_loop()


def test_volume_increase_and_decrease_intents_and_plans(intent_resolver):
    # 1. "increase volume"
    res_up1 = intent_resolver.resolve_intent("increase volume")
    assert res_up1.primary_intent == "VOLUME_UP"

    # 2. "volume up"
    res_up2 = intent_resolver.resolve_intent("volume up")
    assert res_up2.primary_intent == "VOLUME_UP"

    # 3. "decrease volume"
    res_dn1 = intent_resolver.resolve_intent("decrease volume")
    assert res_dn1.primary_intent == "VOLUME_DOWN"

    # 4. "volume down"
    res_dn2 = intent_resolver.resolve_intent("volume down")
    assert res_dn2.primary_intent == "VOLUME_DOWN"

    # Plan synthesis
    agent = AnimusPersonalAgent()
    try:
        plan_up = agent._synthesize_canonical_plan("increase volume", None)
        assert plan_up is not None
        assert plan_up.intent == "VOLUME_UP"

        plan_dn = agent._synthesize_canonical_plan("decrease volume", None)
        assert plan_dn is not None
        assert plan_dn.intent == "VOLUME_DOWN"
    finally:
        agent.stop_scheduler_loop()


def test_weather_live_telemetry_grounding():
    agent = AnimusPersonalAgent()
    try:
        resp = agent.interact("what's the weather outside?")
        assert resp.action_taken is False
        assert resp.agent_message is not None
        # Must not say it can't check
        assert "can't check" not in resp.agent_message.lower() and "cannot check" not in resp.agent_message.lower()
        # Should contain outdoor / weather condition or temperature
        assert any(term in resp.agent_message.lower() for term in ["°c", "weather", "outside", "currently", "cloudy", "rain", "clear", "sunny", "temperature"])
    finally:
        agent.stop_scheduler_loop()


def test_bare_play_and_resume_handling(intent_resolver):
    # 1. Bare "play" when idle (no room_state or unpaused state) -> Must ask follow-up question
    res_idle = intent_resolver.resolve_intent("play")
    assert res_idle.primary_intent == "PLAY_TRACK"
    assert res_idle.requires_followup is True
    assert res_idle.followup_question == "What would you like me to play, buddy?"

    # 2. "resume" or "unpause" -> Must resolve to RESUME_MEDIA
    res_resume = intent_resolver.resolve_intent("resume")
    assert res_resume.primary_intent == "RESUME_MEDIA"

    res_unpause = intent_resolver.resolve_intent("unpause")
    assert res_unpause.primary_intent == "RESUME_MEDIA"

    # 3. Bare "play" when room state has paused audio -> Must resolve to RESUME_MEDIA
    from room_state.models import RoomState, StateField
    paused_room = RoomState()
    paused_room.audio_stream.playback_state = StateField.observed("PAUSED", "TEST")
    res_paused = intent_resolver.resolve_intent("play", room_state=paused_room)
    assert res_paused.primary_intent == "RESUME_MEDIA"
    assert res_paused.requires_followup is False

    # 4. Agent interaction for bare "play" when idle -> returns clarifying message
    agent = AnimusPersonalAgent()
    try:
        resp = agent.interact("play")
        assert resp.followup_required is True
        assert resp.agent_message == "What would you like me to play, buddy?"
        assert resp.action_taken is False
    finally:
        agent.stop_scheduler_loop()

