import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app, orchestrator, fire_tv
from orchestrator import RoomAudioState

client = TestClient(app)

def test_switch_audio_to_pc_success():
    with patch.object(orchestrator, "connect_soundbar", return_value=(True, RoomAudioState.AUDIO_READY, "AUDIO_READY")), \
         patch.object(orchestrator, "get_room_status", return_value={"soundbar_name": "Speakers (LG SNC4R(79))", "room_audio_state": "AUDIO_READY"}):
        resp = client.post("/api/room/audio/switch", json={"target": "PC"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["target"] == "PC"
        assert "Soundbar connected to computer" in data["message"]

def test_switch_audio_to_pc_failure():
    with patch.object(orchestrator, "connect_soundbar", return_value=(False, RoomAudioState.AUDIO_OUTPUT_UNAVAILABLE, "TIMEOUT")), \
         patch.object(orchestrator, "get_room_status", return_value={"soundbar_name": None, "room_audio_state": "AUDIO_OUTPUT_UNAVAILABLE"}):
        resp = client.post("/api/room/audio/switch", json={"target": "PC"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["target"] == "PC"
        assert "Could not connect" in data["message"]

def test_switch_audio_to_fire_tv_success():
    with patch.object(orchestrator, "disconnect_soundbar", return_value=(True, RoomAudioState.DISCONNECTED, "DISCONNECTED")), \
         patch.object(fire_tv, "connect_soundbar", return_value=True), \
         patch.object(fire_tv, "is_required_bluetooth_connected", return_value=True):
        resp = client.post("/api/room/audio/switch", json={"target": "FIRE_TV"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["target"] == "FIRE_TV"
        assert "Audio switched to Fire TV" in data["message"]

def test_switch_audio_to_fire_tv_failure():
    with patch.object(orchestrator, "disconnect_soundbar", return_value=(True, RoomAudioState.DISCONNECTED, "DISCONNECTED")), \
         patch.object(fire_tv, "connect_soundbar", return_value=False), \
         patch.object(fire_tv, "is_required_bluetooth_connected", return_value=False):
        resp = client.post("/api/room/audio/switch", json={"target": "FIRE_TV"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["target"] == "FIRE_TV"
        assert "Could not switch" in data["message"]

def test_switch_audio_invalid_target():
    resp = client.post("/api/room/audio/switch", json={"target": "MICROWAVE"})
    assert resp.status_code == 400
