"""
================================================================================
ANIMUS SMART ROOM — LOCAL TUYA AC READ ADAPTER TEST SUITE
================================================================================
Unit and mock tests for TuyaLocalAcReadAdapter verifying:
1. Decoding of power, target temp, current temp, mode, fan speed (LOCAL_READ_SUCCESS)
2. Handling of socket connection timeout & unreachable LAN (LOCAL_READ_FAILED)
3. Handling of corrupted or non-DPS frames (DECODE_FAILED)
4. Strict Read-Only invariant (zero write commands, zero Tuya cloud calls)
5. Configuration isolation (environment variables and local.properties)
================================================================================
"""

import os
import json
import struct
import binascii
import socket
from unittest.mock import patch, MagicMock
import pytest
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad

import sys
sys.path.insert(0, os.path.abspath("server/music_daemon"))

from tuya_local_read_adapter import (
    TuyaLocalAcReadAdapter,
    ReadDiagnosticStatus,
    LocalReadResult,
    DecodedAcState,
    load_tuya_local_config,
)

TEST_DEV_ID = "mock_dev_id_12345"
TEST_LOCAL_KEY = b"mock_key_16bytes"
TEST_IP = "127.0.0.1"
TEST_PORT = 6668


def build_mock_tuya_response(cmd: int, data_obj: dict, key: bytes, ret_code: int = 0) -> bytes:
    """Helper to build a valid encrypted Tuya 3.3 response packet for testing."""
    payload_str = json.dumps(data_obj, separators=(',', ':'))
    cipher = AES.new(key, AES.MODE_ECB)
    enc = cipher.encrypt(pad(payload_str.encode('utf-8'), 16))
    
    # Body starts with ret_code (4 bytes) + 3.3 header prefix (15 bytes) + encrypted data
    body = struct.pack(">I", ret_code) + b"3.3" + (b"\x00" * 12) + enc
    total_len = len(body) + 8  # 4 bytes CRC + 4 bytes suffix
    
    header = struct.pack(">IIII", 0x000055AA, 1, cmd, total_len)
    crc = binascii.crc32(header + body) & 0xFFFFFFFF
    suffix = struct.pack(">II", crc, 0x0000AA55)
    return header + body + suffix


def test_config_loading_from_env():
    with patch.dict(os.environ, {
        "TUYA_DEVICE_ID": "env_dev_id_abc",
        "TUYA_LOCAL_KEY": "env_key_12345678",
        "TUYA_LOCAL_IP": "192.168.1.55",
        "TUYA_LOCAL_PORT": "6668"
    }):
        cfg = load_tuya_local_config()
        assert cfg["device_id"] == "env_dev_id_abc"
        assert cfg["local_key"] == "env_key_12345678"
        assert cfg["local_ip"] == "192.168.1.55"
        assert cfg["local_port"] == "6668"


def test_decode_dps_numeric_keys():
    adapter = TuyaLocalAcReadAdapter(
        ip=TEST_IP, port=TEST_PORT, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8")
    )
    raw_dps = {
        "1": True,
        "2": 22,
        "3": 21,
        "4": "cold",
        "5": "high",
    }
    state = adapter.decode_dps(raw_dps, latency_ms=12.5)
    assert state is not None
    assert state.power is True
    assert state.target_temperature == 22
    assert state.current_temperature == 21
    assert state.mode == "COOL"
    assert state.fan_speed == "HIGH"
    assert state.latency_ms == 12.5


def test_decode_dps_string_codes():
    adapter = TuyaLocalAcReadAdapter(
        ip=TEST_IP, port=TEST_PORT, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8")
    )
    raw_dps = {
        "switch": False,
        "temp_set": 26,
        "temp_current": 25,
        "mode": "wet",
        "fan_speed_enum": "mid",
    }
    state = adapter.decode_dps(raw_dps, latency_ms=8.0)
    assert state is not None
    assert state.power is False
    assert state.target_temperature == 26
    assert state.current_temperature == 25
    assert state.mode == "DRY"
    assert state.fan_speed == "MEDIUM"


def test_decode_dps_all_mode_and_fan_variants():
    adapter = TuyaLocalAcReadAdapter(
        ip=TEST_IP, port=TEST_PORT, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8")
    )
    # Auto mode, low fan
    st_auto = adapter.decode_dps({"1": True, "2": 24, "4": "auto", "5": "low"}, 5.0)
    assert st_auto.mode == "AUTO"
    assert st_auto.fan_speed == "LOW"

    # Wind mode (FAN), auto fan
    st_fan = adapter.decode_dps({"1": True, "2": 24, "4": "wind", "5": "auto"}, 5.0)
    assert st_fan.mode == "FAN"
    assert st_fan.fan_speed == "AUTO"


def test_read_ac_state_success_mocked():
    adapter = TuyaLocalAcReadAdapter(
        ip=TEST_IP, port=TEST_PORT, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8")
    )

    hb_resp = struct.pack(">IIII", 0x000055AA, 1, 0x09, 12) + struct.pack(">III", 0, 0x12345678, 0x0000AA55)
    dp_data = {"dps": {"1": True, "2": 23, "3": 20, "4": "cold", "5": "low"}}
    dp_resp = build_mock_tuya_response(0x0A, dp_data, TEST_LOCAL_KEY)

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        # First call is heartbeat, second call is DP query
        mock_sock.recv.side_effect = [hb_resp, dp_resp]

        res = adapter.read_ac_state()
        assert res.status == ReadDiagnosticStatus.LOCAL_READ_SUCCESS
        assert res.state is not None
        assert res.state.power is True
        assert res.state.target_temperature == 23
        assert res.state.current_temperature == 20
        assert res.state.mode == "COOL"
        assert res.state.fan_speed == "LOW"
        assert res.error is None


def test_read_ac_state_unreachable_socket_returns_local_read_failed():
    adapter = TuyaLocalAcReadAdapter(
        ip="192.0.2.1", port=6668, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8"), timeout=0.1
    )

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.connect.side_effect = socket.timeout("Connection timed out")

        res = adapter.read_ac_state()
        assert res.status == ReadDiagnosticStatus.LOCAL_READ_FAILED
        assert "unreachable" in res.error.lower() or "timeout" in res.error.lower() or "timed out" in res.error.lower()
        assert res.state is None


def test_read_ac_state_corrupted_response_returns_decode_failed():
    adapter = TuyaLocalAcReadAdapter(
        ip=TEST_IP, port=TEST_PORT, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8")
    )

    hb_resp = struct.pack(">IIII", 0x000055AA, 1, 0x09, 12) + struct.pack(">III", 0, 0x12345678, 0x0000AA55)
    # Corrupted / invalid ciphertext
    corrupt_resp = struct.pack(">IIII", 0x000055AA, 1, 0x0A, 28) + b"corrupted_junk_data_12345678" + struct.pack(">II", 0, 0x0000AA55)

    with patch("socket.socket") as mock_sock_cls:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.recv.side_effect = [hb_resp, corrupt_resp]

        res = adapter.read_ac_state()
        assert res.status == ReadDiagnosticStatus.DECODE_FAILED
        assert "decrypt/parse" in res.error.lower() or "decode" in res.error.lower()
        assert res.state is None


def test_read_adapter_is_strictly_read_only():
    """Verify that the adapter does not define or invoke write/control commands or cloud requests."""
    adapter = TuyaLocalAcReadAdapter(
        ip=TEST_IP, port=TEST_PORT, dev_id=TEST_DEV_ID, local_key=TEST_LOCAL_KEY.decode("utf-8")
    )
    
    # Assert no write methods exist on adapter
    assert not hasattr(adapter, "set_power")
    assert not hasattr(adapter, "set_temperature")
    assert not hasattr(adapter, "set_mode")
    assert not hasattr(adapter, "set_fan_speed")
    assert not hasattr(adapter, "send_dps_command")

    # Assert requests library or cloud URLs are not referenced in the adapter methods
    import inspect
    src = inspect.getsource(TuyaLocalAcReadAdapter)
    assert "requests." not in src
    assert "openapi.tuyain.com" not in src
    assert "openapi.tuya" not in src
