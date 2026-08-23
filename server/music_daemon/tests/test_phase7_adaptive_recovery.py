"""
ANIMUS SMART ROOM — PHASE 7 ADAPTIVE RECOVERY & INTELLIGENCE TEST SUITE
Validates dynamic room divergence detection, adaptive self-recovery,
competing request prioritization, and resource preemption in the Python subsystem.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from orchestrator import SmartRoomOrchestrator, RoomAudioState
from resolver import YouTubeMusicResolver, ResolvedTrack
from player import MpvPlayer
from projector_controller import ProjectorController, ProjectorPowerState, ProjectorSource
from fire_tv_controller import FireTvController


class TestPhase7AdaptiveRecovery:

    @pytest.fixture
    def mock_deps(self):
        resolver = MagicMock(spec=YouTubeMusicResolver)
        resolver.is_authenticated = True
        resolver.auth_method = "oauth"
        resolver.resolve.return_value = ResolvedTrack(
            video_id="v-adaptive-123",
            title="Zara Zara",
            artist="Bombay Jayashri",
            duration=298,
            stream_url="https://audio.stream.example.com/zara",
            is_authenticated=True
        )
        resolver.get_auth_status.return_value = {
            "is_authenticated": True,
            "auth_method": "oauth",
            "has_cookies": False
        }

        player = MagicMock(spec=MpvPlayer)
        player.get_status.return_value = {
            "status": "PLAYING",
            "title": "Zara Zara",
            "artist": "Bombay Jayashri",
            "duration": 298,
            "position": 10,
            "volume": 100,
            "audio_output_status": "CONNECTED",
            "audio_device_id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}",
            "audio_device_name": "Speakers (LG SNC4R(79))"
        }
        player.play.return_value = (True, None)
        player.stop.return_value = True
        player.pause.return_value = True
        player.resume.return_value = True

        player.bt_helper = MagicMock()
        player.bt_helper.scan_active_endpoints.return_value = (
            {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"},
            [{"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"}]
        )
        player.bt_helper.ensure_audio_endpoint.return_value = (
            True,
            {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"},
            200
        )
        player.bt_helper.request_device_portal_connect.return_value = (True, "Connected")
        player.bt_helper.device_portal.is_available.return_value = True
        player.bt_helper.device_portal.connect_lg.return_value = (True, "Connected", 200)
        player.bt_helper.device_portal.disconnect_lg.return_value = (True, "Disconnected", 200)
        player.bt_helper.last_reconnect_method = "device_portal_a2dp"
        player.bt_helper.last_reconnect_duration_ms = 350

        projector = MagicMock(spec=ProjectorController)
        projector.is_connected.return_value = (True, "device")
        projector.get_device_info.return_value = {
            "power_state": "ON",
            "current_source": "HDMI_1",
            "connected": True
        }
        projector.get_power_state.return_value = {
            "connected": True,
            "power_state": "ON",
            "confidence": "high",
            "state": "device",
            "interactive": True,
            "display_state": "ON"
        }
        projector.get_current_source.return_value = ProjectorSource.HDMI_1
        projector.set_source.return_value = True
        projector.set_hdmi.return_value = True
        projector.power_off.return_value = True

        fire_tv = MagicMock(spec=FireTvController)
        fire_tv.is_connected.return_value = (True, "device")
        fire_tv.get_status.return_value = {
            "reachable": True,
            "target": "192.168.1.5:5555",
            "state": "connected",
            "power_state": "Awake",
            "bluetooth": {
                "adapter_enabled": True,
                "required_device_address": "54:15:89:DC:A5:79",
                "required_device_connected": True,
                "state": "CONNECTED",
                "confidence": "high"
            },
            "healthy": True
        }
        fire_tv.get_bluetooth_status.return_value = {
            "adapter_enabled": True,
            "required_device_address": "54:15:89:DC:A5:79",
            "required_device_connected": True,
            "state": "CONNECTED",
            "confidence": "high"
        }
        fire_tv.is_required_bluetooth_connected.return_value = True
        fire_tv.wake.return_value = True
        fire_tv.sleep.return_value = True

        return {
            "resolver": resolver,
            "player": player,
            "projector": projector,
            "fire_tv": fire_tv
        }

    # -------------------------------------------------------------------------
    # TEST P7-01: MID-STREAM SOUNDBAR DISCONNECT AUTO-RECOVERY
    # -------------------------------------------------------------------------
    def test_p7_01_mid_stream_soundbar_disconnect_auto_recovery(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        # 1. Start safe playback
        ok, play_data, err = orch.safe_play("Zara Zara")
        assert ok is True
        assert orch.current_state == RoomAudioState.PLAYING

        # 2. Simulate mid-stream soundbar unpairing / dropout
        mock_deps["player"].bt_helper.scan_active_endpoints.side_effect = [
            (None, []),  # Initially dropped
            ({"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"}, [{"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"}])  # Emerges after reconnect
        ]
        mock_deps["player"].get_status.return_value = {
            "status": "STOPPED",
            "audio_output_status": "DISCONNECTED",
            "audio_device_id": None,
            "audio_device_name": None
        }

        # 3. Request reconnect & recover
        rec_ok, rec_state, _ = orch.connect_soundbar(timeout_seconds=5.0)
        assert rec_ok is True
        assert rec_state in (RoomAudioState.AUDIO_READY, RoomAudioState.CONNECTING)

    # -------------------------------------------------------------------------
    # TEST P7-02: COMPETING ROUTINE ARBITRATION (MUSIC -> MOVIE PREEMPTION)
    # -------------------------------------------------------------------------
    def test_p7_02_music_to_movie_priority_preemption(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        # 1. Active Music Mode
        orch.safe_play("Zara Zara")
        assert orch.current_state == RoomAudioState.PLAYING

        # 2. User commands Movie Mode (Higher Priority 70 > 50)
        movie_result = orch.start_movie_mode()
        assert movie_result["status"] == "HEALTHY"
        assert movie_result["health"]["healthy"] is True

        # 3. Invariant: PC Audio stopped so Fire TV can use Soundbar exclusively
        mock_deps["player"].stop.assert_called()

    # -------------------------------------------------------------------------
    # TEST P7-03: PROJECTOR INPUT DIVERGENCE SELF-HEALING
    # -------------------------------------------------------------------------
    def test_p7_03_projector_input_divergence_self_healing(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        # 1. Simulate Projector on wrong input (ANDROID)
        mock_deps["projector"].get_device_info.return_value = {
            "power_state": "ON",
            "current_source": "ANDROID",
            "connected": True
        }

        health_before = orch.get_movie_mode_health()
        assert health_before["healthy"] is False
        assert health_before["projector_source_hdmi1"] is False
        assert health_before["degradation_reason"] == "Projector not on HDMI_1"

        # 2. Start Movie Mode heals input
        orch.start_movie_mode()
        mock_deps["projector"].set_hdmi.assert_called_with(1)

    # -------------------------------------------------------------------------
    # TEST P7-04: FIRE TV BLUETOOTH DROPOUT DETECTION
    # -------------------------------------------------------------------------
    def test_p7_04_fire_tv_bluetooth_dropout_detection(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        # Simulate Fire TV Bluetooth unpairing from soundbar
        mock_deps["fire_tv"].get_status.return_value = {
            "reachable": True,
            "target": "192.168.1.5:5555",
            "state": "connected",
            "power_state": "Awake",
            "bluetooth": {
                "adapter_enabled": True,
                "required_device_address": "54:15:89:DC:A5:79",
                "required_device_connected": False,
                "state": "DISCONNECTED",
                "confidence": "high"
            },
            "healthy": False
        }

        health = orch.get_movie_mode_health()
        assert health["healthy"] is False
        assert health["degradation_reason"] == "Fire TV Bluetooth Disconnected"

    # -------------------------------------------------------------------------
    # TEST P7-05: BOUNDED RETRY & LATENCY TRACKING
    # -------------------------------------------------------------------------
    def test_p7_05_bounded_retry_and_latency_tracking(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        t0 = time.time()
        st = orch.get_room_status()
        dur = int((time.time() - t0) * 1000)

        assert "room_audio_state" in st
        assert "authentication" in st
        assert dur < 500  # Latency under 500ms
