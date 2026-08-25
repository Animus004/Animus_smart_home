"""
Unit and Integration Tests for Authoritative Backend AC API Endpoints.
Verifies GET /api/ac/status, POST /api/ac/power, POST /api/ac/temperature,
POST /api/ac/mode, POST /api/ac/fan, and POST /api/ac/set.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app, ac_controller


@pytest.fixture
def client():
    return TestClient(app)


def test_ac_status_endpoint(client):
    with patch.object(ac_controller, "get_status", return_value={
        "power": True,
        "target_temperature": 24,
        "ambient_temperature": 26,
        "mode": "COOL",
        "fan_speed": "AUTO",
        "is_online": True
    }):
        resp = client.get("/api/ac/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["power"] is True
        assert data["target_temperature"] == 24
        assert data["mode"] == "COOL"


def test_ac_power_endpoint_success(client):
    with patch.object(ac_controller, "set_power", return_value=(True, {"status": "SUCCESS", "power": True})):
        resp = client.post("/api/ac/power", json={"on": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["power"] is True


def test_ac_power_endpoint_failure(client):
    with patch.object(ac_controller, "set_power", return_value=(False, {"status": "TCP_TIMEOUT", "power": False})):
        resp = client.post("/api/ac/power", json={"on": True})
        assert resp.status_code == 500


def test_ac_temperature_endpoint_valid(client):
    with patch.object(ac_controller, "set_temperature", return_value=(True, {"status": "SUCCESS", "temperature": 22})):
        resp = client.post("/api/ac/temperature", json={"temperature": 22})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"


def test_ac_temperature_endpoint_out_of_range(client):
    # Below 16
    resp_low = client.post("/api/ac/temperature", json={"temperature": 14})
    assert resp_low.status_code == 422 # Validation error

    # Above 30
    resp_high = client.post("/api/ac/temperature", json={"temperature": 35})
    assert resp_high.status_code == 422


def test_ac_mode_endpoint_valid(client):
    with patch.object(ac_controller, "set_mode", return_value=(True, {"status": "SUCCESS", "mode": "COOL"})):
        resp = client.post("/api/ac/mode", json={"mode": "COOL"})
        assert resp.status_code == 200


def test_ac_fan_endpoint_valid(client):
    with patch.object(ac_controller, "set_fan_speed", return_value=(True, {"status": "SUCCESS", "fan_speed": "HIGH"})):
        resp = client.post("/api/ac/fan", json={"speed": "HIGH"})
        assert resp.status_code == 200


def test_ac_set_composite_endpoint(client):
    with patch.object(ac_controller, "set_power", return_value=(True, {"status": "SUCCESS"})), \
         patch.object(ac_controller, "set_temperature", return_value=(True, {"status": "SUCCESS"})), \
         patch.object(ac_controller, "get_status", return_value={"power": True, "target_temperature": 23}):
        resp = client.post("/api/ac/set", json={"power": True, "temperature": 23})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert "power" in data["results"]
        assert "temperature" in data["results"]
