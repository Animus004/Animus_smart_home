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
  mActiveDevice: 54:15:89:DC:A5:79
  StateMachine: name=A2dpStateMachine state=Connected
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

def test_is_app_foreground(fire_tv):
    with patch.object(fire_tv, "_run_shell", return_value=(0, "mCurrentFocus=Window{123 com.amazon.firetv.youtube/dev.cobalt.app.MainActivity}", "")):
        assert fire_tv.is_app_foreground("com.amazon.firetv.youtube") is True
        assert fire_tv.is_app_foreground("com.netflix.ninja") is False

def test_search_or_launch_content_verified(fire_tv):
    with patch.object(fire_tv, "wake", return_value=True), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "Success", "")) as mock_shell, \
         patch.object(fire_tv, "is_app_foreground", return_value=True):
        ok = fire_tv.search_or_launch_content("Article 15")
        assert ok is True
        # Check am start
        assert any("am start -n com.amazon.firetv.youtube" in str(c) for c in mock_shell.call_args_list)
        # Check search navigation & text input
        assert any("Article%s15" in str(c) for c in mock_shell.call_args_list)

def test_connect_soundbar_already_connected(fire_tv):
    with patch.object(fire_tv, "is_required_bluetooth_connected", return_value=True):
        assert fire_tv.connect_soundbar() is True

def test_connect_soundbar_navigation_flow(fire_tv):
    with patch.object(fire_tv, "is_required_bluetooth_connected", side_effect=[False, False, True]), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "Success", "")) as mock_shell:
        assert fire_tv.connect_soundbar(force_fallback=True) is True
        assert any("com.amazon.tv.settings.v2" in str(c) for c in mock_shell.call_args_list)

def test_get_status(fire_tv):
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "get_bluetooth_status", return_value={"required_device_connected": True, "state": "CONNECTED"}), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "mWakefulness=Awake", "")):
        st = fire_tv.get_status()
        assert st["reachable"] is True
        assert st["power_state"] == "AWAKE"
        assert st["healthy"] is True


def test_fire_tv_get_content_title_from_media_session(fire_tv):
    mock_dump = """
    MediaSession: Record
      description=Interstellar (2014) - Official Trailer, MediaDescription
    """
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "_run_shell", return_value=(0, mock_dump, "")):
        title = fire_tv.get_content_title()
        assert title == "Interstellar (2014) - Official Trailer"


def test_fire_tv_get_content_title_from_foreground_app(fire_tv):
    with patch.object(fire_tv, "is_connected", return_value=(True, "device")), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")), \
         patch.object(fire_tv, "get_foreground_app", return_value="com.amazon.firetv.youtube"):
        title = fire_tv.get_content_title()
        assert title == "YouTube"


def test_fire_tv_get_content_title_when_offline(fire_tv):
    with patch.object(fire_tv, "is_connected", return_value=(False, "disconnected")):
        assert fire_tv.get_content_title() is None


def test_launch_streaming_provider_netflix_numeric_id(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.launch_streaming_provider("netflix", "80018191")
        assert res is True
        mock_shell.assert_called_with("am start -a android.intent.action.VIEW -d 'https://www.netflix.com/watch/80018191' -n com.netflix.ninja/.MainActivity")


def test_launch_streaming_provider_netflix_url(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.launch_streaming_provider("netflix", "netflix://title/80018191")
        assert res is True
        mock_shell.assert_called_with("am start -a android.intent.action.VIEW -d 'netflix://title/80018191' -n com.netflix.ninja/.MainActivity")


def test_launch_streaming_provider_netflix_no_content(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.launch_streaming_provider("netflix")
        assert res is True
        mock_shell.assert_called_with("am start -n com.netflix.ninja/.MainActivity")


def test_launch_streaming_provider_youtube_video_id(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.launch_streaming_provider("youtube", "07d2dXHYb94")
        assert res is True
        mock_shell.assert_called_with("am start -a android.intent.action.VIEW -d 'https://www.youtube.com/watch?v=07d2dXHYb94' -n com.amazon.firetv.youtube/dev.cobalt.app.MainActivity")


def test_launch_streaming_provider_prime_asin(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.launch_streaming_provider("prime", "B08W53R987")
        assert res is True
        mock_shell.assert_called_with("am start -a android.intent.action.VIEW -d 'https://www.amazon.com/gp/video/detail/B08W53R987' -n com.amazon.avod/com.amazon.avod.client.activity.HomeScreenActivity")


def test_launch_streaming_provider_hotstar_id(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.launch_streaming_provider("hotstar", "1260014022")
        assert res is True
        mock_shell.assert_called_with("am start -a android.intent.action.VIEW -d 'https://www.hotstar.com/movies/1260014022' -n in.startv.hotstar/in.startv.hotstar.splash.SplashActivity")


def test_search_global(fire_tv):
    with patch.object(fire_tv, "wake"), \
         patch.object(fire_tv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        res = fire_tv.search_global("Interstellar")
        assert res is True
        mock_shell.assert_called_with("am start -a android.intent.action.SEARCH -e query 'Interstellar'")


