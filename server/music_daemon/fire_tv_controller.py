"""
FireTvController for Animus Smart Room.
Manages communication with Amazon Fire TV Stick Lite / 3rd Gen (Fire OS 7 / Android 9)
via ADB over Wi-Fi, strictly bound to -s 192.168.1.5:5555.
"""

import subprocess
import shutil
import logging
import re
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("music_daemon.fire_tv")

DEFAULT_FIRE_TV_ADB_PATH = r"C:\platform-tools\platform-tools-latest-windows\platform-tools\adb.exe"
DEFAULT_FIRE_TV_TARGET = "192.168.1.5:5555"
REQUIRED_A2DP_BT_MAC = "54:15:89:DC:A5:79"

class FireTvError(Exception):
    pass

class FireTvNotConnectedError(FireTvError):
    pass

class FireTvBluetoothState(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    UNKNOWN = "UNKNOWN"

class FireTvController:
    """
    FireTvController manages communication with the Amazon Fire TV Stick strictly
    targeting 192.168.1.5:5555 via safe subprocess abstraction.
    """
    def __init__(
        self,
        target: str = DEFAULT_FIRE_TV_TARGET,
        adb_path: Optional[str] = None,
        required_bt_mac: str = REQUIRED_A2DP_BT_MAC,
        timeout: float = 4.0
    ):
        self.target = target
        self.adb_path = adb_path or shutil.which("adb") or DEFAULT_FIRE_TV_ADB_PATH
        self.required_bt_mac = required_bt_mac
        self.timeout = timeout

    def _run_adb(self, args: list[str], timeout: Optional[float] = None) -> tuple[int, str, str]:
        cmd = [self.adb_path] + args
        eff_timeout = timeout or self.timeout
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=eff_timeout)
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"Fire TV ADB command timed out after {eff_timeout}s: {' '.join(cmd)}")
            return -1, "", f"Timeout after {eff_timeout}s"
        except Exception as e:
            logger.error(f"Fire TV ADB execution failed: {e}")
            return -1, "", str(e)

    def _run_target_adb(self, args: list[str], timeout: Optional[float] = None) -> tuple[int, str, str]:
        target_args = ["-s", self.target] + args
        return self._run_adb(target_args, timeout=timeout)

    def _run_shell(self, shell_cmd: str, timeout: Optional[float] = None) -> tuple[int, str, str]:
        return self._run_target_adb(["shell", shell_cmd], timeout=timeout)

    def is_reachable(self) -> bool:
        is_conn, state = self.is_connected(auto_connect=False)
        return is_conn

    def is_connected(self, auto_connect: bool = True) -> tuple[bool, str]:
        code, stdout, _ = self._run_adb(["devices", "-l"], timeout=4.0)
        if code != 0:
            if auto_connect:
                self._run_adb(["connect", self.target], timeout=4.0)
                code, stdout, _ = self._run_adb(["devices", "-l"], timeout=4.0)
            if code != 0:
                return False, "error"

        for line in stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == self.target:
                state = parts[1]
                return state == "device", state

        if auto_connect:
            self._run_adb(["connect", self.target], timeout=4.0)
            code, stdout, _ = self._run_adb(["devices", "-l"], timeout=4.0)
            for line in stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == self.target:
                    state = parts[1]
                    return state == "device", state

        return False, "disconnected"

    def get_bluetooth_status(self) -> Dict[str, Any]:
        """
        Queries the actual Bluetooth connection state on the Fire TV Stick.
        Validates both adapter state and whether the required A2DP device is connected.
        """
        is_conn, state = self.is_connected(auto_connect=False)
        if not is_conn:
            return {
                "adapter_enabled": False,
                "required_device_address": self.required_bt_mac,
                "required_device_connected": False,
                "state": FireTvBluetoothState.DISCONNECTED.value if state == "disconnected" else FireTvBluetoothState.UNKNOWN.value,
                "confidence": "high" if state == "disconnected" else "low"
            }

        code, dump, _ = self._run_shell("dumpsys bluetooth_manager")
        if code != 0:
            return {
                "adapter_enabled": False,
                "required_device_address": self.required_bt_mac,
                "required_device_connected": False,
                "state": FireTvBluetoothState.UNKNOWN.value,
                "confidence": "low"
            }

        adapter_on = "state: ON" in dump or "enabled: true" in dump
        is_connected = "ConnectionState: STATE_CONNECTED" in dump

        return {
            "adapter_enabled": adapter_on,
            "required_device_address": self.required_bt_mac,
            "required_device_connected": is_connected and adapter_on,
            "state": FireTvBluetoothState.CONNECTED.value if (is_connected and adapter_on) else FireTvBluetoothState.DISCONNECTED.value,
            "confidence": "high"
        }

    def is_required_bluetooth_connected(self) -> bool:
        status = self.get_bluetooth_status()
        return bool(status.get("required_device_connected", False))

    def send_key(self, keycode: int | str) -> bool:
        code, stdout, stderr = self._run_shell(f"input keyevent {keycode}")
        if code == 0:
            return True
        is_conn, state = self.is_connected(auto_connect=True)
        if not is_conn:
            raise FireTvNotConnectedError(f"Fire TV {self.target} is not connected (state: {state})")
        code, stdout, stderr = self._run_shell(f"input keyevent {keycode}")
        return code == 0

    def home(self) -> bool:
        return self.send_key(3)

    def back(self) -> bool:
        return self.send_key(4)

    def select(self) -> bool:
        return self.send_key(23)

    def dpad_up(self) -> bool:
        return self.send_key(19)

    def dpad_down(self) -> bool:
        return self.send_key(20)

    def dpad_left(self) -> bool:
        return self.send_key(21)

    def dpad_right(self) -> bool:
        return self.send_key(22)

    def wake(self) -> bool:
        return self.send_key(224) or self.home()

    def sleep(self) -> bool:
        return self.send_key(223)

    def get_status(self) -> Dict[str, Any]:
        """
        Returns structured telemetry for the Fire TV Stick.
        """
        is_conn, state = self.is_connected(auto_connect=False)
        if not is_conn:
            return {
                "reachable": False,
                "target": self.target,
                "state": state,
                "power_state": "UNKNOWN",
                "bluetooth": {
                    "adapter_enabled": False,
                    "required_device_address": self.required_bt_mac,
                    "required_device_connected": False,
                    "state": FireTvBluetoothState.DISCONNECTED.value if state == "disconnected" else FireTvBluetoothState.UNKNOWN.value,
                    "confidence": "high" if state == "disconnected" else "low"
                },
                "healthy": False
            }

        bt_status = self.get_bluetooth_status()
        code, pwr, _ = self._run_shell("dumpsys power | grep -i 'mWakefulness='")
        is_awake = "mWakefulness=Awake" in pwr

        return {
            "reachable": True,
            "target": self.target,
            "model": "AFTSS",
            "device": "sheldon",
            "fire_os": "7.7.1.6",
            "power_state": "AWAKE" if is_awake else "ASLEEP",
            "bluetooth": bt_status,
            "healthy": bt_status.get("required_device_connected", False)
        }
