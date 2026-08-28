"""
Unit tests for 30 Smart Room High-Value Automations & Room State Transitions.
"""

import pytest
from unittest.mock import MagicMock, patch

from orchestrator import SmartRoomOrchestrator, RoomAudioState, RoomState
from player import MpvPlayer
from queue_manager import PlaybackQueue
from resolver import YouTubeMusicResolver
from fire_tv_controller import FireTvController
from projector_controller import ProjectorController


@pytest.fixture
def mock_orchestrator():
    mock_resolver = MagicMock(spec=YouTubeMusicResolver)
    mock_resolver.ytm = MagicMock()
    mock_resolver._execute_with_ytm.return_value = [{"videoId": "07d2dXHYb94", "title": "Inception Trailer"}]
    mock_player = MagicMock(spec=MpvPlayer)
    mock_player.get_status.return_value = {"playback_status": "STOPPED"}
    mock_player.play.return_value = (True, None)

    mock_bt = MagicMock()
    mock_bt.scan_active_endpoints.return_value = ({"id": "lg_id", "name": "LG SNC4R(79)"}, [])
    mock_bt.device_portal.disconnect_lg.return_value = (True, "OK", 200)
    mock_bt.device_portal.is_available.return_value = True
    mock_bt.ensure_audio_endpoint.return_value = (True, {"id": "lg_id", "name": "LG SNC4R(79)"}, 200)

    mock_ftv = MagicMock(spec=FireTvController)
    mock_ftv.is_connected.return_value = (True, "device")
    mock_ftv.is_required_bluetooth_connected.return_value = True
    mock_ftv.connect_soundbar_with_method.return_value = (True, "DIRECT_CONNECTED")
    mock_ftv.disconnect_soundbar.return_value = (True, "DIRECT_DISCONNECTED")
    mock_ftv.get_bluetooth_status.return_value = {"required_device_connected": True}
    mock_ftv.get_status.return_value = {"reachable": True, "power_state": "AWAKE", "bluetooth": {"required_device_connected": True}, "healthy": True}
    mock_ftv._run_shell.return_value = (0, "mCurrentFocus=in.startv.hotstar/com.hotstar.MainActivity\nmCurrentFocus=com.amazon.firetv.youtube\nmCurrentFocus=com.netflix.ninja\nmCurrentFocus=com.amazon.cloud9\nmWakefulness=Awake\nstate=PlaybackState {state=3", "")
    mock_ftv.is_app_foreground.return_value = True
    mock_ftv.launch_streaming_provider.return_value = True
    mock_ftv.play_video.return_value = True
    mock_ftv.search_or_launch_content.return_value = True

    mock_projector = MagicMock(spec=ProjectorController)
    mock_projector.get_power_state.return_value = {"power_state": "ON"}
    mock_projector.get_device_info.return_value = {"power_state": "ON", "current_source": "HDMI_1"}
    mock_projector.set_hdmi.return_value = True
    mock_projector.power_off.return_value = True

    orch = SmartRoomOrchestrator(
        resolver=mock_resolver,
        player=mock_player,
        bt_helper=mock_bt,
        projector=mock_projector,
        fire_tv=mock_ftv,
        queue=PlaybackQueue()
    )
    return orch


class TestRoomAutomations:

    def test_room_state_idle(self, mock_orchestrator):
        mock_orchestrator.fire_tv.get_bluetooth_status.return_value = {"required_device_connected": False}
        st = mock_orchestrator.get_room_state()
        assert st["room_state"] == RoomState.IDLE.value

    def test_room_state_pc_audio_active(self, mock_orchestrator):
        mock_orchestrator.player.get_status.return_value = {"playback_status": "PLAYING"}
        st = mock_orchestrator.get_room_state()
        assert st["room_state"] == RoomState.PC_AUDIO_ACTIVE.value

    def test_room_state_movie_active(self, mock_orchestrator):
        mock_orchestrator._in_movie_mode = True
        st = mock_orchestrator.get_room_state()
        assert st["room_state"] == RoomState.MOVIE_ACTIVE.value

    def test_automation_start_movie_direct(self, mock_orchestrator):
        res = mock_orchestrator.execute_automation("start_movie_direct", content="Article 15", provider="hotstar")
        assert res["success"] is True
        assert res["content"] == "Article 15"

    def test_automation_pause_resume_movie(self, mock_orchestrator):
        res_pause = mock_orchestrator.execute_automation("pause_movie")
        assert res_pause["action"] == "PAUSE"
        res_resume = mock_orchestrator.execute_automation("resume_movie")
        assert res_resume["action"] == "PLAY"

    def test_automation_watch_providers(self, mock_orchestrator):
        res_yt = mock_orchestrator.execute_automation("watch_youtube_content", query="07d2dXHYb94")
        assert res_yt["success"] is True

        res_nf = mock_orchestrator.execute_automation("watch_netflix_content", title="Stranger Things")
        assert res_nf["success"] is True

        res_pv = mock_orchestrator.execute_automation("watch_prime_content", title="Mirzapur")
        assert res_pv["success"] is True

    def test_automation_audio_routing(self, mock_orchestrator):
        res_ftv = mock_orchestrator.execute_automation("route_audio_to_fire_tv")
        assert res_ftv["success"] is True
        assert res_ftv["target"] == "FIRE_TV"

        mock_orchestrator.connect_soundbar = MagicMock(return_value=(True, RoomAudioState.AUDIO_READY, "AUDIO_READY"))
        res_pc = mock_orchestrator.execute_automation("route_audio_to_pc")
        assert res_pc["success"] is True
        assert res_pc["target"] == "PC"

    def test_automation_projector_controls(self, mock_orchestrator):
        res_p_ftv = mock_orchestrator.execute_automation("projector_fire_tv_mode")
        assert res_p_ftv["source"] == "HDMI_1"

        res_p_pc = mock_orchestrator.execute_automation("projector_pc_mode")
        assert res_p_pc["source"] == "HDMI_2"

        res_p_off = mock_orchestrator.execute_automation("safe_projector_shutdown")
        assert res_p_off["power_state"] == "OFF"

    def test_automation_transitions(self, mock_orchestrator):
        res_m2m = mock_orchestrator.execute_automation("music_to_movie_transition", content="Inception")
        assert res_m2m["success"] is True

        mock_orchestrator.safe_play = MagicMock(return_value=(True, {"title": "Lofi Beat"}, None))
        res_mov2mus = mock_orchestrator.execute_automation("movie_to_music_transition", song_query="Lofi Beat")
        assert res_mov2mus["success"] is True

    def test_automation_break_and_goodnight(self, mock_orchestrator):
        res_break = mock_orchestrator.execute_automation("quick_break")
        assert res_break["action"] == "PAUSE"

        res_resume = mock_orchestrator.execute_automation("resume_after_break")
        assert res_resume["action"] == "PLAY"

        res_gn = mock_orchestrator.execute_automation("goodnight")
        assert res_gn["success"] is True
        assert res_gn["action"] == "GOODNIGHT_COMPLETE"

    def test_automation_emergency_mute(self, mock_orchestrator):
        res_mute = mock_orchestrator.execute_automation("emergency_mute")
        assert res_mute["success"] is True
        mock_orchestrator.player.set_volume.assert_called_with(0)

    def test_automation_unknown(self, mock_orchestrator):
        res = mock_orchestrator.execute_automation("non_existent_automation")
        assert res["success"] is False
        assert "Unknown automation" in res["error"]
