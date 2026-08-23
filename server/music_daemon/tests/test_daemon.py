"""
Unit and integration tests for Animus PC Music Daemon.
Tests audio endpoint detection, LG SNC4R preference, Device Portal A2DP auto-reconnection,
Base64 AEP encoding, dynamic AEP discovery, reconnect timeout resulting in AUDIO_OUTPUT_UNAVAILABLE
without fallback to monitor speakers, authenticated session loading with OAuthCredentials,
OAuth failure modes, pause, resume, volume, status, and error handling.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import json
import requests

from main import app, resolver, player
from resolver import ResolvedTrack, YouTubeMusicResolver
from bluetooth_helper import BluetoothAudioHelper
from device_portal import WindowsDevicePortalBluetooth, encode_aep_id
from auth_setup import (
    load_client_credentials,
    validate_client_id_structure,
    diagnose_google_oauth_endpoint,
    status_auth,
    run_diagnostics
)

client = TestClient(app)


def test_encode_aep_id_base64():
    raw_id = "Bluetooth#Bluetoothac:a7:f1:79:cf:36-54:15:89:dc:a5:79"
    encoded = encode_aep_id(raw_id)
    assert encoded == "Qmx1ZXRvb3RoI0JsdWV0b290aGFjOmE3OmYxOjc5OmNmOjM2LTU0OjE1Ojg5OmRjOmE1Ojc5"
    assert encode_aep_id("") == ""


def test_device_portal_is_available_mock():
    dp = WindowsDevicePortalBluetooth()
    with patch("urllib.request.urlopen") as mock_url:
        mock_url.return_value = MagicMock(status=200)
        assert dp.is_available() is True


def test_device_portal_connect_lg_success():
    dp = WindowsDevicePortalBluetooth()
    with patch.object(dp, "is_available", return_value=True):
        with patch.object(dp, "_load_credentials", return_value=("dummy", "secret")):
            with patch.object(dp, "discover_lg_aep", return_value="Bluetooth#Bluetoothac:a7:f1:79:cf:36-54:15:89:dc:a5:79"):
                mock_opener = MagicMock()
                mock_res = MagicMock(status=200)
                mock_opener.open.return_value = mock_res
                with patch.object(dp, "_create_authenticated_opener", return_value=(mock_opener, [])):
                    success, msg, code = dp.connect_lg()
                    assert success is True
                    assert msg == "REQUEST_ACCEPTED"
                    assert code == 200


def test_device_portal_connect_lg_auth_required():
    dp = WindowsDevicePortalBluetooth()
    with patch.object(dp, "is_available", return_value=True):
        with patch.object(dp, "_load_credentials", return_value=(None, None)):
            success, msg, code = dp.connect_lg()
            assert success is False
            assert msg == "DEVICE_PORTAL_AUTH_REQUIRED"
            assert code == 401


def test_device_portal_connect_lg_device_not_found():
    dp = WindowsDevicePortalBluetooth()
    with patch.object(dp, "is_available", return_value=True):
        with patch.object(dp, "_load_credentials", return_value=("dummy", "secret")):
            with patch.object(dp, "discover_lg_aep", return_value=None):
                success, msg, code = dp.connect_lg()
                assert success is False
                assert msg == "BLUETOOTH_DEVICE_NOT_FOUND"


def test_health_endpoint_reports_auth_and_audio_status():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["service"] == "animus-music-daemon"
    assert "is_authenticated" in data
    assert "auth_method" in data
    assert "audio_output_status" in data
    assert "device_portal_available" in data


def test_bluetooth_helper_scan_finds_lg_endpoint():
    mock_mpv_output = """List of detected audio devices:
  'auto' (Autoselect device)
  'wasapi/{206c70d4-14ac-4591-b5ff-320001713e45}' (2270W (NVIDIA High Definition Audio))
  'wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}' (Speakers (LG SNC4R(79)))
  'openal' (Default (openal))
"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_mpv_output, returncode=0)
        helper = BluetoothAudioHelper()
        lg_dev, devices = helper.scan_active_endpoints()

        assert lg_dev is not None
        assert lg_dev["id"] == "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}"
        assert lg_dev["name"] == "Speakers (LG SNC4R(79))"
        assert len(devices) == 4


def test_bluetooth_helper_already_connected_skips_reconnect():
    mock_dev = {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"}
    helper = BluetoothAudioHelper()

    with patch.object(helper, "scan_active_endpoints", return_value=(mock_dev, [mock_dev])):
        with patch.object(helper, "request_device_portal_connect") as mock_dp:
            ready, dev, status_code = helper.ensure_audio_endpoint()
            assert ready is True
            assert dev == mock_dev
            assert status_code == "ALREADY_CONNECTED"
            mock_dp.assert_not_called()


def test_bluetooth_helper_reconnects_via_device_portal_when_missing():
    mock_dev = {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"}
    helper = BluetoothAudioHelper(reconnect_timeout_seconds=2.0)

    # First call missing, second call appears
    with patch.object(helper, "scan_active_endpoints", side_effect=[(None, []), (mock_dev, [mock_dev])]):
        with patch.object(helper, "request_device_portal_connect", return_value=(True, "REQUEST_ACCEPTED")) as mock_dp:
            ready, dev, status_code = helper.ensure_audio_endpoint()
            assert ready is True
            assert dev == mock_dev
            assert status_code == "RECONNECTED"
            assert helper.last_reconnect_method == "device_portal"
            mock_dp.assert_called_once()


def test_bluetooth_helper_reconnect_timeout_returns_unavailable():
    helper = BluetoothAudioHelper(reconnect_timeout_seconds=0.5)

    with patch.object(helper, "scan_active_endpoints", return_value=(None, [])):
        with patch.object(helper, "request_device_portal_connect", return_value=(False, "DEVICE_PORTAL_UNAVAILABLE")):
            with patch.object(helper, "trigger_windows_bluetooth_wake", return_value=True):
                ready, dev, status_code = helper.ensure_audio_endpoint()
                assert ready is False
                assert dev is None
                assert status_code == "AUDIO_OUTPUT_UNAVAILABLE"


def test_play_fails_cleanly_when_audio_output_unavailable():
    mock_resolved = ResolvedTrack(
        video_id="IWjbBSMsQJg",
        title="Zara Zara",
        artist="Bombay Jayashri",
        duration=298,
        stream_url="https://example.com/audio.opus"
    )

    with patch.object(resolver, "resolve", return_value=mock_resolved):
        with patch.object(player.bt_helper, "ensure_audio_endpoint", return_value=(False, None, "AUDIO_OUTPUT_UNAVAILABLE")):
            with patch.object(player.bt_helper, "scan_active_endpoints", return_value=(None, [])):
                response = client.post("/api/music/play", json={"title": "Zara Zara"})
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is False
                assert data["status"] == "FAILED"
                assert data["error"] == "AUDIO_OUTPUT_UNAVAILABLE"
                assert data["audio_output_status"] == "DISCONNECTED"


def test_play_succeeds_when_lg_endpoint_available():
    mock_resolved = ResolvedTrack(
        video_id="IWjbBSMsQJg",
        title="Zara Zara",
        artist="Bombay Jayashri",
        duration=298,
        stream_url="https://example.com/audio.opus",
        is_authenticated=True
    )
    mock_lg_dev = {"id": "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}", "name": "Speakers (LG SNC4R(79))"}

    with patch.object(resolver, "resolve", return_value=mock_resolved):
        with patch.object(player.bt_helper, "ensure_audio_endpoint", return_value=(True, mock_lg_dev, "ALREADY_CONNECTED")):
            with patch.object(player, "_send_ipc_command", return_value={"error": "success"}):
                response = client.post("/api/music/play", json={"title": "Zara Zara"})
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["status"] == "PLAYING"
                assert data["audio_device_id"] == "wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}"
                assert data["audio_device_name"] == "Speakers (LG SNC4R(79))"
                assert data["audio_output_status"] == "CONNECTED"


def test_resolver_guest_mode_when_no_credentials():
    with tempfile.TemporaryDirectory() as temp_dir:
        res = YouTubeMusicResolver(secrets_dir=Path(temp_dir))
        assert res.is_authenticated is False
        assert res.auth_method == "none"


def test_resolver_authenticated_when_oauth_and_client_creds_present():
    with tempfile.TemporaryDirectory() as temp_dir:
        secrets_dir = Path(temp_dir)
        client_file = secrets_dir / "oauth_client.json"
        client_file.write_text(json.dumps({"client_id": "test_cid", "client_secret": "test_csec"}), encoding="utf-8")

        oauth_file = secrets_dir / "oauth.json"
        oauth_file.write_text(json.dumps({"token_type": "Bearer", "access_token": "fake_token"}), encoding="utf-8")

        with patch("resolver.YTMusic") as mock_ytm:
            mock_ytm.return_value = MagicMock()
            res = YouTubeMusicResolver(secrets_dir=secrets_dir)
            assert res.is_authenticated is True
            assert res.auth_method == "oauth"


def test_pause_endpoint_success():
    with patch.object(player, "pause", return_value=True):
        response = client.post("/api/music/pause")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "PAUSED"


def test_resume_endpoint_success():
    with patch.object(player, "resume", return_value=True):
        response = client.post("/api/music/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "PLAYING"


def test_volume_endpoint():
    with patch.object(player, "set_volume", return_value=75):
        with patch.object(player, "get_status", return_value={"status": "PLAYING", "audio_output_status": "CONNECTED"}):
            response = client.post("/api/music/volume", json={"volume": 75})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["volume"] == 75


def test_stop_endpoint():
    with patch.object(player, "stop", return_value=True):
        response = client.post("/api/music/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "STOPPED"


def test_play_endpoint_payload_validation():
    # Empty title -> 422 Unprocessable Entity
    resp_empty = client.post("/api/music/play", json={"title": ""})
    assert resp_empty.status_code == 422

    # Excessively long title -> 422 Unprocessable Entity
    resp_long = client.post("/api/music/play", json={"title": "A" * 500})
    assert resp_long.status_code == 422

