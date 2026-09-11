"""
Authoritative Air Conditioner (AC) Controller for Animus Smart Room.
Controls the physical Inverter Split Air Conditioner (Tuya Category 'kt', Product ID: XT0UJtiNvEocE9Mu)
at 192.168.1.4:6668 via Local Tuya 3.3 TCP Protocol with Tuya Cloud OpenAPI fallback.

Architectural Flow:
Brain understands -> Router decides -> AC Controller executes -> Physical AC verifies -> UI reports reality
"""

import os
import time
import socket
import struct
import json
import logging
import binascii
import hashlib
import hmac
import threading
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
import requests

logger = logging.getLogger("ac_controller")

class AcMode(str, Enum):
    COOL = "COOL"
    AUTO = "AUTO"
    DRY = "DRY"
    FAN = "FAN"

class AcFanSpeed(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    AUTO = "AUTO"

class TransportType(str, Enum):
    LAN = "LAN"
    CLOUD = "CLOUD"
    NONE = "NONE"


def _read_local_properties() -> Dict[str, str]:
    """Reads local.properties from project root if available."""
    props = {}
    candidates = [
        Path(__file__).parent.parent.parent / "local.properties",
        Path("d:/AnimusSmartRoom/local.properties"),
        Path("local.properties"),
    ]
    for c in candidates:
        if c.exists():
            try:
                with open(c, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            props[k.strip()] = v.strip()
                break
            except Exception as e:
                logger.warning(f"Error reading {c}: {e}")
    return props


class LocalTuyaTransport:
    """
    Local TCP Transport for Tuya Protocol 3.3.
    Communicates directly with 192.168.1.4:6668 with sub-15ms roundtrip.
    """
    def __init__(self, ip: str, port: int, dev_id: str, local_key: str, timeout: float = 2.0):
        self.ip = ip
        self.port = port
        self.dev_id = dev_id
        self.local_key = local_key.encode("utf-8") if isinstance(local_key, str) else local_key
        self.timeout = timeout
        self._lock = threading.Lock()
        self._seq = 1

    def _encrypt_payload(self, data_bytes: bytes) -> bytes:
        cipher = AES.new(self.local_key, AES.MODE_ECB)
        return cipher.encrypt(pad(data_bytes, 16))

    def _decrypt_payload(self, encrypted_bytes: bytes) -> bytes:
        cipher = AES.new(self.local_key, AES.MODE_ECB)
        return unpad(cipher.decrypt(encrypted_bytes), 16)

    def _pack_message(self, cmd: int, data_obj: Optional[Dict[str, Any]] = None) -> bytes:
        with self._lock:
            seq = self._seq
            self._seq += 1

        if data_obj is None:
            # Heartbeat packet without body (8 bytes length = CRC + Suffix)
            prefix = struct.pack(">IIII", 0x000055AA, seq, cmd, 8)
            crc = binascii.crc32(prefix) & 0xFFFFFFFF
            return prefix + struct.pack(">II", crc, 0x0000AA55)

        payload_str = json.dumps(data_obj, separators=(',', ':'))
        payload_encrypted = self._encrypt_payload(payload_str.encode('utf-8'))
        
        # Protocol 3.3 header prefix: "3.3" + 12 zero bytes
        version_header = b"3.3" + (b"\x00" * 12)
        payload_body = version_header + payload_encrypted
        
        total_len = len(payload_body) + 8  # 4 bytes CRC + 4 bytes suffix
        header = struct.pack(">IIII", 0x000055AA, seq, cmd, total_len)
        crc = binascii.crc32(header + payload_body) & 0xFFFFFFFF
        suffix = struct.pack(">II", crc, 0x0000AA55)
        
        return header + payload_body + suffix

    def _unpack_response(self, raw_bytes: bytes) -> Tuple[Optional[Dict[str, Any]], int, str]:
        if len(raw_bytes) < 24:
            return None, -1, f"Packet too short ({len(raw_bytes)} bytes)"
        
        prefix, seq, cmd, length = struct.unpack(">IIII", raw_bytes[:16])
        if prefix != 0x000055AA:
            return None, -1, f"Invalid packet prefix: {hex(prefix)}"
        
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
                return json.loads(dec.decode('utf-8')), ret_code, "Decrypted OK"
            except Exception as e:
                return None, ret_code, f"Decrypt error: {e}"
        else:
            try:
                return json.loads(payload_data.decode('utf-8')), ret_code, "Plain JSON OK"
            except Exception as e:
                return None, ret_code, f"Decode error: {e}"

    def send_heartbeat(self) -> bool:
        """Sends cmd 0x09 heartbeat to verify local LAN socket readiness."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.ip, self.port))
            pkt = self._pack_message(0x09, None)
            sock.sendall(pkt)
            resp = sock.recv(1024)
            if len(resp) >= 24:
                prefix, _, cmd, _ = struct.unpack(">IIII", resp[:16])
                return prefix == 0x000055AA and cmd == 0x09
            return False
        except Exception as e:
            logger.debug(f"[LAN_HEARTBEAT_FAIL] {self.ip}:{self.port} - {e}")
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def send_dps_command(self, dps_dict: Dict[str, Any]) -> bool:
        """Sends cmd 0x07 local control packet with DPS payload, with retry on transient socket reset."""
        for attempt in range(2):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            try:
                sock.connect((self.ip, self.port))
                # Protocol 3.3 requires heartbeat handshake to establish session before control
                try:
                    hb_pkt = self._pack_message(0x09, None)
                    sock.sendall(hb_pkt)
                    sock.recv(1024)
                except Exception:
                    pass

                data_payload = {
                    "devId": self.dev_id,
                    "gwId": self.dev_id,
                    "uid": self.dev_id,
                    "t": str(int(time.time())),
                    "dps": dps_dict
                }
                pkt = self._pack_message(0x07, data_payload)
                sock.sendall(pkt)
                resp = sock.recv(1024)
                _, ret_code, note = self._unpack_response(resp)
                if ret_code == 0:
                    return True
            except Exception as e:
                if attempt == 0:
                    logger.debug(f"[LAN_CONTROL_RETRY] Retry after transient error sending DPS {dps_dict}: {e}")
                    time.sleep(0.15)
                    continue
                logger.warning(f"[LAN_CONTROL_FAIL] Error sending DPS {dps_dict}: {e}")
                return False
            finally:
                try:
                    sock.close()
                except Exception:
                    pass
        return False


class CloudTuyaTransport:
    """
    Tuya Cloud OpenAPI Transport with HMAC-SHA256 signing and token caching.
    """
    def __init__(self, access_id: str, access_secret: str, dev_id: str, endpoint: str = "https://openapi.tuyain.com"):
        self.access_id = access_id.strip()
        self.access_secret = access_secret.strip()
        self.dev_id = dev_id.strip()
        self.endpoint = endpoint.rstrip("/")
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()

    def _sha256_hex(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _hmac_sha256(self, data: str) -> str:
        return hmac.new(self.access_secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest().upper()

    def get_token(self) -> Optional[str]:
        with self._lock:
            now = time.time()
            if self._cached_token and now < self._token_expires_at - 60:
                return self._cached_token

            t = str(int(time.time() * 1000))
            path = "/v1.0/token?grant_type=1"
            string_to_sign = f"GET\n{self._sha256_hex('')}\n\n{path}"
            sign_str = f"{self.access_id}{t}{string_to_sign}"
            sign = self._hmac_sha256(sign_str)

            headers = {
                "client_id": self.access_id,
                "sign": sign,
                "t": t,
                "sign_method": "HMAC-SHA256"
            }

            try:
                resp = requests.get(f"{self.endpoint}{path}", headers=headers, timeout=8.0)
                data = resp.json()
                if data.get("success") and "result" in data:
                    self._cached_token = data["result"]["access_token"]
                    exp_sec = data["result"].get("expire_time", 7200)
                    self._token_expires_at = now + exp_sec
                    return self._cached_token
                else:
                    logger.error(f"[TUYA_TOKEN_FAIL] Error response: {data}")
                    return None
            except Exception as e:
                logger.error(f"[TUYA_TOKEN_EXCEPTION] {e}")
                return None

    def fetch_status(self) -> Optional[List[Dict[str, Any]]]:
        token = self.get_token()
        if not token:
            return None

        t = str(int(time.time() * 1000))
        path = f"/v1.0/devices/{self.dev_id}/status"
        string_to_sign = f"GET\n{self._sha256_hex('')}\n\n{path}"
        sign_str = f"{self.access_id}{token}{t}{string_to_sign}"
        sign = self._hmac_sha256(sign_str)

        headers = {
            "client_id": self.access_id,
            "access_token": token,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256"
        }

        try:
            resp = requests.get(f"{self.endpoint}{path}", headers=headers, timeout=8.0)
            data = resp.json()
            if data.get("success") and "result" in data:
                return data["result"]
            logger.warning(f"[TUYA_STATUS_FAIL] {data}")
            return None
        except Exception as e:
            logger.error(f"[TUYA_STATUS_EXCEPTION] {e}")
            return None

    def send_commands(self, commands: List[Dict[str, Any]]) -> bool:
        token = self.get_token()
        if not token:
            return False

        t = str(int(time.time() * 1000))
        path = f"/v1.0/devices/{self.dev_id}/commands"
        payload_body = json.dumps({"commands": commands}, separators=(',', ':'))
        string_to_sign = f"POST\n{self._sha256_hex(payload_body)}\n\n{path}"
        sign_str = f"{self.access_id}{token}{t}{string_to_sign}"
        sign = self._hmac_sha256(sign_str)

        headers = {
            "client_id": self.access_id,
            "access_token": token,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }

        try:
            resp = requests.post(f"{self.endpoint}{path}", headers=headers, data=payload_body, timeout=8.0)
            data = resp.json()
            return bool(data.get("success"))
        except Exception as e:
            logger.error(f"[TUYA_COMMAND_EXCEPTION] {e}")
            return False


class AcController:
    """
    Authoritative Inverter Split Air Conditioner Controller.
    Enforces hardware invariants, maps values, performs dual-transport dispatch,
    and returns truth-verified telemetry read-backs.
    """
    MIN_TEMPERATURE = 16
    MAX_TEMPERATURE = 30

    # Translations: Animus <-> Tuya
    MODE_MAP = {
        "COOL": "cold",
        "AUTO": "auto",
        "DRY": "wet",
        "FAN": "wind"
    }
    REVERSE_MODE_MAP = {
        "cold": AcMode.COOL.value,
        "auto": AcMode.AUTO.value,
        "wet": AcMode.DRY.value,
        "wind": AcMode.FAN.value
    }

    FAN_MAP = {
        "LOW": "low",
        "MEDIUM": "mid",
        "HIGH": "high",
        "AUTO": "auto"
    }
    REVERSE_FAN_MAP = {
        "low": AcFanSpeed.LOW.value,
        "mid": AcFanSpeed.MEDIUM.value,
        "high": AcFanSpeed.HIGH.value,
        "auto": AcFanSpeed.AUTO.value
    }

    DEFAULT_AC_MAC = "a4-e5-7c-0a-2c-a4"
    DEFAULT_AC_PORT = 6668

    def __init__(
        self,
        lan_ip: Optional[str] = None,
        lan_port: Optional[int] = None,
        dev_id: Optional[str] = None,
        local_key: Optional[str] = None,
        access_id: Optional[str] = None,
        access_secret: Optional[str] = None,
        endpoint: Optional[str] = None,
        strict_zero_cloud: Optional[bool] = None,
        mac_address: Optional[str] = None
    ):
        props = _read_local_properties()
        self.dev_id = dev_id or props.get("tuya.device.id", "76776532a4e57c0a2ca4")
        self.local_key = local_key or props.get("tuya.local.key", "1'/j|^zqMwIX=fL6")
        self.lan_ip = lan_ip or props.get("tuya.local.ip", "192.168.1.4")
        self.lan_port = lan_port or int(props.get("tuya.local.port", "6668"))
        raw_mac = mac_address or os.environ.get("TUYA_AC_MAC", props.get("tuya.ac.mac", self.DEFAULT_AC_MAC))
        self.mac_address = raw_mac.lower().replace(":", "-")
        
        self.access_id = access_id or props.get("tuya.access.id", "x9dwt4jhpvuuduv8aq7m")
        self.access_secret = access_secret or props.get("tuya.access.secret", "4a0a1fb84e414dec9d7d80ae5f0a777b")
        self.endpoint = endpoint or props.get("tuya.region.endpoint", "https://openapi.tuyain.com")

        if strict_zero_cloud is not None:
            self.strict_zero_cloud = strict_zero_cloud
        else:
            self.strict_zero_cloud = os.environ.get("STRICT_ZERO_CLOUD", props.get("tuya.strict_zero_cloud", "true")).strip().lower() == "true"

        # Dynamically discover / verify physical AC IP before socket binding
        if not self._test_tcp_port(self.lan_ip, self.lan_port, timeout=0.3):
            self.resolve_ac_ip()

        self.lan_transport = LocalTuyaTransport(
            ip=self.lan_ip,
            port=self.lan_port,
            dev_id=self.dev_id,
            local_key=self.local_key
        )
        self.cloud_transport = CloudTuyaTransport(
            access_id=self.access_id,
            access_secret=self.access_secret,
            dev_id=self.dev_id,
            endpoint=self.endpoint
        )
        self._last_known_status: Dict[str, Any] = {}
        self._lan_degraded_until: float = 0.0

    def _test_tcp_port(self, ip: str, port: int = 6668, timeout: float = 0.3) -> bool:
        """Fast non-blocking TCP check to verify Tuya port 6668 responsiveness."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            res = sock.connect_ex((ip, port))
            sock.close()
            return res == 0
        except Exception:
            return False

    def _get_arp_table(self) -> Dict[str, str]:
        """Parses Windows ARP table into {ip: normalized_mac}."""
        import subprocess, re
        try:
            out = subprocess.check_output("arp -a", shell=True, text=True)
            entries = {}
            for line in out.splitlines():
                line = line.strip()
                m = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2})', line)
                if m:
                    ip = m.group(1)
                    mac = m.group(2).lower().replace(":", "-")
                    entries[ip] = mac
            return entries
        except Exception as e:
            logger.debug(f"[AC_ARP_ERR] {e}")
            return {}

    def resolve_ac_ip(self, force_rescan: bool = False) -> Optional[str]:
        """
        Dynamically locates the physical AC on the local network using its permanent MAC address
        and Tuya port 6668. Tolerates dynamic DHCP leasing where IP changes across router reboots.
        """
        curr_ip = self.lan_ip

        # 1. Quick check if current target IP still has port 6668 open
        if not force_rescan and self._test_tcp_port(curr_ip, self.lan_port, timeout=0.25):
            return curr_ip

        # 2. Check ARP table for known AC MAC address
        target_mac = self.mac_address.lower().replace(":", "-")
        arp_entries = self._get_arp_table()
        for ip, mac in arp_entries.items():
            if mac == target_mac:
                if self._test_tcp_port(ip, self.lan_port, timeout=0.4):
                    if ip != curr_ip:
                        logger.info(f"[AC_IP_MIGRATION] AC MAC {target_mac} moved from {curr_ip} -> {ip}. Updating target.")
                        self._apply_new_ip(ip)
                    return ip

        # 3. Fast parallel scan of local subnet on port 6668
        prefix = ".".join(curr_ip.split(".")[:3])
        if not prefix or len(prefix.split(".")) != 3:
            prefix = "192.168.1"
        candidates = [f"{prefix}.{i}" for i in range(2, 35)]

        from concurrent.futures import ThreadPoolExecutor
        open_ips = []
        try:
            with ThreadPoolExecutor(max_workers=20) as executor:
                results = executor.map(lambda ip: (ip, self._test_tcp_port(ip, self.lan_port, timeout=0.35)), candidates)
                for ip, is_open in results:
                    if is_open:
                        open_ips.append(ip)
        except Exception as e:
            logger.debug(f"[AC_SCAN_ERR] {e}")

        for ip in open_ips:
            arp_now = self._get_arp_table()
            if arp_now.get(ip) == target_mac:
                logger.info(f"[AC_IP_DISCOVERED] Discovered AC MAC {target_mac} at {ip}:{self.lan_port} via subnet scan.")
                self._apply_new_ip(ip)
                return ip

        return None

    def _apply_new_ip(self, new_ip: str) -> None:
        """Updates internal target and caches to local.properties."""
        self.lan_ip = new_ip
        if hasattr(self, "lan_transport") and self.lan_transport:
            self.lan_transport.ip = new_ip
        try:
            from pathlib import Path
            p_file = Path("d:/AnimusSmartRoom/local.properties")
            if p_file.exists():
                lines = p_file.read_text(encoding="utf-8").splitlines()
                new_lines = []
                replaced = False
                for line in lines:
                    if line.startswith("tuya.local.ip="):
                        new_lines.append(f"tuya.local.ip={new_ip}")
                        replaced = True
                    else:
                        new_lines.append(line)
                if not replaced:
                    new_lines.append(f"tuya.local.ip={new_ip}")
                p_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                logger.info(f"[AC_CACHE_UPDATE] Saved new AC IP {new_ip} to local.properties")
        except Exception as e:
            logger.debug(f"[AC_CACHE_UPDATE_ERR] {e}")

    def get_status(self) -> Dict[str, Any]:
        """
        Queries authoritative physical status.
        Reads live status from Local LAN TCP (Local Key) first with Cloud OpenAPI fallback.
        In Strict Zero-Cloud Mode, never queries Tuya Cloud OpenAPI.
        """
        # 1. Attempt Local LAN Read First (Zero Cloud Quota)
        if time.time() >= self._lan_degraded_until:
            try:
                try:
                    from tuya_local_read_adapter import TuyaLocalAcReadAdapter, ReadDiagnosticStatus
                except ImportError:
                    from server.music_daemon.tuya_local_read_adapter import TuyaLocalAcReadAdapter, ReadDiagnosticStatus
                local_adapter = TuyaLocalAcReadAdapter(
                    ip=self.lan_ip,
                    port=self.lan_port,
                    dev_id=self.dev_id,
                    local_key=self.local_key,
                    timeout=1.5
                )
                local_res = local_adapter.read_ac_state()
                if local_res.status == ReadDiagnosticStatus.LOCAL_READ_SUCCESS and local_res.state:
                    st = local_res.state
                    status_result = {
                        "power": st.power,
                        "target_temperature": st.target_temperature,
                        "ambient_temperature": st.current_temperature,
                        "mode": st.mode,
                        "fan_speed": st.fan_speed,
                        "raw_mode": str(st.raw_dps.get("mode", "cold")),
                        "raw_fan": str(st.raw_dps.get("fan_speed_enum", "low")),
                        "connectivity": "ONLINE",
                        "transport_used": TransportType.LAN.value,
                        "timestamp": time.time(),
                        "verified": True
                    }
                    self._last_known_status = status_result
                    return status_result
            except Exception as e:
                logger.debug(f"[LOCAL_LAN_STATUS_FALLBACK] {e}")

        # In Strict Zero-Cloud Mode, NEVER hit Tuya Cloud OpenAPI on status queries / background polls
        if self.strict_zero_cloud:
            logger.debug("[STRICT_ZERO_CLOUD] Local LAN read unverified, returning offline status without cloud query.")
            return {
                "power": self._last_known_status.get("power", False),
                "target_temperature": self._last_known_status.get("target_temperature", 24),
                "ambient_temperature": self._last_known_status.get("ambient_temperature"),
                "mode": self._last_known_status.get("mode", "UNKNOWN"),
                "fan_speed": self._last_known_status.get("fan_speed", "UNKNOWN"),
                "connectivity": "OFFLINE",
                "transport_used": TransportType.NONE.value,
                "timestamp": time.time(),
                "verified": False,
                "error": "Failed to read physical AC status over local LAN (Strict Zero-Cloud Mode active)."
            }

        # 2. Fallback to Cloud OpenAPI (Only when strict_zero_cloud is False)
        status_items = self.cloud_transport.fetch_status()
        if not status_items:
            # If offline or failed
            return {
                "power": False,
                "target_temperature": 24,
                "ambient_temperature": None,
                "mode": "UNKNOWN",
                "fan_speed": "UNKNOWN",
                "connectivity": "OFFLINE",
                "transport_used": TransportType.NONE.value,
                "timestamp": time.time(),
                "verified": False,
                "error": "Failed to read physical AC status over Cloud and LAN."
            }

        dps: Dict[str, Any] = {}
        for item in status_items:
            code = item.get("code")
            val = item.get("value")
            if code:
                dps[code] = val

        power_on = bool(dps.get("switch", False))
        target_t = int(dps.get("temp_set", 24))
        ambient_t = dps.get("temp_current")
        if ambient_t is not None:
            ambient_t = int(ambient_t)

        raw_mode = str(dps.get("mode", "cold"))
        animus_mode = self.REVERSE_MODE_MAP.get(raw_mode, "UNKNOWN")

        raw_fan = str(dps.get("fan_speed_enum", "low"))
        animus_fan = self.REVERSE_FAN_MAP.get(raw_fan, "UNKNOWN")

        status_result = {
            "power": power_on,
            "target_temperature": target_t,
            "ambient_temperature": ambient_t,
            "mode": animus_mode,
            "fan_speed": animus_fan,
            "raw_mode": raw_mode,
            "raw_fan": raw_fan,
            "connectivity": "ONLINE",
            "transport_used": TransportType.CLOUD.value,
            "timestamp": time.time(),
            "verified": True
        }
        self._last_known_status = status_result
        return status_result

    def _verify_readback(self, predicate, max_wait: float = 3.2, interval: float = 0.4) -> Tuple[bool, Dict[str, Any]]:
        """Polls read-back status until predicate is satisfied or timeout expires."""
        t_end = time.time() + max_wait
        last_st: Dict[str, Any] = {}
        while time.time() < t_end:
            time.sleep(interval)
            last_st = self.get_status()
            if last_st.get("verified") and predicate(last_st):
                return True, last_st
        return False, (last_st or self.get_status())


    def set_power(self, on: bool) -> Tuple[bool, Dict[str, Any]]:
        """
        Turns AC power ON or OFF with authoritative telemetry read-back verification.
        """
        cur = self.get_status()
        if cur.get("verified") and cur.get("power") == on:
            return True, {
                "success": True,
                "idempotent": True,
                "power": on,
                "message": f"AC is already {'ON' if on else 'OFF'}.",
                "transport": cur.get("transport_used"),
                "verified": True
            }

        lan_ok = False
        transport_used = TransportType.CLOUD.value
        if time.time() >= self._lan_degraded_until:
            if not self._test_tcp_port(self.lan_ip, self.lan_port, timeout=0.2):
                self.resolve_ac_ip()
            if self.lan_transport.send_dps_command({"1": on}):
                lan_ok = True
                transport_used = TransportType.LAN.value
            else:
                # Dynamic IP recovery attempt on command failure
                new_ip = self.resolve_ac_ip(force_rescan=True)
                if new_ip and self.lan_transport.send_dps_command({"1": on}):
                    lan_ok = True
                    transport_used = TransportType.LAN.value
                else:
                    self._lan_degraded_until = time.time() + 5.0

        verified = False
        after: Dict[str, Any] = {}
        if lan_ok:
            verified, after = self._verify_readback(lambda s: s.get("power") == on, max_wait=1.2)
            if not verified:
                logger.info("[LAN_FALLBACK] LAN command unverified on readback, falling back to Cloud OpenAPI.")
                lan_ok = False
                self._lan_degraded_until = time.time() + 5.0

        if not lan_ok:
            if self.strict_zero_cloud:
                logger.warning("[STRICT_ZERO_CLOUD] Local LAN power command failed, cloud fallback blocked.")
                return False, {
                    "success": False,
                    "power": on,
                    "error": "Failed to dispatch power command over local LAN (Strict Zero-Cloud Mode active).",
                    "verified": False,
                    "transport": TransportType.LAN.value
                }
            transport_used = TransportType.CLOUD.value
            cloud_ok = self.cloud_transport.send_commands([{"code": "switch", "value": on}])
            if not cloud_ok:
                return False, {
                    "success": False,
                    "power": on,
                    "error": "Failed to dispatch power command over both LAN and Cloud.",
                    "verified": False
                }
            verified, after = self._verify_readback(lambda s: s.get("power") == on, max_wait=3.2)

        return verified, {
            "success": verified,
            "power": after.get("power", on),
            "transport": transport_used,
            "verified": verified,
            "message": f"AC power set to {'ON' if on else 'OFF'} (verified read-back)." if verified else "Power command dispatched but verification failed."
        }

    def set_temperature(self, temp_celsius: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Sets target thermostat temperature (16–30°C) with read-back verification.
        """
        if temp_celsius < self.MIN_TEMPERATURE or temp_celsius > self.MAX_TEMPERATURE:
            return False, {
                "success": False,
                "requested_temperature": temp_celsius,
                "error": f"Temperature {temp_celsius}°C is out of bounds ({self.MIN_TEMPERATURE}–{self.MAX_TEMPERATURE}°C).",
                "status": "INVALID_PARAMETER",
                "verified": False
            }

        cur = self.get_status()
        if cur.get("verified") and cur.get("target_temperature") == temp_celsius:
            return True, {
                "success": True,
                "idempotent": True,
                "target_temperature": temp_celsius,
                "ambient_temperature": cur.get("ambient_temperature"),
                "message": f"AC is already set to {temp_celsius}°C.",
                "transport": cur.get("transport_used"),
                "verified": True
            }

        lan_ok = False
        transport_used = TransportType.CLOUD.value
        if time.time() >= self._lan_degraded_until:
            if not self._test_tcp_port(self.lan_ip, self.lan_port, timeout=0.2):
                self.resolve_ac_ip()
            if self.lan_transport.send_dps_command({"2": temp_celsius}):
                lan_ok = True
                transport_used = TransportType.LAN.value
            else:
                new_ip = self.resolve_ac_ip(force_rescan=True)
                if new_ip and self.lan_transport.send_dps_command({"2": temp_celsius}):
                    lan_ok = True
                    transport_used = TransportType.LAN.value
                else:
                    self._lan_degraded_until = time.time() + 5.0

        verified = False
        after: Dict[str, Any] = {}
        if lan_ok:
            verified, after = self._verify_readback(lambda s: s.get("target_temperature") == temp_celsius, max_wait=1.2)
            if not verified:
                logger.info("[LAN_FALLBACK] LAN temperature unverified on readback, falling back to Cloud OpenAPI.")
                lan_ok = False
                self._lan_degraded_until = time.time() + 5.0

        if not lan_ok:
            if self.strict_zero_cloud:
                logger.warning("[STRICT_ZERO_CLOUD] Local LAN temperature command failed, cloud fallback blocked.")
                return False, {
                    "success": False,
                    "requested_temperature": temp_celsius,
                    "error": f"Failed to dispatch temperature {temp_celsius}°C over local LAN (Strict Zero-Cloud Mode active).",
                    "verified": False,
                    "transport": TransportType.LAN.value
                }
            transport_used = TransportType.CLOUD.value
            cloud_ok = self.cloud_transport.send_commands([{"code": "temp_set", "value": temp_celsius}])
            if not cloud_ok:
                return False, {
                    "success": False,
                    "requested_temperature": temp_celsius,
                    "error": f"Failed to dispatch temperature {temp_celsius}°C over LAN and Cloud.",
                    "verified": False
                }
            verified, after = self._verify_readback(lambda s: s.get("target_temperature") == temp_celsius, max_wait=3.2)

        return verified, {
            "success": verified,
            "target_temperature": after.get("target_temperature", temp_celsius),
            "ambient_temperature": after.get("ambient_temperature"),
            "transport": transport_used,
            "verified": verified,
            "message": f"Target temperature set to {temp_celsius}°C (verified read-back)." if verified else "Temperature command dispatched but verification failed."
        }

    def set_mode(self, mode_input: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Sets operating HVAC mode (COOL, AUTO, DRY, FAN).
        Rejects HEAT and invalid modes cleanly.
        """
        m_str = mode_input.strip().upper()

        if m_str in ["HEAT", "WARM", "HEATING"]:
            return False, {
                "success": False,
                "requested_mode": mode_input,
                "error": "This AC is a cooling-only inverter model. Heat mode is physically unsupported.",
                "status": "UNSUPPORTED_HARDWARE",
                "verified": False
            }

        if m_str in ["COOL", "COLD", "COOLING"]:
            target_animus = AcMode.COOL.value
        elif m_str in ["AUTO", "AUTOMATIC"]:
            target_animus = AcMode.AUTO.value
        elif m_str in ["DRY", "WET", "DEHUMIDIFY"]:
            target_animus = AcMode.DRY.value
        elif m_str in ["FAN", "WIND", "FAN_ONLY"]:
            target_animus = AcMode.FAN.value
        else:
            return False, {
                "success": False,
                "requested_mode": mode_input,
                "error": f"Mode '{mode_input}' is invalid. Supported modes: COOL, AUTO, DRY, FAN.",
                "status": "INVALID_PARAMETER",
                "verified": False
            }

        tuya_mode = self.MODE_MAP[target_animus]

        cur = self.get_status()
        if cur.get("verified") and cur.get("mode") == target_animus:
            return True, {
                "success": True,
                "idempotent": True,
                "mode": target_animus,
                "message": f"AC is already in {target_animus} mode.",
                "transport": cur.get("transport_used"),
                "verified": True
            }

        lan_ok = False
        transport_used = TransportType.CLOUD.value
        if time.time() >= self._lan_degraded_until:
            if not self._test_tcp_port(self.lan_ip, self.lan_port, timeout=0.2):
                self.resolve_ac_ip()
            if self.lan_transport.send_dps_command({"4": tuya_mode}):
                lan_ok = True
                transport_used = TransportType.LAN.value
            else:
                new_ip = self.resolve_ac_ip(force_rescan=True)
                if new_ip and self.lan_transport.send_dps_command({"4": tuya_mode}):
                    lan_ok = True
                    transport_used = TransportType.LAN.value
                else:
                    self._lan_degraded_until = time.time() + 5.0

        verified = False
        after: Dict[str, Any] = {}
        if lan_ok:
            verified, after = self._verify_readback(lambda s: s.get("mode") == target_animus, max_wait=1.2)
            if not verified:
                logger.info("[LAN_FALLBACK] LAN mode unverified on readback, falling back to Cloud OpenAPI.")
                lan_ok = False
                self._lan_degraded_until = time.time() + 5.0

        if not lan_ok:
            if self.strict_zero_cloud:
                logger.warning("[STRICT_ZERO_CLOUD] Local LAN mode command failed, cloud fallback blocked.")
                return False, {
                    "success": False,
                    "requested_mode": target_animus,
                    "error": f"Failed to dispatch mode '{target_animus}' over local LAN (Strict Zero-Cloud Mode active).",
                    "verified": False,
                    "transport": TransportType.LAN.value
                }
            transport_used = TransportType.CLOUD.value
            cloud_ok = self.cloud_transport.send_commands([{"code": "mode", "value": tuya_mode}])
            if not cloud_ok:
                return False, {
                    "success": False,
                    "requested_mode": target_animus,
                    "error": f"Failed to dispatch mode '{target_animus}' over LAN and Cloud.",
                    "verified": False
                }
            verified, after = self._verify_readback(lambda s: s.get("mode") == target_animus, max_wait=3.2)

        return verified, {
            "success": verified,
            "mode": after.get("mode", target_animus),
            "transport": transport_used,
            "verified": verified,
            "message": f"AC mode set to {target_animus} (verified read-back)." if verified else "Mode command dispatched but verification failed."
        }

    def set_fan_speed(self, speed_input: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Sets fan blower speed (LOW, MEDIUM, HIGH, AUTO).
        """
        s_str = speed_input.strip().upper()

        if s_str in ["LOW", "1"]:
            target_animus = AcFanSpeed.LOW.value
        elif s_str in ["MEDIUM", "MID", "2"]:
            target_animus = AcFanSpeed.MEDIUM.value
        elif s_str in ["HIGH", "3"]:
            target_animus = AcFanSpeed.HIGH.value
        elif s_str in ["AUTO"]:
            target_animus = AcFanSpeed.AUTO.value
        else:
            return False, {
                "success": False,
                "requested_fan_speed": speed_input,
                "error": f"Fan speed '{speed_input}' is invalid. Supported speeds: LOW, MEDIUM, HIGH, AUTO.",
                "status": "INVALID_PARAMETER",
                "verified": False
            }

        tuya_speed = self.FAN_MAP[target_animus]

        cur = self.get_status()
        if cur.get("verified") and cur.get("fan_speed") == target_animus:
            return True, {
                "success": True,
                "idempotent": True,
                "fan_speed": target_animus,
                "message": f"AC fan is already set to {target_animus}.",
                "transport": cur.get("transport_used"),
                "verified": True
            }

        lan_ok = False
        transport_used = TransportType.CLOUD.value
        if time.time() >= self._lan_degraded_until:
            if not self._test_tcp_port(self.lan_ip, self.lan_port, timeout=0.2):
                self.resolve_ac_ip()
            if self.lan_transport.send_dps_command({"5": tuya_speed}):
                lan_ok = True
                transport_used = TransportType.LAN.value
            else:
                new_ip = self.resolve_ac_ip(force_rescan=True)
                if new_ip and self.lan_transport.send_dps_command({"5": tuya_speed}):
                    lan_ok = True
                    transport_used = TransportType.LAN.value
                else:
                    self._lan_degraded_until = time.time() + 5.0

        verified = False
        after: Dict[str, Any] = {}
        if lan_ok:
            verified, after = self._verify_readback(lambda s: s.get("fan_speed") == target_animus, max_wait=1.2)
            if not verified:
                logger.info("[LAN_FALLBACK] LAN fan speed unverified on readback, falling back to Cloud OpenAPI.")
                lan_ok = False
                self._lan_degraded_until = time.time() + 5.0

        if not lan_ok:
            if self.strict_zero_cloud:
                logger.warning("[STRICT_ZERO_CLOUD] Local LAN fan speed command failed, cloud fallback blocked.")
                return False, {
                    "success": False,
                    "requested_fan_speed": target_animus,
                    "error": f"Failed to dispatch fan speed '{target_animus}' over local LAN (Strict Zero-Cloud Mode active).",
                    "verified": False,
                    "transport": TransportType.LAN.value
                }
            transport_used = TransportType.CLOUD.value
            cloud_ok = self.cloud_transport.send_commands([{"code": "fan_speed_enum", "value": tuya_speed}])
            if not cloud_ok:
                return False, {
                    "success": False,
                    "requested_fan_speed": target_animus,
                    "error": f"Failed to dispatch fan speed '{target_animus}' over LAN and Cloud.",
                    "verified": False
                }
            verified, after = self._verify_readback(lambda s: s.get("fan_speed") == target_animus, max_wait=3.2)

        return verified, {
            "success": verified,
            "fan_speed": after.get("fan_speed", target_animus),
            "transport": transport_used,
            "verified": verified,
            "message": f"AC fan speed set to {target_animus} (verified read-back)." if verified else "Fan speed command dispatched but verification failed."
        }



    def set_swing(self, enabled: bool = True) -> Tuple[bool, Dict[str, Any]]:
        """
        Rejects swing control with authoritative hardware truth.
        """
        return False, {
            "success": False,
            "requested_swing": enabled,
            "error": "Louver swing control is not available on this AC's Wi-Fi interface.",
            "status": "UNSUPPORTED_HARDWARE",
            "verified": False
        }
