"""
Windows Device Portal integration module for Animus PC Music Daemon.
Handles localhost-only Device Portal discovery, authentication, dynamic AEP discovery,
and Base64-encoded deviceId Bluetooth connection requests.
"""

import base64
import http.cookiejar
import json
import logging
import os
from pathlib import Path
import re
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("music_daemon.device_portal")

LG_MAC_HEX = "541589DCA579"
LG_MAC_COLON = "54:15:89:DC:A5:79"
DEFAULT_CONFIG_PATH = Path(r"D:\AnimusSmartRoom\server\music_daemon\secrets\device_portal.json")


def encode_aep_id(aep_id: str) -> str:
    """
    Encodes an Association Endpoint ID into standard Base64 string for Device Portal.
    """
    if not aep_id:
        return ""
    return base64.b64encode(aep_id.encode("utf-8")).decode("ascii")


class WindowsDevicePortalBluetooth:
    """
    Manages communication with local Windows Device Portal on 127.0.0.1.
    Never connects to external IP addresses, 0.0.0.0, or LAN interfaces.
    """
    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG_PATH,
        https_port: int = 50443,
        http_port: int = 50080
    ):
        self.config_path = config_path
        self.https_port = https_port
        self.http_port = http_port
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def _load_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Loads local Device Portal credentials from secure secrets file if present.
        """
        if self.config_path.is_file():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                return data.get("username"), data.get("password")
            except Exception as e:
                logger.warning(f"[DEVICE_PORTAL_CONFIG_ERROR] Failed to read config: {e}")
        return None, None

    def _create_authenticated_opener(self, username: Optional[str], password: Optional[str]) -> Tuple[urllib.request.OpenerDirector, http.cookiejar.CookieJar]:
        cj = http.cookiejar.CookieJar()
        handlers = [
            urllib.request.HTTPCookieProcessor(cj),
            urllib.request.HTTPSHandler(context=self._ctx)
        ]
        if username and password:
            auth_handler = urllib.request.HTTPBasicAuthHandler()
            auth_handler.add_password(
                realm="Windows Device Portal",
                uri=f"https://127.0.0.1:{self.https_port}",
                user=username,
                passwd=password
            )
            auth_handler.add_password(
                realm="Windows Device Portal",
                uri=f"http://127.0.0.1:{self.http_port}",
                user=username,
                passwd=password
            )
            handlers.append(auth_handler)

        opener = urllib.request.build_opener(*handlers)
        return opener, cj

    def is_available(self) -> bool:
        """
        Checks if Windows Device Portal is listening on localhost.
        """
        try:
            req = urllib.request.Request(f"https://127.0.0.1:{self.https_port}/certprompt.htm")
            res = urllib.request.urlopen(req, timeout=1.5, context=self._ctx)
            return res.status in (200, 302, 307)
        except urllib.error.HTTPError as he:
            return he.code in (200, 302, 307, 401)
        except Exception:
            return False

    def discover_lg_aep(self) -> Optional[str]:
        """
        Dynamically queries Windows WinRT DeviceInformation to obtain current AEP ID for LG SNC4R.
        """
        ps_cmd = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
            "$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod } | Select-Object -First 1;"
            "[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null;"
            "$asTask = $asTaskGeneric.MakeGenericMethod([Windows.Devices.Bluetooth.BluetoothDevice]);"
            "$t = $asTask.Invoke($null, @([Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync(0x541589DCA579)));"
            "if ($t.Wait(3000)) { if ($t.Result) { Write-Output $t.Result.DeviceId } }"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4
            )
            for line in res.stdout.splitlines():
                clean_id = line.strip()
                if "54:15:89:dc:a5:79" in clean_id.lower() or "541589dca579" in clean_id.lower():
                    logger.info(f"[AEP_DISCOVERED] Discovered dynamic LG AEP ID via WinRT: {clean_id[:25]}... (masked)")
                    return clean_id
        except Exception as e:
            logger.warning(f"[AEP_DISCOVERY_ERROR] Failed dynamic AEP query: {e}")

        # Fallback 1: Query Device Portal getpaired
        username, password = self._load_credentials()
        if username and password:
            opener, cj = self._create_authenticated_opener(username, password)
            try:
                opener.open(f"https://127.0.0.1:{self.https_port}/certprompt.htm", timeout=2)
                try:
                    opener.open(f"https://127.0.0.1:{self.https_port}/api/authorize/setSslState?sslState=http&remember=true", timeout=2)
                except Exception:
                    pass

                csrf_token = ""
                for c in cj:
                    if c.name == "CSRF-Token":
                        csrf_token = c.value
                headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
                req = urllib.request.Request(f"https://127.0.0.1:{self.https_port}/api/bt/getpaired", headers=headers)
                res = opener.open(req, timeout=3)
                data = json.loads(res.read().decode("utf-8-sig", errors="ignore"))
                for dev in data.get("PairedDevices", []):
                    dev_id = dev.get("ID", "")
                    if "54:15:89:dc:a5:79" in dev_id.lower():
                        logger.info(f"[AEP_DISCOVERED] Discovered dynamic LG AEP ID via WDP: {dev_id[:25]}... (masked)")
                        return dev_id
            except Exception:
                pass

        # Fallback 2: Construct standard Windows Association Endpoint ID from dynamic adapter MAC + soundbar MAC
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-PnpDevice -Class Bluetooth | Where-Object { $_.InstanceId -match 'USB\\\\VID_' } | Select-Object -First 1 -ExpandProperty InstanceId"],
                capture_output=True,
                text=True,
                timeout=3
            )
            for line in res.stdout.splitlines():
                parts = line.strip().split("\\")
                if len(parts) >= 3 and len(parts[2]) == 12:
                    raw_mac = parts[2].lower()
                    adapter_mac_formatted = ":".join(raw_mac[i:i+2] for i in range(0, 12, 2))
                    synthetic_aep = f"Bluetooth#Bluetooth{adapter_mac_formatted}-54:15:89:dc:a5:79"
                    logger.info(f"[AEP_DISCOVERED] Discovered dynamic LG AEP ID via adapter binding: {synthetic_aep[:25]}... (masked)")
                    return synthetic_aep
        except Exception:
            pass

        return None

    def connect_lg(self) -> Tuple[bool, str, Optional[int]]:
        """
        Requests Windows Device Portal to initiate Bluetooth A2DP connection with LG SNC4R.
        Returns (success: bool, status_message: str, http_status_code: Optional[int]).
        """
        if not self.is_available():
            logger.warning("[DEVICE_PORTAL_UNAVAILABLE] Device Portal not listening on localhost:50443")
            return False, "DEVICE_PORTAL_UNAVAILABLE", None

        username, password = self._load_credentials()
        if not username or not password:
            logger.warning("[DEVICE_PORTAL_AUTH_REQUIRED] No credentials found in secrets/device_portal.json")
            return False, "DEVICE_PORTAL_AUTH_REQUIRED", 401

        aep_id = self.discover_lg_aep()
        if not aep_id:
            logger.error("[BLUETOOTH_DEVICE_NOT_FOUND] Could not find paired AEP ID for LG SNC4R")
            return False, "BLUETOOTH_DEVICE_NOT_FOUND", None

        b64_aep = encode_aep_id(aep_id)
        url_encoded_b64 = urllib.parse.quote(b64_aep)
        url = f"https://127.0.0.1:{self.https_port}/api/bt/connectdevice?deviceId={url_encoded_b64}"

        opener, cj = self._create_authenticated_opener(username, password)
        try:
            # 1. Establish session & CSRF
            opener.open(f"https://127.0.0.1:{self.https_port}/certprompt.htm", timeout=2)
            try:
                opener.open(f"https://127.0.0.1:{self.https_port}/api/authorize/setSslState?sslState=http&remember=true", timeout=2)
            except Exception:
                pass

            csrf_token = ""
            for c in cj:
                if c.name == "CSRF-Token":
                    csrf_token = c.value

            headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

            # 2. Dispatch POST /api/bt/connectdevice?deviceId=Base64
            logger.info(f"[DEVICE_PORTAL_CONNECT_REQUEST] Dispatching POST to connect LG SNC4R...")
            req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
            res = opener.open(req, timeout=4)
            logger.info(f"[DEVICE_PORTAL_CONNECT_SUCCESS] Device Portal accepted connection request (HTTP {res.status})")
            return True, "REQUEST_ACCEPTED", res.status
        except urllib.error.HTTPError as he:
            logger.error(f"[DEVICE_PORTAL_HTTP_ERROR] Request failed with HTTP {he.code}")
            return False, f"DEVICE_PORTAL_HTTP_{he.code}", he.code
        except Exception as e:
            logger.error(f"[DEVICE_PORTAL_EXCEPTION] Error during connect request: {e}")
            return False, "DEVICE_PORTAL_REQUEST_FAILED", None

    def disconnect_lg(self) -> Tuple[bool, str, Optional[int]]:
        """
        Requests Windows Device Portal to disconnect the Bluetooth A2DP connection with LG SNC4R.
        Returns (success: bool, status_message: str, http_status_code: Optional[int]).
        """
        if not self.is_available():
            return False, "DEVICE_PORTAL_UNAVAILABLE", None

        username, password = self._load_credentials()
        if not username or not password:
            return False, "DEVICE_PORTAL_AUTH_REQUIRED", 401

        aep_id = self.discover_lg_aep()
        if not aep_id:
            return False, "BLUETOOTH_DEVICE_NOT_FOUND", None

        b64_aep = encode_aep_id(aep_id)
        url_encoded_b64 = urllib.parse.quote(b64_aep)
        url = f"https://127.0.0.1:{self.https_port}/api/bt/disconnectdevice?deviceId={url_encoded_b64}"

        opener, cj = self._create_authenticated_opener(username, password)
        try:
            opener.open(f"https://127.0.0.1:{self.https_port}/certprompt.htm", timeout=2)
            try:
                opener.open(f"https://127.0.0.1:{self.https_port}/api/authorize/setSslState?sslState=http&remember=true", timeout=2)
            except Exception:
                pass

            csrf_token = ""
            for c in cj:
                if c.name == "CSRF-Token":
                    csrf_token = c.value

            headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
            logger.info("[DEVICE_PORTAL_DISCONNECT_REQUEST] Dispatching POST to disconnect LG SNC4R...")
            req = urllib.request.Request(url, data=b"", headers=headers, method="POST")
            res = opener.open(req, timeout=4)
            logger.info(f"[DEVICE_PORTAL_DISCONNECT_SUCCESS] Device Portal accepted disconnect request (HTTP {res.status})")
            return True, "DISCONNECTED", res.status
        except urllib.error.HTTPError as he:
            logger.error(f"[DEVICE_PORTAL_DISCONNECT_ERROR] Request failed with HTTP {he.code}")
            return False, f"DEVICE_PORTAL_HTTP_{he.code}", he.code
        except Exception as e:
            logger.error(f"[DEVICE_PORTAL_DISCONNECT_EXCEPTION] Error during disconnect request: {e}")
            return False, "DEVICE_PORTAL_REQUEST_FAILED", None
