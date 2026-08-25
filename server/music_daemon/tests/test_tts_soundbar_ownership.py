"""
Phase 2 Stage 4.1 — Soundbar Ownership-Aware TTS Routing Test Suite.
Verifies that RoomTtsService respects soundbar physical ownership:
- When FIRE_TV owns the LG Soundbar, Bluetooth reclaim via ensure_audio_endpoint() is strictly prohibited.
- When PC owns the LG Soundbar, normal WASAPI resolution and standby recovery are preserved.
- When ownership is UNKNOWN, TTS fails safely without stealing Bluetooth.
- Live physical telemetry strictly outranks historical memory.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from tts_service import RoomTtsService, TtsState
from room_state.models import RoomState, SoundbarState, StateField, Provenance


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch._in_movie_mode = False
    orch.player = MagicMock()
    orch.player.get_status.return_value = {"status": "PAUSED", "volume": 100}
    orch.bt_helper = MagicMock()
    orch.fire_tv = MagicMock()
    orch.fire_tv.is_soundbar_connected.return_value = False
    return orch


@pytest.fixture
def mock_room_state_aggregator():
    agg = MagicMock()
    return agg


# =============================================================================
# Test A — FIRE_TV ownership blocks Bluetooth reclaim
# =============================================================================

def test_fire_tv_ownership_blocks_bluetooth_reclaim(mock_orchestrator, mock_room_state_aggregator):
    """
    Given: soundbar.current_owner == FIRE_TV and soundbar absent from PC WASAPI
    Call: tts_service._resolve_audio_device_id()
    Assert: ensure_audio_endpoint() was NOT called, returns None (safe PC/default output).
    """
    mock_room_state = MagicMock()
    mock_room_state.soundbar.current_owner = StateField.observed("FIRE_TV", "FTV_BT", time.time())
    mock_room_state_aggregator.get_room_state.return_value = mock_room_state

    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (None, [])

    tts = RoomTtsService(
        orchestrator=mock_orchestrator,
        room_state_aggregator=mock_room_state_aggregator,
        enabled=True
    )

    dev_id = tts._resolve_audio_device_id()

    assert dev_id is None
    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_not_called()
    tts.shutdown()


# =============================================================================
# Test B — Movie Mode preserves Fire TV ownership
# =============================================================================

def test_movie_mode_preserves_fire_tv_ownership(mock_orchestrator):
    """
    Simulate: Movie Mode active (orchestrator._in_movie_mode = True, Fire TV connected to soundbar)
    Call: tts_service._resolve_audio_device_id()
    Assert: No Bluetooth reconnect, no route_audio_to_pc(), returns None.
    """
    mock_orchestrator._in_movie_mode = True
    mock_orchestrator.fire_tv.is_soundbar_connected.return_value = True
    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (None, [])

    tts = RoomTtsService(orchestrator=mock_orchestrator, enabled=True)

    dev_id = tts._resolve_audio_device_id()

    assert dev_id is None
    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_not_called()
    if hasattr(mock_orchestrator, "route_audio_to_pc"):
        mock_orchestrator.route_audio_to_pc.assert_not_called()
    tts.shutdown()


# =============================================================================
# Test C — PC ownership still reconnects standby soundbar
# =============================================================================

def test_pc_ownership_reconnects_standby_soundbar(mock_orchestrator, mock_room_state_aggregator):
    """
    Given: soundbar.current_owner == PC and soundbar absent from WASAPI
    Call: tts_service._resolve_audio_device_id()
    Assert: ensure_audio_endpoint() IS called and resolves returned device ID.
    """
    mock_room_state = MagicMock()
    mock_room_state.soundbar.current_owner = StateField.observed("PC", "PC_BT", time.time())
    mock_room_state_aggregator.get_room_state.return_value = mock_room_state

    # Soundbar not currently in WASAPI graph
    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (None, [])
    # ensure_audio_endpoint successfully wakes/reconnects it
    mock_orchestrator.bt_helper.ensure_audio_endpoint.return_value = (
        True,
        {"id": "{0.0.0.00000000}.{lg_snc4r_wasapi_endpoint}", "name": "LG SNC4R(79)"},
        "CONNECTED_AFTER_WINRT_PROBE"
    )

    tts = RoomTtsService(
        orchestrator=mock_orchestrator,
        room_state_aggregator=mock_room_state_aggregator,
        enabled=True
    )

    dev_id = tts._resolve_audio_device_id()

    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_called_once()
    assert dev_id == "{0.0.0.00000000}.{lg_snc4r_wasapi_endpoint}"
    tts.shutdown()


# =============================================================================
# Test D — Active PC endpoint is reused without reconnecting
# =============================================================================

def test_active_pc_endpoint_reused_without_reconnecting(mock_orchestrator, mock_room_state_aggregator):
    """
    Given: soundbar.current_owner == PC and soundbar already active in WASAPI
    Call: tts_service._resolve_audio_device_id()
    Assert: ensure_audio_endpoint() is NOT called, active endpoint is returned directly.
    """
    mock_room_state = MagicMock()
    mock_room_state.soundbar.current_owner = StateField.observed("PC", "PC_BT", time.time())
    mock_room_state_aggregator.get_room_state.return_value = mock_room_state

    # Soundbar is already present in WASAPI graph
    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (
        {"id": "{active_lg_endpoint_id}", "name": "LG SNC4R(79)"},
        []
    )

    tts = RoomTtsService(
        orchestrator=mock_orchestrator,
        room_state_aggregator=mock_room_state_aggregator,
        enabled=True
    )

    dev_id = tts._resolve_audio_device_id()

    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_not_called()
    assert dev_id == "{active_lg_endpoint_id}"
    tts.shutdown()


# =============================================================================
# Test E — Unknown ownership fails safe
# =============================================================================

def test_unknown_ownership_fails_safe(mock_orchestrator, mock_room_state_aggregator):
    """
    Given: soundbar owner == UNKNOWN and soundbar absent from WASAPI
    Call: tts_service._resolve_audio_device_id()
    Assert: ensure_audio_endpoint() is NOT called, returns None (safe PC default).
    """
    mock_room_state = MagicMock()
    mock_room_state.soundbar.current_owner = StateField.unknown("NO_TELEMETRY", time.time())
    mock_room_state_aggregator.get_room_state.return_value = mock_room_state

    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (None, [])
    mock_orchestrator.fire_tv.is_soundbar_connected.return_value = False

    tts = RoomTtsService(
        orchestrator=mock_orchestrator,
        room_state_aggregator=mock_room_state_aggregator,
        enabled=True
    )

    dev_id = tts._resolve_audio_device_id()

    assert dev_id is None
    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_not_called()
    tts.shutdown()


# =============================================================================
# Test F — TTS cannot mutate Movie Mode routing
# =============================================================================

def test_tts_cannot_mutate_movie_mode_routing(mock_orchestrator, mock_room_state_aggregator):
    """
    Given: Active Movie Mode with Soundbar connected to Fire TV
    Execute: Full TTS speech synthesis and playback
    Assert: route_audio_to_pc() is NOT called, ensure_audio_endpoint() is NOT called,
            and Fire TV retains uninterrupted Bluetooth ownership.
    """
    mock_orchestrator._in_movie_mode = True
    mock_orchestrator.route_audio_to_pc = MagicMock()
    mock_orchestrator.route_audio_to_fire_tv = MagicMock()
    mock_orchestrator.fire_tv.is_soundbar_connected.return_value = True
    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (None, [])

    mock_room_state = MagicMock()
    mock_room_state.soundbar.current_owner = StateField.observed("FIRE_TV", "FTV_BT", time.time())
    mock_room_state_aggregator.get_room_state.return_value = mock_room_state

    tts = RoomTtsService(
        orchestrator=mock_orchestrator,
        room_state_aggregator=mock_room_state_aggregator,
        enabled=True
    )

    with patch.object(tts, "_synthesize_sapi_wav", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        success = tts.speak("The room is ready, buddy.")

        assert success is True
        # Verify mpv was called without specifying the LG soundbar endpoint (leaving Fire TV intact)
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert not any("--audio-device=" in arg for arg in cmd)

    mock_orchestrator.route_audio_to_pc.assert_not_called()
    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_not_called()
    assert mock_orchestrator._in_movie_mode is True
    tts.shutdown()


# =============================================================================
# Test G — Existing PC TTS behavior remains fully functional
# =============================================================================

def test_existing_pc_tts_behavior_intact(mock_orchestrator, mock_room_state_aggregator):
    """
    Verify: PC owns soundbar, soundbar is in standby, ensure_audio_endpoint() wakes it,
            and speech plays through the reconnected LG SNC4R endpoint.
    """
    mock_orchestrator._in_movie_mode = False
    mock_room_state = MagicMock()
    mock_room_state.soundbar.current_owner = StateField.observed("PC", "PC_BT", time.time())
    mock_room_state_aggregator.get_room_state.return_value = mock_room_state

    mock_orchestrator.bt_helper.scan_active_endpoints.return_value = (None, [])
    mock_orchestrator.bt_helper.ensure_audio_endpoint.return_value = (
        True,
        {"id": "{lg_soundbar_wasapi_guid}", "name": "LG SNC4R"},
        "CONNECTED_AFTER_WINRT_PROBE"
    )

    tts = RoomTtsService(
        orchestrator=mock_orchestrator,
        room_state_aggregator=mock_room_state_aggregator,
        enabled=True
    )

    with patch.object(tts, "_synthesize_sapi_wav", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        success = tts.speak("I've set the temperature to 24 degrees.")

        assert success is True
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert "--audio-device={lg_soundbar_wasapi_guid}" in cmd

    mock_orchestrator.bt_helper.ensure_audio_endpoint.assert_called_once()
    tts.shutdown()


# =============================================================================
# Test H — High-Level End-to-End Movie Mode Preparation Integration Test
# =============================================================================

def test_high_level_movie_mode_tts_integration():
    """
    End-to-End Flow:
    1. User expresses intent: "Get the room ready for a movie."
    2. Room transitions into Movie Mode: Projector ON, AC at setpoint, Soundbar -> Fire TV.
    3. Live telemetry confirms Soundbar current_owner = FIRE_TV.
    4. Animus generates feedback: "Starting Movie Mode, projector is on and AC set to 23."
    5. TTS executes without Bluetooth reclaim.
    6. Soundbar strictly remains owned by Fire TV throughout and after TTS execution.
    """
    mock_orch = MagicMock()
    mock_orch._in_movie_mode = True
    mock_orch.fire_tv.is_soundbar_connected.return_value = True
    mock_orch.bt_helper.scan_active_endpoints.return_value = (None, [])

    mock_agg = MagicMock()
    live_room_state = MagicMock()
    live_room_state.projector.power = StateField.observed(True, "PROJECTOR_ADB", time.time())
    live_room_state.ac.target_temperature = StateField.observed(23, "TUYA_LAN", time.time())
    live_room_state.soundbar.current_owner = StateField.observed("FIRE_TV", "FTV_BT", time.time())
    mock_agg.get_room_state.return_value = live_room_state

    tts = RoomTtsService(
        orchestrator=mock_orch,
        room_state_aggregator=mock_agg,
        enabled=True
    )

    with patch.object(tts, "_synthesize_sapi_wav", return_value=True), \
         patch("os.path.exists", return_value=True), \
         patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        # Feedback generated after Movie Mode setup
        feedback_text = "Starting Movie Mode, projector is on and AC set to 23."
        tts_played = tts.speak(feedback_text)

        assert tts_played is True
        args, kwargs = mock_popen.call_args
        cmd = args[0]
        # Must play through default PC output, NEVER specifying the soundbar endpoint
        assert not any("--audio-device=" in arg for arg in cmd)

    # Assert soundbar ownership was not disturbed
    mock_orch.bt_helper.ensure_audio_endpoint.assert_not_called()
    assert live_room_state.soundbar.current_owner.value == "FIRE_TV"
    assert mock_orch._in_movie_mode is True
    tts.shutdown()
