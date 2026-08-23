import pytest
from unittest.mock import MagicMock, patch
import subprocess
from projector_controller import (
    ProjectorController,
    ProjectorNotConnectedError,
    DEFAULT_TARGET
)

@pytest.fixture
def controller():
    return ProjectorController(target="192.168.1.11:5555", adb_path="mock_adb")

def test_controller_initialization(controller):
    assert controller.target == "192.168.1.11:5555"
    assert controller.adb_path == "mock_adb"
    assert controller.timeout == 4.0

def test_is_connected_authorized(controller):
    mock_output = "List of devices attached\n192.168.1.11:5555      device product:NL5H00X model:HiDPTAndroid_Hi3751V350\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        is_ready, state = controller.is_connected()
        assert is_ready is True
        assert state == "device"
        mock_run.assert_called_once_with(
            ["mock_adb", "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=3.0
        )

def test_is_connected_unauthorized(controller):
    mock_output = "List of devices attached\n192.168.1.11:5555      unauthorized\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        is_ready, state = controller.is_connected()
        assert is_ready is False
        assert state == "unauthorized"

def test_wrong_device_protection(controller):
    # If another device like a phone is attached via USB, controller must ignore it
    mock_output = "List of devices attached\nZY22HLJ86Z      device\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        is_ready, state = controller.is_connected()
        assert is_ready is False
        assert state == "disconnected"

def test_connect_success(controller):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="connected to 192.168.1.11:5555", stderr="")
        success = controller.connect()
        assert success is True
        mock_run.assert_called_once_with(
            ["mock_adb", "connect", "192.168.1.11:5555"],
            capture_output=True,
            text=True,
            timeout=5.0
        )

def test_disconnect_success(controller):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="disconnected 192.168.1.11:5555", stderr="")
        success = controller.disconnect()
        assert success is True
        mock_run.assert_called_once_with(
            ["mock_adb", "disconnect", "192.168.1.11:5555"],
            capture_output=True,
            text=True,
            timeout=3.0
        )

def test_send_key_safe_targeting(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        # Test HOME (3)
        res = controller.home()
        assert res is True
        mock_run.assert_called_with(
            ["mock_adb", "-s", "192.168.1.11:5555", "shell", "input keyevent 3"],
            capture_output=True,
            text=True,
            timeout=4.0
        )

def test_navigation_and_volume_primitives(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "send_key", return_value=True) as mock_send_key:
        
        assert controller.back() is True
        mock_send_key.assert_called_with(4)

        assert controller.menu() is True
        mock_send_key.assert_called_with(82)

        assert controller.volume_up() is True
        mock_send_key.assert_called_with(24)

        assert controller.volume_down() is True
        mock_send_key.assert_called_with(25)

        assert controller.volume_mute() is True
        mock_send_key.assert_called_with(164)

        assert controller.dpad_up() is True
        mock_send_key.assert_called_with(19)

        assert controller.dpad_down() is True
        mock_send_key.assert_called_with(20)

        assert controller.dpad_left() is True
        mock_send_key.assert_called_with(21)

        assert controller.dpad_right() is True
        mock_send_key.assert_called_with(22)

        assert controller.dpad_center() is True
        mock_send_key.assert_called_with(23)

def test_send_key_not_connected_raises_error(controller):
    with patch.object(controller, "is_connected", return_value=(False, "disconnected")), \
         patch.object(controller, "connect", return_value=False):
        with pytest.raises(ProjectorNotConnectedError):
            controller.home()

def test_timeout_handling(controller):
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["adb"], timeout=4.0)):
        code, stdout, stderr = controller._run_target_adb(["shell", "dumpsys power"])
        assert code == -1
        assert "Timeout after 4.0s" in stderr

def test_fastapi_projector_status_endpoint():
    from fastapi.testclient import TestClient
    from main import app, projector as main_projector

    client = TestClient(app)
    mock_info = {
        "connected": True,
        "ip": "192.168.1.11",
        "target": "192.168.1.11:5555",
        "model": "HiDPTAndroid_Hi3751V350",
        "android": "12",
        "product": "NL5H00X",
        "interactive": True,
        "foreground_package": "com.newlink.overseaslauncher"
    }

    with patch.object(main_projector, "get_device_info", return_value=mock_info):
        resp = client.get("/api/room/projector/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["ip"] == "192.168.1.11"
        assert data["model"] == "HiDPTAndroid_Hi3751V350"
        assert data["android"] == "12"
        assert data["foreground_package"] == "com.newlink.overseaslauncher"

def test_fastapi_projector_key_endpoint():
    from fastapi.testclient import TestClient
    from main import app, projector as main_projector

    client = TestClient(app)
    with patch.object(main_projector, "home", return_value=True):
        resp = client.post("/api/room/projector/key", json={"key": "home"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "key": "home"}

    with patch.object(main_projector, "back", return_value=True):
        resp = client.post("/api/room/projector/key", json={"key": "back"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "key": "back"}

def test_fastapi_projector_volume_endpoint():
    from fastapi.testclient import TestClient
    from main import app, projector as main_projector

    client = TestClient(app)
    with patch.object(main_projector, "volume_up", return_value=True):
        resp = client.post("/api/room/projector/volume", json={"action": "up"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "action": "up"}

    with patch.object(main_projector, "volume_down", return_value=True):
        resp = client.post("/api/room/projector/volume", json={"action": "down"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "action": "down"}

def test_source_enum_and_hdmi_methods(controller):
    from projector_controller import ProjectorSource

    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "home", return_value=True) as mock_home, \
         patch.object(controller, "_run_shell", return_value=(0, "", "")) as mock_shell:

        # ANDROID source triggers home()
        assert controller.set_source(ProjectorSource.ANDROID) is True
        mock_home.assert_called_once()

        # HDMI 1, 2, 3
        assert controller.set_hdmi(1) is True
        mock_shell.assert_called_with("am start -n com.newlink.nlsource/.MainActivity")

        assert controller.set_hdmi(2) is True
        assert controller.set_hdmi(3) is True
        assert controller.set_hdmi(4) is False

        # USB source
        assert controller.set_source(ProjectorSource.USB) is True
        mock_shell.assert_called_with("am start -n com.newlink.filemanager/.activity.MainActivity")

        # Invalid source
        assert controller.set_source("INVALID_SOURCE") is False

def test_power_state_parsing(controller):
    from projector_controller import ProjectorPowerState

    # Awake + Display ON -> ON (High confidence)
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "mWakefulness=Awake\nDisplay Power: state=ON", ""),
             (0, "mState=ON", "")
         ]):
        pwr = controller.get_power_state()
        assert pwr["power_state"] == ProjectorPowerState.ON.value
        assert pwr["confidence"] == "high"
        assert pwr["interactive"] is True
        assert pwr["display_state"] == "ON"

    # Awake + Display OFF -> AWAKE (Medium confidence)
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "mWakefulness=Awake", ""),
             (0, "mState=OFF", "")
         ]):
        pwr = controller.get_power_state()
        assert pwr["power_state"] == ProjectorPowerState.AWAKE.value
        assert pwr["confidence"] == "medium"
        assert pwr["interactive"] is False

    # Asleep -> STANDBY (High confidence)
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "mWakefulness=Asleep", ""),
             (0, "mState=OFF", "")
         ]):
        pwr = controller.get_power_state()
        assert pwr["power_state"] == ProjectorPowerState.STANDBY.value
        assert pwr["confidence"] == "high"

def test_fastapi_projector_source_and_power_endpoints():
    from fastapi.testclient import TestClient
    from main import app, projector as main_projector

    client = TestClient(app)
    with patch.object(main_projector, "set_source", return_value=True):
        resp = client.post("/api/room/projector/source", json={"source": "HDMI_1"})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "source": "HDMI_1"}

    with patch.object(main_projector, "set_source", return_value=False):
        resp = client.post("/api/room/projector/source", json={"source": "INVALID"})
        assert resp.status_code == 400

    mock_pwr = {"connected": True, "power_state": "ON", "confidence": "high", "interactive": True}
    with patch.object(main_projector, "get_power_state", return_value=mock_pwr), \
         patch.object(main_projector, "power_off", return_value=True):
        resp = client.post("/api/room/projector/power", json={"action": "STATUS"})
        assert resp.status_code == 200
        assert resp.json()["power_state"] == "ON"

        resp = client.post("/api/room/projector/power", json={"action": "ON"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = client.post("/api/room/projector/power", json={"action": "OFF"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    resp = client.post("/api/room/projector/power", json={"action": "INVALID"})
    assert resp.status_code == 400

def test_power_off_oem_targeting_and_safety(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, "", "")) as mock_shell:
        assert controller.power_off() is True
        mock_shell.assert_called_with("am start -n com.zhiying.powerservice/.PowerActivity")

    with patch.object(controller, "is_connected", return_value=(False, "disconnected")):
        with pytest.raises(ProjectorNotConnectedError):
            controller.power_off()

def test_get_cec_status_telemetry(controller):
    mock_dump = """
mProhibitMode: false
mPowerStatus: 0
mIsCecAvailable: true
mCecVersion: 5
CEC settings:
  hdmi_cec_enabled (int): 1 (default: 1) [modifiable]
  power_control_mode (string): to_tv (default: to_tv) [modifiable]
  tv_wake_on_one_touch_play (int): 1 (default: 1) [modifiable]
HDMI CEC Network
  mPortInfo:
    port_id: 1, type: HDMI_IN, address: 0x0000, cec: true, arc: false, mhl: false
"""
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, mock_dump, "")):
        cec = controller.get_cec_status()
        assert cec["available"] is True
        assert cec["enabled"] is True
        assert cec["tv_wake_on_one_touch_play"] is True
        assert cec["power_control_mode"] == "to_tv"

    with patch.object(controller, "is_connected", return_value=(False, "disconnected")):
        cec = controller.get_cec_status()
        assert cec["available"] is False
        assert cec["enabled"] is False





