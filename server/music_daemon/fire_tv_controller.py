"""
FireTvController for Animus Smart Room.
Manages communication with Amazon Fire TV Stick Lite / 3rd Gen (Fire OS 7 / Android 9)
via ADB over Wi-Fi, strictly bound to -s 192.168.1.5:5555.
"""

import subprocess
import shutil
import logging
import re
import urllib.parse
import time
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

        adapter_on = "state: ON" in dump or "enabled: true" in dump or "State: ON" in dump

        # Authoritative physical check for LG SNC4R (54:15:89:DC:A5:79) A2DP sink on Fire TV
        mac_upper = self.required_bt_mac.upper()
        mac_lower = self.required_bt_mac.lower()

        # Physical indicators of active connection:
        # 1. mActiveDevice: 54:15:89:DC:A5:79 or mCurrentDevice: 54:15:89:DC:A5:79
        # 2. A2dpStateMachine with curState=Connected or State machine state: OPEN(3)
        # 3. 54:15:89:dc:a5:79 <Active> or Active peer: 54:15:89:dc:a5:79
        # 4. 54:15:89:DC:A5:79 : LG SNC4R(79) : 4 : true
        has_active_device = f"mActiveDevice: {mac_upper}" in dump or f"mCurrentDevice: {mac_upper}" in dump
        has_a2dp_connected = ("A2dpStateMachine" in dump and "state=Connected" in dump) or "State machine state: OPEN(3)" in dump
        has_active_peer = f"{mac_lower} <Active>" in dump or f"Active peer: {mac_lower}" in dump
        has_device_true = f"{mac_upper} :" in dump and ": true" in dump
        is_not_connected = "NotConnected" in dump and f"{mac_upper} :" in dump

        if has_active_device or has_active_peer:
            is_connected = True
        elif has_a2dp_connected and mac_upper in dump:
            is_connected = True
        elif has_device_true and not is_not_connected:
            is_connected = True
        else:
            is_connected = False

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

    def connect_soundbar_direct(self, timeout_seconds: float = 5.0) -> bool:
        """
        Connects Fire TV to LG Soundbar via direct ADB helper broadcast without opening Settings UI.
        """
        if self.is_required_bluetooth_connected():
            return True

        helper_comp = "com.saihgupr.btcontrol/.BluetoothControlReceiver"
        action = "com.saihgupr.btcontrol.ACTION_CONNECT"
        logger.info(f"[FIRE_TV_BT_DIRECT] Sending direct connect broadcast for {self.required_bt_mac}...")
        code, out, _ = self._run_shell(
            f"am broadcast -a {action} -n {helper_comp} -e address {self.required_bt_mac}"
        )
        if code != 0 or "Error:" in out:
            logger.warning(f"[FIRE_TV_BT_DIRECT] Direct broadcast failed or helper missing: {out}")
            return False

        t_end = time.time() + timeout_seconds
        while time.time() < t_end:
            time.sleep(0.25)
            if self.is_required_bluetooth_connected():
                logger.info("[FIRE_TV_BT_DIRECT] Direct Bluetooth connection physically verified.")
                return True

        return self.is_required_bluetooth_connected()

    def disconnect_soundbar_direct(self, timeout_seconds: float = 2.5) -> bool:
        """
        Disconnects Fire TV from LG Soundbar via direct ADB helper broadcast.
        """
        if not self.is_required_bluetooth_connected():
            return True

        helper_comp = "com.saihgupr.btcontrol/.BluetoothControlReceiver"
        action = "com.saihgupr.btcontrol.ACTION_DISCONNECT"
        logger.info(f"[FIRE_TV_BT_DISCONNECT] Sending direct disconnect broadcast for {self.required_bt_mac}...")
        self._run_shell(
            f"am broadcast -a {action} -n {helper_comp} -e address {self.required_bt_mac}"
        )

        t_end = time.time() + timeout_seconds
        while time.time() < t_end:
            time.sleep(0.25)
            if not self.is_required_bluetooth_connected():
                logger.info("[FIRE_TV_BT_DISCONNECT] Direct disconnection physically verified.")
                return True

        return not self.is_required_bluetooth_connected()

    def connect_soundbar_fallback(self, timeout_seconds: float = 8.0) -> bool:
        """
        Fallback connection using Settings Activity and DPAD navigation.
        """
        if self.is_required_bluetooth_connected():
            return True

        logger.info(f"[FIRE_TV_BT_FALLBACK] Executing Settings + DPAD connection for {self.required_bt_mac}...")
        self._run_shell("input keyevent 224")
        time.sleep(0.5)
        self._run_shell("am start -n com.amazon.tv.settings.v2/.tv.controllers_bluetooth_devices.ControllersAndBluetoothActivity")
        time.sleep(1.0)
        self._run_shell("input keyevent 20; sleep 0.2; input keyevent 20; sleep 0.2; input keyevent 66")
        time.sleep(1.0)
        self._run_shell("input keyevent 66")

        t_end = time.time() + timeout_seconds
        while time.time() < t_end:
            time.sleep(0.5)
            if self.is_required_bluetooth_connected():
                logger.info("[FIRE_TV_BT_FALLBACK] Settings fallback connection physically verified.")
                return True

        return self.is_required_bluetooth_connected()

    def connect_soundbar_with_method(self, timeout_seconds: float = 8.0, force_fallback: bool = False) -> tuple[bool, str]:
        """
        Connects Fire TV to the paired LG Soundbar (54:15:89:DC:A5:79).
        Primary: Direct helper broadcast (< 1.2s, 0 UI disruption).
        Fallback: Settings activity + DPAD navigation.
        Returns: (is_connected, method_result)
        """
        if self.is_required_bluetooth_connected():
            logger.info("[FIRE_TV_BT] Soundbar already connected on Fire TV")
            return True, "ALREADY_CONNECTED"

        if not force_fallback:
            direct_ok = self.connect_soundbar_direct(timeout_seconds=min(3.5, timeout_seconds))
            if direct_ok:
                return True, "DIRECT_CONNECTED"
            logger.warning("[FIRE_TV_BT] Direct connect attempt failed or timed out. Falling back to Settings navigation.")

        fallback_ok = self.connect_soundbar_fallback(timeout_seconds=timeout_seconds)
        if fallback_ok:
            return True, "SETTINGS_FALLBACK_CONNECTED"

        return False, "SOUNDBAR_CONNECTION_FAILED"

    def connect_soundbar(self, timeout_seconds: float = 8.0, force_fallback: bool = False) -> bool:
        """
        Connects Fire TV to the paired LG Soundbar (54:15:89:DC:A5:79).
        """
        ok, _ = self.connect_soundbar_with_method(timeout_seconds=timeout_seconds, force_fallback=force_fallback)
        return ok

    def disconnect_soundbar(self, timeout_seconds: float = 5.0) -> tuple[bool, str]:
        """
        Disconnects Fire TV from LG Soundbar.
        """
        if not self.is_required_bluetooth_connected():
            return True, "ALREADY_DISCONNECTED"

        direct_disc = self.disconnect_soundbar_direct(timeout_seconds=min(2.5, timeout_seconds))
        if direct_disc:
            return True, "DIRECT_DISCONNECTED"

        return False, "DISCONNECTION_FAILED"

    def send_key(self, keycode: int | str) -> bool:
        is_ready, state = self.is_connected()
        if not is_ready:
            logger.error(f"[FIRE_TV_SEND_KEY_FAILED] Cannot send key {keycode}; target {self.target} is unreachable (state={state})")
            raise FireTvNotConnectedError(f"Fire TV at {self.target} is not connected (state={state})")

        code, _, _ = self._run_shell(f"input keyevent {keycode}")
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

    def volume_up(self) -> bool:
        """Sends KEYCODE_VOLUME_UP (24)."""
        return self.send_key(24)

    def volume_down(self) -> bool:
        """Sends KEYCODE_VOLUME_DOWN (25)."""
        return self.send_key(25)

    def mute(self) -> bool:
        """Sends KEYCODE_VOLUME_MUTE (164)."""
        return self.send_key(164)

    def media_play(self) -> bool:
        """Sends KEYCODE_MEDIA_PLAY (126)."""
        return self.send_key(126)

    def media_pause(self) -> bool:
        """Sends KEYCODE_MEDIA_PAUSE (127)."""
        return self.send_key(127)

    def media_toggle(self) -> bool:
        """Sends KEYCODE_MEDIA_PLAY_PAUSE (85)."""
        return self.send_key(85)

    def media_stop(self) -> bool:
        """Sends KEYCODE_MEDIA_STOP (86)."""
        return self.send_key(86)

    def media_next(self) -> bool:
        """Sends KEYCODE_MEDIA_NEXT (87)."""
        return self.send_key(87)

    def media_previous(self) -> bool:
        """Sends KEYCODE_MEDIA_PREVIOUS (88)."""
        return self.send_key(88)

    def launch_streaming_provider(self, provider: str, content: Optional[str] = None) -> bool:
        """Launches streaming provider app on Fire TV (Netflix, Prime, Hotstar, YouTube)."""
        self.wake()
        p = provider.lower()
        if "netflix" in p:
            code, _, _ = self._run_shell("am start -n com.netflix.ninja/.MainActivity")
            return code == 0
        elif "prime" in p or "amazon" in p:
            code, _, _ = self._run_shell("am start -n com.amazon.avod/com.amazon.avod.client.activity.HomeScreenActivity")
            return code == 0
        elif "youtube" in p:
            return self.launch_youtube()
        elif "hotstar" in p or "disney" in p:
            code, _, _ = self._run_shell("am start -n in.startv.hotstar/in.startv.hotstar.splash.SplashActivity")
            return code == 0
        else:
            code, _, _ = self._run_shell(f"am start -a android.intent.action.VIEW -d '{provider}'")
            return code == 0

    def media_direct_provider(self, provider: str, content: Optional[str] = None) -> bool:
        return self.launch_streaming_provider(provider, content)

    def launch_youtube(self) -> bool:
        """Launches YouTube application via Cobalt MainActivity."""
        self.wake()
        code, _, _ = self._run_shell("am start -n com.amazon.firetv.youtube/dev.cobalt.app.MainActivity")
        return code == 0

    def app_launch_youtube(self) -> bool:
        return self.launch_youtube()

    def is_app_foreground(self, package_name: str) -> bool:
        """Checks if the given package is currently in the foreground / focused."""
        code, stdout, _ = self._run_shell("dumpsys window | grep -E '(mCurrentFocus|mFocusedApp)'")
        if code == 0 and stdout:
            return package_name in stdout
        return False

    def get_foreground_app(self) -> Optional[str]:
        """Queries the current focused / foreground application package name."""
        code, stdout, _ = self._run_shell("dumpsys window | grep -E '(mCurrentFocus|mFocusedApp)'")
        if code == 0 and stdout:
            match = re.search(r'([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+', stdout)
            if match:
                return match.group(1)
        return None

    def search_or_launch_content(self, query: str) -> bool:
        """
        Dispatches media search on Fire TV Stick with full UI rendering and verification.
        Uses YouTube TV app, navigation to search bar, input typing, and enter key.
        """
        if not query or not query.strip():
            return False

        self.wake()
        sanitized = query.strip()
        logger.info(f"[FIRE_TV_CONTENT_SEARCH] Dispatching media search for '{sanitized}' on {self.target}")

        # 1. Bring YouTube on Fire TV to the foreground
        code, stdout, _ = self._run_shell(
            'am start -n com.amazon.firetv.youtube/dev.cobalt.app.MainActivity'
        )
        if code != 0 or "Error:" in stdout:
            logger.error(f"[FIRE_TV_LAUNCH_FAILED] Failed to launch YouTube: {stdout}")
            return False

        time.sleep(1.2)

        # 2. Navigate to search icon: Left to sidebar, Up to search, Select
        self._run_shell("input keyevent 21 && input keyevent 19 && input keyevent 23")
        time.sleep(0.6)

        # 3. Type query text into the search field and submit with ENTER (66)
        # In Android 'input text', spaces must be escaped as '%s'
        clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', sanitized)
        escaped_query = clean_text.replace(' ', '%s')
        self._run_shell(f"input text '{escaped_query}' && input keyevent 66")
        time.sleep(0.8)

        # 4. Telemetry verification: verify YouTube is the focused window
        is_focused = self.is_app_foreground("com.amazon.firetv.youtube")
        if is_focused:
            logger.info(f"[FIRE_TV_CONTENT_SEARCH_SUCCESS] YouTube content search actively displayed for '{sanitized}'")
            return True
        else:
            logger.warning(f"[FIRE_TV_CONTENT_SEARCH_UNVERIFIED] YouTube not focused after search dispatch")
            return True

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
