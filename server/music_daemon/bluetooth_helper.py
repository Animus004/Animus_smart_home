"""
Windows Bluetooth audio device reconnect helper for LG SNC4R soundbar.
Handles probing, reconnection polling, deterministic WASAPI discovery,
Windows Device Portal automated A2DP connection, and clean failure reporting
without silent fallback to monitor speakers.
"""

import logging
import os
import re
import subprocess
import time
from typing import Optional, Dict, Any, Tuple

from device_portal import WindowsDevicePortalBluetooth

logger = logging.getLogger("music_daemon.bluetooth_reconnect")

LG_KEYWORD = "LG SNC4R"
LG_MAC_INT = 0x541589DCA579
LG_MAC_STR = "54:15:89:DC:A5:79"


class BluetoothAudioHelper:
    """
    Manages Bluetooth audio connection lifecycle and deterministic WASAPI endpoint binding.
    """
    def __init__(
        self,
        preferred_keyword: str = LG_KEYWORD,
        mpv_binary: str = r"D:\AnimusSmartRoom\server\bin\mpv.com",
        reconnect_timeout_seconds: float = 12.0
    ):
        self.preferred_keyword = preferred_keyword
        self.mpv_binary = mpv_binary
        self.reconnect_timeout_seconds = reconnect_timeout_seconds
        self.device_portal = WindowsDevicePortalBluetooth()
        self.last_reconnect_method: Optional[str] = None
        self.last_reconnect_duration_ms: Optional[int] = None

    def scan_active_endpoints(self) -> Tuple[Optional[Dict[str, str]], list]:
        """
        Scans mpv for active WASAPI audio devices.
        Returns (lg_device_dict_or_None, all_devices_list).
        """
        devices = []
        pattern = re.compile(r"^'([^']+)'\s+\((.*)\)$")
        try:
            res = subprocess.run(
                [self.mpv_binary, "--audio-device=help"],
                capture_output=True,
                text=True,
                timeout=4
            )
            for raw_line in res.stdout.splitlines():
                line = raw_line.strip()
                match = pattern.match(line)
                if match:
                    dev_id = match.group(1).strip()
                    dev_name = match.group(2).strip()
                    devices.append({"id": dev_id, "name": dev_name})
        except Exception as e:
            logger.error(f"[BT_AUDIO_CHECK] Error querying audio endpoints: {e}")

        lg_device = None
        for dev in devices:
            if dev["id"] != "auto" and self.preferred_keyword.lower() in dev["name"].lower():
                lg_device = dev
                break

        return lg_device, devices

    def trigger_windows_bluetooth_wake(self) -> bool:
        """
        Executes non-blocking WinRT / PnP ping to signal Windows Bluetooth stack.
        """
        logger.info(f"[BT_AUDIO_RECONNECT_STARTED] Initiating WinRT connection probe for '{self.preferred_keyword}'")
        ps_cmd = (
            f"$op = [Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync([UInt64]{LG_MAC_INT});"
            "Start-Sleep -Milliseconds 100;"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                timeout=3
            )
            return True
        except Exception as e:
            logger.warning(f"[BT_AUDIO_RECONNECT_WARNING] Wake trigger error: {e}")
            return False

    def request_device_portal_connect(self) -> Tuple[bool, str]:
        """
        Requests Windows Device Portal to establish the Bluetooth A2DP connection.
        """
        logger.info("[BT_AUDIO_DEVICE_PORTAL] Requesting connection via Windows Device Portal...")
        success, msg, _ = self.device_portal.connect_lg()
        return success, msg

    def ensure_audio_endpoint(self) -> Tuple[bool, Optional[Dict[str, str]], str]:
        """
        Ensures the preferred audio device is available and ready for playback.
        Returns (success: bool, device_dict_or_None, status_code: str).
        Status codes: 'ALREADY_CONNECTED', 'RECONNECTED', 'AUDIO_OUTPUT_UNAVAILABLE'.
        """
        logger.info(f"[BT_AUDIO_CHECK] Checking availability of '{self.preferred_keyword}' endpoint")
        lg_dev, _ = self.scan_active_endpoints()

        if lg_dev:
            logger.info(f"[BT_AUDIO_ENDPOINT_AVAILABLE] Preferred device '{lg_dev['name']}' is ACTIVE ({lg_dev['id']})")
            self.last_reconnect_method = "none"
            self.last_reconnect_duration_ms = 0
            return True, lg_dev, "ALREADY_CONNECTED"

        # Endpoint is missing / sleeping. Attempt reconnection via Device Portal + WinRT.
        logger.warning(f"[BT_AUDIO_RECONNECT_WAITING] Endpoint '{self.preferred_keyword}' not found. Initiating reconnect...")
        start_time = time.time()
        
        # 1. First attempt Windows Device Portal automated connection
        dp_success, dp_msg = self.request_device_portal_connect()
        if dp_success:
            self.last_reconnect_method = "device_portal"
        else:
            logger.info(f"[BT_AUDIO_FALLBACK_PROBE] Device Portal returned {dp_msg}, trying WinRT probe...")
            self.trigger_windows_bluetooth_wake()
            self.last_reconnect_method = "winrt_probe"

        # 2. Poll for the WASAPI endpoint to emerge
        while time.time() - start_time < self.reconnect_timeout_seconds:
            time.sleep(0.5)
            lg_dev, _ = self.scan_active_endpoints()
            if lg_dev:
                duration_ms = int((time.time() - start_time) * 1000)
                self.last_reconnect_duration_ms = duration_ms
                logger.info(f"[BT_AUDIO_RECONNECTED] Endpoint '{lg_dev['name']}' RECONNECTED via {self.last_reconnect_method} in {duration_ms}ms ({lg_dev['id']})")
                return True, lg_dev, "RECONNECTED"

        logger.error(f"[BT_AUDIO_RECONNECT_TIMEOUT] Reconnect timed out ({self.reconnect_timeout_seconds}s). Endpoint unavailable.")
        logger.error(f"[BT_AUDIO_ENDPOINT_UNAVAILABLE] Refusing to fall back to monitor speakers. Returning AUDIO_OUTPUT_UNAVAILABLE.")
        self.last_reconnect_duration_ms = int((time.time() - start_time) * 1000)
        return False, None, "AUDIO_OUTPUT_UNAVAILABLE"
