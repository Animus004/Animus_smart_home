"""
Tests for Phase A Media Engine Hardening:
Deterministic PlaybackQueue, Continuous Mpv IPC Event Listener,
EOF auto-advance, related track resolution, and Movie Mode non-interference.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from queue_manager import PlaybackQueue, QueueTrack
from player import MpvPlayer
from resolver import YouTubeMusicResolver, ResolvedTrack
from orchestrator import SmartRoomOrchestrator, RoomAudioState
from main import app


@pytest.fixture
def queue():
    return PlaybackQueue(auto_radio=True)


@pytest.fixture
def mock_resolver():
    res = MagicMock(spec=YouTubeMusicResolver)
    res.is_authenticated = True
    res.auth_method = "oauth"
    res.get_auth_status.return_value = {"is_authenticated": True, "auth_method": "oauth", "has_cookies": True}
    res.resolve.return_value = ResolvedTrack(
        video_id="test_vid_123",
        title="Test Song",
        artist="Test Artist",
        duration=200,
        stream_url="https://audio.stream/test.mp3",
        thumbnail_url="https://img.youtube.com/thumb.jpg",
        is_authenticated=True
    )
    res.get_related_tracks.return_value = [
        {"video_id": "rel_1", "title": "Related Song 1", "artist": "Artist 1", "duration": 180},
        {"video_id": "rel_2", "title": "Related Song 2", "artist": "Artist 2", "duration": 210}
    ]
    return res


@pytest.fixture
def mock_player():
    player = MagicMock(spec=MpvPlayer)
    player._eof_callbacks = []
    def reg_cb(cb):
        player._eof_callbacks.append(cb)
    def unreg_cb(cb):
        if cb in player._eof_callbacks:
            player._eof_callbacks.remove(cb)
    player.register_eof_callback.side_effect = reg_cb
    player.unregister_eof_callback.side_effect = unreg_cb
    player.play.return_value = (True, None)
    player.pause.return_value = True
    player.resume.return_value = True
    player.stop.return_value = True
    player.set_volume.return_value = 80
    player._active_audio_device_name = "LG SNC4R(79)"
    player._playback_status = "PLAYING"
    player.current_track = {"title": "Current Song", "artist": "Current Artist", "video_id": "curr_123"}
    player.get_status.return_value = {
        "status": "PLAYING",
        "title": "Current Song",
        "artist": "Current Artist",
        "duration": 200,
        "position": 50,
        "volume": 80,
        "audio_output_status": "CONNECTED",
        "audio_device_id": "endpoint_123",
        "audio_device_name": "LG SNC4R(79)"
    }
    return player


@pytest.fixture
def mock_bt_helper():
    helper = MagicMock()
    helper.scan_active_endpoints.return_value = ({"id": "endpoint_123", "name": "LG SNC4R(79)"}, "LG SNC4R(79)")
    helper.ensure_audio_endpoint.return_value = (True, {"id": "endpoint_123", "name": "LG SNC4R(79)"}, 200)
    helper.device_portal.is_available.return_value = True
    helper.last_reconnect_method = "AEP_DEVICE_PORTAL"
    helper.last_reconnect_duration_ms = 450
    return helper


@pytest.fixture
def orchestrator(mock_resolver, mock_player, mock_bt_helper, queue):
    orch = SmartRoomOrchestrator(
        resolver=mock_resolver,
        player=mock_player,
        bt_helper=mock_bt_helper,
        queue=queue
    )
    return orch


# ─── 1. Queue Data Structure Tests ──────────────────────────────────────────

def test_queue_operations(queue):
    t1 = QueueTrack(video_id="v1", title="Song 1", artist="Artist 1")
    t2 = QueueTrack(video_id="v2", title="Song 2", artist="Artist 2")
    t3 = QueueTrack(video_id="v3", title="Song 3", artist="Artist 3")

    # Enqueue
    assert queue.enqueue(t1) == 1
    assert queue.enqueue(t2) == 2
    assert queue.size() == 2
    assert not queue.is_empty()

    # Enqueue next
    assert queue.enqueue_next(t3) == 3
    assert queue.peek_next().video_id == "v3"

    # Pop next
    popped = queue.pop_next()
    assert popped.video_id == "v3"
    assert queue.size() == 2

    # Set current and check history
    queue.set_current_track(popped)
    assert queue.current_track.video_id == "v3"

    next_track = queue.pop_next()
    queue.set_current_track(next_track)
    assert len(queue.get_history_items()) == 1
    assert queue.get_history_items()[0]["video_id"] == "v3"

    # Pop previous
    prev = queue.pop_previous()
    assert prev.video_id == "v3"
    # Current track was pushed back to front of queue
    assert queue.peek_next().video_id == "v1"

    # Clear
    queue.clear()
    assert queue.is_empty()


# ─── 2. MpvPlayer Continuous Event Listener & EOF Dispatch Tests ────────────

def test_mpv_player_event_listener_registration():
    player = MpvPlayer()
    cb = MagicMock()
    player.register_eof_callback(cb)
    assert cb in player._eof_callbacks

    # Simulate EOF event
    player.current_track = {"title": "Test Song", "video_id": "t1"}
    player._handle_ipc_message({"event": "end-file", "reason": "eof"})
    cb.assert_called_once_with({"title": "Test Song", "video_id": "t1"}, {"event": "end-file", "reason": "eof"})

    # Simulate non-EOF event (e.g. user stopped)
    cb.reset_mock()
    player._handle_ipc_message({"event": "end-file", "reason": "stop"})
    cb.assert_not_called()

    # Unregister
    player.unregister_eof_callback(cb)
    assert cb not in player._eof_callbacks


# ─── 3. Orchestrator Auto-Advance on EOF Tests ───────────────────────────────

def test_orchestrator_auto_advance_from_queue(orchestrator, mock_player, mock_resolver, queue):
    # Pre-populate queue
    t1 = QueueTrack(video_id="next_1", title="Next Song", artist="Next Artist")
    queue.enqueue(t1)

    # Trigger EOF callback
    last_track = {"title": "Finished Song", "video_id": "fin_123"}
    orchestrator._handle_player_eof(last_track, {"event": "end-file", "reason": "eof"})
    import time; time.sleep(0.2)

    # Verifies player.play was called with next song
    mock_resolver.resolve.assert_called_with(title="Next Song", artist="Next Artist", direct_id="next_1")
    mock_player.play.assert_called_once()
    assert orchestrator.current_state == RoomAudioState.PLAYING
    assert queue.current_track.video_id == "test_vid_123"


def test_orchestrator_auto_radio_continuation(orchestrator, mock_player, mock_resolver, queue):
    # Queue is initially empty, but auto_radio is True
    assert queue.is_empty()
    queue.auto_radio = True

    last_track = {"title": "Seed Song", "video_id": "seed_999"}
    orchestrator._handle_player_eof(last_track, {"event": "end-file", "reason": "eof"})
    import time; time.sleep(0.2)

    # Verifies related tracks were fetched and next track was played
    mock_resolver.get_related_tracks.assert_called_once_with("seed_999", limit=5)
    mock_player.play.assert_called_once()
    assert orchestrator.current_state == RoomAudioState.PLAYING


def test_movie_mode_suppresses_auto_advance(orchestrator, mock_player):
    # Enable movie mode
    orchestrator._in_movie_mode = True

    last_track = {"title": "Last Song", "video_id": "seed_999"}
    orchestrator._handle_player_eof(last_track, {"event": "end-file", "reason": "eof"})
    import time; time.sleep(0.1)

    # Must NOT call play when movie mode owns audio
    mock_player.play.assert_not_called()


# ─── 4. Manual Skip Next & Previous Tests ────────────────────────────────────

def test_manual_skip_next(orchestrator, mock_player, queue):
    t1 = QueueTrack(video_id="s1", title="Queued Song", artist="Artist")
    queue.enqueue(t1)

    ok, data, err = orchestrator.skip_next()
    assert ok is True
    mock_player.stop.assert_called_once()
    mock_player.play.assert_called()


def test_manual_skip_previous(orchestrator, mock_player, queue):
    t_prev = QueueTrack(video_id="p1", title="Prev Song", artist="Artist")
    t_curr = QueueTrack(video_id="c1", title="Current Song", artist="Artist")
    queue.set_current_track(t_prev)
    queue.set_current_track(t_curr)

    ok, data, err = orchestrator.skip_previous()
    assert ok is True
    mock_player.stop.assert_called_once()
    mock_player.play.assert_called()


# ─── 5. Failure Recovery Tests ───────────────────────────────────────────────

def test_auto_advance_resolution_failure_recovery(orchestrator, mock_player, mock_resolver, queue):
    # Track 1 fails to resolve, Track 2 succeeds
    t_bad = QueueTrack(video_id="bad_vid", title="Bad Song", artist="Artist")
    t_good = QueueTrack(video_id="good_vid", title="Good Song", artist="Artist")
    queue.enqueue(t_bad)
    queue.enqueue(t_good)

    mock_resolver.resolve.side_effect = [
        None,  # First call fails
        ResolvedTrack(
            video_id="good_vid",
            title="Good Song",
            artist="Artist",
            duration=190,
            stream_url="https://audio.stream/good.mp3",
            is_authenticated=True
        )
    ]

    orchestrator._handle_player_eof(None, {"event": "end-file", "reason": "eof"})
    import time; time.sleep(0.2)

    # Verifies it skipped bad track and played good track
    assert mock_resolver.resolve.call_count == 2
    mock_player.play.assert_called_once()
    assert queue.current_track.video_id == "good_vid"


# ─── 6. FastAPI REST Endpoints Tests ────────────────────────────────────────

def test_fastapi_queue_endpoints():
    client = TestClient(app)

    # 1. Enqueue track
    res = client.post("/api/music/queue", json={"title": "Tum Hi Ho", "artist": "Arijit Singh", "play_next": False})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["title"] == "Tum Hi Ho"
    assert data["queue_length"] >= 1

    # 2. Get queue status
    res = client.get("/api/music/queue")
    assert res.status_code == 200
    st = res.json()
    assert "queue_length" in st
    assert "upcoming" in st

    # 3. Clear queue
    res = client.post("/api/music/queue/clear")
    assert res.status_code == 200
    assert res.json()["success"] is True
