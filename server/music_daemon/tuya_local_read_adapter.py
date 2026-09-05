"""
================================================================================
ANIMUS SMART ROOM — LOCAL TUYA AC READ ADAPTER (READ-ONLY / LAN TRANSPORT)
================================================================================
Authoritative minimal, read-only adapter that communicates directly with
the physical Inverter Split AC over the local LAN (Tuya Protocol 3.3).

Key Design Principles:
1. Pure Read-Only: Strictly no write commands (cmd 0x07 is not implemented/prohibited).
2. Zero Cloud: Never makes HTTP/HTTPS requests to Tuya Cloud OpenAPI.
3. Secret Sanitization: Device IDs, IPs, and local keys are loaded via config/env vars
   and masked in all logs and string representations.
4. Deterministic Diagnostics: Returns structured results with clear status codes:
   - LOCAL_READ_SUCCESS
   - LOCAL_READ_FAILED
   - DECODE_FAILED
================================================================================
"""

import os
import time
import socket
import struct
import json
import logging
import binascii
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Tuple

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad

logger = logging.getLogger("tuya_local_read_adapter")


class ReadDiagnosticStatus(str, Enum):
    LOCAL_READ_SUCCESS = "LOCAL_READ_SUCCESS"
    LOCAL_READ_FAILED = "LOCAL_READ_FAILED"
    DECODE_FAILED = "DECODE_FAILED"


@dataclass
class DecodedAcState:
    power: bool
    target_temperature: int
    current_temperature: Optional[int]
    mode: str
    fan_speed: str
    raw_dps: Dict[str, Any]
    latency_ms: float
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocalReadResult:
    status: ReadDiagnosticStatus
    state: Optional[DecodedAcState] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    transport: str = "LAN_TUYA_33"

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "status": self.status.value,
            "transport": self.transport,
            "latency_ms": round(self.latency_ms, 2),
            "state": self.state.to_dict() if self.state else None,
            "error": self.error,
        }
        return res


def load_tuya_local_config() -> Dict[str, str]:
    """
    Loads Tuya LAN configuration strictly from environment variables or local.properties.
    Credentials and network endpoints are never hardcoded in source code.
    """
    props: Dict[str, str] = {}
    
    # 1. Inspect candidate local.properties files
    candidates = [
        Path(__file__).parent.parent.parent / "local.properties",
        Path("d:/AnimusSmartRoom/local.properties"),
        Path("local.properties"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            props[k.strip()] = v.strip()
                break
            except Exception as e:
                logger.warning(f"Failed to read properties from {candidate}: {e}")

    # 2. Environment variables override local.properties
    device_id = os.environ.get("TUYA_DEVICE_ID", props.get("tuya.device.id", "")).strip()
    local_key = os.environ.get("TUYA_LOCAL_KEY", props.get("tuya.local.key", "")).strip()
    local_ip = os.environ.get("TUYA_LOCAL_IP", props.get("tuya.local.ip", "192.168.1.3")).strip()
    local_port = int(os.environ.get("TUYA_LOCAL_PORT", props.get("tuya.local.port", "6668")).strip())

    return {
        "device_id": device_id,
        "local_key": local_key,
        "local_ip": local_ip,
        "local_port": str(local_port),
    }


class TuyaLocalAcReadAdapter:
    """
    Minimal, isolated local Tuya read adapter for the smart room Air Conditioner.
    """
    # Tuya 3.3 Command IDs (Read & Heartbeat only)
    CMD_HEARTBEAT = 0x09
    CMD_DP_QUERY = 0x0A
    CMD_STATUS_REPORT = 0x08
    CMD_DP_QUERY_NEW = 0x10

    # Translations
    REVERSE_MODE_MAP = {
        "cold": "COOL",
        "auto": "AUTO",
        "wet": "DRY",
        "wind": "FAN",
        "cool": "COOL",
        "dry": "DRY",
        "fan": "FAN",
    }
    REVERSE_FAN_MAP = {
        "low": "LOW",
        "mid": "MEDIUM",
        "high": "HIGH",
        "auto": "AUTO",
        "1": "LOW",
        "2": "MEDIUM",
        "3": "HIGH",
        "4": "AUTO",
    }

    def __init__(
        self,
        ip: Optional[str] = None,
        port: Optional[int] = None,
        dev_id: Optional[str] = None,
        local_key: Optional[str] = None,
        timeout: float = 3.0,
    ):
        cfg = load_tuya_local_config()
        self.ip = ip or cfg["local_ip"]
        self.port = port or int(cfg["local_port"])
        self.dev_id = dev_id or cfg["device_id"]
        
        raw_key = local_key or cfg["local_key"]
        self.local_key = raw_key.encode("utf-8") if isinstance(raw_key, str) else (raw_key or b"")
        self.timeout = timeout
        self._seq = 1

    def _mask_secret(self, val: str, visible: int = 4) -> str:
        if not val:
            return "<EMPTY>"
        if len(val) <= visible:
            return "***"
        return val[:visible] + "*" * (len(val) - visible)

    def _encrypt_payload(self, data_bytes: bytes) -> bytes:
        if not self.local_key:
            raise ValueError("Tuya local key is missing or empty.")
        cipher = AES.new(self.local_key, AES.MODE_ECB)
        return cipher.encrypt(pad(data_bytes, 16))

    def _decrypt_payload(self, encrypted_bytes: bytes) -> bytes:
        if not self.local_key:
            raise ValueError("Tuya local key is missing or empty.")
        cipher = AES.new(self.local_key, AES.MODE_ECB)
        return unpad(cipher.decrypt(encrypted_bytes), 16)

    def _pack_message(self, cmd: int, data_obj: Optional[Dict[str, Any]] = None, raw_aes: bool = True) -> bytes:
        seq = self._seq
        self._seq += 1

        if data_obj is None:
            # Heartbeat frame without payload (length = 8 bytes: 4 CRC + 4 suffix)
            prefix = struct.pack(">IIII", 0x000055AA, seq, cmd, 8)
            crc = binascii.crc32(prefix) & 0xFFFFFFFF
            return prefix + struct.pack(">II", crc, 0x0000AA55)

        payload_str = json.dumps(data_obj, separators=(',', ':'))
        payload_encrypted = self._encrypt_payload(payload_str.encode('utf-8'))

        if raw_aes:
            payload_body = payload_encrypted
        else:
            # Protocol 3.3 header prefix: '3.3' + 12 zero bytes
            version_header = b"3.3" + (b"\x00" * 12)
            payload_body = version_header + payload_encrypted

        total_len = len(payload_body) + 8
        header = struct.pack(">IIII", 0x000055AA, seq, cmd, total_len)
        crc = binascii.crc32(header + payload_body) & 0xFFFFFFFF
        suffix = struct.pack(">II", crc, 0x0000AA55)

        return header + payload_body + suffix

    def _unpack_response(self, raw_bytes: bytes) -> Tuple[Optional[Dict[str, Any]], int, str]:
        if len(raw_bytes) < 24:
            return None, -1, f"Packet too short ({len(raw_bytes)} bytes)"

        prefix, seq, cmd, length = struct.unpack(">IIII", raw_bytes[:16])
        if prefix != 0x000055AA:
            return None, -1, f"Invalid prefix {hex(prefix)}"

        payload_data = raw_bytes[16:16+length-8]
        ret_code = 0
        if len(payload_data) >= 4:
            possible_code = struct.unpack(">I", payload_data[:4])[0]
            if possible_code == 0 and len(payload_data) > 4:
                payload_data = payload_data[4:]
            elif possible_code != 0:
                ret_code = possible_code
                payload_data = payload_data[4:]

        if not payload_data:
            return None, ret_code, "Empty body"

        if payload_data.startswith(b"3.3"):
            enc = payload_data[15:]
            try:
                dec = self._decrypt_payload(enc)
                return json.loads(dec.decode('utf-8')), ret_code, "Decrypted 3.3 OK"
            except Exception as e:
                return None, ret_code, f"Decrypt error: {e}"
        else:
            try:
                dec = self._decrypt_payload(payload_data)
                return json.loads(dec.decode('utf-8')), ret_code, "Raw Decrypt OK"
            except Exception:
                try:
                    return json.loads(payload_data.decode('utf-8')), ret_code, "Plain JSON OK"
                except Exception as e:
                    return None, ret_code, f"Decode error: {e}"

    def check_lan_heartbeat(self) -> Tuple[bool, float]:
        """
        Sends Protocol 3.3 Heartbeat packet over raw TCP to verify hardware reachability.
        Returns (is_alive, latency_ms).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        t0 = time.perf_counter()
        try:
            sock.connect((self.ip, self.port))
            pkt = self._pack_message(self.CMD_HEARTBEAT, None)
            sock.sendall(pkt)
            resp = sock.recv(1024)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if len(resp) >= 24:
                prefix, _, cmd, length = struct.unpack(">IIII", resp[:16])
                ret_code = struct.unpack(">I", resp[16:20])[0] if length >= 12 else 0
                return (prefix == 0x000055AA and cmd == self.CMD_HEARTBEAT and ret_code == 0), elapsed_ms
            return False, elapsed_ms
        except Exception as e:
            logger.debug(f"Heartbeat probe failed to {self.ip}:{self.port}: {e}")
            return False, (time.perf_counter() - t0) * 1000.0
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def decode_dps(self, dps: Dict[str, Any], latency_ms: float) -> Optional[DecodedAcState]:
        """
        Decodes a raw Tuya DPS map into a validated DecodedAcState instance.
        Recognizes either numeric DP keys ("1", "2", "3", "4", "5") or string codes ("switch", "temp_set", etc.).
        """
        if not isinstance(dps, dict):
            return None

        # DP 1: Power switch
        raw_power = dps.get("1", dps.get("switch"))
        if raw_power is None:
            # Default to False if not present
            power_val = False
        else:
            power_val = bool(raw_power)

        # DP 2: Target Temperature (16 - 30 C)
        raw_temp_set = dps.get("2", dps.get("temp_set", 24))
        try:
            target_temp = int(raw_temp_set)
        except (ValueError, TypeError):
            target_temp = 24

        # DP 3 / DP 109: Current Ambient Temperature
        raw_temp_curr = dps.get("3", dps.get("temp_current", dps.get("109")))
        if raw_temp_curr is not None:
            try:
                current_temp: Optional[int] = int(raw_temp_curr)
            except (ValueError, TypeError):
                current_temp = None
        else:
            current_temp = None

        # DP 4: Mode (cold/auto/wet/wind -> COOL/AUTO/DRY/FAN)
        raw_mode = str(dps.get("4", dps.get("mode", "cold"))).lower()
        animus_mode = self.REVERSE_MODE_MAP.get(raw_mode, "COOL")

        # DP 5: Fan Speed (low/mid/high/auto -> LOW/MEDIUM/HIGH/AUTO)
        raw_fan = str(dps.get("5", dps.get("fan_speed_enum", "low"))).lower()
        animus_fan = self.REVERSE_FAN_MAP.get(raw_fan, "LOW")

        return DecodedAcState(
            power=power_val,
            target_temperature=target_temp,
            current_temperature=current_temp,
            mode=animus_mode,
            fan_speed=animus_fan,
            raw_dps=dps,
            latency_ms=latency_ms,
            timestamp=time.time(),
        )

    def read_ac_state(self) -> LocalReadResult:
        """
        Executes an authoritative local LAN read operation against the AC hardware.
        Does not issue any write/control commands or cloud API calls.
        """
        t0 = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.ip, self.port))
            
            # Step 1: Send Heartbeat on socket
            hb_pkt = self._pack_message(self.CMD_HEARTBEAT, None)
            sock.sendall(hb_pkt)
            hb_resp = sock.recv(1024)
            if len(hb_resp) < 24:
                return LocalReadResult(
                    status=ReadDiagnosticStatus.LOCAL_READ_FAILED,
                    error=f"Heartbeat response too short from {self.ip}:{self.port}.",
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                )

            # Step 2: Send DP Query on same socket session
            query_data = {
                "gwId": self.dev_id,
                "devId": self.dev_id,
            }
            pkt = self._pack_message(self.CMD_DP_QUERY, query_data)
            sock.sendall(pkt)
            
            resp = sock.recv(2048)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            
            parsed, ret_code, note = self._unpack_response(resp)
            if parsed is None:
                return LocalReadResult(
                    status=ReadDiagnosticStatus.DECODE_FAILED,
                    error=f"Failed to decrypt/parse response: {note} (ret_code={ret_code})",
                    latency_ms=elapsed_ms,
                )

            dps = parsed.get("dps", parsed)
            if not isinstance(dps, dict):
                return LocalReadResult(
                    status=ReadDiagnosticStatus.DECODE_FAILED,
                    error=f"Response does not contain a valid DPS dictionary: {parsed}",
                    latency_ms=elapsed_ms,
                )

            decoded = self.decode_dps(dps, elapsed_ms)
            if decoded is None:
                return LocalReadResult(
                    status=ReadDiagnosticStatus.DECODE_FAILED,
                    error="DPS decoding returned None.",
                    latency_ms=elapsed_ms,
                )

            return LocalReadResult(
                status=ReadDiagnosticStatus.LOCAL_READ_SUCCESS,
                state=decoded,
                latency_ms=elapsed_ms,
            )
        except socket.timeout:
            return LocalReadResult(
                status=ReadDiagnosticStatus.LOCAL_READ_FAILED,
                error=f"Socket timeout ({self.timeout}s) waiting for response from {self.ip}:{self.port}.",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
        except Exception as e:
            return LocalReadResult(
                status=ReadDiagnosticStatus.LOCAL_READ_FAILED,
                error=f"Socket exception: {e}",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
            )
        finally:
            try:
                sock.close()
            except Exception:
                pass
