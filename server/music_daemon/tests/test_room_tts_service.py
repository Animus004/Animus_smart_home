"""
Isolated Unit and Integration Tests for Room-Level Backend TTS Service.
Verifies synthesis, FIFO queuing, concurrency serialization, music ducking restoration,
content security filtering, fault isolation, and FastAPI endpoint integration.
"""

import os
import queue
import time
import pytest
from unittest.mock import MagicMock, patch

from tts_service import RoomTtsService, TtsState


@pytest.fixture
def temp_cache_dir(tmp_path):
    d = tmp_path / "tts_cache"
    d.mkdir()
    return str(d)


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.player = MagicMock()
    orch.player.get_status.return_value = {
        "status": "PLAYING",
        "volume": 80
    }
    return orch


def test_tts_service_initializes(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=False)
    try:
        assert service.state == TtsState.IDLE
        assert not service.is_speaking()
        assert not service.is_enabled()
    finally:
        service.shutdown()


def test_basic_text_synthesis(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    out_wav = os.path.join(temp_cache_dir, "test_out.wav")
    try:
        ok = service.synthesize_to_wav("Hello, this is a test.", out_wav)
        assert ok is True
        assert os.path.exists(out_wav)
        assert os.path.getsize(out_wav) > 1000
    finally:
        service.shutdown()


def test_generated_audio_is_valid(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    out_wav = os.path.join(temp_cache_dir, "valid_audio.wav")
    try:
        ok = service.synthesize_to_wav("Testing audio header validation.", out_wav)
        assert ok is True
        # Verify RIFF header
        with open(out_wav, "rb") as f:
            header = f.read(4)
            assert header == b"RIFF"
    finally:
        service.shutdown()


def test_speak_queue_is_fifo(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    processed_items = []

    # Mock _process_utterance to record order without actual hardware playback
    service._process_utterance = lambda text, timeout=15.0: processed_items.append(text) or True

    try:
        service.speak_async("First utterance")
        service.speak_async("Second utterance")
        service.speak_async("Third utterance")

        assert service.wait_until_finished(timeout=3.0)
        assert processed_items == ["First utterance", "Second utterance", "Third utterance"]
    finally:
        service.shutdown()


def test_concurrent_speak_calls_do_not_overlap(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    active_threads = []
    max_simultaneous = 0

    def mock_process(text, timeout=15.0):
        nonlocal max_simultaneous
        active_threads.append(text)
        max_simultaneous = max(max_simultaneous, len(active_threads))
        time.sleep(0.05)
        active_threads.remove(text)
        return True

    service._process_utterance = mock_process

    try:
        for i in range(5):
            service.speak_async(f"Message {i}")

        assert service.wait_until_finished(timeout=5.0)
        # Verify at most 1 utterance processed simultaneously
        assert max_simultaneous == 1
    finally:
        service.shutdown()


def test_is_speaking_state_transitions(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)

    # Patch _play_wav_file to simulate playback duration
    def mock_play(wav_file, timeout=15.0):
        assert service.is_speaking()
        assert service.state == TtsState.PLAYING
        time.sleep(0.05)

    service._play_wav_file = mock_play
    service.synthesize_to_wav = lambda text, path: True

    try:
        assert not service.is_speaking()
        service.speak("State test")
        assert not service.is_speaking()
        assert service.state == TtsState.IDLE
    finally:
        service.shutdown()


def test_tts_failure_does_not_fail_agent_execution(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    # Simulate broken synthesis
    service.synthesize_to_wav = lambda text, path: False

    try:
        res = service.speak("This synthesis will fail.")
        assert res is False
        # Service survives and remains in IDLE or ERROR ready for next item
        assert not service.is_speaking()
    finally:
        service.shutdown()


def test_audio_sink_failure_does_not_crash_daemon(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    service.synthesize_to_wav = lambda text, path: True

    def broken_play(wav_file, timeout=15.0):
        raise RuntimeError("Audio device disconnected")

    service._play_wav_file = broken_play

    try:
        res = service.speak("This playback will fail.")
        assert res is False
        assert not service.is_speaking()
    finally:
        service.shutdown()


def test_music_volume_restored_after_tts(temp_cache_dir, mock_orchestrator):
    service = RoomTtsService(cache_dir=temp_cache_dir, orchestrator=mock_orchestrator, enabled=True)
    service.synthesize_to_wav = lambda text, path: True
    service._play_wav_file = lambda wav, timeout=15.0: time.sleep(0.02)

    try:
        mock_orchestrator.player.get_status.return_value = {"status": "PLAYING", "volume": 80}
        service.speak("Ducking test.")

        # Verify ducked volume was set (< 80) and original volume (80) was restored
        calls = mock_orchestrator.player.set_volume.call_args_list
        assert len(calls) >= 2
        # First call is ducking (e.g. 80 * 0.3 = 24)
        assert calls[0][0][0] == 24
        # Final call is restoration (80)
        assert calls[-1][0][0] == 80
    finally:
        service.shutdown()


def test_duplicate_response_is_not_played_twice(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    processed = []
    service._process_utterance = lambda text, timeout=15.0: processed.append(text) or True

    try:
        service.speak_async("Identical response message")
        service.speak_async("Identical response message")

        service.wait_until_finished(timeout=2.0)
        # Duplicate enqueued within < 1.5s should be suppressed
        assert len(processed) == 1
    finally:
        service.shutdown()


def test_sensitive_internal_data_is_not_sent_to_tts(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    try:
        # Traceback leak
        res1 = service._sanitize_text("Traceback (most recent call last):\nFile \"main.py\", line 40 in <module>")
        assert res1 == "I encountered an internal error processing that request, buddy."

        # Secret key leak
        res2 = service._sanitize_text("The device local_key is 76776532a4e57c0a2ca4")
        assert res2 == "I encountered an internal error processing that request, buddy."

        # Clean normal message
        res3 = service._sanitize_text("Good morning buddy! Room is prepared.")
        assert res3 == "Good morning buddy! Room is prepared."
    finally:
        service.shutdown()


def test_shutdown_releases_tts_resources(temp_cache_dir):
    service = RoomTtsService(cache_dir=temp_cache_dir, enabled=True)
    service.speak_async("Pending item")
    service.shutdown()
    assert not service._worker_thread.is_alive()
    assert not service.is_speaking()


def test_agent_interact_endpoint_tts_integration():
    from fastapi.testclient import TestClient
    from main import app, room_tts_service

    client = TestClient(app)

    # Disable room TTS by default
    room_tts_service.set_enabled(False)
    resp = client.post("/api/agent/interact", json={"utterance": "What did I accomplish today?"})
    assert resp.status_code == 200
    data = resp.json()
    assert "agent_message" in data
    assert "understood_intent" in data

    # Test status endpoint
    status_resp = client.get("/api/agent/tts/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["enabled"] is False

    # Test config endpoint
    cfg_resp = client.post("/api/agent/tts/config?enabled=true")
    assert cfg_resp.status_code == 200
    assert cfg_resp.json()["enabled"] is True
    assert room_tts_service.is_enabled() is True

    # Revert to disabled
    room_tts_service.set_enabled(False)
