import unittest
from unittest.mock import MagicMock, patch

from orchestrator import SmartRoomOrchestrator, RoomAudioState
from resolver import ResolvedTrack


class TestSmartRoomOrchestrator(unittest.TestCase):

    def setUp(self):
        self.mock_resolver = MagicMock()
        self.mock_player = MagicMock()
        self.mock_bt_helper = MagicMock()
        self.mock_dp = MagicMock()
        self.mock_bt_helper.device_portal = self.mock_dp

        self.orchestrator = SmartRoomOrchestrator(
            resolver=self.mock_resolver,
            player=self.mock_player,
            bt_helper=self.mock_bt_helper
        )

    def test_initial_state_and_get_room_status_disconnected(self):
        self.mock_player.get_status.return_value = {"status": "IDLE"}
        self.mock_resolver.get_auth_status.return_value = {"is_authenticated": True, "auth_method": "oauth"}
        self.mock_bt_helper.scan_active_endpoints.return_value = (None, [])
        self.mock_dp.is_available.return_value = True

        status = self.orchestrator.get_room_status()
        self.assertEqual(status["room_audio_state"], RoomAudioState.DISCONNECTED.value)
        self.assertFalse(status["is_audio_ready"])
        self.assertIsNone(status["soundbar_name"])
        self.assertTrue(status["device_portal_available"])

    def test_connect_soundbar_already_connected(self):
        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        self.mock_bt_helper.scan_active_endpoints.return_value = (lg_mock, [lg_mock])

        ok, state, msg = self.orchestrator.connect_soundbar(timeout_seconds=2.0)
        self.assertTrue(ok)
        self.assertEqual(state, RoomAudioState.AUDIO_READY)
        self.assertEqual(msg, "ALREADY_CONNECTED")
        self.mock_bt_helper.request_device_portal_connect.assert_not_called()

    def test_connect_soundbar_success_after_polling(self):
        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        # 1st scan: missing, 2nd scan: present
        self.mock_bt_helper.scan_active_endpoints.side_effect = [
            (None, []),
            (lg_mock, [lg_mock])
        ]
        self.mock_bt_helper.request_device_portal_connect.return_value = (True, "REQUEST_ACCEPTED")

        ok, state, msg = self.orchestrator.connect_soundbar(timeout_seconds=3.0)
        self.assertTrue(ok)
        self.assertEqual(state, RoomAudioState.AUDIO_READY)
        self.assertEqual(msg, "AUDIO_READY")
        self.mock_bt_helper.request_device_portal_connect.assert_called_once()

    def test_connect_soundbar_timeout_returns_unavailable(self):
        self.mock_bt_helper.scan_active_endpoints.return_value = (None, [])
        self.mock_bt_helper.request_device_portal_connect.return_value = (True, "REQUEST_ACCEPTED")

        ok, state, msg = self.orchestrator.connect_soundbar(timeout_seconds=0.6)
        self.assertFalse(ok)
        self.assertEqual(state, RoomAudioState.AUDIO_OUTPUT_UNAVAILABLE)
        self.assertEqual(msg, "AUDIO_OUTPUT_UNAVAILABLE")

    def test_disconnect_soundbar_success(self):
        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        self.mock_dp.disconnect_lg.return_value = (True, "DISCONNECTED", 200)
        # after disconnect, scan returns None
        self.mock_bt_helper.scan_active_endpoints.return_value = (None, [])

        ok, state, msg = self.orchestrator.disconnect_soundbar()
        self.assertTrue(ok)
        self.assertEqual(state, RoomAudioState.DISCONNECTED)
        self.assertEqual(msg, "DISCONNECTED")
        self.mock_player.stop.assert_called_once()
        self.mock_dp.disconnect_lg.assert_called_once()

    def test_safe_play_success_when_ready(self):
        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        self.mock_bt_helper.scan_active_endpoints.return_value = (lg_mock, [lg_mock])
        self.mock_bt_helper.ensure_audio_endpoint.return_value = (True, lg_mock, "ALREADY_CONNECTED")
        self.mock_resolver.resolve.return_value = ResolvedTrack(
            title="Zara Zara",
            artist="Bombay Jayashri",
            duration=200,
            stream_url="https://audio.googlevideo.com/mock",
            video_id="mock_id",
            is_authenticated=True
        )
        self.mock_player.play.return_value = (True, None)
        self.mock_player.get_status.return_value = {
            "status": "PLAYING",
            "audio_output_status": "CONNECTED",
            "audio_device_id": lg_mock["id"],
            "audio_device_name": lg_mock["name"]
        }

        ok, data, error = self.orchestrator.safe_play("Zara Zara")
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(data["title"], "Zara Zara")
        self.assertEqual(data["audio_output_status"], "CONNECTED")
        self.assertEqual(self.orchestrator.current_state, RoomAudioState.PLAYING)

    def test_safe_play_fails_cleanly_when_soundbar_unavailable(self):
        self.mock_bt_helper.scan_active_endpoints.return_value = (None, [])
        self.mock_bt_helper.ensure_audio_endpoint.return_value = (False, None, "AUDIO_OUTPUT_UNAVAILABLE")
        self.mock_bt_helper.request_device_portal_connect.return_value = (False, "DEVICE_PORTAL_UNAVAILABLE")
        self.mock_resolver.resolve.return_value = ResolvedTrack(
            title="Zara Zara",
            artist="Bombay Jayashri",
            duration=200,
            stream_url="https://audio.googlevideo.com/mock",
            video_id="mock_id",
            is_authenticated=True
        )

    def test_movie_mode_health_healthy(self):
        mock_proj = MagicMock()
        mock_proj.get_device_info.return_value = {
            "power_state": "ON",
            "current_source": "HDMI_1"
        }
        mock_fire_tv = MagicMock()
        mock_fire_tv.get_status.return_value = {
            "reachable": True,
            "bluetooth": {"required_device_connected": True},
            "healthy": True
        }

        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        self.mock_bt_helper.scan_active_endpoints.return_value = (lg_mock, [lg_mock])

        orch = SmartRoomOrchestrator(
            resolver=self.mock_resolver,
            player=self.mock_player,
            bt_helper=self.mock_bt_helper,
            projector=mock_proj,
            fire_tv=mock_fire_tv
        )

        health = orch.get_movie_mode_health()
        self.assertTrue(health["healthy"])
        self.assertIsNone(health["degradation_reason"])
        self.assertTrue(health["projector_on"])
        self.assertTrue(health["projector_source_hdmi1"])

    def test_movie_mode_health_degraded_when_fire_tv_bluetooth_lost(self):
        mock_proj = MagicMock()
        mock_proj.get_device_info.return_value = {
            "power_state": "ON",
            "current_source": "HDMI_1"
        }
        mock_fire_tv = MagicMock()
        mock_fire_tv.get_status.return_value = {
            "reachable": True,
            "bluetooth": {"required_device_connected": False},
            "healthy": False
        }

        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        self.mock_bt_helper.scan_active_endpoints.return_value = (lg_mock, [lg_mock])

        orch = SmartRoomOrchestrator(
            resolver=self.mock_resolver,
            player=self.mock_player,
            bt_helper=self.mock_bt_helper,
            projector=mock_proj,
            fire_tv=mock_fire_tv
        )

        health = orch.get_movie_mode_health()
        self.assertFalse(health["healthy"])
        self.assertEqual(health["degradation_reason"], "Fire TV Bluetooth Disconnected")

    def test_start_and_stop_movie_mode_workflow(self):
        mock_proj = MagicMock()
        mock_proj.get_power_state.return_value = {"power_state": "ON"}
        mock_proj.get_device_info.return_value = {"power_state": "ON", "current_source": "HDMI_1"}
        mock_fire_tv = MagicMock()
        mock_fire_tv.get_status.return_value = {
            "reachable": True,
            "bluetooth": {"required_device_connected": True},
            "healthy": True
        }

        lg_mock = {"id": "wasapi/{mock-guid}", "name": "Speakers (LG SNC4R(79))"}
        self.mock_bt_helper.scan_active_endpoints.return_value = (lg_mock, [lg_mock])
        self.mock_dp.disconnect_lg.return_value = (True, "DISCONNECT_ACCEPTED", 200)

        orch = SmartRoomOrchestrator(
            resolver=self.mock_resolver,
            player=self.mock_player,
            bt_helper=self.mock_bt_helper,
            projector=mock_proj,
            fire_tv=mock_fire_tv
        )

        res_start = orch.start_movie_mode()
        self.assertEqual(res_start["status"], "HEALTHY")
        mock_fire_tv.wake.assert_called_once()
        mock_proj.set_hdmi.assert_called_with(1)

        res_stop = orch.stop_movie_mode()
        self.assertEqual(res_stop["status"], "OFF")
        mock_proj.power_off.assert_called_once()


if __name__ == "__main__":
    unittest.main()


