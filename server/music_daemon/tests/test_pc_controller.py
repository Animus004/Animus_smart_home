"""
Unit Test Suite for PC Controller, Router, and REST Endpoints.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from pc_controller import PcController, MediaVirtualKey
from pc_command_router import PcCommandRouter, PcCommandCategory
from main import app

@pytest.fixture
def controller():
    ctrl = PcController()
    return ctrl

@pytest.fixture
def client():
    return TestClient(app)

# =========================================================================
# 1. AUDIO SUBSYSTEM TESTS
# =========================================================================

def test_pc_get_audio_status_structure(controller):
    with patch.object(controller, "_get_default_endpoint_volume", return_value=(None, None)):
        st = controller.get_audio_status()
        assert "master_volume" in st
        assert "is_muted" in st
        assert "default_endpoint" in st
        assert "active_endpoints" in st
        assert st["verified"] is True


def test_pc_set_volume_valid_with_readback(controller):
    with patch.object(controller, "get_volume", side_effect=[50, 70]), \
         patch.object(controller, "_get_default_endpoint_volume") as mock_epv:

        mock_dev = MagicMock()
        mock_vol = MagicMock()
        mock_vol.contents.lpVtbl.contents.SetMasterVolumeLevelScalar.return_value = 0
        mock_epv.return_value = (mock_dev, mock_vol)

        ok, res = controller.set_volume(70)
        assert ok is True
        assert res["master_volume"] == 70
        assert res["verified"] is True

def test_pc_set_volume_bounds_rejection(controller):
    # Below 0%
    ok_low, res_low = controller.set_volume(-5)
    assert ok_low is False
    assert res_low["status"] == "INVALID_PARAMETER"

    # Above 100%
    ok_high, res_high = controller.set_volume(120)
    assert ok_high is False
    assert res_high["status"] == "INVALID_PARAMETER"

def test_pc_set_volume_idempotent(controller):
    with patch.object(controller, "get_volume", return_value=80):
        ok, res = controller.set_volume(80)
        assert ok is True
        assert res["idempotent"] is True
        assert res["master_volume"] == 80

def test_pc_set_mute_verified(controller):
    with patch.object(controller, "get_audio_status", return_value={"is_muted": True, "verified": True}), \
         patch.object(controller, "_get_default_endpoint_volume") as mock_epv:

        mock_dev = MagicMock()
        mock_vol = MagicMock()
        mock_vol.contents.lpVtbl.contents.SetMute.return_value = 0
        mock_epv.return_value = (mock_dev, mock_vol)

        ok, res = controller.set_mute(True)
        assert ok is True
        assert res["is_muted"] is True

# =========================================================================
# 2. BLUETOOTH SUBSYSTEM TESTS
# =========================================================================

def test_pc_bluetooth_status_mock(controller):
    with patch.object(controller, "get_bluetooth_status") as mock_bt:
        mock_bt.return_value = {
            "success": True,
            "radio_present": True,
            "radio_name": "ANIMUS",
            "radio_mac": "AC:A7:F1:79:CF:36",
            "device_count": 1,
            "devices": [
                {
                    "name": "LG SNC4R(79)",
                    "mac": "54:15:89:DC:A5:79",
                    "connected": False,
                    "paired": True,
                    "is_audio": True
                }
            ],
            "verified": True
        }
        st = controller.get_bluetooth_status()
        assert st["radio_present"] is True
        assert st["devices"][0]["name"] == "LG SNC4R(79)"
        assert st["devices"][0]["is_audio"] is True

# =========================================================================
# 3. MEDIA TRANSPORT TESTS
# =========================================================================

def test_pc_media_controls(controller):
    with patch.object(controller, "_send_virtual_key", return_value=True):
        ok_pp, res_pp = controller.media_play_pause()
        assert ok_pp is True
        assert res_pp["action"] == "PLAY_PAUSE"

        ok_next, res_next = controller.media_next()
        assert ok_next is True
        assert res_next["action"] == "NEXT_TRACK"

        ok_prev, res_prev = controller.media_previous()
        assert ok_prev is True
        assert res_prev["action"] == "PREVIOUS_TRACK"

        ok_stop, res_stop = controller.media_stop()
        assert ok_stop is True
        assert res_stop["action"] == "STOP"

# =========================================================================
# 4. POWER & SYSTEM MANAGEMENT TESTS
# =========================================================================

def test_pc_get_power_state(controller):
    pwr = controller.get_power_state()
    assert pwr["power_state"] == "AWAKE_AND_RUNNING"
    assert "uptime_hours" in pwr
    assert "power_source" in pwr
    assert pwr["verified"] is True

def test_pc_lock_workstation(controller):
    with patch("pc_controller.user32.LockWorkStation", return_value=1):
        ok, res = controller.lock_workstation()
        assert ok is True
        assert res["action"] == "LOCK_WORKSTATION"

def test_pc_sleep_method(controller):
    with patch("pc_controller.powrprof.SetSuspendState", return_value=1):
        ok, res = controller.sleep()
        assert ok is True
        assert res["action"] == "SLEEP"

# =========================================================================
# 5. SAFE ALLOWLISTED APP LAUNCH TESTS
# =========================================================================

def test_pc_launch_allowlisted_app_success(controller):
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 4321
        mock_popen.return_value = mock_proc

        ok, res = controller.launch_allowlisted_app("notepad")
        assert ok is True
        assert res["app"] == "notepad"
        assert res["pid"] == 4321

def test_pc_launch_unlisted_app_rejected(controller):
    ok, res = controller.launch_allowlisted_app("malicious_hacker_tool.exe")
    assert ok is False
    assert res["status"] == "SECURITY_REJECTED"

# =========================================================================
# 6. COMMAND ROUTER UNIT TESTS
# =========================================================================

def test_pc_router_audio_queries_and_controls(controller):
    router = PcCommandRouter(controller=controller)

    with patch.object(controller, "get_audio_status", return_value={"master_volume": 60, "is_muted": False, "verified": True}), \
         patch.object(controller, "set_volume", return_value=(True, {"master_volume": 60, "message": "OK"})), \
         patch.object(controller, "set_mute", return_value=(True, {"is_muted": True, "message": "OK"})):

        res_v = router.route_command("What's the PC volume?")
        assert res_v["category"] == PcCommandCategory.AUDIO.value
        assert res_v["capability"] == "PC_GET_VOLUME"
        assert res_v["master_volume"] == 60

        res_set = router.route_command("Set the PC volume to 60%.")
        assert res_set["category"] == PcCommandCategory.AUDIO.value
        assert res_set["capability"] == "PC_SET_VOLUME"

        res_mute = router.route_command("Mute the computer.")
        assert res_mute["capability"] == "PC_MUTE"

        res_unmute = router.route_command("Unmute the computer.")
        assert res_unmute["capability"] == "PC_UNMUTE"

def test_pc_router_media_and_bluetooth_commands(controller):
    router = PcCommandRouter(controller=controller)

    with patch.object(controller, "media_play_pause", return_value=(True, {"message": "OK"})), \
         patch.object(controller, "media_next", return_value=(True, {"message": "OK"})), \
         patch.object(controller, "get_bluetooth_status", return_value={"radio_name": "ANIMUS", "radio_mac": "AC:A7:F1:79:CF:36", "devices": [], "verified": True}):

        res_pp = router.route_command("Pause the music.")
        assert res_pp["category"] == PcCommandCategory.MEDIA.value
        assert res_pp["capability"] == "PC_MEDIA_PLAY_PAUSE"

        res_next = router.route_command("Skip this song.")
        assert res_next["capability"] == "PC_MEDIA_NEXT"

        res_bt = router.route_command("Show me connected Bluetooth devices.")
        assert res_bt["category"] == PcCommandCategory.BLUETOOTH.value
        assert res_bt["capability"] == "PC_GET_BLUETOOTH_DEVICES"

def test_pc_router_power_and_security_guards(controller):
    router = PcCommandRouter(controller=controller)

    with patch.object(controller, "lock_workstation", return_value=(True, {"message": "OK"})):
        res_lock = router.route_command("Lock the computer.")
        assert res_lock["category"] == PcCommandCategory.POWER.value
        assert res_lock["capability"] == "PC_LOCK"

    # Security Guard: Arbitrary shell execution strictly blocked
    res_sec1 = router.route_command("powershell -Command Remove-Item -Recurse C:\\")
    assert res_sec1["category"] == PcCommandCategory.SAFETY_NEGATIVE.value
    assert res_sec1["status"] == "SECURITY_REJECTED"

    res_sec2 = router.route_command("rm -rf /")
    assert res_sec2["status"] == "SECURITY_REJECTED"

# =========================================================================
# 7. FASTAPI REST ENDPOINTS TESTS
# =========================================================================

def test_fastapi_pc_endpoints(client):
    with patch("main.pc_controller.get_status") as mock_st, \
         patch("main.pc_controller.set_volume") as mock_vol, \
         patch("main.pc_controller.set_mute") as mock_mute, \
         patch("main.pc_controller.media_play_pause") as mock_pp, \
         patch("main.pc_controller.lock_workstation") as mock_lock, \
         patch("main.pc_controller.get_bluetooth_status") as mock_bt, \
         patch("main.pc_router.route_command") as mock_cmd:

        mock_st.return_value = {
            "device": "PC",
            "hostname": "Animus",
            "power": {"power_state": "AWAKE_AND_RUNNING"},
            "audio": {"master_volume": 80, "is_muted": False},
            "bluetooth": {"radio_present": True},
            "verified": True
        }
        mock_vol.return_value = (True, {"success": True, "master_volume": 80, "verified": True})
        mock_mute.return_value = (True, {"success": True, "is_muted": True, "verified": True})
        mock_pp.return_value = (True, {"success": True, "action": "PLAY_PAUSE", "verified": True})
        mock_lock.return_value = (True, {"success": True, "action": "LOCK_WORKSTATION", "verified": True})
        mock_bt.return_value = {"success": True, "radio_present": True, "devices": [], "verified": True}
        mock_cmd.return_value = {"success": True, "capability": "PC_GET_VOLUME", "master_volume": 80}

        # GET /api/pc/status
        r_st = client.get("/api/pc/status")
        assert r_st.status_code == 200
        assert r_st.json()["hostname"] == "Animus"

        # POST /api/pc/volume
        r_vol = client.post("/api/pc/volume", json={"volume": 80})
        assert r_vol.status_code == 200
        assert r_vol.json()["master_volume"] == 80

        # POST /api/pc/mute
        r_mute = client.post("/api/pc/mute", json={"mute": True})
        assert r_mute.status_code == 200
        assert r_mute.json()["is_muted"] is True

        # POST /api/pc/media
        r_media = client.post("/api/pc/media", json={"action": "PLAY_PAUSE"})
        assert r_media.status_code == 200

        # POST /api/pc/power
        r_pwr = client.post("/api/pc/power", json={"action": "LOCK"})
        assert r_pwr.status_code == 200

        # GET /api/pc/bluetooth
        r_bt = client.get("/api/pc/bluetooth")
        assert r_bt.status_code == 200

        # POST /api/pc/command
        r_cmd = client.post("/api/pc/command", json={"query": "What's the PC volume?"})
        assert r_cmd.status_code == 200
