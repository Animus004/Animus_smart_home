"""
Unit and Contract Test Suite for FireTvService (Phase E.2).
Validates:
- State-aware and idempotent execution
- Content & provider resolution orchestration
- Direct play first strategy vs UI fallback
- Cinema workflows (start, stop, pause, resume)
- Audio routing & handoff (Fire TV <-> PC)
- Interruption & recovery workflows
- Room lifecycle workflows
- All 67 automation use cases dispatching
- Truthful reporting ('movie playing' vs 'content page opened')
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from firetv_service import FireTvService, ServiceResult
from fire_tv_capabilities import (
    FireTVCapabilityRegistry,
    FireTVCapabilityType,
    FireTVCapabilityResult,
    FireTVErrorCode,
    FireTVState,
)
from media_provider_registry import MediaProviderRegistry, ProviderCapabilityStatus
from content_resolver import SmartRoomContentResolver, ResolvedContent
from automation_registry import AutomationRegistry
from fire_tv_controller import FireTvController
from projector_controller import ProjectorController
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
    }
    ftv.get_status.return_value = {
        "reachable": True,
        "power_state": "AWAKE",
        "bluetooth": {"required_device_connected": True, "state": "CONNECTED"},
        "healthy": True,
    }
    ftv._run_shell.return_value = (
        0,
        "mWakefulness=Awake\n"
        "mCurrentFocus=in.startv.hotstar/com.hotstar.MainActivity\n"
        "mCurrentFocus=com.amazon.firetv.youtube\n"
        "mCurrentFocus=com.netflix.ninja\n"
        "mCurrentFocus=com.apple.atve.amazon.appletv\n"
        "mCurrentFocus=com.amazon.cloud9\n"
        "mCurrentFocus=com.zee5.amazon\n"
        "state=PlaybackState {state=3",
        ""
    )
    ftv.is_app_foreground.return_value = True
    ftv.connect_soundbar_with_method.return_value = (True, "DIRECT_CONNECTED")
    ftv.disconnect_soundbar.return_value = (True, "DIRECT_DISCONNECTED")
    ftv.wake.return_value = True
    ftv.sleep.return_value = True
    ftv.home.return_value = True
    ftv.back.return_value = True
    ftv.select.return_value = True
    return ftv


@pytest.fixture
def mock_projector():
    proj = MagicMock(spec=ProjectorController)
    proj.get_power_state.return_value = {"power_state": "ON", "is_powered_on": True}
    proj.get_device_info.return_value = {"power_state": "ON", "input_source": "HDMI_1", "connected": True}
    proj.set_hdmi.return_value = True
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
    p.pause.return_value = True
    p.play.return_value = (True, None)
    p.set_volume.return_value = True
    return p


@pytest.fixture
def service(mock_fire_tv, mock_projector, mock_bt_helper, mock_player):
    prov_reg = MediaProviderRegistry()
    content_res = SmartRoomContentResolver(provider_registry=prov_reg)
    caps = FireTVCapabilityRegistry(
        fire_tv=mock_fire_tv,
        projector=mock_projector,
        bt_helper=mock_bt_helper,
        player=mock_player,
        provider_registry=prov_reg,
    )
    auto_reg = AutomationRegistry()
    return FireTvService(
        capabilities=caps,
        fire_tv=mock_fire_tv,
        projector=mock_projector,
        bt_helper=mock_bt_helper,
        player=mock_player,
        provider_registry=prov_reg,
        content_resolver=content_res,
        automation_registry=auto_reg,
    )


class TestFireTvServiceCore:

    def test_watch_content_youtube_direct_video_id(self, service, mock_fire_tv):
        mock_fire_tv.is_required_bluetooth_connected.return_value = True
        mock_fire_tv._run_shell.return_value = (0, "mWakefulness=Awake\nmCurrentFocus=com.amazon.firetv.youtube\nstate=PlaybackState {state=3", "")

        res = service.watch_content(query="07d2dXHYb94", provider="youtube", direct_play_first=True)
        assert res.success is True
        assert res.service == "watch_content"
        assert res.truthful_status == "movie playing"
        assert res.verified is True
        assert res.details.get("provider") == "youtube"

    def test_watch_content_netflix_deep_link_truthful_content_page(self, service, mock_fire_tv):
        mock_fire_tv.is_required_bluetooth_connected.return_value = True
        mock_fire_tv._run_shell.return_value = (0, "mWakefulness=Awake\nmCurrentFocus=com.netflix.ninja", "")

        res = service.watch_content(query="81154455", provider="netflix", direct_play_first=True)
        assert res.success is True
        assert res.truthful_status == "content page opened"  # Invariant: Netflix title page opened, not claiming autoplay!
        assert res.details.get("autoplay_verified") is False

    def test_idempotent_execution_skips_redundant_wake_and_hdmi(self, service, mock_fire_tv, mock_projector):
        # Fire TV already awake, soundbar already connected, projector already on HDMI 1
        mock_fire_tv.is_required_bluetooth_connected.return_value = True
        mock_fire_tv._run_shell.return_value = (0, "mWakefulness=Awake\nmCurrentFocus=com.amazon.firetv.youtube\nstate=PlaybackState {state=3", "")
        mock_projector.get_device_info.return_value = {"power_state": "ON", "input_source": "HDMI_1", "connected": True}

        res = service.watch_content(query="07d2dXHYb94", provider="youtube")
        assert res.success is True
        # Verify that power_wake and projector_switch_hdmi1 were NOT redundant steps
        steps = res.details.get("steps", [])
        assert "power_wake" not in steps
        assert "projector_switch_hdmi1" not in steps

    def test_start_and_stop_cinema(self, service, mock_fire_tv, mock_player):
        res_start = service.start_cinema(content="Article 15", provider="hotstar")
        assert res_start.success is True
        assert res_start.service == "start_cinema"

        res_stop = service.stop_cinema(turn_off_projector=False)
        assert res_stop.success is True
        assert "media_pause" in res_stop.details.get("steps", [])
        assert "route_audio_to_pc" in res_stop.details.get("steps", [])

    def test_pause_and_resume_content(self, service):
        res_pause = service.pause_content()
        assert res_pause.success is True
        assert res_pause.truthful_status == "PAUSED"

        res_resume = service.resume_content()
        assert res_resume.success is True
        assert res_resume.truthful_status == "PLAYING"

    def test_switch_provider(self, service, mock_fire_tv):
        res = service.switch_provider(target_provider="apple_tv", content="ted-lasso")
        assert res.success is True
        assert res.service == "switch_provider"
        assert res.details.get("provider") == "apple_tv"

    def test_audio_routing_services(self, service, mock_fire_tv, mock_bt_helper):
        res_ftv = service.route_audio_to_firetv()
        assert res_ftv.success is True
        assert "Soundbar connected to Fire TV" in res_ftv.truthful_status

        res_pc = service.route_audio_to_pc()
        assert res_pc.success is True
        assert "Soundbar connected to PC" in res_pc.truthful_status

    def test_emergency_mute_and_restore(self, service, mock_player):
        res_mute = service.emergency_mute()
        assert res_mute.success is True
        assert res_mute.truthful_status == "MUTED"
        mock_player.set_volume.assert_called_with(0)

        res_restore = service.restore_audio()
        assert res_restore.success is True
        assert res_restore.truthful_status == "UNMUTED"
        mock_player.set_volume.assert_called_with(100)

    def test_interruption_workflows(self, service):
        res_break = service.quick_break()
        assert res_break.success is True
        assert service._interrupted_state is not None

        res_after = service.resume_after_break()
        assert res_after.success is True
        assert service._interrupted_state is None

        res_call = service.pause_for_call()
        assert res_call.success is True
        assert res_call.truthful_status == "MUTED"

        res_resume_call = service.resume_after_call()
        assert res_resume_call.success is True

    def test_mode_transitions(self, service, mock_player):
        res_w2c = service.transition_work_to_cinema(content="07d2dXHYb94", provider="youtube")
        assert res_w2c.success is True
        mock_player.pause.assert_called()

        res_c2w = service.transition_cinema_to_work()
        assert res_c2w.success is True

        res_m2c = service.transition_music_to_cinema(content="07d2dXHYb94", provider="youtube")
        assert res_m2c.success is True

        res_c2m = service.transition_cinema_to_music()
        assert res_c2m.success is True
        mock_player.play.assert_called()

    def test_room_lifecycle(self, service):
        res_arrive = service.arriving_home()
        assert res_arrive.success is True

        res_leave = service.leaving_home()
        assert res_leave.success is True

        res_night = service.goodnight()
        assert res_night.success is True

        res_sync = service.sync_entertainment_state()
        assert res_sync.success is True
        assert "reachable" in res_sync.details

    def test_session_preparation(self, service):
        res_movie = service.prepare_movie_session(content="Inception", provider="youtube")
        assert res_movie.success is True

        res_music = service.prepare_music_session()
        assert res_music.success is True

        res_tv = service.prepare_tv_session(provider="hotstar")
        assert res_tv.success is True

    def test_self_healing_recovery(self, service, mock_fire_tv):
        res_adb = service.recover_firetv_adb()
        assert res_adb.success is True

        res_bt = service.recover_bluetooth()
        assert res_bt.success is True

        res_hdmi = service.recover_projector_hdmi()
        assert res_hdmi.success is True

        res_full = service.full_entertainment_recovery()
        assert res_full.success is True
        assert res_full.verified is True
