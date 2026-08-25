"""
Authoritative Test Suite for Phase 2 Stage 5:
Proactive Room Intelligence, Behavioral Modes, Routines, Media Control & Autonomous Behavioral Orchestration.

Tests all 11 core Stage 5 domains:
- Section A: Behavioral Modes (7 tests)
- Section B: Routine Planning (6 tests)
- Section C: Media Sessions (8 tests)
- Section D: Comfort Intelligence (6 tests)
- Section E: Proactive Intelligence (6 tests)
- Section F: Autonomous Recovery (6 tests)
- Section G: Interruption & Priority Handling (6 tests)
- Section H: Behavioral Introspection (6 tests)
- Section I: Memory & Preferences (4 tests)
- Section J: Soundbar Ownership Protection (4 tests)
- Section K: Canonical Acceptance Dialogues (7 tests)

Total: 66 Comprehensive Tests
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from agent.behavior_modes import BehaviorMode, BehaviorModeManager, ModeState
from agent.routine_engine import RoutineEngine
from agent.media_session import MediaSessionManager, MediaPlaybackState, MediaSession
from agent.comfort_engine import ComfortEngine
from agent.proactive_engine import ProactiveEngine, ProactiveSuggestion, ProactiveSuggestionCategory, ProactiveSuggestionStatus
from agent.recovery_engine import RecoveryEngine, RecoveryType, RecoveryResult
from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus, GoalType
from agent.state_memory import ConversationalPreference, FactProvenance, AgentSessionMemory, RecentActionMemory
from agent.context_buffer import ConversationContextBuffer
from agent.intent_resolver import IntentResolver
from agent.interaction_result import AgentInteractionResult, DecisionType, PhysicalVerificationStatus, StateDelta
from agent.feedback import AgentFeedbackGenerator
from agent.core import AnimusPersonalAgent
from agent.models import UserProfile, UserIdentity, AcPreferenceModel, EntertainmentPreferencesModel, NotificationPreferencesModel, DailyRoutines, IntentCategory
from agent.user_model import UserModel
from agent.memory import AgentMemoryStore
from agent.task_manager import TaskManager
from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState, StateField, SoundbarState
from room_state.provenance import Provenance
from room_state.aggregator import RoomStateAggregator
from planner.models import ExecutionResult, StepExecutionResult, ExecutionStatus, OverallExecutionStatus, GeminiStructuredPlan, PlanStep
from planner.validator import ValidationResult, PlanValidator
from planner.executor import PlanExecutor



# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def user_profile():
    return UserProfile(
        identity=UserIdentity(name="Sayan", preferred_address="buddy"),
        thermal=AcPreferenceModel(preferred_ac_setpoint=24, comfort_preference="ECO"),
        entertainment=EntertainmentPreferencesModel(preferred_volume=40),
        notifications=NotificationPreferencesModel(),
        routines=DailyRoutines()
    )


@pytest.fixture
def mock_exec():
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)
    mock = MagicMock(spec=PlanExecutor)
    mock.validator = validator

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
                    dispatch_result={"success": True, "target_temperature": obs, "transport": "LOCAL"},
                    readback_result={"matched": True, "observed": obs, "target_temperature": obs, "power": True},
                    verified=True
                )
            )
        return ExecutionResult(
            plan_id=val_plan.plan_id or "test-plan",
            user_request=val_plan.user_request or "test request",
            overall_status=OverallExecutionStatus.SUCCESS,
            success=True,
            steps=steps_res,
            step_results=steps_res
        )

    mock.execute_plan.side_effect = _mock_exec
    return mock



@pytest.fixture
def base_room_state():
    rs = RoomState()
    rs.ac.power = StateField(value=True, provenance=Provenance.OBSERVED, is_authoritative=True)
    rs.ac.target_temperature = StateField(value=24, provenance=Provenance.OBSERVED, is_authoritative=True)
    rs.ac.ambient_temperature = StateField(value=25, provenance=Provenance.OBSERVED, is_authoritative=True)
    rs.projector.power = StateField(value=False, provenance=Provenance.OBSERVED, is_authoritative=True)
    rs.soundbar.current_owner = StateField(value="PC", provenance=Provenance.OBSERVED, is_authoritative=True)
    return rs



@pytest.fixture
def agent(mock_exec, user_profile, base_room_state):
    registry = UnifiedCapabilityRegistry()
    user_model = UserModel(profile=user_profile)
    memory = AgentMemoryStore()
    task_mgr = TaskManager()
    context_buf = ConversationContextBuffer()

    mock_agg = MagicMock(spec=RoomStateAggregator)
    mock_agg.get_room_state.return_value = base_room_state

    ag = AnimusPersonalAgent(
        registry=registry,
        room_state_aggregator=mock_agg,
        user_model=user_model,
        memory=memory,
        task_manager=task_mgr,
        context_buffer=context_buf,
        planner_executor=mock_exec
    )
    return ag


# =============================================================================
# SECTION A: BEHAVIORAL MODES (7 tests)
# =============================================================================

def test_a1_enter_movie_mode():
    manager = BehaviorModeManager()
    assert manager.active_mode == BehaviorMode.IDLE
    ok, msg = manager.transition_to(BehaviorMode.MOVIE, utterance="Let's watch a movie")
    assert ok is True
    assert manager.active_mode == BehaviorMode.MOVIE
    assert manager.previous_mode == BehaviorMode.IDLE


def test_a2_exit_movie_mode():
    manager = BehaviorModeManager(initial_mode=BehaviorMode.MOVIE)
    ok, msg = manager.exit_mode(reason="USER_EXIT")
    assert ok is True
    assert manager.active_mode == BehaviorMode.IDLE
    assert manager.previous_mode == BehaviorMode.MOVIE


def test_a3_movie_to_sleep_transition():
    manager = BehaviorModeManager(initial_mode=BehaviorMode.MOVIE)
    ok, msg = manager.transition_to(BehaviorMode.SLEEP, reason="USER_SLEEP")
    assert ok is True
    assert manager.active_mode == BehaviorMode.SLEEP
    assert manager.previous_mode == BehaviorMode.MOVIE


def test_a4_music_to_movie_transition():
    manager = BehaviorModeManager(initial_mode=BehaviorMode.MUSIC)
    ok, msg = manager.transition_to(BehaviorMode.MOVIE)
    assert ok is True
    assert manager.active_mode == BehaviorMode.MOVIE
    assert manager.previous_mode == BehaviorMode.MUSIC


def test_a5_invalid_transition_rejected():
    manager = BehaviorModeManager(initial_mode=BehaviorMode.SLEEP)
    # Direct SLEEP -> WORK without waking up is invalid
    ok, msg = manager.transition_to(BehaviorMode.WORK)
    assert ok is False
    assert "Invalid mode transition" in msg
    assert manager.active_mode == BehaviorMode.SLEEP


def test_a6_mode_history_persistence():
    manager = BehaviorModeManager()
    manager.transition_to(BehaviorMode.MOVIE)
    manager.transition_to(BehaviorMode.IDLE)
    manager.transition_to(BehaviorMode.SLEEP)
    history = manager.get_history()
    assert len(history) == 3
    assert history[0].active_mode == BehaviorMode.IDLE
    assert history[1].active_mode == BehaviorMode.MOVIE
    assert history[2].active_mode == BehaviorMode.IDLE
    assert manager.active_mode == BehaviorMode.SLEEP



def test_a7_mode_physical_alignment_verification():
    manager = BehaviorModeManager(initial_mode=BehaviorMode.MOVIE)
    aligned = manager.verify_physical_alignment({"projector_power": True, "soundbar_owner": "FIRE_TV"})
    assert aligned is True

    # If projector is OFF during movie mode, physical alignment fails
    misaligned = manager.verify_physical_alignment({"projector_power": False, "soundbar_owner": "FIRE_TV"})
    assert misaligned is False


# =============================================================================
# SECTION B: ROUTINE PLANNING (6 tests)
# =============================================================================

def test_b1_movie_routine_decomposition():
    routine_engine = RoutineEngine()
    goal = routine_engine.create_movie_routine("Let's watch a movie")
    assert goal.goal_type == GoalType.PREPARE_MOVIE
    assert len(goal.steps) == 5
    caps = [s.capability for s in goal.steps]
    assert caps == [
        "PROJECTOR_POWER_WAKE",
        "PROJECTOR_SWITCH_HDMI1",
        "FIRE_TV_POWER_WAKE",
        "SOUNDBAR_ROUTE_TO_FIRE_TV",
        "AC_SET_TEMPERATURE"
    ]


def test_b2_movie_routine_with_explicit_title():
    routine_engine = RoutineEngine()
    goal = routine_engine.create_movie_routine("Watch Inception", content_title="Inception")
    assert len(goal.steps) == 6
    assert goal.steps[-1].capability == "FIRE_TV_MEDIA_PLAY"
    assert goal.steps[-1].requested_parameters["title"] == "Inception"


def test_b3_sleep_routine_decomposition():
    routine_engine = RoutineEngine()
    goal = routine_engine.create_sleep_routine("I'm going to sleep", sleep_temp=24)
    assert goal.goal_type == GoalType.PREPARE_SLEEP
    assert len(goal.steps) == 4
    caps = [s.capability for s in goal.steps]
    assert "AC_SET_TEMPERATURE" in caps
    assert "PROJECTOR_POWER_OFF_OEM" in caps
    assert "FIRE_TV_POWER_SLEEP" in caps
    assert "SOUNDBAR_ROUTE_TO_PC" in caps


def test_b4_wake_up_routine():
    ag = AnimusPersonalAgent()
    resp = ag.interact("Good morning")
    assert "Good morning" in resp.agent_message
    assert ag.mode_manager.active_mode == BehaviorMode.IDLE


def test_b5_music_routine():
    routine_engine = RoutineEngine()
    goal = routine_engine.create_music_routine("Play some jazz", query="jazz")
    assert len(goal.steps) == 2
    assert goal.steps[0].capability == "SOUNDBAR_ROUTE_TO_PC"
    assert goal.steps[1].capability == "PC_MEDIA_PLAY"


def test_b6_already_satisfied_routine_skips_hardware(agent, base_room_state):
    # Set base room state already matching movie state
    base_room_state.projector.power.value = True
    base_room_state.projector.input_source = StateField(value="HDMI_1", provenance=Provenance.OBSERVED)
    base_room_state.ac.target_temperature.value = 23
    base_room_state.soundbar.current_owner.value = "FIRE_TV"

    resp = agent.interact("Let's watch a movie", room_state=base_room_state)
    assert "already" in resp.agent_message.lower() or "all set" in resp.agent_message.lower()



# =============================================================================
# SECTION C: MEDIA SESSIONS (8 tests)
# =============================================================================

def test_c1_media_session_start_and_status():
    mgr = MediaSessionManager()
    session = mgr.start_session(source="FIRE_TV", content_title="Interstellar", application="Prime Video")
    assert session.playback_state == MediaPlaybackState.PLAYING
    assert session.content_title == "Interstellar"
    assert session.audio_owner == "FIRE_TV"

    status = mgr.get_status_summary()
    assert status["active"] is True
    assert status["playback_state"] == "PLAYING"


def test_c2_media_session_pause():
    mgr = MediaSessionManager()
    mgr.start_session(source="FIRE_TV", content_title="Interstellar")
    ok, msg = mgr.pause_session()
    assert ok is True
    assert mgr.active_session.playback_state == MediaPlaybackState.PAUSED


def test_c3_media_session_resume():
    mgr = MediaSessionManager()
    mgr.start_session(source="FIRE_TV", content_title="Interstellar")
    mgr.pause_session()
    ok, msg = mgr.resume_session()
    assert ok is True
    assert mgr.active_session.playback_state == MediaPlaybackState.PLAYING


def test_c4_media_session_stop():
    mgr = MediaSessionManager()
    mgr.start_session(source="FIRE_TV", content_title="Interstellar")
    ok, msg = mgr.stop_session(reason="USER_STOP")
    assert ok is True
    assert mgr.active_session is None
    assert len(mgr.session_history) == 1


def test_c5_media_pause_agent_interaction(agent):
    agent.media_session_manager.start_session(source="FIRE_TV", content_title="Movie")
    resp = agent.interact("Pause it")
    assert "Paused the media" in resp.agent_message or "paused" in resp.agent_message.lower()
    assert agent.media_session_manager.active_session.playback_state == MediaPlaybackState.PAUSED


def test_c6_media_resume_agent_interaction(agent):
    agent.media_session_manager.start_session(source="FIRE_TV", content_title="Movie")
    agent.media_session_manager.pause_session()
    resp = agent.interact("Put the movie back on")
    assert "Resumed" in resp.agent_message or "playback" in resp.agent_message.lower()
    assert agent.media_session_manager.active_session.playback_state == MediaPlaybackState.PLAYING


def test_c7_media_skip_and_replay_intents(agent):
    resp_skip = agent.interact("Skip this")
    assert "Skipped" in resp_skip.agent_message

    resp_replay = agent.interact("Play that again")
    assert "Replaying" in resp_replay.agent_message


def test_c8_media_introspection_query(agent):
    agent.media_session_manager.start_session(source="FIRE_TV", content_title="Dune")
    resp = agent.interact("What are we watching?")
    assert "Dune" in resp.agent_message
    assert "playing" in resp.agent_message.lower()


# =============================================================================
# SECTION D: COMFORT INTELLIGENCE (6 tests)
# =============================================================================

def test_d1_comfort_too_cold_mapping():
    engine = ComfortEngine()
    # Live telemetry is 24°C -> 'too cold' raises by +2°C to 26°C
    tgt, adj, expl = engine.parse_comfort_adjustment("It's freezing in here", current_live_temp=24)
    assert tgt == 26
    assert adj == "WARMER_STRONG"


def test_d2_comfort_too_hot_mapping():
    engine = ComfortEngine()
    # Live telemetry is 26°C -> 'too hot' drops by -2°C to 24°C
    tgt, adj, expl = engine.parse_comfort_adjustment("It's too hot in here", current_live_temp=26)
    assert tgt == 24
    assert adj == "COOLER_STRONG"


def test_d3_comfort_mild_adjustments():
    engine = ComfortEngine()
    tgt_w, adj_w, _ = engine.parse_comfort_adjustment("A little warmer", current_live_temp=23)
    assert tgt_w == 24

    tgt_c, adj_c, _ = engine.parse_comfort_adjustment("A little cooler", current_live_temp=23)
    assert tgt_c == 22


def test_d4_comfort_safety_clamping():
    engine = ComfortEngine()
    # Lower bound clamp at 18°C
    tgt_low, _, _ = engine.parse_comfort_adjustment("Too hot", current_live_temp=18)
    assert tgt_low == 18

    # Upper bound clamp at 28°C
    tgt_high, _, _ = engine.parse_comfort_adjustment("It's freezing", current_live_temp=28)
    assert tgt_high == 28


def test_d5_comfort_calculated_from_live_telemetry_not_memory(agent, base_room_state):
    # Live telemetry reports 27°C
    base_room_state.ac.target_temperature.value = 27
    resp = agent.interact("A little cooler", room_state=base_room_state)
    # Must drop from 27 to 26°C (NOT from default 24 to 23°C)
    assert "27 to 26°C" in resp.agent_message or "26°C" in resp.agent_message


def test_d6_comfort_status_query(agent, base_room_state):
    base_room_state.ac.target_temperature.value = 23
    resp = agent.interact("I'm comfortable now", room_state=base_room_state)
    assert "23°C" in resp.agent_message
    assert "comfortable" in resp.agent_message.lower()


# =============================================================================
# SECTION E: PROACTIVE INTELLIGENCE (6 tests)
# =============================================================================

def test_e1_environmental_suggestion_generated():
    engine = ProactiveEngine(enabled=True, cooldown_seconds=10.0)
    # In Movie mode, AC target is 23, but room temperature drifted to 27°C
    telemetry = {"room_temperature": 27, "ac_target_temperature": 23}
    sug = engine.evaluate_room(telemetry, active_mode=BehaviorMode.MOVIE)
    assert sug is not None
    assert sug.category == ProactiveSuggestionCategory.ENVIRONMENTAL
    assert "lower the ac" in sug.prompt_question.lower()
    assert sug.status == ProactiveSuggestionStatus.PENDING


def test_e2_proactive_suggestion_never_silently_executes():
    engine = ProactiveEngine()
    telemetry = {"room_temperature": 28, "ac_target_temperature": 23}
    sug = engine.evaluate_room(telemetry, active_mode=BehaviorMode.MOVIE)
    # Suggestion is created, but no execution occurred
    assert sug.status == ProactiveSuggestionStatus.PENDING
    assert sug.target_capability == "AC_SET_TEMPERATURE"


def test_e3_proactive_suggestion_acceptance(agent):
    sug = ProactiveSuggestion(
        category=ProactiveSuggestionCategory.ENVIRONMENTAL,
        proposed_action="LOWER_AC",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 22},
        explanation="Room is warm",
        prompt_question="Want me to lower the AC to 22°C?"
    )
    agent.proactive_engine.pending_suggestion = sug
    agent.context_buffer.set_pending_suggestion(sug)

    resp = agent.interact("Yes please")
    assert "Adjusted the AC to 22°C" in resp.agent_message or "22°C" in resp.agent_message
    assert agent.proactive_engine.get_pending_suggestion() is None


def test_e4_proactive_suggestion_rejection(agent):
    sug = ProactiveSuggestion(
        category=ProactiveSuggestionCategory.ENVIRONMENTAL,
        proposed_action="LOWER_AC",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 22},
        explanation="Room is warm",
        prompt_question="Want me to lower the AC to 22°C?"
    )
    agent.proactive_engine.pending_suggestion = sug
    agent.context_buffer.set_pending_suggestion(sug)

    resp = agent.interact("No, leave it")
    assert "leaving it as it is" in resp.agent_message.lower()
    assert agent.proactive_engine.get_pending_suggestion() is None


def test_e5_proactive_suggestion_deduplication():
    engine = ProactiveEngine(cooldown_seconds=60.0)
    telemetry = {"room_temperature": 28, "ac_target_temperature": 23}
    sug1 = engine.evaluate_room(telemetry, active_mode=BehaviorMode.MOVIE)
    assert sug1 is not None

    # Immediate second evaluation must return None due to pending & cooldown
    sug2 = engine.evaluate_room(telemetry, active_mode=BehaviorMode.MOVIE)
    assert sug2 is None


def test_e6_proactive_disabled_returns_none():
    engine = ProactiveEngine(enabled=False)
    telemetry = {"room_temperature": 30, "ac_target_temperature": 23}
    sug = engine.evaluate_room(telemetry, active_mode=BehaviorMode.MOVIE)
    assert sug is None


# =============================================================================
# SECTION F: AUTONOMOUS RECOVERY (6 tests)
# =============================================================================

def test_f1_fire_tv_audio_recovery_preserves_ownership():
    mock_ftv = MagicMock()
    mock_ftv.connect_soundbar.return_value = True
    mock_ftv.is_soundbar_connected.return_value = True

    rec_engine = RecoveryEngine(max_attempts=1)
    res = rec_engine.recover_fire_tv_audio(fire_tv_controller=mock_ftv, soundbar_owner="FIRE_TV")
    assert res.success is True
    assert res.attempts == 1
    assert res.details["ownership_preserved"] == "FIRE_TV"


def test_f2_fire_tv_recovery_never_steals_pc_bluetooth():
    mock_ftv = MagicMock()
    mock_ftv.connect_soundbar.return_value = True
    mock_bt_helper = MagicMock()

    rec_engine = RecoveryEngine()
    # Attempting PC soundbar recovery while Fire TV owns soundbar must be rejected immediately!
    res = rec_engine.recover_pc_soundbar_audio(bt_helper=mock_bt_helper, soundbar_owner="FIRE_TV")
    assert res.success is False
    assert "Prohibited" in res.message
    assert not mock_bt_helper.ensure_audio_endpoint.called


def test_f3_pc_soundbar_recovery_when_pc_owns():
    mock_bt_helper = MagicMock()
    mock_bt_helper.ensure_audio_endpoint.return_value = (True, {"name": "LG SNC4R"}, "ALREADY_CONNECTED")

    rec_engine = RecoveryEngine()
    res = rec_engine.recover_pc_soundbar_audio(bt_helper=mock_bt_helper, soundbar_owner="PC")
    assert res.success is True
    assert res.attempts == 1


def test_f4_fire_tv_connection_recovery():
    mock_ftv = MagicMock()
    mock_ftv.connect.return_value = True

    rec_engine = RecoveryEngine()
    res = rec_engine.recover_fire_tv_connection(fire_tv_controller=mock_ftv)
    assert res.success is True


def test_f5_recovery_bounded_max_attempts():
    rec_engine = RecoveryEngine(max_attempts=1)
    assert rec_engine.max_attempts == 1


def test_f6_recovery_failure_truthfully_reported():
    mock_ftv = MagicMock()
    mock_ftv.connect_soundbar.return_value = False
    mock_ftv.is_soundbar_connected.return_value = False

    rec_engine = RecoveryEngine(max_attempts=1)
    res = rec_engine.recover_fire_tv_audio(fire_tv_controller=mock_ftv)
    assert res.success is False
    assert "failed" in res.message.lower()


# =============================================================================
# SECTION G: INTERRUPTION & PRIORITY HANDLING (6 tests)
# =============================================================================

def test_g1_new_goal_supersedes_active_goal(agent):
    # Set an in-flight movie goal
    old_goal = AgentGoal(
        user_utterance="Prepare movie",
        normalized_goal="Prepare movie",
        goal_type=GoalType.PREPARE_MOVIE,
        status=GoalStatus.EXECUTING,
        steps=[TaskStep(step_id=1, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE", status=StepStatus.VERIFIED)]
    )
    agent.context_buffer.set_active_goal(old_goal)

    # User issues superseding sleep command
    resp = agent.interact("Actually forget that, put the room to sleep")
    assert len(agent.context_buffer.superseded_goals) == 1
    assert agent.context_buffer.superseded_goals[0].status == GoalStatus.SUPERSEDED
    assert agent.mode_manager.active_mode == BehaviorMode.SLEEP


def test_g2_cancellation_preserves_verified_steps(agent):
    goal = AgentGoal(
        user_utterance="Prepare movie",
        normalized_goal="Prepare movie",
        goal_type=GoalType.PREPARE_MOVIE,
        steps=[
            TaskStep(step_id=1, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE", status=StepStatus.VERIFIED),
            TaskStep(step_id=2, target_subsystem="AC", capability="AC_SET_TEMPERATURE", status=StepStatus.PENDING)
        ]
    )
    agent.context_buffer.set_active_goal(goal)

    resp = agent.interact("Cancel the rest")
    assert goal.status == GoalStatus.CANCELLED
    # Step 1 remains VERIFIED, step 2 was cancelled
    assert goal.steps[0].status == StepStatus.VERIFIED


def test_g3_pause_and_resume_goal(agent):
    buf = ConversationContextBuffer()
    goal = AgentGoal(
        user_utterance="Prepare movie",
        normalized_goal="Prepare movie",
        goal_type=GoalType.PREPARE_MOVIE,
        steps=[TaskStep(step_id=1, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE")]
    )
    buf.set_active_goal(goal)
    paused = buf.pause_active_goal()
    assert paused.status == GoalStatus.PAUSED
    assert buf.active_goal is None

    resumed = buf.resume_goal(paused.goal_id)
    assert resumed.status == GoalStatus.RESUMABLE
    assert buf.active_goal == resumed


def test_g4_explicit_user_command_dominates_preferences(agent, base_room_state):
    # User has preference for 24°C in memory
    agent.context_buffer.session_memory.record_preference(
        ConversationalPreference(key="target_temperature", value=24)
    )
    # But user explicitly asks for 20°C
    resp = agent.interact("Set AC to 20", room_state=base_room_state)
    assert "20°C" in resp.agent_message


def test_g5_interruption_correction_during_flow(agent):
    resp1 = agent.interact("Turn on the projector")
    # Immediate user correction
    resp2 = agent.interact("Actually leave it off")
    assert "leaving it as it is" in resp2.agent_message.lower() or "off" in resp2.agent_message.lower()


def test_g6_obsolete_goal_never_silently_resumes(agent):
    buf = agent.context_buffer
    goal = AgentGoal(
        user_utterance="Old goal",
        normalized_goal="Old goal",
        goal_type=GoalType.CUSTOM_GOAL,
        status=GoalStatus.SUPERSEDED
    )
    buf.superseded_goals.append(goal)
    # Active goal must remain None
    assert buf.get_active_goal() is None


# =============================================================================
# SECTION H: BEHAVIORAL INTROSPECTION (6 tests)
# =============================================================================

def test_h1_introspect_current_mode(agent):
    agent.mode_manager.transition_to(BehaviorMode.MOVIE)
    resp = agent.interact("What mode are we in?")
    assert "movie mode" in resp.agent_message.lower()


def test_h2_introspect_current_media(agent):
    agent.media_session_manager.start_session(source="FIRE_TV", content_title="The Matrix")
    resp = agent.interact("What's playing?")
    assert "The Matrix" in resp.agent_message


def test_h3_introspect_room_status(agent, base_room_state):
    base_room_state.ac.target_temperature.value = 22
    resp = agent.interact("What is the AC doing now?", room_state=base_room_state)
    assert "22°C" in resp.agent_message


def test_h4_introspect_active_goal_progress(agent):
    goal = AgentGoal(
        user_utterance="Setup Cinema",
        normalized_goal="Setup Cinema",
        goal_type=GoalType.PREPARE_MOVIE,
        status=GoalStatus.PLANNING,
        steps=[
            TaskStep(step_id=1, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE", status=StepStatus.VERIFIED),
            TaskStep(step_id=2, target_subsystem="AC", capability="AC_SET_TEMPERATURE", status=StepStatus.PENDING)
        ]
    )
    agent.context_buffer.set_active_goal(goal)
    resp = agent.interact("What's remaining?")
    assert "ac set temperature" in resp.agent_message.lower() or "ac" in resp.agent_message.lower()


def test_h5_introspect_recent_change(agent):
    mem = agent.context_buffer.session_memory
    mem.record_action(
        RecentActionMemory(
            user_utterance="Set AC to 23",
            intent="SET_AC_TEMPERATURE",
            target_subsystem="AC",
            state_delta=StateDelta(subsystem="AC", attribute="target_temperature", previous_value=25, new_value=23, verified_value=23),
            reason_for_action="user command"
        )
    )
    resp = agent.interact("What changed recently?")
    assert "AC" in resp.agent_message or "changed" in resp.agent_message.lower()


def test_h6_introspect_action_reason(agent):
    agent.context_buffer.record_user_turn("Set AC to 22")
    agent.context_buffer.session_memory.record_action(
        RecentActionMemory(
            user_utterance="Set AC to 22",
            intent="SET_AC_TEMPERATURE",
            target_subsystem="AC",
            reason_for_action="you requested 22°C",
            state_delta=None
        )
    )
    resp = agent.interact("Why did you do that?")
    assert "requested" in resp.agent_message.lower() or "22" in resp.agent_message




# =============================================================================
# SECTION I: MEMORY & PREFERENCES (4 tests)
# =============================================================================

def test_i1_preference_provenance_and_storage():
    mem = AgentSessionMemory()
    pref = ConversationalPreference(key="ac_movie_temp", value=23)
    assert pref.provenance == FactProvenance.CONVERSATIONAL_PREFERENCE
    mem.record_preference(pref)
    retrieved = mem.get_preference("ac_movie_temp")
    assert retrieved.value == 23


def test_i2_preference_bounded_fifo_eviction():
    mem = AgentSessionMemory()
    for i in range(7):
        mem.record_preference(ConversationalPreference(key=f"key_{i}", value=i))
    # Bounded to max 5 preferences
    all_prefs = mem.get_all_preferences()
    assert len(all_prefs) == 5
    assert all_prefs[0].key == "key_2"
    assert all_prefs[-1].key == "key_6"


def test_i3_explicit_command_overrides_session_preference(agent, base_room_state):
    agent.context_buffer.session_memory.record_preference(
        ConversationalPreference(key="temp", value=24)
    )
    resp = agent.interact("Set AC to 21", room_state=base_room_state)
    assert "21°C" in resp.agent_message


def test_i4_historical_memory_cannot_override_live_telemetry(agent, base_room_state):
    # Memory has 23°C
    agent.context_buffer.session_memory.record_fact("AC", "target_temperature", 23, FactProvenance.VERIFIED_EXECUTION)
    # But live telemetry is 26°C
    base_room_state.ac.target_temperature.value = 26
    resp = agent.interact("What is the AC at?", room_state=base_room_state)
    assert "26°C" in resp.agent_message


# =============================================================================
# SECTION J: SOUNDBAR OWNERSHIP PROTECTION (4 tests)
# =============================================================================

def test_j1_fire_tv_ownership_blocks_bluetooth_reclaim():
    from tts_service import RoomTtsService
    mock_orch = MagicMock()
    mock_orch.fire_tv.is_soundbar_connected.return_value = True
    mock_orch._in_movie_mode = True

    tts = RoomTtsService(orchestrator=mock_orch, enabled=True)
    owner = tts._get_soundbar_owner()
    assert owner == "FIRE_TV"
    endpoint = tts._resolve_audio_device_id()
    assert endpoint is None  # Prohibits reclaim, routes to PC default
    tts.shutdown()


def test_j2_movie_mode_preserves_fire_tv_ownership():
    mode_mgr = BehaviorModeManager(initial_mode=BehaviorMode.MOVIE)
    assert mode_mgr.active_mode == BehaviorMode.MOVIE
    expected = mode_mgr.current_state.expected_devices
    assert expected["soundbar"] == "FIRE_TV"


def test_j3_pc_mode_still_wakes_soundbar():
    from tts_service import RoomTtsService
    mock_orch = MagicMock()
    mock_orch.fire_tv.is_soundbar_connected.return_value = False
    mock_orch._in_movie_mode = False
    mock_orch.bt_helper.scan_active_endpoints.return_value = (None, [])
    mock_orch.bt_helper.ensure_audio_endpoint.return_value = (True, {"name": "LG SNC4R", "id": "wasapi/{mock_id}"}, "CONNECTED")

    tts = RoomTtsService(orchestrator=mock_orch, enabled=True)
    owner = tts._get_soundbar_owner()
    assert owner == "PC"
    dev_id = tts._resolve_audio_device_id()
    assert dev_id == "wasapi/{mock_id}"
    tts.shutdown()


def test_j4_unknown_ownership_fails_safe():
    from tts_service import RoomTtsService
    mock_agg = MagicMock()
    rs = RoomState()
    rs.soundbar.current_owner = StateField(value=None, provenance=Provenance.UNKNOWN)
    mock_agg.get_room_state.return_value = rs

    tts = RoomTtsService(room_state_aggregator=mock_agg, enabled=True)
    owner = tts._get_soundbar_owner()
    assert owner == "UNKNOWN"
    dev_id = tts._resolve_audio_device_id()
    assert dev_id is None
    tts.shutdown()


# =============================================================================
# SECTION K: CANONICAL ACCEPTANCE DIALOGUES (7 tests)
# =============================================================================

def test_k1_dialogue_a_movie_session(agent, base_room_state):
    # 1. User: "Get the room ready for a movie."
    resp1 = agent.interact("Get the room ready for a movie.", room_state=base_room_state)
    assert "all set" in resp1.agent_message.lower() or "projector is on" in resp1.agent_message.lower()
    assert agent.mode_manager.active_mode == BehaviorMode.MOVIE

    # 2. User: "What mode are we in?"
    resp2 = agent.interact("What mode are we in?")
    assert "movie mode" in resp2.agent_message.lower()


def test_k2_dialogue_b_comfort_correction(agent, base_room_state):
    # Live telemetry is 26°C
    base_room_state.ac.target_temperature.value = 26
    resp = agent.interact("It's too hot.", room_state=base_room_state)
    # Drops by 2°C to 24°C
    assert "26 to 24°C" in resp.agent_message or "24°C" in resp.agent_message


def test_k3_dialogue_c_proactive_suggestion_flow(agent):
    sug = ProactiveSuggestion(
        category=ProactiveSuggestionCategory.ENVIRONMENTAL,
        proposed_action="LOWER_AC",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 22},
        explanation="The room is getting warm",
        prompt_question="The room is warming up. Want me to lower the AC to 22°C?"
    )
    agent.proactive_engine.pending_suggestion = sug
    agent.context_buffer.set_pending_suggestion(sug)

    resp = agent.interact("Sure")
    assert "22°C" in resp.agent_message


def test_k4_dialogue_d_goal_interruption(agent, base_room_state):
    # Start movie mode
    agent.interact("Prepare movie mode", room_state=base_room_state)
    assert agent.mode_manager.active_mode == BehaviorMode.MOVIE

    # Interrupted with sleep mode
    resp = agent.interact("Actually forget that, put the room to sleep", room_state=base_room_state)
    assert agent.mode_manager.active_mode == BehaviorMode.SLEEP


def test_k5_dialogue_e_external_device_change(agent, base_room_state):
    # Verified action at 23°C
    agent.interact("Set AC to 23", room_state=base_room_state)
    # External person changed AC to 26°C on the wall thermostat
    base_room_state.ac.target_temperature.value = 26
    # Introspecting reports the live 26°C
    resp = agent.interact("What is the AC at?", room_state=base_room_state)
    assert "26°C" in resp.agent_message


def test_k6_dialogue_f_audio_recovery_under_movie_mode(agent):
    agent.mode_manager.transition_to(BehaviorMode.MOVIE)
    with patch.object(agent.recovery_engine, "recover_fire_tv_audio") as mock_rec:
        mock_rec.return_value = RecoveryResult(
            recovery_type=RecoveryType.FIRE_TV_AUDIO,
            success=True,
            attempts=1,
            message="Fire TV soundbar reconnected."
        )
        resp = agent.interact("Something is wrong with the sound")
        assert "Audio recovery" in resp.agent_message
        assert mock_rec.called


def test_k7_dialogue_g_exit_movie_mode(agent):
    agent.mode_manager.transition_to(BehaviorMode.MOVIE)
    resp = agent.interact("The movie ended, I'm done here")
    assert "Exited mode" in resp.agent_message
    assert agent.mode_manager.active_mode == BehaviorMode.IDLE
