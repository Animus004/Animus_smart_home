"""
Integration and Contract Test Suite for Phase E.2 FastAPI Service Endpoints.
Validates:
- POST /api/room/service/watch
- POST /api/room/service/cinema/start
- POST /api/room/service/cinema/stop
- POST /api/room/service/cinema/pause
- POST /api/room/service/cinema/resume
- POST /api/room/service/provider/switch
- POST /api/room/service/audio/route
- POST /api/room/service/recover
- GET  /api/room/service/state
- GET  /api/room/service/automations
- POST /api/room/service/automation/execute
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app, firetv_service, orchestrator, fire_tv, projector, player
from firetv_service import ServiceResult
from fire_tv_capabilities import FireTVState


@pytest.fixture
def client():
    return TestClient(app)


class TestServiceEndpoints:

    def test_get_service_state_endpoint(self, client):
        with patch.object(firetv_service, "get_live_state") as mock_state:
            mock_state.return_value = FireTVState(
                reachable=True,
                power_state="AWAKE",
                foreground_app="com.amazon.firetv.youtube",
                soundbar_connected=True,
                projector_hdmi1_active=True
            )
            response = client.get("/api/room/service/state")
            assert response.status_code == 200
            data = response.json()
            assert data["reachable"] is True
            assert data["power_state"] == "AWAKE"
            assert data["soundbar_connected"] is True
            assert data["projector_hdmi1_active"] is True

    def test_post_service_watch_endpoint(self, client):
        with patch.object(firetv_service, "watch_content") as mock_watch:
            mock_watch.return_value = ServiceResult(
                service="watch_content",
                success=True,
                action_taken="direct_launch_youtube",
                truthful_status="movie playing",
                message="YouTube video launched.",
                details={"provider": "youtube", "resolved_id": "07d2dXHYb94"},
                duration_ms=250,
                verified=True
            )
            payload = {"query": "07d2dXHYb94", "provider": "youtube", "direct_play_first": True}
            response = client.post("/api/room/service/watch", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["truthful_status"] == "movie playing"
            assert data["verified"] is True

    def test_post_service_cinema_start_stop(self, client):
        with patch.object(firetv_service, "start_cinema") as mock_start, \
             patch.object(firetv_service, "stop_cinema") as mock_stop:
            mock_start.return_value = ServiceResult(
                service="watch_content",
                success=True,
                action_taken="power_wake, projector_switch_hdmi1, direct_launch_hotstar",
                truthful_status="movie playing",
                message="Cinema started.",
                verified=True
            )
            mock_stop.return_value = ServiceResult(
                service="stop_cinema",
                success=True,
                action_taken="media_pause, route_audio_to_pc",
                truthful_status="cinema stopped and audio restored to PC",
                message="Cinema stopped.",
                verified=True
            )

            res_start = client.post("/api/room/service/cinema/start", json={"content": "Article 15", "provider": "hotstar"})
            assert res_start.status_code == 200
            assert res_start.json()["success"] is True

            res_stop = client.post("/api/room/service/cinema/stop", json={"turn_off_projector": False})
            assert res_stop.status_code == 200
            assert res_stop.json()["success"] is True

    def test_post_service_cinema_pause_resume(self, client):
        with patch.object(firetv_service, "pause_content") as mock_pause, \
             patch.object(firetv_service, "resume_content") as mock_resume:
            mock_pause.return_value = ServiceResult(
                service="pause_content",
                success=True,
                action_taken="media_pause",
                truthful_status="PAUSED",
                verified=True
            )
            mock_resume.return_value = ServiceResult(
                service="resume_content",
                success=True,
                action_taken="media_play",
                truthful_status="PLAYING",
                verified=True
            )

            res_pause = client.post("/api/room/service/cinema/pause")
            assert res_pause.status_code == 200
            assert res_pause.json()["truthful_status"] == "PAUSED"

            res_resume = client.post("/api/room/service/cinema/resume")
            assert res_resume.status_code == 200
            assert res_resume.json()["truthful_status"] == "PLAYING"

    def test_post_service_provider_switch(self, client):
        with patch.object(firetv_service, "switch_provider") as mock_switch:
            mock_switch.return_value = ServiceResult(
                service="watch_content",
                success=True,
                action_taken="direct_launch_netflix",
                truthful_status="content page opened",
                details={"provider": "netflix"},
                verified=True
            )
            payload = {"target_provider": "netflix", "content": "Stranger Things"}
            response = client.post("/api/room/service/provider/switch", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["truthful_status"] == "content page opened"

    def test_post_service_audio_route(self, client):
        with patch.object(firetv_service, "route_audio_to_firetv") as mock_ftv, \
             patch.object(firetv_service, "route_audio_to_pc") as mock_pc:
            mock_ftv.return_value = ServiceResult(
                service="route_audio_to_firetv",
                success=True,
                action_taken="audio_switch_to_fire_tv",
                truthful_status="Soundbar connected to Fire TV (A2DP)",
                verified=True
            )
            mock_pc.return_value = ServiceResult(
                service="route_audio_to_pc",
                success=True,
                action_taken="audio_switch_to_pc",
                truthful_status="Soundbar connected to PC",
                verified=True
            )

            res_ftv = client.post("/api/room/service/audio/route", json={"target": "FIRE_TV"})
            assert res_ftv.status_code == 200
            assert res_ftv.json()["success"] is True

            res_pc = client.post("/api/room/service/audio/route", json={"target": "PC"})
            assert res_pc.status_code == 200
            assert res_pc.json()["success"] is True

            res_bad = client.post("/api/room/service/audio/route", json={"target": "UNKNOWN"})
            assert res_bad.status_code == 400

    def test_post_service_recover(self, client):
        with patch.object(firetv_service, "full_entertainment_recovery") as mock_rec:
            mock_rec.return_value = ServiceResult(
                service="full_entertainment_recovery",
                success=True,
                action_taken="adb=True, hdmi=True, bt=True, media=True",
                truthful_status="Full recovery complete",
                verified=True
            )
            response = client.post("/api/room/service/recover", json={"subsystem": "all"})
            assert response.status_code == 200
            assert response.json()["success"] is True

    def test_get_service_automations_list(self, client):
        response = client.get("/api/room/service/automations")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 67
        assert len(data["automations"]) == 67

    def test_post_service_automation_execute(self, client):
        with patch.object(firetv_service, "execute_automation") as mock_exec:
            mock_exec.return_value = ServiceResult(
                service="start_cinema",
                success=True,
                action_taken="start_cinema",
                truthful_status="movie playing",
                verified=True
            )
            payload = {"automation_id": "start_cinema", "params": {"content": "Article 15", "provider": "hotstar"}}
            response = client.post("/api/room/service/automation/execute", json=payload)
            assert response.status_code == 200
            assert response.json()["success"] is True
