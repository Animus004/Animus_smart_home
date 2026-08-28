"""
Unit Test Battery for TuyaLocalIrAdapter:
Verifies Zero-Cloud Local LAN Tuya Protocol (v3.5), Heartbeat, Dispatch, and Learning mode.
"""

import pytest
from unittest.mock import MagicMock, patch
from tuya_local_ir_adapter import TuyaLocalIrAdapter


class TestTuyaLocalIrAdapter:
    """Rigorous verification of Zero-Cloud TuyaLocalIrAdapter."""

    def test_init_loads_defaults(self):
        adapter = TuyaLocalIrAdapter()
        assert adapter.ip == "192.168.1.12"
        assert adapter.dev_id == "d7c9483cd505ac54eauidb"
        assert adapter.local_key in ["a9.o$M~_G}BXXyzC", "^$0WJKhafPb64-c}"]
        assert adapter._device is not None

    def test_check_online_success(self):
        adapter = TuyaLocalIrAdapter()
        with patch.object(adapter._device, "heartbeat", return_value=None):
            online, lat = adapter.check_online()
            assert online is True
            assert lat >= 0.0

    def test_check_online_failure(self):
        adapter = TuyaLocalIrAdapter()
        with patch.object(adapter._device, "heartbeat", side_effect=Exception("Connection refused")):
            online, lat = adapter.check_online()
            assert online is False

    def test_send_raw_ir_payload_structure(self):
        adapter = TuyaLocalIrAdapter()
        with patch.object(adapter._device, "set_value", return_value=None) as mock_set:
            ok = adapter.send_raw_ir("TEST_BASE64_CODE==")
            assert ok is True
            mock_set.assert_called_once()
            call_args = mock_set.call_args[0]
            assert call_args[0] == 201
            assert "TEST_BASE64_CODE==" in call_args[1]
            assert '"control":"send_ir"' in call_args[1]

    def test_send_raw_ir_rejects_empty(self):
        adapter = TuyaLocalIrAdapter()
        ok = adapter.send_raw_ir("")
        assert ok is False

    def test_send_power_wake_fallback_key(self):
        adapter = TuyaLocalIrAdapter()
        with patch("tuya_cloud_ir_transport.TuyaCloudIrTransport.send_pulse", return_value=(True, "CLOUD_IR_DISPATCH_SUCCESS")):
            ok, msg = adapter.send_power_wake()
            assert ok is True
            assert msg == "CLOUD_IR_PULSE_SENT"

    def test_enter_and_exit_study_mode(self):
        adapter = TuyaLocalIrAdapter()
        with patch.object(adapter._device, "set_value", return_value=None) as mock_set:
            ok1 = adapter.enter_study_mode()
            assert ok1 is True
            assert '"control"' in mock_set.call_args[0][1] and '"study"' in mock_set.call_args[0][1]

            ok2 = adapter.exit_study_mode()
            assert ok2 is True
            assert '"control"' in mock_set.call_args[0][1] and '"study_exit"' in mock_set.call_args[0][1]
