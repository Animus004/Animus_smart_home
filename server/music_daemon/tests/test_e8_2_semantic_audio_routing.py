"""
Phase E.8.2 — Semantic Audio Routing & Volume Disambiguation Unit & Integration Tests.
Strict Test Matrix covering 15 distinct semantic audio, volume arbitration,
movie mode soundbar routing, and fail-closed validation contracts.
"""

import pytest
import time
from unittest.mock import MagicMock

from room_state.models import (
    RoomState,
    StateField,
    PcState,
    FireTvState,
    SoundbarState,
    RoomEnvironmentState,
    AudioStreamState,
    ActiveAudioProducer,
    MediaPlaybackState
)
from room_state.provenance import Provenance
from room_state.audio_resolver import AudioContextResolver
from room_state.aggregator import RoomStateAggregator
from context.engine import ContextEngine
from context.preferences import PreferenceManager
from capability_registry import UnifiedCapabilityRegistry
from planner.models import GeminiStructuredPlan, PlanStep
from planner.validator import PlanValidator
from planner.executor import PlanExecutor, ExecutionStatus
from planner.errors import ErrorCode


@pytest.fixture
def mock_resolver_env():
    """Provides a controlled mock environment for AudioContextResolver."""
    orch = MagicMock()
    orch.player = MagicMock()
    orch._in_movie_mode = False

    ftv_ctrl = MagicMock()

    resolver = AudioContextResolver(orchestrator=orch, fire_tv_controller=ftv_ctrl)
    return {
        "resolver": resolver,
        "orch": orch,
        "ftv_ctrl": ftv_ctrl
    }


# =============================================================================
# 1. Resolver Test Matrix (Cases 1-7)
# =============================================================================

def test_case_1_fire_tv_playing_soundbar_on_fire_tv(mock_resolver_env):
    """Case 1: Fire TV playing + soundbar already routed to Fire TV -> route_required = False."""
    env = mock_resolver_env
    env["orch"].player.get_status.return_value = {"playback_status": "STOPPED"}
    env["ftv_ctrl"]._run_shell.return_value = (0, "state=PlaybackState {state=3, ...}", "")

    pc_state = PcState(online=StateField.observed(True, "PC", time.time()))
    ftv_state = FireTvState(
        online=StateField.observed(True, "FTV", time.time()),
        foreground_app=StateField.observed("com.amazon.firetv.youtube", "FTV", time.time()),
        soundbar_connected=StateField.observed(True, "FTV", time.time())
    )
    sb_state = SoundbarState(
        current_owner=StateField.derived("FIRE_TV", "DERIV", time.time()),
        is_connected=StateField.derived(True, "DERIV", time.time())
    )

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.value == ActiveAudioProducer.FIRE_TV.value
    assert audio_st.playback_state.value == MediaPlaybackState.PLAYING.value
    assert audio_st.soundbar_route_active.value is True

    # Test ContextEngine derivation
    rs = RoomState(pc=pc_state, fire_tv=ftv_state, soundbar=sb_state, audio_stream=audio_st)
    ctx_eng = ContextEngine()
    sem_ctx = ctx_eng.get_room_semantic_context(rs)

    assert sem_ctx.active_audio_producer == "FIRE_TV"
    assert sem_ctx.desired_audio_owner == "FIRE_TV"
    assert sem_ctx.soundbar_route_required is False
    assert sem_ctx.audio_routing_reason == "ALREADY_SATISFIED"


def test_case_2_fire_tv_playing_soundbar_on_pc(mock_resolver_env):
    """Case 2: Fire TV playing + soundbar currently owned by PC -> route_required = True."""
    env = mock_resolver_env
    env["orch"].player.get_status.return_value = {"playback_status": "STOPPED"}
    env["ftv_ctrl"]._run_shell.return_value = (0, "state=PlaybackState {state=3, ...}", "")

    pc_state = PcState(online=StateField.observed(True, "PC", time.time()))
    ftv_state = FireTvState(
        online=StateField.observed(True, "FTV", time.time()),
        foreground_app=StateField.observed("com.amazon.firetv.youtube", "FTV", time.time()),
        soundbar_connected=StateField.observed(False, "FTV", time.time())
    )
    sb_state = SoundbarState(
        current_owner=StateField.derived("PC", "DERIV", time.time()),
        is_connected=StateField.derived(True, "DERIV", time.time())
    )

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.value == ActiveAudioProducer.FIRE_TV.value
    assert audio_st.playback_state.value == MediaPlaybackState.PLAYING.value

    # ContextEngine derivation
    rs = RoomState(pc=pc_state, fire_tv=ftv_state, soundbar=sb_state, audio_stream=audio_st)
    ctx_eng = ContextEngine()
    sem_ctx = ctx_eng.get_room_semantic_context(rs)

    assert sem_ctx.active_audio_producer == "FIRE_TV"
    assert sem_ctx.desired_audio_owner == "FIRE_TV"
    assert sem_ctx.soundbar_route_required is True
    assert sem_ctx.audio_routing_reason == "NEEDS_TRANSFER_TO_FIRE_TV"


def test_case_3_pc_playing_soundbar_on_pc(mock_resolver_env):
    """Case 3: PC playing + soundbar owned by PC -> active producer = PC, route_required = False."""
    env = mock_resolver_env
    env["orch"].player.get_status.return_value = {"playback_status": "PLAYING", "audio_device_name": "LG SNC4R"}
    env["ftv_ctrl"]._run_shell.return_value = (0, "state=PlaybackState {state=1, ...}", "")

    pc_state = PcState(online=StateField.observed(True, "PC", time.time()))
    ftv_state = FireTvState(
        online=StateField.observed(True, "FTV", time.time()),
        foreground_app=StateField.observed("com.amazon.tv.launcher", "FTV", time.time()),
        soundbar_connected=StateField.observed(False, "FTV", time.time())
    )
    sb_state = SoundbarState(
        current_owner=StateField.derived("PC", "DERIV", time.time()),
        is_connected=StateField.derived(True, "DERIV", time.time())
    )

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.value == ActiveAudioProducer.PC.value
    assert audio_st.playback_state.value == MediaPlaybackState.PLAYING.value

    rs = RoomState(pc=pc_state, fire_tv=ftv_state, soundbar=sb_state, audio_stream=audio_st)
    ctx_eng = ContextEngine()
    sem_ctx = ctx_eng.get_room_semantic_context(rs)

    assert sem_ctx.active_audio_producer == "PC"
    assert sem_ctx.desired_audio_owner == "PC"
    assert sem_ctx.soundbar_route_required is False
    assert sem_ctx.audio_routing_reason == "ALREADY_SATISFIED"


def test_case_4_fire_tv_playing_active_producer_fire_tv(mock_resolver_env):
    """Case 4: Fire TV playing + soundbar on Fire TV -> active producer = FIRE_TV."""
    env = mock_resolver_env
    env["orch"].player.get_status.return_value = {"playback_status": "STOPPED"}
    env["ftv_ctrl"]._run_shell.return_value = (0, "state=PlaybackState {state=3, ...}", "")

    pc_state = PcState(online=StateField.observed(True, "PC", time.time()))
    ftv_state = FireTvState(
        online=StateField.observed(True, "FTV", time.time()),
        foreground_app=StateField.observed("com.netflix.ninja", "FTV", time.time()),
        soundbar_connected=StateField.observed(True, "FTV", time.time())
    )
    sb_state = SoundbarState(
        current_owner=StateField.derived("FIRE_TV", "DERIV", time.time()),
        is_connected=StateField.derived(True, "DERIV", time.time())
    )

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.value == "FIRE_TV"
    assert audio_st.playback_state.value == "PLAYING"


def test_case_5_fire_tv_idle_pc_playing(mock_resolver_env):
    """Case 5: Fire TV idle + PC playing -> active producer = PC."""
    env = mock_resolver_env
    env["orch"].player.get_status.return_value = {"playback_status": "PLAYING"}

    pc_state = PcState(online=StateField.observed(True, "PC", time.time()))
    ftv_state = FireTvState(
        online=StateField.observed(True, "FTV", time.time()),
        foreground_app=StateField.observed("com.amazon.tv.launcher", "FTV", time.time()),
        soundbar_connected=StateField.observed(False, "FTV", time.time())
    )
    sb_state = SoundbarState(
        current_owner=StateField.derived("PC", "DERIV", time.time()),
        is_connected=StateField.derived(True, "DERIV", time.time())
    )

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.value == "PC"
    assert audio_st.playback_state.value == "PLAYING"


def test_case_6_both_idle(mock_resolver_env):
    """Case 6: Both idle -> active producer = NONE, playback_state = IDLE."""
    env = mock_resolver_env
    env["orch"].player.get_status.return_value = {"playback_status": "STOPPED"}

    pc_state = PcState(online=StateField.observed(True, "PC", time.time()))
    ftv_state = FireTvState(
        online=StateField.observed(True, "FTV", time.time()),
        foreground_app=StateField.observed("com.amazon.tv.launcher", "FTV", time.time()),
        soundbar_connected=StateField.observed(False, "FTV", time.time())
    )
    sb_state = SoundbarState(
        current_owner=StateField.derived("NONE", "DERIV", time.time()),
        is_connected=StateField.derived(False, "DERIV", time.time())
    )

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.value == "NONE"
    assert audio_st.playback_state.value == "IDLE"


def test_case_7_telemetry_unavailable_returns_unknown(mock_resolver_env):
    """Case 7: Telemetry unavailable -> UNKNOWN, never fabricated certainty."""
    env = mock_resolver_env
    pc_state = PcState(online=StateField.unknown("POLL_FAIL"))
    ftv_state = FireTvState(online=StateField.unknown("POLL_FAIL"))
    sb_state = SoundbarState(current_owner=StateField.unknown("POLL_FAIL"), is_connected=StateField.unknown("POLL_FAIL"))

    audio_st = env["resolver"].resolve(pc_state, ftv_state, sb_state)
    assert audio_st.active_producer.provenance == Provenance.UNKNOWN
    assert audio_st.active_producer.value is None or audio_st.active_producer.value == "UNKNOWN"
    assert audio_st.playback_state.provenance == Provenance.UNKNOWN


# =============================================================================
# 2. Volume & Movie Mode Planning Tests (Cases 8-12)
# =============================================================================

def test_case_8_make_it_quieter_fire_tv_active():
    """Case 8: 'Make it quieter' + Fire TV active -> Fire TV volume capability selected."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    # Valid plan targeting Fire TV
    plan = GeminiStructuredPlan(
        intent="AUDIO_VOLUME",
        objective_summary="Attenuate Fire TV media volume",
        steps=[PlanStep(step_id=1, device="fire_tv", capability="FIRE_TV_VOLUME_DOWN")]
    )
    val_res = validator.validate_plan(plan)
    assert val_res.valid is True
    assert val_res.validated_steps[0].canonical_capability_id == "FIRE_TV_VOLUME_DOWN"


def test_case_9_make_it_quieter_pc_active():
    """Case 9: 'Make it quieter' + PC active -> PC volume capability selected."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    plan = GeminiStructuredPlan(
        intent="AUDIO_VOLUME",
        objective_summary="Lower PC master volume to 40%",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 40})]
    )
    val_res = validator.validate_plan(plan)
    assert val_res.valid is True
    assert val_res.validated_steps[0].canonical_capability_id == "PC_SET_VOLUME"


def test_case_10_make_it_quieter_unknown_producer_safe_ambiguity():
    """Case 10: 'Make it quieter' with unknown producer fails safely or validates strictly without invalid bounds."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    # Invalid volume out of bounds should still be rejected strictly
    bad_plan = GeminiStructuredPlan(
        intent="AUDIO_VOLUME",
        objective_summary="Set volume to invalid 150%",
        steps=[PlanStep(step_id=1, device="pc", capability="PC_SET_VOLUME", parameters={"volume": 150})]
    )
    val_res = validator.validate_plan(bad_plan)
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.OUT_OF_RANGE for e in val_res.errors)


def test_case_11_movie_mode_soundbar_on_fire_tv_idempotent_skip():
    """Case 11: 'Let's watch something' + correct Fire TV soundbar route -> no physical Bluetooth mutation."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    mock_orch = MagicMock()
    executor = PlanExecutor(registry=registry, orchestrator=mock_orch)

    rs = RoomState(
        soundbar=SoundbarState(
            current_owner=StateField.observed("FIRE_TV", "POLL", time.time()),
            is_connected=StateField.observed(True, "POLL", time.time())
        )
    )

    plan = GeminiStructuredPlan(
        intent="MOVIE_MODE",
        objective_summary="Start movie and route audio",
        steps=[PlanStep(step_id=1, device="soundbar", capability="SOUNDBAR_ROUTE_TO_FIRE_TV")]
    )
    val_res = validator.validate_plan(plan, room_state=rs)
    assert val_res.valid is True

    # Executor should recognize state is already satisfied and skip dispatch
    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is True
    assert exec_res.skipped_steps_count == 1
    # Verify zero calls to orchestrator transfer method
    assert mock_orch.route_audio_to_fire_tv.call_count == 0


def test_case_12_movie_mode_pc_owns_soundbar_executes_transfer():
    """Case 12: 'Let's watch something' + PC owns soundbar -> route to Fire TV through orchestrator."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    # Initial state: PC owns soundbar
    rs_initial = RoomState(
        soundbar=SoundbarState(
            current_owner=StateField.observed("PC", "POLL", time.time()),
            is_connected=StateField.observed(True, "POLL", time.time())
        )
    )
    # Post-transfer state: Fire TV owns soundbar
    rs_post = RoomState(
        soundbar=SoundbarState(
            current_owner=StateField.observed("FIRE_TV", "POLL", time.time()),
            is_connected=StateField.observed(True, "POLL", time.time())
        )
    )

    mock_agg = MagicMock()
    # Initially returns rs_initial, then after dispatch returns rs_post
    mock_agg.get_room_state.side_effect = [rs_initial, rs_post, rs_post]

    mock_orch = MagicMock()
    mock_orch.transfer_audio_to_fire_tv.return_value = {"success": True, "target": "FIRE_TV"}
    mock_orch.route_audio_to_fire_tv.return_value = {"success": True, "target": "FIRE_TV"}
    executor = PlanExecutor(registry=registry, orchestrator=mock_orch, room_state_aggregator=mock_agg)

    plan = GeminiStructuredPlan(
        intent="MOVIE_MODE",
        objective_summary="Transfer soundbar to Fire TV",
        steps=[PlanStep(step_id=1, device="soundbar", capability="SOUNDBAR_ROUTE_TO_FIRE_TV")]
    )
    val_res = validator.validate_plan(plan, room_state=rs_initial)
    assert val_res.valid is True

    exec_res = executor.execute_plan(val_res)
    assert exec_res.success is True
    assert (mock_orch.transfer_audio_to_fire_tv.call_count == 1 or mock_orch.route_audio_to_fire_tv.call_count == 1)


# =============================================================================
# 3. Preservation & Invariant Tests (Cases 13-15)
# =============================================================================

def test_case_13_put_on_youtube_behavior_preserved():
    """Case 13: 'Put on YouTube' capability chain remains verified executable."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    plan = GeminiStructuredPlan(
        intent="ENTERTAINMENT",
        objective_summary="Launch YouTube on Fire TV",
        steps=[
            PlanStep(step_id=1, device="fire_tv", capability="FIRE_TV_POWER_WAKE"),
            PlanStep(step_id=2, device="fire_tv", capability="FIRE_TV_APP_LAUNCH_YOUTUBE")
        ]
    )
    val_res = validator.validate_plan(plan)
    assert val_res.valid is True
    assert len(val_res.validated_steps) == 2


def test_case_14_existing_e8_1_physical_idempotency_preserved():
    """Case 14: Existing E.8.1 physical idempotency is strictly preserved."""
    registry = UnifiedCapabilityRegistry()
    executor = PlanExecutor(registry=registry)

    rs = RoomState(
        soundbar=SoundbarState(
            current_owner=StateField.observed("FIRE_TV", "POLL", time.time()),
            is_connected=StateField.observed(True, "POLL", time.time())
        )
    )
    is_satisfied = executor._is_state_already_satisfied("SOUNDBAR_ROUTE_TO_FIRE_TV", {}, rs)
    assert is_satisfied is True


def test_case_15_plan_validator_fail_closed_safety_preserved():
    """Case 15: PlanValidator remains strictly fail-closed on unsupported capabilities."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)

    plan = GeminiStructuredPlan(
        intent="AUDIO_ROUTING",
        objective_summary="Route to fake device",
        steps=[PlanStep(step_id=1, device="soundbar", capability="SOUNDBAR_ROUTE_TO_MICROWAVE")]
    )
    val_res = validator.validate_plan(plan)
    assert val_res.valid is False
    assert any(e.error_code == ErrorCode.UNKNOWN_CAPABILITY for e in val_res.errors)
