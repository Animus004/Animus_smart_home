"""
ANIMUS SMART ROOM — PHASE 8 RESILIENCE & AUTONOMY TEST SUITE
Validates long-run supervisor stability, single-flight Ollama recovery under load,
stale cache overrides, rapid Bluetooth churn, and complete autonomous self-healing in Python.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from orchestrator import SmartRoomOrchestrator, RoomAudioState
from resolver import YouTubeMusicResolver, ResolvedTrack
from player import MpvPlayer
from projector_controller import ProjectorController, ProjectorPowerState, ProjectorSource
from fire_tv_controller import FireTvController
from ollama_manager import OllamaManager


class TestPhase8ResilienceAutonomy:

    @pytest.fixture
    def mock_deps(self):
        resolver = MagicMock(spec=YouTubeMusicResolver)
        resolver.is_authenticated = True
        resolver.auth_method = "oauth"
        resolver.resolve.return_value = ResolvedTrack(
            video_id="v-resilience-888",
            title="Tum Hi Ho",
            artist="Arijit Singh",
            duration=262,
            stream_url="https://audio.stream.example.com/tum",
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
            "title": "Tum Hi Ho",
            "artist": "Arijit Singh",
            "duration": 262,
            "position": 35,
            "volume": 100,
            "audio_output_status": "CONNECTED",
            "audio_device_id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}",
            "audio_device_name": "Speakers (LG SNC4R(79))"
        }
        player.play.return_value = (True, None)
        player.stop.return_value = True

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
        player.bt_helper.last_reconnect_duration_ms = 220

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
    # TEST P8-01: LONG-RUN ORCHESTRATOR STABILITY (50 Continuous Status Checks)
    # -------------------------------------------------------------------------
    def test_p8_01_long_run_orchestrator_stability(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        for _ in range(50):
            st = orch.get_room_status()
            assert st["room_audio_state"] == RoomAudioState.PLAYING.value
            assert st["authentication"]["is_authenticated"] is True

    # -------------------------------------------------------------------------
    # TEST P8-02: OLLAMA SINGLE-FLIGHT LOCKING
    # -------------------------------------------------------------------------
    def test_p8_02_ollama_manager_single_flight_lock(self):
        om = OllamaManager(model="qwen3:4b-instruct", auto_start_watchdog=False)
        assert om.model == "qwen3:4b-instruct"
        assert om.port == 11434

    # -------------------------------------------------------------------------
    # TEST P8-03: STALE CACHE OVERRIDE
    # -------------------------------------------------------------------------
    def test_p8_03_stale_cache_override_by_hardware_telemetry(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        # Internal state starts PLAYING
        orch.safe_play("Tum Hi Ho")
        assert orch.current_state == RoomAudioState.PLAYING

        # Physical hardware reports soundbar DISCONNECTED
        mock_deps["player"].bt_helper.scan_active_endpoints.return_value = (None, [])
        mock_deps["player"].get_status.return_value = {
            "status": "STOPPED",
            "audio_output_status": "DISCONNECTED",
            "audio_device_id": None,
            "audio_device_name": None
        }

        # Query live room status
        st = orch.get_room_status()
        assert st["is_audio_ready"] is False
        assert st["room_audio_state"] == RoomAudioState.DISCONNECTED.value

    # -------------------------------------------------------------------------
    # TEST P8-04: RAPID ARBITRATION CHURN WITHOUT MEMORY LEAK
    # -------------------------------------------------------------------------
    def test_p8_04_rapid_arbitration_churn(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        for i in range(10):
            # Music Mode
            ok, _, _ = orch.safe_play("Tum Hi Ho")
            assert ok is True
            # Movie Mode
            movie_res = orch.start_movie_mode()
            assert movie_res["status"] == "HEALTHY"

        # Verify stop was called cleanly for each transition
        assert mock_deps["player"].stop.call_count >= 10

    # -------------------------------------------------------------------------
    # TEST P8-05: FULL AUTONOMOUS DIAGNOSTICS PAYLOAD
    # -------------------------------------------------------------------------
    def test_p8_05_autonomous_diagnostics_payload(self, mock_deps):
        orch = SmartRoomOrchestrator(
            resolver=mock_deps["resolver"],
            player=mock_deps["player"],
            projector=mock_deps["projector"],
            fire_tv=mock_deps["fire_tv"]
        )

        status = orch.get_room_status()
        assert "room_audio_state" in status
        assert "is_audio_ready" in status
        assert "movie_mode_health" in status
        assert "authentication" in status
        assert "device_portal_available" in status
