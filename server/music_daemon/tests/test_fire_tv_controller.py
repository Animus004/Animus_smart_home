import pytest
from unittest.mock import patch, MagicMock
from fire_tv_controller import FireTvController, FireTvBluetoothState, FireTvNotConnectedError

@pytest.fixture
def fire_tv():
    return FireTvController(target="192.168.1.5:5555", adb_path="adb.exe")

def test_fire_tv_initialization(fire_tv):
    assert fire_tv.target == "192.168.1.5:5555"
    assert fire_tv.required_bt_mac == "54:15:89:DC:A5:79"

def test_is_connected_success(fire_tv):
    mock_devices = "List of devices attached\n192.168.1.5:5555\tdevice product:sheldon\n"
    with patch.object(fire_tv, "_run_adb", return_value=(0, mock_devices, "")):
        is_conn, state = fire_tv.is_connected(auto_connect=False)
        assert is_conn is True
        assert state == "device"

def test_is_connected_disconnected(fire_tv):
    mock_devices = "List of devices attached\n192.168.1.11:5555\tdevice\n"
    with patch.object(fire_tv, "_run_adb", return_value=(0, mock_devices, "")):
        is_conn, state = fire_tv.is_connected(auto_connect=False)
        assert is_conn is False
        assert state == "disconnected"

def test_get_bluetooth_status_connected(fire_tv):
    mock_dump = """
Bluetooth Status
  enabled: true
  state: ON
  ConnectionState: STATE_CONNECTED
  Bonded devices:
    54:15:89:DC:A5:79 [BR/EDR]
"""
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "_run_shell", return_value=(0, mock_dump, "")):
        status = fire_tv.get_bluetooth_status()
        assert status["adapter_enabled"] is True
        assert status["required_device_connected"] is True
        assert status["state"] == FireTvBluetoothState.CONNECTED.value
        assert status["confidence"] == "high"

def test_get_bluetooth_status_disconnected(fire_tv):
    mock_dump = """
Bluetooth Status
  enabled: true
  state: ON
  ConnectionState: STATE_DISCONNECTED
"""
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "_run_shell", return_value=(0, mock_dump, "")):
        status = fire_tv.get_bluetooth_status()
        assert status["adapter_enabled"] is True
        assert status["required_device_connected"] is False
        assert status["state"] == FireTvBluetoothState.DISCONNECTED.value

def test_send_keys_and_navigation(fire_tv):
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        assert fire_tv.home() is True
        mock_shell.assert_called_with("input keyevent 3")
        assert fire_tv.back() is True
        mock_shell.assert_called_with("input keyevent 4")
        assert fire_tv.select() is True
        mock_shell.assert_called_with("input keyevent 23")

def test_send_key_not_connected_raises(fire_tv):
    with patch.object(fire_tv, "is_connected", return_value=(False, "disconnected")):
        with pytest.raises(FireTvNotConnectedError):
            fire_tv.home()

def test_get_status(fire_tv):
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "get_bluetooth_status", return_value={"required_device_connected": True, "state": "CONNECTED"}), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "mWakefulness=Awake", "")):
        st = fire_tv.get_status()
        assert st["reachable"] is True
        assert st["power_state"] == "AWAKE"
        assert st["healthy"] is True
