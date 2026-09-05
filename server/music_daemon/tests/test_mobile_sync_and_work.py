"""
Integration tests for Mobile App Work Mode Execution & Cross-Device Chat Synchronization.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from main import app, animus_personal_agent, agent_event_bus, pc_controller


@pytest.fixture
def client():
    return TestClient(app)


def test_mobile_interact_executes_work_mode(client):
    with patch.object(pc_controller, "launch_allowlisted_app", return_value=(True, "Launched")) as mock_launch, \
         patch.object(pc_controller, "bring_work_windows_to_foreground") as mock_focus, \
         patch.object(pc_controller, "set_volume") as mock_vol:

        resp = client.post("/api/agent/interact", json={"utterance": "start work mode"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] is True
        assert "work mode" in data["agent_message"].lower()

        # Verify PC controller tools were invoked
        assert mock_launch.call_count >= 1
        assert mock_focus.called
        assert mock_vol.called


def test_mobile_interact_executes_work_wrapup(client):
    with patch.object(pc_controller, "send_save_keystrokes", return_value={"success": True, "any_files_modified": False}) as mock_save, \
         patch.object(pc_controller, "close_apps", return_value={"closed": []}) as mock_close:

        resp = client.post("/api/agent/interact", json={"utterance": "wrap up work"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_taken"] is True
        assert "progress saved" in data["agent_message"].lower() or "applications closed" in data["agent_message"].lower()


def test_cross_device_chat_sync_history(client):
    # 1. Send message from PC Chat
    pc_resp = client.post("/api/agent/chat", json={"message": "What is my current career target?", "active_mode": "WORK"})
    assert pc_resp.status_code == 200

    # 2. Send message from Mobile Interact
    mob_resp = client.post("/api/agent/interact", json={"utterance": "What is my active project?"})
    assert mob_resp.status_code == 200

    # 3. Fetch history
    hist_resp = client.get("/api/agent/chat/history?limit=10")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    turns = hist_data["turns"]
    assert len(turns) >= 2

    # Check that both turns exist
    user_msgs = [t["user"] for t in turns]
    assert any("career target" in m for m in user_msgs)
    assert any("active project" in m for m in user_msgs)

    # 4. Check incremental polling with since
    old_ts = turns[0]["timestamp"]
    inc_resp = client.get(f"/api/agent/chat/history?since={old_ts}&limit=10")
    assert inc_resp.status_code == 200
    inc_data = inc_resp.json()
    for t in inc_data["turns"]:
        assert t["timestamp"] > old_ts
