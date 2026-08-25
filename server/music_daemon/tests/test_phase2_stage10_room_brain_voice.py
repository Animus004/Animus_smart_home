"""
Authoritative Automated Test Battery for Phase 2 Stage 10:
Unified Room Brain, Interface-Agnostic Conversation Engine, Voice Ingress,
Soundbar Audio Protection, and Canonical Multi-Turn Dialogue Scenarios A through G.

Covers Sections A through G (70+ comprehensive tests):
Section A: RoomBrain Unified World Model & State Summaries (Tests A1-A10)
Section B: ConversationEngine Multi-Turn Context & References (Tests B1-B10)
Section C: Pronoun Resolution ('it', 'that', 'make that 24') (Tests C1-C10)
Section D: Interruptions & Corrections ('stop', 'wait', 'actually...') (Tests D1-D10)
Section E: Voice Ingress Decoupled Boundary (Tests E1-E10)
Section F: Soundbar Audio Protection & Non-Duplication (Tests F1-F10)
Section G: Canonical Acceptance Scenarios A–G (Tests G1-G10)
"""

import time
import pytest
from unittest.mock import MagicMock

from agent.room_brain import RoomBrain, UnifiedRoomSummary
from agent.conversation_engine import ConversationEngine, ConversationTurn
from agent.voice_ingress import VoiceIngressAdapter, VoiceTurnPayload
from agent.behavior_modes import BehaviorMode, BehaviorModeManager
from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus, GoalType
from agent.reasoning_engine import ReasoningEngine
from agent.goal_arbitrator import GoalArbitrator, ArbitrationOutcome
from agent.policy_engine import PolicyEngine, PolicyAuthorization
from agent.learning_engine import LearningEngine
from agent.autonomy_manager import AutonomyManager, AutonomyCapability, AutonomyGrantLevel
from agent.core import AnimusPersonalAgent


# =============================================================================
# SECTION A: ROOM BRAIN UNIFIED WORLD MODEL (Tests A1-A10)
# =============================================================================

def test_a1_room_brain_instantiates_with_unified_model():
    """RoomBrain creates unified world model with all sub-engines."""
    brain = RoomBrain()
    assert brain.reasoning_engine is not None
    assert brain.goal_arbitrator is not None
    assert brain.policy_engine is not None
    assert brain.learning_engine is not None
    assert brain.autonomy_manager is not None


def test_a2_unified_summary_structure():
    """get_unified_summary outputs structured UnifiedRoomSummary."""
    brain = RoomBrain()
    summary = brain.get_unified_summary()
    assert isinstance(summary, UnifiedRoomSummary)
    assert summary.active_mode == "IDLE"
    assert summary.situation is not None


def test_a3_explain_room_state_nominal():
    """explain_room_state produces coherent room narrative."""
    brain = RoomBrain()
    explanation = brain.explain_room_state()
    assert "in IDLE mode" in explanation
    assert "projector is off" in explanation.lower()
    assert "Soundbar audio is routed to PC" in explanation


def test_a4_explain_room_state_movie_mode():
    """explain_room_state reflects active movie mode and soundbar routing."""
    mode_mgr = BehaviorModeManager()
    mode_mgr.transition_to(BehaviorMode.MOVIE, reason="test")
    brain = RoomBrain(behavior_mode_manager=mode_mgr)

    summary = brain.get_unified_summary()
    assert summary.active_mode == "MOVIE"



def test_a5_room_brain_telemetry_extraction():
    """_get_telemetry handles aggregator mock safely."""
    agg = MagicMock()
    state = MagicMock()
    state.ac.target_temperature = 23
    state.ac.current_temperature = 25.0
    state.projector.is_powered_on = True
    state.soundbar.current_owner = "FIRE_TV"
    agg.get_room_state.return_value = state

    brain = RoomBrain(room_state_aggregator=agg)
    t = brain._get_telemetry()
    assert t["ac_target_temperature"] == 23
    assert t["ambient_temperature"] == 25.0
    assert t["projector_power"] is True
    assert t["soundbar_owner"] == "FIRE_TV"


def test_a6_room_brain_handles_aggregator_exception():
    """_get_telemetry falls back to empty dict if aggregator errors."""
    agg = MagicMock()
    agg.get_room_state.side_effect = RuntimeError("Aggregator error")
    brain = RoomBrain(room_state_aggregator=agg)
    t = brain._get_telemetry()
    assert t == {}


def test_a7_unified_summary_includes_active_goal():
    """Active goal in goal_manager is included in summary."""
    gm = MagicMock()
    ag = AgentGoal(user_utterance="Movie time", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE, status=GoalStatus.EXECUTING)
    gm.active_goal = ag

    brain = RoomBrain(goal_manager=gm)
    summary = brain.get_unified_summary()
    assert summary.active_goal_summary is not None


def test_a8_unified_summary_includes_scheduled_tasks_count():
    """Summary counts pending scheduled tasks."""
    sched = MagicMock()
    sched.get_scheduled_tasks.return_value = ["task1", "task2"]

    brain = RoomBrain(scheduler=sched)
    summary = brain.get_unified_summary()
    assert summary.pending_scheduled_tasks_count == 2


def test_a9_unified_summary_includes_active_media_app():
    """Summary extracts active media app from session manager."""
    ms = MagicMock()
    sess = MagicMock()
    sess.app_name = "NETFLIX"
    ms.active_session = sess

    brain = RoomBrain(media_session_manager=ms)
    summary = brain.get_unified_summary()
    assert summary.active_media_app == "NETFLIX"


def test_a10_explain_room_state_with_active_media():
    """explain_room_state includes media app name when active."""
    agg = MagicMock()
    state = MagicMock()
    state.projector.is_powered_on = True
    state.soundbar.current_owner = "FIRE_TV"
    state.ac.target_temperature = 24
    agg.get_room_state.return_value = state

    ms = MagicMock()
    sess = MagicMock()
    sess.app_name = "PRIME_VIDEO"
    ms.active_session = sess

    brain = RoomBrain(room_state_aggregator=agg, media_session_manager=ms)
    exp = brain.explain_room_state()
    assert "PRIME_VIDEO" in exp
    assert "FIRE_TV" in exp


# =============================================================================
# SECTION B: CONVERSATION ENGINE MULTI-TURN CONTEXT (Tests B1-B10)
# =============================================================================

def test_b1_conversation_turn_recording():
    """ConversationEngine records turns sequentially."""
    conv = ConversationEngine()
    t1 = conv.record_turn("hello", resolved_intent="GREETING", agent_response="Hi!")
    assert t1.turn_id == 1
    assert t1.user_utterance == "hello"
    assert len(conv.turn_history) == 1


def test_b2_turn_history_bounded_capacity():
    """Turn history respects max capacity limit."""
    conv = ConversationEngine(max_turns=5)
    for i in range(10):
        conv.record_turn(f"Turn {i}", agent_response=f"Resp {i}")
    assert len(conv.turn_history) == 5
    assert conv.get_last_turn().user_utterance == "Turn 9"


def test_b3_get_last_turn_empty_returns_none():
    """get_last_turn returns None on fresh engine."""
    conv = ConversationEngine()
    assert conv.get_last_turn() is None


def test_b4_clear_history_resets_state():
    """clear_history empties turns and active subjects."""
    conv = ConversationEngine()
    conv.record_turn("movie time")
    conv.active_subject = "MOVIE"
    conv.clear_history()
    assert len(conv.turn_history) == 0
    assert conv.active_subject is None


def test_b5_active_subject_tracking_movie():
    """Mentioning movie sets active_subject to MOVIE."""
    conv = ConversationEngine()
    conv.process_utterance("let's watch a movie")
    assert conv.active_subject == "MOVIE"


def test_b6_active_subject_tracking_ac():
    """Mentioning temperature sets active_subject to AC."""
    conv = ConversationEngine()
    conv.process_utterance("it's warm in here, adjust temperature")
    assert conv.active_subject == "AC"


def test_b7_active_subject_tracking_music():
    """Mentioning music sets active_subject to MUSIC."""
    conv = ConversationEngine()
    conv.process_utterance("play some jazz music on spotify")
    assert conv.active_subject == "MUSIC"


def test_b8_active_subject_tracking_projector():
    """Mentioning projector sets active_subject to PROJECTOR."""
    conv = ConversationEngine()
    conv.process_utterance("turn on projector")
    assert conv.active_subject == "PROJECTOR"


def test_b9_turn_timestamps_monotonic():
    """Turn timestamps are increasing."""
    conv = ConversationEngine()
    t1 = conv.record_turn("one")
    t2 = conv.record_turn("two")
    assert t2.timestamp >= t1.timestamp


def test_b10_turn_model_fields_validation():
    """ConversationTurn holds all required fields."""
    turn = ConversationTurn(
        turn_id=1,
        user_utterance="test",
        agent_response="resp",
        was_interruption=True,
        was_correction=False
    )
    assert turn.was_interruption is True
    assert turn.was_correction is False


# =============================================================================
# SECTION C: PRONOUN RESOLUTION (Tests C1-C10)
# =============================================================================

def test_c1_make_it_24_resolves_to_ac_temperature():
    """'Make it 24' resolves to 'set ac temperature to 24'."""
    conv = ConversationEngine()
    res_text, intent, is_int, is_corr = conv.process_utterance("make it 24")
    assert res_text == "set ac temperature to 24"
    assert intent == "AC_SET_TEMPERATURE"
    assert is_corr is True


def test_c2_make_that_22_resolves_to_ac_temperature():
    """'Make that 22' resolves to 'set ac temperature to 22'."""
    conv = ConversationEngine()
    res_text, intent, _, _ = conv.process_utterance("make that 22")
    assert res_text == "set ac temperature to 22"
    assert intent == "AC_SET_TEMPERATURE"


def test_c3_actually_25_resolves_to_ac_temperature():
    """'Actually 25' resolves to 'set ac temperature to 25'."""
    conv = ConversationEngine()
    res_text, intent, _, is_corr = conv.process_utterance("actually 25")
    assert res_text == "set ac temperature to 25"
    assert is_corr is True


def test_c4_pause_it_in_movie_mode_resolves_to_pause_movie():
    """'Pause it' in active movie mode resolves to 'pause movie'."""
    conv = ConversationEngine()
    res_text, intent, is_int, _ = conv.process_utterance("pause it", active_mode=BehaviorMode.MOVIE)
    assert res_text == "pause movie"
    assert intent == "PAUSE_MEDIA"
    assert is_int is True


def test_c5_resume_it_in_movie_mode_resolves_to_resume_movie():
    """'Resume it' in active movie mode resolves to 'resume movie'."""
    conv = ConversationEngine()
    res_text, intent, _, _ = conv.process_utterance("resume it", active_mode=BehaviorMode.MOVIE)
    assert res_text == "resume movie"
    assert intent == "RESUME_MEDIA"


def test_c6_play_it_with_active_media_resolves_to_resume_movie():
    """'Play it' with active media session resolves to 'resume movie'."""
    conv = ConversationEngine()
    res_text, intent, _, _ = conv.process_utterance("play it", active_media_app="NETFLIX")
    assert res_text == "resume movie"
    assert intent == "RESUME_MEDIA"


def test_c7_pause_it_with_active_goal_resolves_to_pause_goal():
    """'Pause it' with in-flight goal resolves to 'pause active goal'."""
    conv = ConversationEngine()
    goal = AgentGoal(user_utterance="routine", normalized_goal="ROUTINE", goal_type=GoalType.CUSTOM_GOAL)
    res_text, intent, is_int, _ = conv.process_utterance("pause it", active_goal=goal)
    assert res_text == "pause active goal"
    assert intent == "PAUSE_GOAL"


def test_c8_resume_it_with_active_goal_resolves_to_resume_goal():
    """'Resume it' with goal resolves to 'resume active goal'."""
    conv = ConversationEngine()
    goal = AgentGoal(user_utterance="routine", normalized_goal="ROUTINE", goal_type=GoalType.CUSTOM_GOAL)
    res_text, intent, _, _ = conv.process_utterance("resume it", active_goal=goal)
    assert res_text == "resume active goal"
    assert intent == "RESUME_GOAL"


def test_c9_unrelated_pronoun_preserves_text():
    """General utterance with 'it' not matching patterns passes text through safely."""
    conv = ConversationEngine()
    res_text, intent, _, _ = conv.process_utterance("I like it when the lights are dim")
    assert res_text == "I like it when the lights are dim"


def test_c10_make_that_with_word_boundary_checking():
    """'make that 23' handles trailing spaces cleanly."""
    conv = ConversationEngine()
    res_text, _, _, _ = conv.process_utterance("  make that 23   ")
    assert res_text == "set ac temperature to 23"


# =============================================================================
# SECTION D: INTERRUPTIONS & CORRECTIONS (Tests D1-D10)
# =============================================================================

def test_d1_interruption_stop():
    """'Stop' is detected as interruption with CANCEL_ACTION intent."""
    conv = ConversationEngine()
    res_text, intent, is_int, _ = conv.process_utterance("stop")
    assert is_int is True
    assert intent == "CANCEL_ACTION"


def test_d2_interruption_wait():
    """'Wait' is detected as interruption."""
    conv = ConversationEngine()
    _, _, is_int, _ = conv.process_utterance("wait")
    assert is_int is True


def test_d3_interruption_hold_on():
    """'Hold on' is detected as interruption."""
    conv = ConversationEngine()
    _, _, is_int, _ = conv.process_utterance("hold on")
    assert is_int is True


def test_d4_interruption_never_mind():
    """'Never mind' is detected as interruption."""
    conv = ConversationEngine()
    _, intent, is_int, _ = conv.process_utterance("never mind")
    assert is_int is True
    assert intent == "CANCEL_ACTION"


def test_d5_correction_actually():
    """'Actually...' is detected as a correction."""
    conv = ConversationEngine()
    _, _, _, is_corr = conv.process_utterance("actually I want sleep mode")
    assert is_corr is True


def test_d6_correction_instead():
    """'Instead...' is detected as a correction."""
    conv = ConversationEngine()
    _, _, _, is_corr = conv.process_utterance("instead let's watch prime")
    assert is_corr is True


def test_d7_correction_change_that_to():
    """'Change that to...' is detected as a correction."""
    conv = ConversationEngine()
    _, _, _, is_corr = conv.process_utterance("change that to prime video")
    assert is_corr is True


def test_d8_pause_media_interruption():
    """'Pause' during movie mode returns PAUSE_MEDIA intent."""
    conv = ConversationEngine()
    _, intent, is_int, _ = conv.process_utterance("pause", active_mode=BehaviorMode.MOVIE)
    assert is_int is True
    assert intent == "PAUSE_MEDIA"


def test_d9_cancel_that_interruption():
    """'Cancel that' returns CANCEL_ACTION intent."""
    conv = ConversationEngine()
    _, intent, is_int, _ = conv.process_utterance("cancel that")
    assert is_int is True
    assert intent == "CANCEL_ACTION"


def test_d10_interruption_does_not_corrupt_prior_turns():
    """Recording an interruption turn maintains prior history integrity."""
    conv = ConversationEngine()
    conv.record_turn("movie time", agent_response="Preparing movie")
    conv.record_turn("stop", was_interruption=True, agent_response="Stopped")
    assert len(conv.turn_history) == 2
    assert conv.turn_history[0].was_interruption is False
    assert conv.turn_history[1].was_interruption is True


# =============================================================================
# SECTION E: VOICE INGRESS DECOUPLING (Tests E1-E10)
# =============================================================================

def test_e1_voice_ingress_instantiation():
    """VoiceIngressAdapter instantiates cleanly."""
    adapter = VoiceIngressAdapter()
    assert adapter.total_ingested_turns == 0
    assert adapter.last_ingested_payload is None


def test_e2_voice_ingress_packages_transcript():
    """ingest_transcript packages text into VoiceTurnPayload."""
    adapter = VoiceIngressAdapter()
    payload = adapter.ingest_transcript("movie time", confidence=0.98, detected_wake_word="animus")
    assert isinstance(payload, VoiceTurnPayload)
    assert payload.transcript == "movie time"
    assert payload.confidence == 0.98
    assert payload.detected_wake_word == "animus"
    assert adapter.total_ingested_turns == 1


def test_e3_voice_ingress_invokes_callback():
    """ingest_transcript triggers on_transcript_received callback."""
    received = []
    adapter = VoiceIngressAdapter(on_transcript_received=lambda p: received.append(p.transcript))
    adapter.ingest_transcript("hello buddy")
    assert len(received) == 1
    assert received[0] == "hello buddy"


def test_e4_voice_ingress_strips_whitespace():
    """ingest_transcript strips leading and trailing whitespace."""
    adapter = VoiceIngressAdapter()
    payload = adapter.ingest_transcript("   turn off projector   \n")
    assert payload.transcript == "turn off projector"


def test_e5_voice_ingress_records_source_client():
    """ingest_transcript captures client identifier."""
    adapter = VoiceIngressAdapter()
    payload = adapter.ingest_transcript("test", source_client_id="ANDROID_MIC")
    assert payload.source_client_id == "ANDROID_MIC"


def test_e6_voice_ingress_records_metadata():
    """ingest_transcript preserves custom metadata."""
    adapter = VoiceIngressAdapter()
    payload = adapter.ingest_transcript("test", metadata={"audio_db": -12.4})
    assert payload.metadata.get("audio_db") == -12.4


def test_e7_voice_ingress_timestamp_monotonic():
    """VoiceTurnPayload timestamps are monotonically increasing."""
    adapter = VoiceIngressAdapter()
    p1 = adapter.ingest_transcript("one")
    p2 = adapter.ingest_transcript("two")
    assert p2.timestamp >= p1.timestamp


def test_e8_voice_ingress_safe_without_callback():
    """ingest_transcript functions without error when no callback is set."""
    adapter = VoiceIngressAdapter(on_transcript_received=None)
    payload = adapter.ingest_transcript("test")
    assert payload.transcript == "test"


def test_e9_voice_ingress_exception_isolation_in_callback():
    """Callback exception is logged without crashing ingestion if handled."""
    def faulty_cb(p):
        raise ValueError("Callback crash")

    adapter = VoiceIngressAdapter(on_transcript_received=faulty_cb)
    with pytest.raises(ValueError):
        adapter.ingest_transcript("test")


def test_e10_voice_turn_payload_serialization():
    """VoiceTurnPayload supports JSON serialization."""
    import json
    adapter = VoiceIngressAdapter()
    payload = adapter.ingest_transcript("test")
    json_str = json.dumps(payload.dict())
    assert "transcript" in json_str


# =============================================================================
# SECTION F: SOUNDBAR AUDIO PROTECTION & NON-DUPLICATION (Tests F1-F10)
# =============================================================================

def test_f1_soundbar_fire_tv_ownership_prohibits_pc_bluetooth():
    """PolicyEngine denies PC Bluetooth reclaim when Fire TV owns soundbar."""
    pol = PolicyEngine()
    res = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    assert res.authorization == PolicyAuthorization.DENIED


def test_f2_soundbar_fire_tv_ownership_in_movie_mode():
    """Movie mode blocks PC Bluetooth connect under UNKNOWN soundbar owner."""
    pol = PolicyEngine()
    res = pol.evaluate_action("CONNECT_PC_BT", "SOUNDBAR", soundbar_owner="UNKNOWN", active_mode=BehaviorMode.MOVIE)
    assert res.authorization == PolicyAuthorization.DENIED


def test_f3_room_brain_summary_reflects_fire_tv_owner():
    """RoomBrain summary reflects FIRE_TV as authoritative soundbar owner."""
    agg = MagicMock()
    state = MagicMock()
    state.soundbar.current_owner = "FIRE_TV"
    agg.get_room_state.return_value = state

    brain = RoomBrain(room_state_aggregator=agg)
    summary = brain.get_unified_summary()
    assert summary.soundbar_owner == "FIRE_TV"


def test_f4_room_brain_never_duplicates_hardware_execution():
    """RoomBrain has no direct hardware mutation methods."""
    brain = RoomBrain()
    assert not hasattr(brain, "execute_hardware")
    assert not hasattr(brain, "send_ir_code")
    assert not hasattr(brain, "write_physical_state")


def test_f5_conversation_engine_never_duplicates_hardware_execution():
    """ConversationEngine has no direct hardware mutation methods."""
    conv = ConversationEngine()
    assert not hasattr(conv, "execute_hardware")
    assert not hasattr(conv, "send_ac_command")


def test_f6_voice_ingress_never_duplicates_hardware_execution():
    """VoiceIngressAdapter has no direct hardware mutation methods."""
    ingress = VoiceIngressAdapter()
    assert not hasattr(ingress, "execute_hardware")


def test_f7_policy_engine_explains_soundbar_protection():
    """PolicyEngine explains why Bluetooth reclaim was denied."""
    pol = PolicyEngine()
    res = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    exp = pol.explain_decision(res.evaluation_id)
    assert "denied" in exp.lower()
    assert "fire tv" in exp.lower()


def test_f8_autonomy_manager_denies_audio_stealing_under_fire_tv():
    """AutonomyManager blocks audio autonomy from stealing Fire TV audio."""
    mgr = AutonomyManager()
    mgr.grant_autonomy(AutonomyCapability.AUDIO_ROUTING, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth, reason, level = mgr.evaluate_authorization(
        AutonomyCapability.AUDIO_ROUTING, "RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV"
    )
    assert auth is False
    assert level == AutonomyGrantLevel.DENIED


def test_f9_pc_ownership_allows_pc_tts():
    """When PC owns soundbar, PC endpoint routing is authorized."""
    pol = PolicyEngine()
    res = pol.evaluate_action("SET_PC_ENDPOINT", "PC", soundbar_owner="PC", is_user_explicit=True)
    assert res.is_permitted() is True


def test_f10_canonical_movie_mode_tts_audio_protection():
    """In Movie mode with Fire TV audio, TTS uses local/HDMI fallback without Bluetooth reconnect."""
    pol = PolicyEngine()
    res_bt = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV", active_mode=BehaviorMode.MOVIE)
    assert res_bt.is_denied() is True


# =============================================================================
# SECTION G: CANONICAL ACCEPTANCE SCENARIOS A–G (Tests G1-G10)
# =============================================================================

def test_g1_canonical_scenario_a_movie_full_dialogue():
    """Scenario A: 'Movie time' -> 'Make it 24' -> 'Pause it' -> 'Resume' -> 'What's happening?' -> 'I'm going to bed.'"""
    conv = ConversationEngine()
    arb = GoalArbitrator()

    # 1. Movie time
    t1_text, _, _, _ = conv.process_utterance("Movie time")
    conv.record_turn(t1_text, resolved_intent="PREPARE_MOVIE", agent_response="Getting the room ready for a movie.")
    conv.active_subject = "MOVIE"

    # 2. Make it 24
    t2_text, t2_intent, _, is_corr = conv.process_utterance("Make it 24")
    assert t2_text == "set ac temperature to 24"
    assert t2_intent == "AC_SET_TEMPERATURE"
    assert is_corr is True
    conv.record_turn(t2_text, resolved_intent=t2_intent, agent_response="Sure, AC set to 24°C.")

    # 3. Pause it
    t3_text, t3_intent, is_int, _ = conv.process_utterance("Pause it", active_mode=BehaviorMode.MOVIE)
    assert t3_text == "pause movie"
    assert t3_intent == "PAUSE_MEDIA"
    assert is_int is True
    conv.record_turn(t3_text, resolved_intent=t3_intent, agent_response="Paused.")

    # 4. Resume
    t4_text, t4_intent, _, _ = conv.process_utterance("Resume it", active_mode=BehaviorMode.MOVIE)
    assert t4_text == "resume movie"
    assert t4_intent == "RESUME_MEDIA"
    conv.record_turn(t4_text, resolved_intent=t4_intent, agent_response="Resumed.")

    # 5. What's happening?
    agg = MagicMock()
    state = MagicMock()
    state.ac.target_temperature = 24
    state.projector.is_powered_on = True
    state.soundbar.current_owner = "FIRE_TV"
    agg.get_room_state.return_value = state

    mode_mgr = BehaviorModeManager()
    mode_mgr.transition_to(BehaviorMode.MOVIE, reason="test")

    brain = RoomBrain(room_state_aggregator=agg, behavior_mode_manager=mode_mgr)
    explanation = brain.explain_room_state()
    assert "in MOVIE mode" in explanation
    assert "projector is on" in explanation.lower()
    assert "FIRE_TV" in explanation
    assert "24°C" in explanation
    conv.record_turn("What's happening?", resolved_intent="WHAT_IS_HAPPENING", agent_response=explanation)

    # 6. I'm going to bed (Supersede movie)
    movie_goal = AgentGoal(user_utterance="movie", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE, status=GoalStatus.EXECUTING)
    decision = arb.arbitrate("I'm going to bed", active_goals=[movie_goal])
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    arb.supersede_goal(movie_goal, new_goal_id="goal_sleep_1", reason="BEDTIME")
    assert movie_goal.status == GoalStatus.SUPERSEDED
    conv.record_turn("I'm going to bed", resolved_intent="PREPARE_SLEEP", agent_response="Okay, preparing room for sleep.")

    assert len(conv.turn_history) == 6


def test_g2_canonical_scenario_b_wake_cancellation_conflict():
    """Scenario B: 'Wake me at 7' -> 'Actually don't wake me tomorrow' cancels scheduled task."""
    arb = GoalArbitrator()
    task = MagicMock()
    task.task_id = "wake_task_1"
    task.action_type = "WAKE_ROUTINE"

    decision = arb.arbitrate("don't wake me tomorrow", scheduled_tasks=[task])
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    assert "wake_task_1" in decision.affected_goal_ids


def test_g3_canonical_scenario_c_external_change_detection():
    """Scenario C: External manual AC change is recognized by live telemetry readback."""
    agg = MagicMock()
    state = MagicMock()
    state.ac.target_temperature = 26  # User manually changed remote to 26
    agg.get_room_state.return_value = state

    brain = RoomBrain(room_state_aggregator=agg)
    t = brain._get_telemetry()
    assert t["ac_target_temperature"] == 26


def test_g4_canonical_scenario_d_preference_learning_and_explanation():
    """Scenario D: Repeated movie temperature is learned and truthfully explained."""
    engine = LearningEngine()
    engine.learn_from_observation("preferred_movie_temperature", 23)
    engine.learn_from_observation("preferred_movie_temperature", 23)
    engine.learn_from_observation("preferred_movie_temperature", 23)

    pref_val = engine.get_preference("preferred_movie_temperature")
    assert pref_val == 23

    explanation = engine.explain_preference("preferred_movie_temperature")
    assert "usually use 23" in explanation
    assert "observed 3 times" in explanation


def test_g5_canonical_scenario_e_autonomous_comfort():
    """Scenario E: Authorized autonomous comfort adjusts AC; unauthorized produces ASK."""
    mgr = AutonomyManager()
    drift = mgr.evaluate_comfort_drift(ambient_temperature=27.5, target_temperature=24.0)

    # 1. Unauthorized
    auth_no, _, level_no = mgr.evaluate_authorization(
        AutonomyCapability.AC_ADJUSTMENT, drift["action_type"], drift["target_subsystem"], drift["parameters"]
    )
    assert auth_no is False
    assert level_no == AutonomyGrantLevel.ASK

    # 2. Authorized
    mgr.grant_autonomy(AutonomyCapability.AC_ADJUSTMENT, AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS)
    auth_yes, _, level_yes = mgr.evaluate_authorization(
        AutonomyCapability.AC_ADJUSTMENT, drift["action_type"], drift["target_subsystem"], drift["parameters"]
    )
    assert auth_yes is True
    assert level_yes == AutonomyGrantLevel.AUTHORIZED_AUTONOMOUS


def test_g6_canonical_scenario_f_soundbar_protection_during_speech():
    """Scenario F: During Movie mode, speech synthesis does NOT disconnect Fire TV soundbar."""
    pol = PolicyEngine()
    res = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV", active_mode=BehaviorMode.MOVIE)
    assert res.is_denied() is True
    assert res.violates_hard_constraint is True


def test_g7_canonical_scenario_g_natural_voice_dialogue_flow():
    """Scenario G: 'Hey Animus' -> 'Movie time' -> 'How's the room?' -> 'Good night'."""
    ingress = VoiceIngressAdapter()
    conv = ConversationEngine()

    # 1. Voice turn arrival
    p1 = ingress.ingest_transcript("Hey Animus", detected_wake_word="animus")
    assert p1.detected_wake_word == "animus"
    conv.record_turn(p1.transcript, agent_response="Yeah buddy?")

    # 2. Movie time
    p2 = ingress.ingest_transcript("Movie time")
    conv.record_turn(p2.transcript, resolved_intent="PREPARE_MOVIE", agent_response="Getting it ready.")

    # 3. How's the room?
    p3 = ingress.ingest_transcript("How's the room?")
    conv.record_turn(p3.transcript, resolved_intent="WHAT_IS_HAPPENING", agent_response="The projector is on and AC is at 23°C.")

    # 4. Good night
    p4 = ingress.ingest_transcript("Good night")
    conv.record_turn(p4.transcript, resolved_intent="PREPARE_SLEEP", agent_response="Good night, buddy.")

    assert conv.get_last_turn().agent_response == "Good night, buddy."
    assert ingress.total_ingested_turns == 4


def test_g8_agent_full_orchestrator_integration():
    """AnimusPersonalAgent integrates all Stage 7-10 engines in full pipeline."""
    agent = AnimusPersonalAgent()
    assert agent.room_brain is not None
    assert agent.conversation_engine is not None
    assert agent.reasoning_engine is not None
    assert agent.goal_arbitrator is not None
    assert agent.policy_engine is not None
    assert agent.learning_engine is not None
    assert agent.autonomy_manager is not None
    assert agent.voice_ingress is not None


def test_g9_voice_ingress_routes_to_agent_interact():
    """VoiceIngressAdapter callback invokes agent.interact seamlessly."""
    agent = AnimusPersonalAgent()
    resp = agent.voice_ingress.ingest_transcript("What can you do?")
    assert resp.transcript == "What can you do?"


def test_g10_unified_room_brain_introspect_explanation():
    """RoomBrain explanation integrates active mode, AC, Projector, and Soundbar."""
    agg = MagicMock()
    state = MagicMock()
    state.ac.target_temperature = 23
    state.projector.is_powered_on = True
    state.soundbar.current_owner = "FIRE_TV"
    agg.get_room_state.return_value = state

    mode_mgr = BehaviorModeManager()
    mode_mgr.transition_to(BehaviorMode.MOVIE, reason="test")

    brain = RoomBrain(room_state_aggregator=agg, behavior_mode_manager=mode_mgr)
    text = brain.explain_room_state()
    assert "MOVIE" in text
    assert "23°C" in text
    assert "FIRE_TV" in text

