import pytest
from unittest.mock import MagicMock, patch
import subprocess
from projector_controller import (
    ProjectorController,
    ProjectorPowerState,
    ProjectorSource,
    ProjectorSignalState,
    ThermalStatus,
    FanStatus,
    ProjectorNotConnectedError,
    DEFAULT_TARGET
)

@pytest.fixture
def controller():
    return ProjectorController(target="192.168.1.11:5555", adb_path="mock_adb")

# =========================================================================
# 1. Connection & Target Isolation Tests
# =========================================================================

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
    mock_output = "List of devices attached\nZY22HLJ86Z      device\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
        is_ready, state = controller.is_connected()
        assert is_ready is False
        assert state == "disconnected"

def test_connect_and_disconnect(controller):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="connected to 192.168.1.11:5555", stderr="")
        assert controller.connect() is True

        mock_run.return_value = MagicMock(returncode=0, stdout="disconnected 192.168.1.11:5555", stderr="")
        assert controller.disconnect() is True

# =========================================================================
# 2. Navigation, Keyevents, & Volume
# =========================================================================

def test_navigation_and_volume_primitives(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "send_key", return_value=True) as mock_send_key:
        
        assert controller.home() is True
        mock_send_key.assert_called_with(3)

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

# =========================================================================
# 3. Power State, Standby Sleep, & Wake
# =========================================================================

def test_power_state_parsing_awake_and_on(controller):
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
        assert pwr["wakefulness"] == "Awake"

def test_power_state_parsing_awake_and_display_off(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "mWakefulness=Awake", ""),
             (0, "mState=OFF", "")
         ]):
        pwr = controller.get_power_state()
        assert pwr["power_state"] == ProjectorPowerState.AWAKE.value
        assert pwr["confidence"] == "medium"
        assert pwr["interactive"] is False
        assert pwr["display_state"] == "OFF"

def test_power_state_parsing_asleep_standby(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "mWakefulness=Asleep", ""),
             (0, "mState=OFF", "")
         ]):
        pwr = controller.get_power_state()
        assert pwr["power_state"] == ProjectorPowerState.STANDBY.value
        assert pwr["confidence"] == "high"
        assert pwr["display_state"] == "OFF"

def test_power_state_disconnected(controller):
    with patch.object(controller, "is_connected", return_value=(False, "disconnected")):
        pwr = controller.get_power_state()
        assert pwr["reachable"] is False
        assert pwr["power_state"] == ProjectorPowerState.OFF.value

def test_wake_and_sleep_methods(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "send_key", return_value=True) as mock_send, \
         patch.object(controller, "get_power_state", return_value={"power_state": "ON", "display_state": "ON", "interactive": True}):
        assert controller.wake() is True
        # If already ON/interactive, wake returns True

    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "send_key", return_value=True) as mock_send, \
         patch.object(controller, "get_power_state", side_effect=[
             {"power_state": "STANDBY", "display_state": "OFF", "interactive": False},
             {"power_state": "ON", "display_state": "ON", "interactive": True}
         ]):
        assert controller.wake() is True
        mock_send.assert_called_with(224)

    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "send_key", return_value=True) as mock_send, \
         patch.object(controller, "get_power_state", return_value={"power_state": "STANDBY", "display_state": "OFF"}):
        assert controller.sleep() is True
        mock_send.assert_called_with(223)

def test_power_off_oem(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, "", "")) as mock_shell:
        assert controller.power_off() is True
        mock_shell.assert_called_with("am start -n com.zhiying.powerservice/.PowerActivity")

# =========================================================================
# 4. HDMI Signal State & Handshake Parsing
# =========================================================================

def test_signal_state_active_video_flow(controller):
    mock_tv_input_dump = """
  serviceStateMap: ComponentName -> ServiceState
    ComponentInfo{com.hisilicon.tvinput.external/com.hisilicon.tvinput.external.HiHdmiTvInputService}: bound: true
  sessionStateMap: ITvInputSession -> SessionState
    inputId: com.hisilicon.tvinput.external/.HiHdmiTvInputService/HDMI0000C2
  TvInputHardwareManager Info:
    3: Connection{ mConfigs: [TvStreamConfig {mStreamId=0;mType=1;mGeneration=2}], hdmi_port=2 }
"""
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, mock_tv_input_dump, "")):
        sig = controller.get_signal_state()
        assert sig["signal_state"] == ProjectorSignalState.HDMI_SIGNAL_ACTIVE.value
        assert sig["active_stream"] is True
        assert sig["is_session_bound"] is True
        assert sig["verified"] is True

def test_signal_state_no_active_stream(controller):
    mock_tv_input_dump = """
  sessionStateMap: ITvInputSession -> SessionState
    inputId: com.hisilicon.tvinput.external/.HiHdmiTvInputService/HDMI0000C2
  TvInputHardwareManager Info:
    3: Connection{ mConfigs: [], hdmi_port=2 }
"""
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, mock_tv_input_dump, "")):
        sig = controller.get_signal_state()
        assert sig["signal_state"] == ProjectorSignalState.HDMI_CONNECTED_NO_ACTIVE_STREAM.value
        assert sig["active_stream"] is False

def test_signal_state_disconnected(controller):
    with patch.object(controller, "is_connected", return_value=(False, "disconnected")):
        sig = controller.get_signal_state()
        assert sig["signal_state"] == ProjectorSignalState.UNKNOWN.value
        assert sig["active_stream"] is False
        assert sig["verified"] is False

# =========================================================================
# 5. Input Source & Single HDMI Port Hardware Invariant
# =========================================================================

def test_source_management_and_single_hdmi_port_enforcement(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "home", return_value=True) as mock_home, \
         patch.object(controller, "_run_shell", return_value=(0, "", "")) as mock_shell:

        # HDMI 1 -> ALLOWED
        assert controller.set_hdmi(1) is True
        mock_shell.assert_called_with("am start -n com.newlink.nlsource/.MainActivity")

        # HDMI 2 & HDMI 3 -> STRICTLY REJECTED (Hardware only has 1 port)
        assert controller.set_hdmi(2) is False
        assert controller.set_hdmi(3) is False
        assert controller.set_source("HDMI_2") is False
        assert controller.set_source(ProjectorSource.HDMI_2) is False

        # ANDROID -> ALLOWED (Home)
        assert controller.set_source(ProjectorSource.ANDROID) is True
        mock_home.assert_called_once()

        # USB -> ALLOWED (File Manager)
        assert controller.set_source(ProjectorSource.USB) is True
        mock_shell.assert_called_with("am start -n com.newlink.filemanager/.activity.MainActivity")

        # Invalid source
        assert controller.set_source("INVALID_SOURCE") is False

def test_current_source_detection(controller):
    with patch.object(controller, "get_foreground_package", return_value="com.newlink.nlsource"):
        assert controller.get_current_source() == ProjectorSource.HDMI_1

    with patch.object(controller, "get_foreground_package", return_value="com.newlink.filemanager"):
        assert controller.get_current_source() == ProjectorSource.USB

    with patch.object(controller, "get_foreground_package", return_value="com.newlink.overseaslauncher"):
        assert controller.get_current_source() == ProjectorSource.ANDROID_HOME

    with patch.object(controller, "get_foreground_package", return_value=None):
        assert controller.get_current_source() == ProjectorSource.UNKNOWN

# =========================================================================
# 6. Hardware Health & Thermals Telemetry
# =========================================================================

def test_hardware_health_safe(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "32.4℃ ", ""),
             (0, "3247.19rpm", ""),
             (0, "3625.56rpm", "")
         ]):
        health = controller.get_hardware_health()
        assert health["temperature_celsius"] == 32.4
        assert health["main_fan_rpm"] == 3247.19
        assert health["sub_fan_rpm"] == 3625.56
        assert health["thermal_status"] == ThermalStatus.SAFE.value
        assert health["fan_status"] == FanStatus.HEALTHY.value
        assert health["verified"] is True

def test_hardware_health_warning_thermal(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "58.0℃ ", ""),
             (0, "3100.0rpm", ""),
             (0, "3200.0rpm", "")
         ]):
        health = controller.get_hardware_health()
        assert health["temperature_celsius"] == 58.0
        assert health["thermal_status"] == ThermalStatus.WARNING.value
        assert health["fan_status"] == FanStatus.HEALTHY.value

def test_hardware_health_critical_thermal(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "68.5℃ ", ""),
             (0, "3100.0rpm", ""),
             (0, "3200.0rpm", "")
         ]):
        health = controller.get_hardware_health()
        assert health["temperature_celsius"] == 68.5
        assert health["thermal_status"] == ThermalStatus.CRITICAL.value

def test_hardware_health_fan_warning(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "45.0℃ ", ""),
             (0, "1200.0rpm", ""),  # Low fan RPM
             (0, "3200.0rpm", "")
         ]):
        health = controller.get_hardware_health()
        assert health["fan_status"] == FanStatus.WARNING.value

# =========================================================================
# 7. Motor Focus & Gyro Keystone
# =========================================================================

def test_auto_focus_trigger(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = controller.auto_focus()
        assert res["status"] == "TRIGGERED"
        assert res["action"] == "auto_focus"
        assert res["verified"] is False
        mock_shell.assert_called_with("am start -a com.zhiying.AUTO_FOCUS_CORRECTION")

def test_auto_keystone_trigger(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = controller.auto_keystone()
        assert res["status"] == "TRIGGERED"
        assert res["action"] == "auto_keystone"
        assert res["verified"] is False
        mock_shell.assert_called_with("am start -a com.zhiying.ONE_AUTO_CORRECTION_KEYSTONE")

# =========================================================================
# 8. Brightness Scaling, Validation, & Read-Back Verification
# =========================================================================

def test_brightness_get_normalized(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", return_value=(0, "102", "")):
        # 102 / 255.0 * 100 = 40%
        pct = controller.get_brightness()
        assert pct == 40

def test_brightness_set_valid_with_readback(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "", ""),    # settings put system screen_brightness 179 (70%)
             (0, "179", "")  # settings get system screen_brightness -> 179 (70%)
         ]):
        ok, actual = controller.set_brightness(70)
        assert ok is True
        assert actual == 70

def test_brightness_set_invalid_bounds(controller):
    with patch.object(controller, "get_brightness", return_value=50):
        ok, actual = controller.set_brightness(-10)
        assert ok is False

        ok, actual = controller.set_brightness(110)
        assert ok is False

# =========================================================================
# 9. Device Info & Cold Power-On Invariant
# =========================================================================

def test_get_device_info_structure(controller):
    with patch.object(controller, "is_connected", return_value=(True, "device")), \
         patch.object(controller, "_run_shell", side_effect=[
             (0, "NL5H00X", ""),
             (0, "12", ""),
             (0, "NL5H00X", "")
         ]), \
         patch.object(controller, "get_power_state", return_value={"power_state": "ON", "wakefulness": "Awake", "display_state": "ON", "interactive": True}), \
         patch.object(controller, "get_foreground_package", return_value="com.newlink.nlsource"), \
         patch.object(controller, "get_signal_state", return_value={"signal_state": "HDMI_SIGNAL_ACTIVE", "active_stream": True}), \
         patch.object(controller, "get_hardware_health", return_value={"temperature_celsius": 32.1, "thermal_status": "SAFE"}), \
         patch.object(controller, "get_brightness", return_value=40), \
         patch.object(controller, "get_cec_status", return_value={"enabled": True}):

        info = controller.get_device_info()
        assert info["connected"] is True
        assert info["hdmi_ports"] == 1
        assert info["cold_power_on_supported_via_adb"] is False
        assert info["current_source"] == "HDMI_1"
        assert info["brightness_percent"] == 40
        assert info["signal_state"] == "HDMI_SIGNAL_ACTIVE"

# =========================================================================
# 10. FastAPI Projector Endpoints Battery
# =========================================================================

def test_fastapi_all_projector_endpoints():
    from fastapi.testclient import TestClient
    from main import app, projector as main_projector

    client = TestClient(app)

    # 1. GET /api/projector/status
    with patch.object(main_projector, "get_device_info", return_value={"connected": True, "hdmi_ports": 1, "model": "NL5H00X"}):
        resp = client.get("/api/projector/status")
        assert resp.status_code == 200
        assert resp.json()["hdmi_ports"] == 1

    # 2. GET /api/projector/health
    with patch.object(main_projector, "get_hardware_health", return_value={"temperature_celsius": 32.1, "thermal_status": "SAFE"}):
        resp = client.get("/api/projector/health")
        assert resp.status_code == 200
        assert resp.json()["thermal_status"] == "SAFE"

    # 3. GET /api/projector/signal
    with patch.object(main_projector, "get_signal_state", return_value={"signal_state": "HDMI_SIGNAL_ACTIVE", "active_stream": True}):
        resp = client.get("/api/projector/signal")
        assert resp.status_code == 200
        assert resp.json()["signal_state"] == "HDMI_SIGNAL_ACTIVE"

    # 4. GET /api/projector/input
    with patch.object(main_projector, "get_current_source", return_value=ProjectorSource.HDMI_1):
        resp = client.get("/api/projector/input")
        assert resp.status_code == 200
        assert resp.json()["current_input"] == "HDMI_1"
        assert resp.json()["hdmi_ports"] == 1

    # 5. POST /api/projector/focus
    with patch.object(main_projector, "auto_focus", return_value={"status": "TRIGGERED", "action": "auto_focus"}):
        resp = client.post("/api/projector/focus")
        assert resp.status_code == 200
        assert resp.json()["status"] == "TRIGGERED"

    # 6. POST /api/projector/keystone
    with patch.object(main_projector, "auto_keystone", return_value={"status": "TRIGGERED", "action": "auto_keystone"}):
        resp = client.post("/api/projector/keystone")
        assert resp.status_code == 200
        assert resp.json()["status"] == "TRIGGERED"

    # 7. GET & POST /api/projector/brightness
    with patch.object(main_projector, "get_brightness", return_value=45):
        resp = client.get("/api/projector/brightness")
        assert resp.status_code == 200
        assert resp.json()["brightness_percent"] == 45

    with patch.object(main_projector, "set_brightness", return_value=(True, 70)):
        resp = client.post("/api/projector/brightness", json={"brightness": 70})
        assert resp.status_code == 200
        assert resp.json()["actual_percent"] == 70
        assert resp.json()["verified"] is True

    # 8. POST /api/projector/power
    with patch.object(main_projector, "wake", return_value=True), \
         patch.object(main_projector, "get_power_state", return_value={"power_state": "ON"}):
        resp = client.post("/api/projector/power", json={"action": "WAKE"})
        assert resp.status_code == 200
        assert resp.json()["power_state"] == "ON"

    with patch.object(main_projector, "sleep", return_value=True), \
         patch.object(main_projector, "get_power_state", return_value={"power_state": "STANDBY"}):
        resp = client.post("/api/projector/power", json={"action": "SLEEP"})
        assert resp.status_code == 200
        assert resp.json()["power_state"] == "STANDBY"

    with patch.object(main_projector, "get_power_state", return_value={"power_state": "OFF"}):
        resp = client.post("/api/projector/power", json={"action": "ON"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False
        assert "Cold power-on unavailable via ADB" in resp.json()["error"]
