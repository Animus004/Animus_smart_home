"""
Comprehensive Automated Test Suite for Phase 2 Stage 1:
Agent Intelligence, Multi-Turn Context Buffer, Natural Intent Resolution,
Anaphoric Pronoun Resolution, Relative Adjustments, and Safe Deterministic Execution.
"""

import pytest
import time
from unittest.mock import MagicMock

from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState, StateField
from room_state.aggregator import RoomStateAggregator



from context import ContextEngine, PreferenceManager
from planner import PlanValidator, PlanExecutor
from agent.models import IntentCategory, UserProfile, UserIdentity, AcPreferenceModel, EntertainmentPreferencesModel
from agent.user_model import UserModel
from agent.memory import AgentMemoryStore
from agent.task_manager import TaskManager
from agent.context_buffer import ConversationContextBuffer
from agent.intent_resolver import IntentResolver
from agent.followup_engine import FollowUpEngine
from agent.core import AnimusPersonalAgent


@pytest.fixture
def mock_stage1_agent():
    """Builds an AnimusPersonalAgent with mock executors to verify end-to-end routing."""
    registry = UnifiedCapabilityRegistry()
    user_prof = UserProfile(
        identity=UserIdentity(name="Sayan Halder", preferred_address="buddy"),
        thermal=AcPreferenceModel(preferred_ac_setpoint=24),
        entertainment=EntertainmentPreferencesModel(

            preferred_movie_devices=["PROJECTOR", "FIRE_TV", "LG_SOUNDBAR"],
            preferred_streaming_services=["netflix", "prime_video", "youtube"]
        )
    )
    user_model = UserModel(profile=user_prof)
    memory = AgentMemoryStore()
    task_mgr = TaskManager()
    context_buf = ConversationContextBuffer()

    # Mock RoomState
    mock_agg = MagicMock(spec=RoomStateAggregator)
    now = time.time()
    st = RoomState()
    st.ac.target_temperature = StateField.observed(24, "MOCK", now)
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
    mock_agg.get_room_state.return_value = st




    # Mock PlanExecutor & Validator
    validator = PlanValidator(registry=registry)
    mock_executor = MagicMock(spec=PlanExecutor)
    mock_executor.validator = validator
    
    exec_res = MagicMock()
    exec_res.success = True
    exec_res.to_dict.return_value = {"success": True, "dispatched_steps": 1}
    mock_executor.execute_plan.return_value = exec_res

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
# 1. DIRECT HARDWARE COMMANDS & EXECUTION ROUTING
# =============================================================================

def test_direct_projector_wake_and_sleep(mock_stage1_agent):
    """Verifies direct 'turn on projector' and 'turn off projector' route to PlanExecutor."""
    agent, mock_executor, _ = mock_stage1_agent

    # 1. Turn on Projector
    r_on = agent.interact("turn on the projector")
    assert r_on.action_taken is True
    assert r_on.understood_intent == "PROJECTOR_POWER_WAKE"
    assert mock_executor.execute_plan.called
    assert len(r_on.physical_audits) > 0
    assert r_on.physical_audits[0].target == "PROJECTOR"
    assert r_on.physical_audits[0].capability == "PROJECTOR_POWER_WAKE"

    mock_executor.execute_plan.reset_mock()

    # 2. Turn off Projector
    r_off = agent.interact("turn off the projector")
    assert r_off.action_taken is True
    assert r_off.understood_intent == "PROJECTOR_POWER_SLEEP"
    assert mock_executor.execute_plan.called
    assert r_off.physical_audits[0].target == "PROJECTOR"
    assert r_off.physical_audits[0].capability == "PROJECTOR_POWER_SLEEP"


def test_direct_ac_power_on_and_off(mock_stage1_agent):
    """Verifies direct AC power commands route to PlanExecutor."""
    agent, mock_executor, _ = mock_stage1_agent

    # 1. Turn on AC
    r_on = agent.interact("turn on the AC")
    assert r_on.action_taken is True
    assert r_on.understood_intent == "AC_POWER_ON"
    assert r_on.physical_audits[0].target == "AC"
    assert r_on.physical_audits[0].capability == "AC_POWER_ON"

    mock_executor.execute_plan.reset_mock()

    # 2. Turn off AC
    r_off = agent.interact("turn off the AC")
    assert r_off.action_taken is True
    assert r_off.understood_intent == "AC_POWER_OFF"
    assert r_off.physical_audits[0].target == "AC"
    assert r_off.physical_audits[0].capability == "AC_POWER_OFF"


def test_direct_media_pause_and_resume(mock_stage1_agent):
    """Verifies direct media pause/resume routes to Fire TV playback capability."""
    agent, mock_executor, _ = mock_stage1_agent

    # 1. Pause
    r_pause = agent.interact("pause the movie")
    assert r_pause.action_taken is True
    assert r_pause.understood_intent == "PAUSE_MEDIA"
    assert r_pause.physical_audits[0].target == "FIRE_TV"
    assert r_pause.physical_audits[0].capability == "FIRE_TV_MEDIA_PAUSE"

    mock_executor.execute_plan.reset_mock()

    # 2. Resume
    r_resume = agent.interact("resume the video")
    assert r_resume.action_taken is True
    assert r_resume.understood_intent == "RESUME_MEDIA"
    assert r_resume.physical_audits[0].target == "FIRE_TV"
    assert r_resume.physical_audits[0].capability == "FIRE_TV_MEDIA_PLAY"


# =============================================================================
# 2. NATURAL LANGUAGE VARIATIONS & WORD NUMBERS
# =============================================================================

def test_natural_ac_phrasing_and_word_numbers(mock_stage1_agent):
    """Verifies colloquial AC phrasing and word-to-digit normalization."""
    agent, mock_executor, _ = mock_stage1_agent

    # Word numbers: "AC twenty four"
    r1 = agent.interact("AC twenty four")
    assert r1.action_taken is True
    assert r1.understood_intent == "SET_AC_TEMPERATURE"
    assert r1.physical_audits[0].requested_value.get("temperature") == 24

    mock_executor.execute_plan.reset_mock()

    # "make it twenty six degrees"
    r2 = agent.interact("make it twenty six degrees")
    assert r2.action_taken is True
    assert r2.understood_intent == "SET_AC_TEMPERATURE"
    assert r2.physical_audits[0].requested_value.get("temperature") == 26

    mock_executor.execute_plan.reset_mock()

    # Conversational: "it's hot, turn on the AC"
    r3 = agent.interact("it's hot, turn on the AC")
    assert r3.action_taken is True
    assert r3.understood_intent == "AC_POWER_ON"


# =============================================================================
# 3. MULTI-TURN CONTEXT & IN-FLIGHT CORRECTIONS
# =============================================================================

def test_multi_turn_cinema_with_in_flight_correction(mock_stage1_agent):
    """Verifies cinema multi-turn dialog and 'Actually YouTube' provider correction."""
    agent, mock_executor, _ = mock_stage1_agent

    # Turn 1: "Let's watch something" -> asks provider
    t1 = agent.interact("Let's watch something.")
    assert t1.followup_required is True
    assert "Netflix" in t1.agent_message and "Prime Video" in t1.agent_message


    # Turn 2: "Netflix" -> launches Netflix
    t2 = agent.interact("Netflix")
    assert t2.action_taken is True
    assert "LAUNCH_NETFLIX" in t2.understood_intent or "MOVIE_MODE" in t2.understood_intent or "PLAY" in t2.understood_intent
    assert agent.context_buffer.last_media_provider == "netflix"

    mock_executor.execute_plan.reset_mock()

    # Turn 3: "Actually make it YouTube" -> provider correction
    t3 = agent.interact("Actually make it YouTube.")
    assert t3.action_taken is True
    assert "YOUTUBE" in t3.understood_intent
    assert mock_executor.execute_plan.called


def test_multi_turn_ac_temperature_correction(mock_stage1_agent):
    """Verifies AC temperature followed by 'Actually 25' resolves as correction."""
    agent, mock_executor, _ = mock_stage1_agent

    # Turn 1: "Set AC to 24"
    t1 = agent.interact("Set AC to 24")
    assert t1.action_taken is True
    assert t1.understood_intent == "SET_AC_TEMPERATURE"
    assert agent.context_buffer.last_target_device == "AC"

    mock_executor.execute_plan.reset_mock()

    # Turn 2: "Actually 25" -> must NOT be BARE_NUMERIC_AMBIGUOUS!
    t2 = agent.interact("Actually 25")
    assert t2.action_taken is True
    assert t2.understood_intent == "SET_AC_TEMPERATURE"
    assert t2.physical_audits[0].requested_value.get("temperature") == 25


def test_multi_turn_relaxation_negative_constraints(mock_stage1_agent):
    """Verifies 3-turn relaxation narrowing: 'I'm tired' -> 'Not music' -> 'Movie'."""
    agent, _, _ = mock_stage1_agent

    # Turn 1: "I'm exhausted"
    t1 = agent.interact("I'm exhausted.")
    assert t1.followup_required is True
    assert "music, a movie, or just a quiet room" in t1.agent_message

    # Turn 2: "Not music" -> negative constraint
    t2 = agent.interact("Not music.")
    assert t2.followup_required is True
    assert "movie" in t2.agent_message.lower() and "quiet" in t2.agent_message.lower()

    # Turn 3: "Movie" -> cinema flow
    t3 = agent.interact("Movie.")
    assert t3.followup_required is True
    assert "Netflix" in t3.agent_message or "Prime" in t3.agent_message


# =============================================================================
# 4. TOPIC SWITCHING & CANCELLATION
# =============================================================================

def test_topic_switch_cancels_pending_intent_safely(mock_stage1_agent):
    """Verifies that switching topics supersedes pending questions with zero accidental dispatch."""
    agent, mock_executor, _ = mock_stage1_agent

    # Turn 1: "Let's watch something" -> asks provider
    t1 = agent.interact("Let's watch something.")
    assert t1.followup_required is True

    mock_executor.execute_plan.reset_mock()

    # Turn 2: "I'm going to my desk" -> topic switch!
    t2 = agent.interact("I'm going to my desk.")
    assert t2.understood_intent == "USER_LOCATION_UPDATE"
    assert t2.action_taken is False
    assert agent.followup_engine.has_pending_followup is False
    assert agent.context_buffer.active_thread is None


# =============================================================================
# 5. RELATIVE HARDWARE ADJUSTMENTS
# =============================================================================

def test_relative_ac_cooling_and_warming(mock_stage1_agent):
    """Verifies 'a little cooler' and 'a little warmer' compute relative setpoints."""
    agent, mock_executor, mock_agg = mock_stage1_agent

    # Base AC temp = 24
    st = mock_agg.get_room_state.return_value
    st.ac.target_temperature.value = 24

    # 1. "a little cooler" -> 23°C
    r1 = agent.interact("make it a little cooler")
    assert r1.action_taken is True
    assert r1.understood_intent == "SET_AC_TEMPERATURE"
    assert r1.physical_audits[0].requested_value.get("temperature") == 23

    mock_executor.execute_plan.reset_mock()

    # 2. "a little warmer" -> 25°C
    r2 = agent.interact("make it a little warmer")
    assert r2.action_taken is True
    assert r2.understood_intent == "SET_AC_TEMPERATURE"
    assert r2.physical_audits[0].requested_value.get("temperature") == 25


def test_relative_volume_adjustments(mock_stage1_agent):
    """Verifies 'turn it down a bit' and 'make it louder' use active audio producer."""
    agent, mock_executor, mock_agg = mock_stage1_agent

    # Active audio = FIRE_TV
    r1 = agent.interact("turn it down a bit")
    assert r1.action_taken is True
    assert r1.understood_intent == "VOLUME_DOWN"
    assert r1.physical_audits[0].target == "FIRE_TV"

    mock_executor.execute_plan.reset_mock()

    # Switch audio to PC
    st = mock_agg.get_room_state.return_value
    st.audio_stream.active_producer.value = "PC"
    st.pc.master_volume.value = 50

    r2 = agent.interact("make it louder")
    assert r2.action_taken is True
    assert r2.understood_intent == "VOLUME_UP"
    assert r2.physical_audits[0].target == "PC"
    assert r2.physical_audits[0].requested_value.get("volume") == 50 + 10



# =============================================================================
# 6. ANAPHORIC PRONOUNS ("that", "it")
# =============================================================================

def test_anaphoric_turn_that_off(mock_stage1_agent):
    """Verifies 'turn that off' routes to AC when AC was last active device."""
    agent, mock_executor, mock_agg = mock_stage1_agent

    # Simulate AC context
    agent.context_buffer.last_target_device = "AC"

    r = agent.interact("turn that off")
    assert r.action_taken is True
    assert r.understood_intent == "AC_POWER_OFF"
    assert r.physical_audits[0].target == "AC"
    assert r.physical_audits[0].capability == "AC_POWER_OFF"


# =============================================================================
# 7. UNSAFE & UNSUPPORTED REJECTIONS
# =============================================================================

def test_unsafe_ac_and_volume_deterministic_rejection(mock_stage1_agent):
    """Verifies unsafe out-of-bounds requests are rejected before PlanExecutor."""
    agent, mock_executor, _ = mock_stage1_agent

    # 1. AC 12°C -> Rejected
    r1 = agent.interact("Set AC to 12 degrees")
    assert r1.action_taken is False
    assert r1.understood_intent == "AC_TEMPERATURE_OUT_OF_BOUNDS"
    assert not mock_executor.execute_plan.called

    # 2. Volume 120% -> Rejected
    r2 = agent.interact("Set volume to 120 percent")
    assert r2.action_taken is False
    assert r2.understood_intent == "VOLUME_OUT_OF_BOUNDS"
    assert not mock_executor.execute_plan.called


def test_unsupported_hardware_rejection(mock_stage1_agent):
    """Verifies unsupported appliances are truthfully refused."""
    agent, mock_executor, _ = mock_stage1_agent

    r = agent.interact("Turn on the microwave")
    assert r.action_taken is False
    assert r.understood_intent == "UNSUPPORTED_DEVICE_CONTROL"
    assert not mock_executor.execute_plan.called
    assert "microwave" in r.agent_message.lower()
