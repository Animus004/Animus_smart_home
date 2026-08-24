"""
Unit & Contract tests for Direct Bluetooth Capabilities and Fallback Mechanism.
"""

import pytest
from unittest.mock import MagicMock, patch

from fire_tv_controller import FireTvController, FireTvBluetoothState
from fire_tv_capabilities import (
    FireTVCapabilityRegistry,
    FireTVCapabilityType,
    FireTVErrorCode
)


class TestDirectBluetoothCapability:

    def test_connect_soundbar_already_connected(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.is_required_bluetooth_connected = MagicMock(return_value=True)

        ok, method = controller.connect_soundbar_with_method()
        assert ok is True
        assert method == "ALREADY_CONNECTED"

    def test_connect_soundbar_direct_success(self):
        controller = FireTvController(target="192.168.1.5:5555")
        # First check False, then after broadcast True
        controller.is_required_bluetooth_connected = MagicMock(side_effect=[False, False, True])
        controller._run_shell = MagicMock(return_value=(0, "Broadcast completed: result=0", ""))

        ok, method = controller.connect_soundbar_with_method(timeout_seconds=2.0)
        assert ok is True
        assert method == "DIRECT_CONNECTED"

    def test_connect_soundbar_direct_fails_then_fallback_succeeds(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.connect_soundbar_direct = MagicMock(return_value=False)
        controller.connect_soundbar_fallback = MagicMock(return_value=True)
        controller.is_required_bluetooth_connected = MagicMock(return_value=False)

        ok, method = controller.connect_soundbar_with_method(timeout_seconds=4.0)
        assert ok is True
        assert method == "SETTINGS_FALLBACK_CONNECTED"
        controller.connect_soundbar_direct.assert_called_once()
        controller.connect_soundbar_fallback.assert_called_once()

    def test_connect_soundbar_all_fail(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.connect_soundbar_direct = MagicMock(return_value=False)
        controller.connect_soundbar_fallback = MagicMock(return_value=False)
        controller.is_required_bluetooth_connected = MagicMock(return_value=False)

        ok, method = controller.connect_soundbar_with_method(timeout_seconds=4.0)
        assert ok is False
        assert method == "SOUNDBAR_CONNECTION_FAILED"

    def test_disconnect_soundbar_direct_success(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.is_required_bluetooth_connected = MagicMock(side_effect=[True, False])
        controller._run_shell = MagicMock(return_value=(0, "Broadcast completed: result=0", ""))

        ok, method = controller.disconnect_soundbar(timeout_seconds=2.0)
        assert ok is True
        assert method == "DIRECT_DISCONNECTED"

    def test_disconnect_soundbar_already_disconnected(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.is_required_bluetooth_connected = MagicMock(return_value=False)

        ok, method = controller.disconnect_soundbar()
        assert ok is True
        assert method == "ALREADY_DISCONNECTED"

    def test_registry_connect_soundbar_returns_direct_capability(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.is_connected = MagicMock(return_value=(True, "device"))
        controller.connect_soundbar_with_method = MagicMock(return_value=(True, "DIRECT_CONNECTED"))
        controller.is_required_bluetooth_connected = MagicMock(side_effect=[False, True])

        reg = FireTVCapabilityRegistry(fire_tv=controller)
        res = reg.connect_soundbar()

        assert res.success is True
        assert res.capability == FireTVCapabilityType.BT_CONNECT_SOUNDBAR_DIRECT.value
        assert res.details.get("connection_method") == "DIRECT_CONNECTED"
        assert res.verified is True

    def test_registry_disconnect_soundbar(self):
        controller = FireTvController(target="192.168.1.5:5555")
        controller.is_connected = MagicMock(return_value=(True, "device"))
        controller.disconnect_soundbar = MagicMock(return_value=(True, "DIRECT_DISCONNECTED"))
        controller.is_required_bluetooth_connected = MagicMock(side_effect=[True, False])

        reg = FireTVCapabilityRegistry(fire_tv=controller)
        res = reg.disconnect_soundbar()

        assert res.success is True
        assert res.capability == FireTVCapabilityType.BT_DISCONNECT_SOUNDBAR_DIRECT.value
        assert res.details.get("disconnection_method") == "DIRECT_DISCONNECTED"
