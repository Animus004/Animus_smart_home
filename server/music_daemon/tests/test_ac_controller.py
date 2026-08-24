import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from ac_controller import (
    AcController,
    AcMode,
    AcFanSpeed,
    TransportType,
    LocalTuyaTransport,
    CloudTuyaTransport
)
from ac_command_router import AcCommandRouter, AcCommandCategory
from main import app

@pytest.fixture
def mock_ac_status_cloud():
    return [
        {"code": "switch", "value": True},
        {"code": "temp_set", "value": 24},
        {"code": "mode", "value": "cold"},
        {"code": "fan_speed_enum", "value": "low"},
        {"code": "temp_current", "value": 21}
    ]

@pytest.fixture
def controller(mock_ac_status_cloud):
    ctrl = AcController(
        lan_ip="192.168.1.4",
        lan_port=6668,
        dev_id="dummy_dev_id",
        local_key="dummy_key_123456",
        access_id="dummy_access_id",
        access_secret="dummy_access_sec",
        endpoint="https://openapi.tuyain.com"
    )
    # Mock transports by default
    ctrl.cloud_transport.fetch_status = MagicMock(return_value=mock_ac_status_cloud)
    ctrl.cloud_transport.send_commands = MagicMock(return_value=True)
    ctrl.lan_transport.send_heartbeat = MagicMock(return_value=False)
    ctrl.lan_transport.send_dps_command = MagicMock(return_value=False)
    return ctrl

@pytest.fixture
def client():
    return TestClient(app)

# =========================================================================
# 1. Status Parsing & Telemetry Truth
# =========================================================================

def test_ac_get_status_parsing(controller):
    st = controller.get_status()
    assert st["power"] is True
    assert st["target_temperature"] == 24
    assert st["ambient_temperature"] == 21
    assert st["mode"] == "COOL"
    assert st["fan_speed"] == "LOW"
    assert st["connectivity"] == "ONLINE"
    assert st["verified"] is True

def test_ac_get_status_offline_handling(controller):
    controller.cloud_transport.fetch_status = MagicMock(return_value=None)
    st = controller.get_status()
    assert st["connectivity"] == "OFFLINE"
    assert st["verified"] is False
    assert "Failed to read" in st["error"]

# =========================================================================
# 2. Power Operations & Verification
# =========================================================================

def test_ac_set_power_on_verified(controller):
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": False}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_power(True)
    assert ok is True
    assert res["power"] is True
    assert res["verified"] is True
    controller.cloud_transport.send_commands.assert_called_with([{"code": "switch", "value": True}])

def test_ac_set_power_off_verified(controller):
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": False}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_power(False)
    assert ok is True
    assert res["power"] is False
    assert res["verified"] is True
    controller.cloud_transport.send_commands.assert_called_with([{"code": "switch", "value": False}])

def test_ac_set_power_idempotent(controller):
    controller.cloud_transport.fetch_status.return_value = [
        {"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}
    ]
    ok, res = controller.set_power(True)
    assert ok is True
    assert res["idempotent"] is True
    controller.cloud_transport.send_commands.assert_not_called()

def test_ac_set_power_verification_mismatch(controller):
    controller.cloud_transport.fetch_status = MagicMock(return_value=[
        {"code": "switch", "value": False},
        {"code": "temp_set", "value": 24},
        {"code": "mode", "value": "cold"},
        {"code": "fan_speed_enum", "value": "low"},
        {"code": "temp_current", "value": 21}
    ])
    ok, res = controller.set_power(True)
    assert ok is False
    assert res["verified"] is False


# =========================================================================
# 3. Temperature Operations & Boundary Safety
# =========================================================================

def test_ac_set_temperature_valid_verified(controller):
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 22}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_temperature(22)
    assert ok is True
    assert res["target_temperature"] == 22
    assert res["verified"] is True
    controller.cloud_transport.send_commands.assert_called_with([{"code": "temp_set", "value": 22}])

def test_ac_set_temperature_bounds_rejection(controller):
    # Lower bound < 16
    ok_low, res_low = controller.set_temperature(14)
    assert ok_low is False
    assert res_low["status"] == "INVALID_PARAMETER"
    assert "out of bounds" in res_low["error"]

    # Upper bound > 30
    ok_high, res_high = controller.set_temperature(32)
    assert ok_high is False
    assert res_high["status"] == "INVALID_PARAMETER"
    assert "out of bounds" in res_high["error"]

def test_ac_set_temperature_idempotent(controller):
    controller.cloud_transport.fetch_status.return_value = [
        {"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}
    ]
    ok, res = controller.set_temperature(24)
    assert ok is True
    assert res["idempotent"] is True
    controller.cloud_transport.send_commands.assert_not_called()

# =========================================================================
# 4. Mode Operations & Heat Rejection Invariant
# =========================================================================

def test_ac_set_mode_cool_verified(controller):
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "auto"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_mode("COOL")
    assert ok is True
    assert res["mode"] == "COOL"
    controller.cloud_transport.send_commands.assert_called_with([{"code": "mode", "value": "cold"}])

def test_ac_set_mode_dry_and_fan_and_auto(controller):
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "wet"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "wind"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "auto"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok_dry, _ = controller.set_mode("DRY")
    assert ok_dry is True
    controller.cloud_transport.send_commands.assert_called_with([{"code": "mode", "value": "wet"}])

def test_ac_set_mode_heat_rejected(controller):
    ok, res = controller.set_mode("HEAT")
    assert ok is False
    assert res["status"] == "UNSUPPORTED_HARDWARE"
    assert "cooling-only" in res["error"]
    controller.cloud_transport.send_commands.assert_not_called()

def test_ac_set_mode_invalid_rejected(controller):
    ok, res = controller.set_mode("PARTY_MODE")
    assert ok is False
    assert res["status"] == "INVALID_PARAMETER"

# =========================================================================
# 5. Fan Speed Operations
# =========================================================================

def test_ac_set_fan_speed_high_verified(controller):
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "high"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_fan_speed("HIGH")
    assert ok is True
    assert res["fan_speed"] == "HIGH"
    controller.cloud_transport.send_commands.assert_called_with([{"code": "fan_speed_enum", "value": "high"}])

def test_ac_set_fan_speed_invalid_rejected(controller):
    ok, res = controller.set_fan_speed("TURBO_MAX")
    assert ok is False
    assert res["status"] == "INVALID_PARAMETER"

# =========================================================================
# 6. Swing Rejection Invariant
# =========================================================================

def test_ac_swing_rejection(controller):
    ok, res = controller.set_swing(True)
    assert ok is False
    assert res["status"] == "UNSUPPORTED_HARDWARE"
    assert "Louver swing control is not available" in res["error"]

# =========================================================================
# 7. Dual Transport (LAN & Cloud Fallback)
# =========================================================================

def test_ac_lan_transport_used_when_available(controller):
    controller.lan_transport.send_heartbeat = MagicMock(return_value=True)
    controller.lan_transport.send_dps_command = MagicMock(return_value=True)
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": False}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_power(True)
    assert ok is True
    assert res["transport"] == TransportType.LAN.value
    controller.lan_transport.send_dps_command.assert_called_with({"1": True})
    controller.cloud_transport.send_commands.assert_not_called()

def test_ac_lan_transport_timeout_falls_back_to_cloud(controller):
    controller.lan_transport.send_heartbeat = MagicMock(return_value=False)
    controller.cloud_transport.fetch_status.side_effect = [
        [{"code": "switch", "value": False}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}],
        [{"code": "switch", "value": True}, {"code": "temp_set", "value": 24}, {"code": "mode", "value": "cold"}, {"code": "fan_speed_enum", "value": "low"}, {"code": "temp_current", "value": 21}]
    ]
    ok, res = controller.set_power(True)
    assert ok is True
    assert res["transport"] == TransportType.CLOUD.value
    controller.cloud_transport.send_commands.assert_called_with([{"code": "switch", "value": True}])

# =========================================================================
# 8. Command Router Unit Tests
# =========================================================================

def test_ac_router_power_commands(controller):
    router = AcCommandRouter(controller=controller)
    controller.set_power = MagicMock(return_value=(True, {"success": True, "power": True, "message": "AC power ON"}))
    res1 = router.route_command("Turn on the AC.")
    assert res1["category"] == AcCommandCategory.POWER.value
    assert res1["capability"] == "AC_POWER_ON"
    assert res1["success"] is True

    controller.set_power = MagicMock(return_value=(True, {"success": True, "power": False, "message": "AC power OFF"}))
    res2 = router.route_command("Turn off the AC.")
    assert res2["capability"] == "AC_POWER_OFF"
    assert res2["success"] is True

def test_ac_router_temperature_commands(controller):
    router = AcCommandRouter(controller=controller)
    controller.set_temperature = MagicMock(return_value=(True, {"success": True, "target_temperature": 24, "message": "Set 24C"}))
    res1 = router.route_command("Set the AC to 24 degrees.")
    assert res1["category"] == AcCommandCategory.TEMPERATURE.value
    assert res1["capability"] == "AC_SET_TEMPERATURE"
    assert res1["requested_temperature"] == 24

def test_ac_router_ambient_temperature_query(controller):
    router = AcCommandRouter(controller=controller)
    res = router.route_command("What's the room temperature?")
    assert res["category"] == AcCommandCategory.DIAGNOSTICS.value
    assert res["capability"] == "AC_GET_AMBIENT_TEMPERATURE"
    assert res["ambient_temperature"] == 21

def test_ac_router_mode_and_fan_commands(controller):
    router = AcCommandRouter(controller=controller)
    controller.set_mode = MagicMock(return_value=(True, {"success": True, "mode": "COOL", "message": "Set cool"}))
    res1 = router.route_command("Put the AC on cool mode.")
    assert res1["capability"] == "AC_SET_MODE_COOL"

    controller.set_fan_speed = MagicMock(return_value=(True, {"success": True, "fan_speed": "HIGH", "message": "Set high"}))
    res2 = router.route_command("Set the fan to high.")
    assert res2["capability"] == "AC_SET_FAN_SPEED_HIGH"

def test_ac_router_safety_rejections(router=None, controller=None):
    ctrl = controller or AcController()
    router = AcCommandRouter(controller=ctrl)

    res_heat = router.route_command("Turn on heat mode.")
    assert res_heat["success"] is False
    assert res_heat["status"] == "UNSUPPORTED_HARDWARE"
    assert "cooling-only" in res_heat["error"]

    res_swing = router.route_command("Turn on AC swing.")
    assert res_swing["success"] is False
    assert res_swing["status"] == "UNSUPPORTED_HARDWARE"
    assert "Louver swing control is not available" in res_swing["error"]

    res_bound = router.route_command("Set AC to 14 degrees.")
    assert res_bound["success"] is False
    assert res_bound["status"] == "INVALID_PARAMETER"

# =========================================================================
# 9. FastAPI REST Endpoints Tests
# =========================================================================

def test_fastapi_ac_endpoints(client):
    with patch("main.ac_controller.get_status") as mock_st, \
         patch("main.ac_controller.set_power") as mock_pwr, \
         patch("main.ac_controller.set_temperature") as mock_temp, \
         patch("main.ac_controller.set_mode") as mock_mode, \
         patch("main.ac_controller.set_fan_speed") as mock_fan, \
         patch("main.ac_router.route_command") as mock_cmd:

        mock_st.return_value = {
            "power": True,
            "target_temperature": 24,
            "ambient_temperature": 21,
            "mode": "COOL",
            "fan_speed": "LOW",
            "connectivity": "ONLINE",
            "verified": True
        }
        mock_pwr.return_value = (True, {"success": True, "power": True, "verified": True})
        mock_temp.return_value = (True, {"success": True, "target_temperature": 24, "verified": True})
        mock_mode.return_value = (True, {"success": True, "mode": "COOL", "verified": True})
        mock_fan.return_value = (True, {"success": True, "fan_speed": "LOW", "verified": True})
        mock_cmd.return_value = {"success": True, "capability": "AC_POWER_ON", "status": "POWER_ON_VERIFIED"}

        # GET /api/ac/status
        r_st = client.get("/api/ac/status")
        assert r_st.status_code == 200
        assert r_st.json()["power"] is True

        # POST /api/ac/power
        r_pwr = client.post("/api/ac/power", json={"on": True})
        assert r_pwr.status_code == 200
        assert r_pwr.json()["power"] is True

        # POST /api/ac/temperature
        r_temp = client.post("/api/ac/temperature", json={"temperature": 24})
        assert r_temp.status_code == 200
        assert r_temp.json()["target_temperature"] == 24

        # POST /api/ac/mode
        r_mode = client.post("/api/ac/mode", json={"mode": "COOL"})
        assert r_mode.status_code == 200

        # POST /api/ac/fan
        r_fan = client.post("/api/ac/fan", json={"speed": "LOW"})
        assert r_fan.status_code == 200

        # POST /api/ac/command
        r_cmd = client.post("/api/ac/command", json={"query": "Turn on the AC."})
        assert r_cmd.status_code == 200
