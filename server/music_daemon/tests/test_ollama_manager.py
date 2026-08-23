import pytest
import os
import time
from unittest.mock import patch, MagicMock
from ollama_manager import OllamaManager, OllamaState

def test_ollama_manager_initialization():
    mgr = OllamaManager(auto_start_watchdog=False)
    assert mgr.host == "127.0.0.1"
    assert mgr.port == 11434
    assert mgr.model == "qwen3:4b-instruct"
    assert mgr.current_state in [OllamaState.OFFLINE, OllamaState.READY, OllamaState.SERVER_READY]

def test_ollama_manager_status_contract():
    mgr = OllamaManager(auto_start_watchdog=False)
    st = mgr.get_status()
    assert "state" in st
    assert "host" in st
    assert "port" in st
    assert "target_model" in st
    assert "is_process_running" in st
    assert "is_server_reachable" in st

@patch("requests.get")
def test_ollama_manager_http_health_mock(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    mgr = OllamaManager(auto_start_watchdog=False)
    assert mgr._check_http_health() is True

@patch("requests.get")
def test_ollama_manager_get_loaded_model_info(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "models": [{
            "name": "qwen3:4b-instruct",
            "size_vram": 3178149969,
            "expires_at": "2026-08-24T14:00:00Z"
        }]
    }
    mock_get.return_value = mock_resp

    mgr = OllamaManager(auto_start_watchdog=False)
    info = mgr._get_loaded_model_info()
    assert info is not None
    assert info["name"] == "qwen3:4b-instruct"
    assert info["size_vram"] == 3178149969

@patch("requests.post")
@patch("requests.get")
def test_ollama_manager_model_warmup_success(mock_get, mock_post):
    # Mock server healthy
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"models": []}
    mock_get.return_value = mock_get_resp

    # Mock generate 200
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post.return_value = mock_post_resp

    mgr = OllamaManager(auto_start_watchdog=False)
    with patch.object(mgr, "_is_process_running", return_value=(True, 1234)):
        success = mgr.ensure_model_ready()
        assert success is True
        assert mgr.current_state == OllamaState.READY
