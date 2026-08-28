"""
Tests for Phase B Android <-> PC Routing Consolidation:
Movie Mode REST endpoints, content parameter propagation ("Article 15"),
Fire TV content launching, and audio ownership preemption.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from orchestrator import SmartRoomOrchestrator, RoomAudioState
from fire_tv_controller import FireTvController
from projector_controller import ProjectorController, ProjectorPowerState, ProjectorSource
from main import app


@pytest.fixture
def mock_fire_tv():
    ftv = MagicMock(spec=FireTvController)
    ftv.is_connected.return_value = (True, "device")
    ftv.wake.return_value = True
    ftv.sleep.return_value = True
    ftv.search_or_launch_content.return_value = True
    ftv.get_status.return_value = {
        "reachable": True,
        "power_state": "AWAKE",
        "healthy": True,
        "bluetooth": {"required_device_connected": True}
    }
    return ftv


@pytest.fixture
def mock_projector():
    proj = MagicMock(spec=ProjectorController)
    proj.is_connected.return_value = (True, "device")
    proj.get_power_state.return_value = {"power_state": "ON"}
    proj.get_device_info.return_value = {"power_state": "ON", "current_source": "HDMI_1"}
    proj.set_hdmi.return_value = True
    proj.power_off.return_value = True
    return proj


@pytest.fixture
def mock_orchestrator(mock_fire_tv, mock_projector):
    player = MagicMock()
    player.stop.return_value = True
    player.get_status.return_value = {"status": "PLAYING"}

    bt_helper = MagicMock()
    bt_helper.scan_active_endpoints.return_value = ({"id": "endpoint_123", "name": "LG SNC4R(79)"}, "LG SNC4R(79)")
    bt_helper.device_portal.disconnect_lg.return_value = (True, "OK", 200)

    resolver = MagicMock()

    orch = SmartRoomOrchestrator(
        resolver=resolver,
        player=player,
        bt_helper=bt_helper,
        projector=mock_projector,
        fire_tv=mock_fire_tv
    )
    return orch


# ─── 1. FireTvController search_or_launch_content Tests ─────────────────────

def test_fire_tv_search_or_launch_content_command():
    ftv = FireTvController()
    with patch.object(ftv, "_run_shell", return_value=(0, "Success", "")) as mock_shell, \
         patch.object(ftv, "wake", return_value=True), \
         patch.object(ftv, "is_app_foreground", return_value=True):
        
        ok = ftv.search_or_launch_content("Article 15")
        assert ok is True
        assert any('com.amazon.firetv.youtube' in str(call) for call in mock_shell.call_args_list)
        assert any('Article%s15' in str(call) for call in mock_shell.call_args_list)


def test_fire_tv_search_empty_query_returns_false():
    ftv = FireTvController()
    assert ftv.search_or_launch_content("") is False
    assert ftv.search_or_launch_content("   ") is False


# ─── 2. Orchestrator Movie Mode with Content Title Tests ────────────────────

def test_orchestrator_start_movie_mode_with_article_15(mock_orchestrator, mock_fire_tv, mock_projector):
    res = mock_orchestrator.start_movie_mode(content="Article 15")
    
    assert res["status"] == "HEALTHY"
    assert res["content"] == "Article 15"
    assert res["content_launched"] is True
    assert mock_orchestrator._in_movie_mode is True

    # Verifies PC music was stopped (Audio ownership arbitration)
    assert mock_orchestrator.player.stop.call_count >= 1
    # Verifies Fire TV wake and search were executed
    mock_fire_tv.wake.assert_called_once()
    mock_fire_tv.search_or_launch_content.assert_called_once_with("Article 15")
    # Verifies projector set to HDMI 1
    mock_projector.set_hdmi.assert_called_once_with(1)


def test_orchestrator_movie_mode_content_launch_failed_marks_degraded(mock_orchestrator, mock_fire_tv, mock_projector):
    mock_fire_tv.search_or_launch_content.return_value = False
    res = mock_orchestrator.start_movie_mode(content="Article 15")

    assert res["status"] == "DEGRADED"
    assert res["success"] is False
    assert res["content_launched"] is False
    assert res["health"]["degradation_reason"] == "Content Launch Failed"


def test_orchestrator_movie_mode_fire_tv_bluetooth_disconnected_marks_degraded(mock_orchestrator, mock_fire_tv, mock_projector):
    mock_fire_tv.get_status.return_value = {
        "reachable": True,
        "power_state": "AWAKE",
        "healthy": False,
        "bluetooth": {"required_device_connected": False}
    }
    res = mock_orchestrator.start_movie_mode(content="Article 15")

    assert res["status"] == "DEGRADED"
    assert res["success"] is False
    assert res["health"]["degradation_reason"] == "Fire TV Bluetooth Disconnected"


def test_orchestrator_movie_mode_blocked_when_projector_off(mock_orchestrator, mock_fire_tv, mock_projector):
    mock_projector.get_power_state.return_value = {"power_state": "OFF"}
    mock_projector.wake.return_value = False
    res = mock_orchestrator.start_movie_mode(content="Article 15")

    assert res["status"] == "PROJECTOR_OFF_REQUIRES_MANUAL_ACTION"
    assert res["success"] is False
    assert "The projector is currently off" in res["spoken_response"]
    assert res["content_launched"] is False
    assert mock_orchestrator._in_movie_mode is False

    # Invariants: No audio preemption and No Fire TV search when projector is OFF
    mock_orchestrator.player.stop.assert_not_called()
    mock_fire_tv.wake.assert_not_called()


def test_orchestrator_movie_mode_wakes_projector_when_off(mock_orchestrator, mock_fire_tv, mock_projector):
    mock_projector.get_power_state.side_effect = [{"power_state": "OFF"}, {"power_state": "ON"}]
    mock_projector.wake.return_value = True
    res = mock_orchestrator.start_movie_mode(content="Article 15")

    assert res["success"] is True
    assert mock_projector.wake.called
    mock_fire_tv.wake.assert_called_once()
    mock_fire_tv.search_or_launch_content.assert_called_once_with("Article 15")
    mock_projector.set_hdmi.assert_called_once_with(1)


def test_orchestrator_start_movie_mode_without_content(mock_orchestrator, mock_fire_tv):
    res = mock_orchestrator.start_movie_mode()
    
    assert res["status"] == "HEALTHY"
    assert res["content"] is None
    assert res["content_launched"] is False
    mock_fire_tv.search_or_launch_content.assert_not_called()


def test_orchestrator_stop_movie_mode(mock_orchestrator, mock_projector):
    mock_orchestrator._in_movie_mode = True
    res = mock_orchestrator.stop_movie_mode()

    assert res["status"] == "OFF"
    assert mock_orchestrator._in_movie_mode is False
    mock_projector.power_off.assert_called_once()


def test_duplicate_movie_mode_request(mock_orchestrator, mock_fire_tv):
    # Calling start movie mode multiple times is idempotent
    r1 = mock_orchestrator.start_movie_mode(content="Article 15")
    r2 = mock_orchestrator.start_movie_mode(content="Article 15")
    assert r1["status"] == "HEALTHY"
    assert r2["status"] == "HEALTHY"


# ─── 3. FastAPI Movie Mode Endpoints Tests ──────────────────────────────────

def test_fastapi_movie_mode_start_with_article_15():
    client = TestClient(app)
    
    with patch("main.orchestrator.start_movie_mode") as mock_start:
        mock_start.return_value = {
            "status": "HEALTHY",
            "content": "Article 15",
            "content_launched": True,
            "duration_ms": 120
        }
        res = client.post("/api/room/movie-mode/start", json={"content": "Article 15"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "HEALTHY"
        assert data["content"] == "Article 15"
        mock_start.assert_called_once_with(content="Article 15", provider=None)


def test_fastapi_movie_mode_start_with_provider():
    client = TestClient(app)

    with patch("main.orchestrator.start_movie_mode") as mock_start:
        mock_start.return_value = {
            "status": "HEALTHY",
            "content": "Article 15",
            "provider": "hotstar",
            "content_launched": True,
            "duration_ms": 120
        }
        res = client.post("/api/room/movie-mode/start", json={"content": "Article 15", "provider": "hotstar"})
        assert res.status_code == 200
        mock_start.assert_called_once_with(content="Article 15", provider="hotstar")


def test_fastapi_movie_mode_start_without_body():
    client = TestClient(app)

    with patch("main.orchestrator.start_movie_mode") as mock_start:
        mock_start.return_value = {
            "status": "HEALTHY",
            "content": None,
            "content_launched": False,
            "duration_ms": 95
        }
        res = client.post("/api/room/movie-mode/start")
        assert res.status_code == 200
        mock_start.assert_called_once_with(content=None, provider=None)


def test_fastapi_movie_mode_stop():
    client = TestClient(app)

    with patch("main.orchestrator.stop_movie_mode") as mock_stop:
        mock_stop.return_value = {"status": "OFF", "duration_ms": 50}
        res = client.post("/api/room/movie-mode/stop")
        assert res.status_code == 200
        assert res.json()["status"] == "OFF"
        mock_stop.assert_called_once()


def test_fastapi_firetv_playback_endpoint():
    client = TestClient(app)

    with patch("main.orchestrator.fire_tv_playback_control") as mock_ctrl:
        mock_ctrl.return_value = {"success": True, "action": "PLAY", "message": "Sent MEDIA_PLAY", "duration_ms": 20}
        res = client.post("/api/room/firetv/playback", json={"action": "PLAY"})
        assert res.status_code == 200
        assert res.json()["success"] is True
        mock_ctrl.assert_called_once_with("PLAY")


def test_fastapi_firetv_capabilities_endpoint():
    client = TestClient(app)
    res = client.get("/api/room/firetv/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert "registry" in data
    assert "capabilities" in data["registry"]
    assert "providers" in data["registry"]


def test_fastapi_movie_mode_start_with_provider_only():
    client = TestClient(app)

    with patch("main.orchestrator.start_movie_mode") as mock_start:
        mock_start.return_value = {
            "status": "HEALTHY",
            "content": None,
            "provider": "netflix",
            "content_launched": True,
            "spoken_response": "Starting Movie Mode with Netflix",
            "duration_ms": 110
        }
        res = client.post("/api/room/movie-mode/start", json={"provider": "netflix"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "HEALTHY"
        assert data["provider"] == "netflix"
        assert data["spoken_response"] == "Starting Movie Mode with Netflix"
        mock_start.assert_called_once_with(content=None, provider="netflix")


def test_content_resolver_natural_language_and_provider():
    from content_resolver import SmartRoomContentResolver
    resolver = SmartRoomContentResolver()

    # 1. Natural Language Netflix (No Content Title -> Provider Only)
    r1 = resolver.resolve_content("I feel like watching Netflix right now")
    assert r1.provider_id == "netflix"
    assert r1.resolution_type == "APP_LAUNCH_ONLY"
    assert r1.title == ""

    # 2. Watch Netflix command
    r2 = resolver.resolve_content("watch netflix")
    assert r2.provider_id == "netflix"
    assert r2.resolution_type == "APP_LAUNCH_ONLY"

    # 3. Open Netflix command
    r3 = resolver.resolve_content("open netflix")
    assert r3.provider_id == "netflix"
    assert r3.resolution_type == "APP_LAUNCH_ONLY"

    # 4. Deep-link with Content on Netflix
    r4 = resolver.resolve_content("I feel like watching Stranger Things on Netflix right now")
    assert r4.provider_id == "netflix"
    assert r4.resolution_type == "PROVIDER_DETAILS"
    assert r4.title == "Stranger Things"

    # 5. Generic Unspecified Watch
    r5 = resolver.resolve_content("I feel like watching something right now")
    assert r5.resolution_type == "APP_LAUNCH_ONLY"
    assert r5.title == ""

    # 6. Explicit provider without query
    r6 = resolver.resolve_content("", explicit_provider="netflix")
    assert r6.provider_id == "netflix"
    assert r6.resolution_type == "APP_LAUNCH_ONLY"
    assert r6.title == ""


def test_orchestrator_start_movie_mode_with_provider_only(mock_orchestrator, mock_fire_tv, mock_projector):
    # Mock launch_streaming_provider on capabilities
    mock_caps = MagicMock()
    mock_caps.launch_streaming_provider.return_value = MagicMock(success=True, details={})
    mock_orchestrator.capabilities = mock_caps

    res = mock_orchestrator.start_movie_mode(provider="netflix")

    assert res["status"] == "HEALTHY"
    assert res["success"] is True
    assert res["content"] is None
    assert res["provider"] == "netflix"
    assert res["content_launched"] is True
    assert res["launch_type"] == "APP_LAUNCH_ONLY"
    assert res["spoken_response"] == "Starting Movie Mode with Netflix"
    mock_caps.launch_streaming_provider.assert_called_once_with("netflix")

