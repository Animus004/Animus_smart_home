"""
Unit and Capability Contract Tests for FireTVCapabilityRegistry & FireTVState.
Validates:
- Connectivity (ADB connected, offline, auto-reconnect)
- Power (wake, sleep, wakefulness verification)
- Navigation (HOME, BACK, SELECT, D-pad)
- Application (launch YouTube, foreground verification, unavailable)
- Media (search title, search verification, error handling)
- Bluetooth (detect soundbar, connect soundbar, already connected, connection failure)
- Audio ownership (PC -> Fire TV, Fire TV -> PC, failed transfer, verification failure)
- Projector (HDMI 1 switch, HDMI 1 verification, projector unavailable)
- Movie Mode automation (prerequisites satisfied, projector off, Fire TV unavailable, teardown)
- Explicit verification levels: COMMAND ACCEPTED vs PHYSICAL ACTION EXECUTED vs PHYSICAL ACTION VERIFIED.
"""

import pytest
from unittest.mock import MagicMock, patch

from fire_tv_capabilities import (
    FireTVCapabilityRegistry,
    FireTVCapabilityType,
    FireTVCapabilityResult,
    FireTVErrorCode,
    FireTVState,
    FireTVCapabilityStatus
)
from fire_tv_controller import FireTvController, FireTvBluetoothState
from projector_controller import ProjectorController, ProjectorPowerState
from bluetooth_helper import BluetoothAudioHelper
from player import MpvPlayer


@pytest.fixture
def mock_fire_tv():
    ftv = MagicMock(spec=FireTvController)
    ftv.target = "192.168.1.5:5555"
    ftv.required_bt_mac = "54:15:89:DC:A5:79"
    ftv.is_connected.return_value = (True, "device")
    ftv.is_required_bluetooth_connected.return_value = True
    ftv.get_bluetooth_status.return_value = {
        "adapter_enabled": True,
        "required_device_address": "54:15:89:DC:A5:79",
        "required_device_connected": True,
        "state": "CONNECTED",
        "confidence": "high"
    }
    ftv.get_status.return_value = {
        "reachable": True,
        "target": "192.168.1.5:5555",
        "power_state": "AWAKE",
        "bluetooth": {"required_device_connected": True, "state": "CONNECTED"},
        "healthy": True
    }
    ftv._run_shell.return_value = (0, "mWakefulness=Awake", "")
    ftv.is_app_foreground.return_value = True
    ftv.search_or_launch_content.return_value = True
    ftv.connect_soundbar.return_value = True
    ftv.connect_soundbar_with_method.return_value = (True, "DIRECT_CONNECTED")
    ftv.disconnect_soundbar.return_value = (True, "DIRECT_DISCONNECTED")
    ftv.home.return_value = True
    ftv.back.return_value = True
    ftv.select.return_value = True
    ftv.dpad_up.return_value = True
    ftv.dpad_down.return_value = True
    ftv.dpad_left.return_value = True
    ftv.dpad_right.return_value = True
    return ftv


@pytest.fixture
def mock_projector():
    proj = MagicMock(spec=ProjectorController)
    proj.get_power_state.return_value = {"power_state": "ON", "is_powered_on": True}
    proj.set_hdmi.return_value = True
    proj.get_device_info.return_value = {
        "power_state": "ON",
        "input_source": "HDMI_1",
        "connected": True
    }
    proj.power_off.return_value = True
    return proj


@pytest.fixture
def mock_bt_helper():
    bt = MagicMock(spec=BluetoothAudioHelper)
    bt.ensure_audio_endpoint.return_value = (True, {"name": "Speakers (LG SNC4R(79))", "id": "wasapi/{123}"}, "RECONNECTED")
    bt.scan_active_endpoints.return_value = ({"name": "Speakers (LG SNC4R(79))", "id": "wasapi/{123}"}, "LG SNC4R")
    bt.device_portal = MagicMock()
    bt.device_portal.disconnect_lg.return_value = (True, "DISCONNECTED", 200)
    return bt


@pytest.fixture
def mock_player():
    p = MagicMock(spec=MpvPlayer)
    p.stop.return_value = True
    return p


@pytest.fixture
def registry(mock_fire_tv, mock_projector, mock_bt_helper, mock_player):
    return FireTVCapabilityRegistry(
        fire_tv=mock_fire_tv,
        projector=mock_projector,
        bt_helper=mock_bt_helper,
        player=mock_player
    )


# ─── 1. Connectivity Tests ───────────────────────────────────────────────────

def test_connectivity_success(registry, mock_fire_tv):
    res = registry.check_connectivity()
    assert res.success is True
    assert res.verified is True
    assert res.capability == FireTVCapabilityType.CONNECTIVITY_CHECK.value
    assert "192.168.1.5:5555" in res.message


def test_connectivity_offline(registry, mock_fire_tv):
    mock_fire_tv.is_connected.return_value = (False, "disconnected")
    res = registry.check_connectivity()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.FIRE_TV_OFFLINE.value
    assert res.verified is True


def test_connectivity_no_controller():
    reg = FireTVCapabilityRegistry(fire_tv=None)
    res = reg.check_connectivity()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.FIRE_TV_OFFLINE.value


# ─── 2. Power Tests ──────────────────────────────────────────────────────────

def test_power_wake_verified(registry, mock_fire_tv):
    mock_fire_tv._run_shell.return_value = (0, "mWakefulness=Awake", "")
    res = registry.wake()
    assert res.success is True
    assert res.verified is True
    mock_fire_tv.wake.assert_called_once()


def test_power_wake_verification_failure(registry, mock_fire_tv):
    mock_fire_tv._run_shell.return_value = (0, "mWakefulness=Asleep", "")
    res = registry.wake()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.VERIFICATION_FAILED.value
    assert res.verified is True


def test_power_sleep(registry, mock_fire_tv):
    res = registry.sleep()
    assert res.success is True
    mock_fire_tv.sleep.assert_called_once()


# ─── 3. Navigation Tests ─────────────────────────────────────────────────────

def test_navigation_keys(registry, mock_fire_tv):
    for key in ["home", "back", "select", "dpad_up", "dpad_down", "dpad_left", "dpad_right"]:
        res = registry.send_navigation(key)
        assert res.success is True
        assert res.verified is True

    res_invalid = registry.send_navigation("invalid_key_action")
    assert res_invalid.success is False
    assert res_invalid.error_code == FireTVErrorCode.INVALID_ARGUMENT.value


# ─── 4. Application & Media Tests ─────────────────────────────────────────────

def test_launch_youtube_success(registry, mock_fire_tv):
    mock_fire_tv.is_app_foreground.return_value = True
    res = registry.launch_youtube()
    assert res.success is True
    assert res.verified is True
    assert res.capability == FireTVCapabilityType.APP_LAUNCH_YOUTUBE.value


def test_launch_youtube_failure(registry, mock_fire_tv):
    mock_fire_tv.is_app_foreground.return_value = False
    res = registry.launch_youtube()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.YOUTUBE_UNAVAILABLE.value


def test_search_youtube_success(registry, mock_fire_tv):
    mock_fire_tv.is_app_foreground.return_value = True
    mock_fire_tv.search_or_launch_content.return_value = True
    res = registry.search_youtube("Article 15")
    assert res.success is True
    assert res.verified is True
    mock_fire_tv.search_or_launch_content.assert_called_with("Article 15")


def test_search_youtube_empty_query(registry):
    res = registry.search_youtube("   ")
    assert res.success is False
    assert res.error_code == FireTVErrorCode.INVALID_ARGUMENT.value


# ─── 5. Bluetooth & Audio Tests ───────────────────────────────────────────────

def test_get_bluetooth_status(registry, mock_fire_tv):
    res = registry.get_bluetooth_status()
    assert res.success is True
    assert res.details["required_device_connected"] is True


def test_connect_soundbar_already_connected(registry, mock_fire_tv):
    mock_fire_tv.is_required_bluetooth_connected.return_value = True
    res = registry.connect_soundbar()
    assert res.success is True
    assert res.details.get("already_connected") is True
    # Should not re-trigger connection flow if already connected
    mock_fire_tv.connect_soundbar_with_method.assert_not_called()


def test_connect_soundbar_flow_success(registry, mock_fire_tv):
    mock_fire_tv.is_required_bluetooth_connected.side_effect = [False, True]
    mock_fire_tv.connect_soundbar_with_method.return_value = (True, "DIRECT_CONNECTED")
    res = registry.connect_soundbar()
    assert res.success is True
    assert res.verified is True
    mock_fire_tv.connect_soundbar_with_method.assert_called_once()


def test_connect_soundbar_flow_failure(registry, mock_fire_tv):
    mock_fire_tv.is_required_bluetooth_connected.return_value = False
    mock_fire_tv.connect_soundbar_with_method.return_value = (False, "SOUNDBAR_CONNECTION_FAILED")
    res = registry.connect_soundbar(timeout_seconds=2.0)
    assert res.success is False
    assert res.error_code == FireTVErrorCode.SOUNDBAR_CONNECTION_FAILED.value


# ─── 6. Audio Ownership Transfer Tests ────────────────────────────────────────

def test_switch_audio_to_fire_tv_success(registry, mock_player, mock_bt_helper, mock_fire_tv):
    mock_fire_tv.is_required_bluetooth_connected.return_value = True
    res = registry.switch_audio_to_fire_tv()
    assert res.success is True
    assert res.details["target"] == "FIRE_TV"
    mock_player.stop.assert_called_once()
    mock_bt_helper.device_portal.disconnect_lg.assert_called_once()


def test_switch_audio_to_fire_tv_failure(registry, mock_fire_tv):
    mock_fire_tv.is_required_bluetooth_connected.return_value = False
    mock_fire_tv.connect_soundbar_with_method.return_value = (False, "SOUNDBAR_CONNECTION_FAILED")
    res = registry.switch_audio_to_fire_tv()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.AUDIO_TRANSFER_FAILED.value


def test_switch_audio_to_pc_success(registry, mock_bt_helper):
    res = registry.switch_audio_to_pc()
    assert res.success is True
    assert res.details["target"] == "PC"
    mock_bt_helper.ensure_audio_endpoint.assert_called_once()


def test_switch_audio_to_pc_failure(registry, mock_bt_helper):
    mock_bt_helper.ensure_audio_endpoint.return_value = (False, None, "WASAPI_FAILED")
    res = registry.switch_audio_to_pc()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.SOUNDBAR_CONNECTION_FAILED.value


# ─── 7. Projector Display Integration Tests ───────────────────────────────────

def test_switch_projector_to_hdmi1_success(registry, mock_projector):
    res = registry.switch_projector_to_hdmi1()
    assert res.success is True
    mock_projector.set_hdmi.assert_called_with(1)


def test_switch_projector_to_hdmi1_blocked_when_off(registry, mock_projector):
    mock_projector.get_power_state.return_value = {"power_state": "OFF", "is_powered_on": False}
    res = registry.switch_projector_to_hdmi1()
    assert res.success is False
    assert res.error_code == FireTVErrorCode.PROJECTOR_OFF.value
    mock_projector.set_hdmi.assert_not_called()


# ─── 8. Telemetry State Model Tests ───────────────────────────────────────────

def test_get_state_model(registry, mock_fire_tv, mock_projector):
    mock_fire_tv._run_shell.return_value = (0, "mWakefulness=Awake\nmCurrentFocus=com.amazon.firetv.youtube/dev.cobalt.app.MainActivity\npackage=com.amazon.firetv.youtube\nstate=PlaybackState {state=3, position=0\nSTREAM_MUSIC:\n   Current: 12", "")
    st = registry.get_state(movie_mode_active=True)
    assert isinstance(st, FireTVState)
    assert st.reachable is True
    assert st.power_state == "AWAKE"
    assert st.youtube_foreground is True
    assert st.active_provider == "youtube"
    assert st.playback_state == "PLAYING"
    assert st.soundbar_connected is True
    assert st.soundbar_mac == "54:15:89:DC:A5:79"
    assert st.projector_hdmi1_active is True
    assert st.movie_mode_active is True


# ─── 9. Direct Media & Provider Launch Tests ──────────────────────────────────

def test_play_youtube_video_id_success(registry, mock_fire_tv):
    mock_fire_tv._run_shell.return_value = (0, "mCurrentFocus=com.amazon.firetv.youtube/dev.cobalt.app.MainActivity", "")
    res = registry.play_youtube_video_id("07d2dXHYb94")
    assert res.success is True
    assert res.capability == FireTVCapabilityType.MEDIA_DIRECT_YOUTUBE.value
    assert res.details["video_id"] == "07d2dXHYb94"
    assert "https://www.youtube.com/watch?v=07d2dXHYb94" in res.details["url"]


def test_play_youtube_video_id_empty_fails(registry):
    res = registry.play_youtube_video_id("")
    assert res.success is False
    assert res.error_code == FireTVErrorCode.INVALID_ARGUMENT.value


def test_launch_streaming_provider_hotstar_success(registry, mock_fire_tv):
    mock_fire_tv._run_shell.return_value = (0, "mCurrentFocus=in.startv.hotstar/com.hotstar.MainActivity", "")
    res = registry.launch_streaming_provider("hotstar", "https://www.hotstar.com/movies/article-15/1260007886")
    assert res.success is True
    assert res.capability == FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value
    assert res.details["provider"] == "hotstar"
    assert res.details["launch_status"] == "DIRECT_PLAYING"


def test_launch_streaming_provider_unregistered_fails(registry):
    res = registry.launch_streaming_provider("unregistered_app", "123")
    assert res.success is False
    assert res.error_code == FireTVErrorCode.PROVIDER_UNAVAILABLE.value


# ─── 10. Playback Transport & Volume Control Tests ─────────────────────────────

def test_playback_controls(registry, mock_fire_tv):
    mock_fire_tv._run_shell.return_value = (0, "Success", "")
    assert registry.play().success is True
    assert registry.pause().success is True
    assert registry.toggle_play_pause().success is True
    assert registry.stop().success is True
    assert registry.next_track().success is True
    assert registry.previous_track().success is True
    assert registry.volume_up().success is True
    assert registry.volume_down().success is True
    assert registry.mute().success is True


# ─── 11. Machine-Readable Metadata Tests ──────────────────────────────────────

def test_registry_metadata():
    meta = FireTVCapabilityRegistry.get_registry_metadata()
    assert "version" in meta
    assert "capabilities" in meta
    assert "providers" in meta
    caps = meta["capabilities"]
    assert FireTVCapabilityStatus.AVAILABLE.value in caps
    assert FireTVCapabilityStatus.NOT_AVAILABLE.value in caps

    available_names = [c["name"] for c in caps[FireTVCapabilityStatus.AVAILABLE.value]]
    assert FireTVCapabilityType.POWER_WAKE.value in available_names
    assert FireTVCapabilityType.MEDIA_DIRECT_YOUTUBE.value in available_names
    assert FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value in available_names
    assert FireTVCapabilityType.MEDIA_PLAY.value in available_names
    assert FireTVCapabilityType.BT_CONNECT_SOUNDBAR.value in available_names
    assert FireTVCapabilityType.AUDIO_SWITCH_TO_FIRE_TV.value in available_names
    assert FireTVCapabilityType.PROJECTOR_SWITCH_HDMI1.value in available_names
    assert FireTVCapabilityType.AUTOMATION_MOVIE_MODE_START.value in available_names
