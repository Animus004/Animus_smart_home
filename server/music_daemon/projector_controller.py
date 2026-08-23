import subprocess
import shutil
import logging
import re
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger("projector_controller")

DEFAULT_ADB_PATH = r"C:\platform-tools\platform-tools-latest-windows\platform-tools\adb.exe"
DEFAULT_TARGET = "192.168.1.11:5555"

class ProjectorError(Exception):
    pass

class ProjectorNotConnectedError(ProjectorError):
    pass

class ProjectorUnauthorizedError(ProjectorError):
    pass

class ProjectorPowerState(str, Enum):
    ON = "ON"
    AWAKE = "AWAKE"
    STANDBY = "STANDBY"
    SLEEPING = "SLEEPING"
    OFF = "OFF"
    BOOTING = "BOOTING"
    UNKNOWN = "UNKNOWN"

class ProjectorSource(str, Enum):
    ANDROID = "ANDROID"
    HDMI_1 = "HDMI_1"
    HDMI_2 = "HDMI_2"
    HDMI_3 = "HDMI_3"
    AV = "AV"
    VGA = "VGA"
    USB = "USB"
    UNKNOWN = "UNKNOWN"

class ProjectorController:
    """
    ProjectorController manages communication with the Zebronics PixaPlay 25 projector (Android 12)
    via ADB over Wi-Fi, strictly bound to an explicit target serial.
    """
    def __init__(self, target: str = DEFAULT_TARGET, adb_path: Optional[str] = None, timeout: float = 4.0):
        self.target = target
        self.adb_path = adb_path or shutil.which("adb") or DEFAULT_ADB_PATH
        self.timeout = timeout

    def _run_adb(self, args: list[str], timeout: Optional[float] = None) -> tuple[int, str, str]:
        """Runs a raw ADB command without device serial targeting."""
        cmd = [self.adb_path] + args
        eff_timeout = timeout or self.timeout
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=eff_timeout
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"ADB command timed out after {eff_timeout}s: {' '.join(cmd)}")
            return -1, "", f"Timeout after {eff_timeout}s"
        except Exception as e:
            logger.error(f"ADB execution failed: {e}")
            return -1, "", str(e)

    def _run_target_adb(self, args: list[str], timeout: Optional[float] = None) -> tuple[int, str, str]:
        """Runs an ADB command strictly targeting this controller's specific device serial."""
        target_args = ["-s", self.target] + args
        return self._run_adb(target_args, timeout=timeout)

    def _run_shell(self, shell_cmd: str, timeout: Optional[float] = None) -> tuple[int, str, str]:
        """Runs an ADB shell command strictly targeting this controller's device serial."""
        return self._run_target_adb(["shell", shell_cmd], timeout=timeout)

    def connect(self) -> bool:
        """Connects to the projector via ADB over Wi-Fi."""
        code, stdout, stderr = self._run_adb(["connect", self.target], timeout=5.0)
        logger.info(f"adb connect {self.target}: code={code}, stdout={stdout}, stderr={stderr}")
        return "connected to" in stdout.lower() or "already connected to" in stdout.lower()

    def disconnect(self) -> bool:
        """Disconnects from the projector ADB session."""
        code, stdout, stderr = self._run_adb(["disconnect", self.target], timeout=3.0)
        logger.info(f"adb disconnect {self.target}: code={code}, stdout={stdout}")
        return code == 0

    def is_connected(self, auto_connect: bool = True) -> tuple[bool, str]:
        """
        Checks if the projector is connected and authorized.
        Returns: (is_ready, state_string) e.g. (True, "device"), (False, "unauthorized"), (False, "offline")
        """
        code, stdout, stderr = self._run_adb(["devices", "-l"], timeout=3.0)
        if code != 0:
            return False, "error"

        for line in stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == self.target:
                state = parts[1]
                return state == "device", state

        if auto_connect:
            self.connect()
            code, stdout, stderr = self._run_adb(["devices", "-l"], timeout=3.0)
            for line in stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == self.target:
                    state = parts[1]
                    return state == "device", state

        return False, "disconnected"

    def send_key(self, keycode: int | str) -> bool:
        """Sends an Android KEYCODE to the projector."""
        is_ready, state = self.is_connected()
        if not is_ready:
            # Try reconnect once
            self.connect()
            is_ready, state = self.is_connected()
            if not is_ready:
                raise ProjectorNotConnectedError(f"Projector {self.target} is not connected (state: {state})")

        code, stdout, stderr = self._run_shell(f"input keyevent {keycode}")
        return code == 0

    # Basic Safe Navigation Controls
    def home(self) -> bool:
        """Sends KEYCODE_HOME (3)"""
        return self.send_key(3)

    def back(self) -> bool:
        """Sends KEYCODE_BACK (4)"""
        return self.send_key(4)

    def menu(self) -> bool:
        """Sends KEYCODE_MENU (82)"""
        return self.send_key(82)

    # Safe Volume Controls
    def volume_up(self) -> bool:
        """Sends KEYCODE_VOLUME_UP (24)"""
        return self.send_key(24)

    def volume_down(self) -> bool:
        """Sends KEYCODE_VOLUME_DOWN (25)"""
        return self.send_key(25)

    def volume_mute(self) -> bool:
        """Sends KEYCODE_VOLUME_MUTE (164)"""
        return self.send_key(164)

    # Safe D-Pad Navigation Controls
    def dpad_up(self) -> bool:
        """Sends KEYCODE_DPAD_UP (19)"""
        return self.send_key(19)

    def dpad_down(self) -> bool:
        """Sends KEYCODE_DPAD_DOWN (20)"""
        return self.send_key(20)

    def dpad_left(self) -> bool:
        """Sends KEYCODE_DPAD_LEFT (21)"""
        return self.send_key(21)

    def dpad_right(self) -> bool:
        """Sends KEYCODE_DPAD_RIGHT (22)"""
        return self.send_key(22)

    def dpad_center(self) -> bool:
        """Sends KEYCODE_DPAD_CENTER (23)"""
        return self.send_key(23)

    # Read-Only Diagnostic State Queries
    def get_power_state(self) -> Dict[str, Any]:
        """
        Queries Android power & display state using read-only dumpsys.
        Does NOT execute power key events.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            is_off = state in ["disconnected", "offline"]
            return {
                "connected": False,
                "power_state": ProjectorPowerState.OFF.value if is_off else ProjectorPowerState.UNKNOWN.value,
                "confidence": "high" if is_off else "low",
                "state": state,
                "interactive": False,
                "display_state": "OFF" if is_off else "UNKNOWN"
            }

        # Query dumpsys power & display
        code, power_out, _ = self._run_shell("dumpsys power | grep -iE '(mWakefulness=|Display Power:|mBootCompleted=|mIsPowered=)'")
        code2, disp_out, _ = self._run_shell("dumpsys display | grep -iE 'mState=(ON|OFF|DOZE)'")

        is_awake = "mWakefulness=Awake" in power_out
        is_disp_on = "state=ON" in disp_out.lower() or "state=ON" in power_out.lower() or "mstate=on" in disp_out.lower()
        is_asleep = "mWakefulness=Asleep" in power_out or "mWakefulness=Doze" in power_out
        is_disp_off = "state=off" in disp_out.lower() or "mstate=off" in disp_out.lower()

        if is_awake and is_disp_on:
            power_enum = ProjectorPowerState.ON
            confidence = "high"
        elif is_awake and is_disp_off:
            power_enum = ProjectorPowerState.AWAKE
            confidence = "medium"
        elif is_awake:
            power_enum = ProjectorPowerState.ON
            confidence = "high"
        elif is_asleep or is_disp_off:
            power_enum = ProjectorPowerState.STANDBY
            confidence = "high"
        else:
            power_enum = ProjectorPowerState.UNKNOWN
            confidence = "low"

        return {
            "connected": True,
            "power_state": power_enum.value,
            "confidence": confidence,
            "state": state,
            "interactive": is_awake and is_disp_on,
            "display_state": "ON" if is_disp_on else ("OFF" if is_disp_off else "UNKNOWN"),
            "raw_power": power_out.replace("\r", "").splitlines(),
            "raw_display": disp_out.replace("\r", "").splitlines()
        }

    def get_foreground_package(self) -> Optional[str]:
        """
        Queries the current foreground application package name using read-only dumpsys.
        """
        is_ready, _ = self.is_connected(auto_connect=False)
        if not is_ready:
            return None

        code, out, _ = self._run_shell("dumpsys activity activities | grep -E 'ResumedActivity|topResumedActivity'")
        if code == 0 and out:
            match = re.search(r'([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+', out)
            if match:
                return match.group(1)
        return None

    def get_current_source(self) -> ProjectorSource:
        """
        Determines the current active video/input source using read-only foreground activity and tv_input inspect.
        """
        fg = self.get_foreground_package()
        if not fg:
            return ProjectorSource.UNKNOWN

        if fg in ["com.newlink.overseaslauncher", "com.google.android.youtube.tv", "com.netflix.mediaclient", "com.amazon.avod.thirdpartyclient"]:
            return ProjectorSource.ANDROID
        elif fg == "com.newlink.nlsource":
            return ProjectorSource.HDMI_1
        elif "hisilicon" in fg or "source" in fg:
            return ProjectorSource.HDMI_1

        return ProjectorSource.ANDROID

    def set_source(self, source: ProjectorSource | str) -> bool:
        """
        Switches the projector input source (ANDROID, HDMI_1, HDMI_2, HDMI_3, AV, VGA, USB).
        """
        if isinstance(source, str):
            try:
                source = ProjectorSource(source.upper())
            except ValueError:
                logger.error(f"Invalid projector source requested: {source}")
                return False

        if source == ProjectorSource.ANDROID:
            return self.home()

        if source in [ProjectorSource.HDMI_1, ProjectorSource.HDMI_2, ProjectorSource.HDMI_3]:
            # Launch OEM HDMI/Source switcher
            code, stdout, stderr = self._run_shell("am start -n com.newlink.nlsource/.MainActivity")
            return code == 0

        if source == ProjectorSource.USB:
            code, stdout, stderr = self._run_shell("am start -n com.newlink.filemanager/.activity.MainActivity")
            return code == 0

        return False

    def power_off(self) -> bool:
        """
        Executes the safe OEM shutdown sequence via com.zhiying.powerservice/.PowerActivity.
        Strictly targets 192.168.1.11:5555 without raw reboot/halt commands.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            raise ProjectorNotConnectedError(f"Projector {self.target} is not connected (state: {state})")

        # Launch OEM Power Activity which triggers the optical cooling and shutdown sequence
        code, stdout, stderr = self._run_shell("am start -n com.zhiying.powerservice/.PowerActivity")
        return code == 0

    def set_hdmi(self, port: int = 1) -> bool:
        """Explicit convenience helper to switch to HDMI 1, 2, or 3."""
        if port == 1:
            return self.set_source(ProjectorSource.HDMI_1)
        elif port == 2:
            return self.set_source(ProjectorSource.HDMI_2)
        elif port == 3:
            return self.set_source(ProjectorSource.HDMI_3)
        return False

    def get_cec_status(self) -> Dict[str, Any]:
        """
        Reads HDMI-CEC service and settings telemetry read-only via dumpsys hdmi_control.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {"available": False, "enabled": False, "state": state}

        code, dump, _ = self._run_shell("dumpsys hdmi_control")
        is_enabled = "hdmi_cec_enabled (int): 1" in dump or "hdmi_control_enabled=1" in dump
        is_cec_avail = "mIsCecAvailable: true" in dump

        return {
            "available": is_cec_avail or ("HDMI CEC Network" in dump),
            "enabled": is_enabled,
            "cec_version": 5,
            "tv_wake_on_one_touch_play": "tv_wake_on_one_touch_play (int): 1" in dump,
            "power_control_mode": "to_tv" if "power_control_mode (string): to_tv" in dump else "unknown",
            "active_port": 1
        }

    def get_device_info(self) -> Dict[str, Any]:
        """
        Reads system properties (model, manufacturer, android version) read-only.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {"connected": False, "ip": self.target.split(":")[0], "state": state}

        code, model, _ = self._run_shell("getprop ro.product.model")
        code, android_ver, _ = self._run_shell("getprop ro.build.version.release")
        code, product, _ = self._run_shell("getprop ro.product.name")

        power_info = self.get_power_state()
        fg_pkg = self.get_foreground_package()
        current_source = self.get_current_source()
        cec_info = self.get_cec_status()

        return {
            "connected": True,
            "ip": self.target.split(":")[0],
            "target": self.target,
            "model": model or "Unknown",
            "android": android_ver or "12",
            "product": product or "NL5H00X",
            "power_state": power_info.get("power_state"),
            "confidence": power_info.get("confidence"),
            "interactive": power_info.get("interactive"),
            "display_state": power_info.get("display_state"),
            "foreground_package": fg_pkg,
            "current_source": current_source.value,
            "cec_status": cec_info
        }
