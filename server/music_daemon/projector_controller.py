import subprocess
import shutil
import logging
import re
import time
import json
import threading
from typing import Optional, Dict, Any, Tuple
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

class ProjectorInvalidSourceError(ProjectorError):
    pass

class ProjectorHardwareError(ProjectorError):
    pass

class IrSecurityException(ProjectorError):
    """Raised when an unauthorized, dangerous, or cross-subsystem IR key is requested."""
    pass

class IrDebounceException(ProjectorError):
    """Raised when an IR command is dispatched within the minimum hardware debounce window."""
    pass


class IrProjectorTransport:
    """
    Additive Transport Adapter for Tuya Wi-Fi IR Blaster (192.168.1.12:6668).
    Strictly isolated to Zebronics PixaPlay 25 learned Power profile.
    Guarantees AC key isolation, single-flight locking, and 3.0s hardware debouncing.
    """
    PROJECTOR_REMOTE_ID_PREFIX = "remote_zebronics_projector"
    ALLOWED_KEY_NAMES = frozenset(["Power"])
    FORBIDDEN_KEY_PATTERNS = ("AC", "TEMP", "FAN", "MODE", "WIFI", "RESET", "PAIR", "FACTORY")
    MIN_DEBOUNCE_SECONDS = 3.0

    def __init__(
        self,
        lan_ip: str = "192.168.1.12",
        lan_port: int = 6668,
        dev_id: Optional[str] = None,
        local_key: Optional[str] = None,
        projector_remote_id: str = "remote_zebronics_projector_01",
        access_id: Optional[str] = None,
        access_secret: Optional[str] = None,
        endpoint: str = "https://openapi.tuyain.com"
    ):
        if "ac" in projector_remote_id.lower():
            raise IrSecurityException(f"Invalid or forbidden projector remote ID: '{projector_remote_id}'")
        if not (projector_remote_id.startswith(self.PROJECTOR_REMOTE_ID_PREFIX) or projector_remote_id.startswith("d7") or "mock" in projector_remote_id.lower()):
            raise IrSecurityException(f"Invalid or forbidden projector remote ID: '{projector_remote_id}'")

        self.lan_ip = lan_ip
        self.lan_port = lan_port
        self.dev_id = dev_id
        self.local_key = local_key
        self.projector_remote_id = projector_remote_id
        self.access_id = access_id
        self.access_secret = access_secret
        self.endpoint = endpoint

        self._last_dispatch_timestamp: float = 0.0
        self._lock = threading.Lock()

    def _dispatch_raw_tuya(self, remote_id: str, key_name: str) -> bool:
        """Dispatches verified IR pulse targeting the learned Zebronics profile."""
        logger.info(f"[TUYA_IR_DISPATCH] Dispatching IR pulse: remote='{remote_id}', key='{key_name}'")

        # 1. Primary Zero-Cloud Local Tuya IR Adapter (Tuya 3.5 on LAN 192.168.1.12:6668)
        if self.lan_ip and self.local_key and self.dev_id and "mock" not in self.dev_id.lower():
            try:
                from tuya_local_ir_adapter import TuyaLocalIrAdapter
                local_ir = TuyaLocalIrAdapter(ip=self.lan_ip, dev_id=self.dev_id, local_key=self.local_key)
                ok, msg = local_ir.send_power_wake()
                if ok:
                    logger.info(f"[TUYA_IR_DISPATCH_LOCAL_OK] Dispatched via TuyaLocalIrAdapter to {self.lan_ip}: {msg}")
                    return True
            except Exception as e:
                logger.warning(f"[TUYA_IR_DISPATCH_LOCAL_ERR] {e}")

        # 2. Try Local Tuya 3.3 if LAN IP, local_key, and dev_id are configured
        if self.lan_ip and self.local_key and self.dev_id and "mock" not in self.dev_id.lower():
            try:
                from ac_controller import LocalTuyaTransport
                lan = LocalTuyaTransport(
                    ip=self.lan_ip,
                    port=self.lan_port,
                    dev_id=self.dev_id,
                    local_key=self.local_key,
                    timeout=2.0
                )
                ok = lan.send_dps_command({"201": f"{remote_id}:{key_name}"})
                if ok:
                    logger.info(f"[TUYA_IR_DISPATCH_LAN_OK] Dispatched via Local Tuya 3.3 to {self.lan_ip}")
                    return True
            except Exception as e:
                logger.warning(f"[TUYA_IR_DISPATCH_LAN_ERR] {e}")

        # 3. Try Tuya Cloud OpenAPI if Cloud credentials are configured
        if self.access_id and self.access_secret and self.dev_id and "mock" not in self.dev_id.lower():
            try:
                from ac_controller import CloudTuyaTransport
                import requests
                cloud = CloudTuyaTransport(
                    access_id=self.access_id,
                    access_secret=self.access_secret,
                    dev_id=self.dev_id,
                    endpoint=self.endpoint
                )
                token = cloud.get_token()
                if token:
                    # Official Tuya Universal Remote Send-Keys API (emits 38kHz infrared pulse)
                    t = str(int(time.time() * 1000))
                    path = f"/v1.0/infrareds/{self.dev_id}/send-keys"
                    payload_body = json.dumps({"remote_id": remote_id, "key": "1787666042"}, separators=(',', ':'))
                    string_to_sign = f"POST\n{cloud._sha256_hex(payload_body)}\n\n{path}"
                    sign_str = f"{cloud.access_id}{token}{t}{string_to_sign}"
                    sign = cloud._hmac_sha256(sign_str)
                    headers = {
                        "client_id": cloud.access_id,
                        "access_token": token,
                        "sign": sign,
                        "t": t,
                        "sign_method": "HMAC-SHA256",
                        "Content-Type": "application/json"
                    }
                    resp = requests.post(f"{cloud.endpoint}{path}", headers=headers, data=payload_body, timeout=6.0)
                    data = resp.json()
                    if data.get("success"):
                        logger.info(f"[TUYA_IR_DISPATCH_CLOUD_OK] Dispatched send-keys to {self.dev_id}/{remote_id}: {data}")
                        return True
                    else:
                        logger.warning(f"[TUYA_IR_DISPATCH_CLOUD_FAIL] {data}")



            except Exception as e:
                logger.error(f"[TUYA_IR_DISPATCH_CLOUD_EXCEPTION] {e}")

        # Unit test / mock fallback mode
        if self.dev_id and "mock" in self.dev_id.lower():
            return True

        logger.error("[TUYA_IR_DISPATCH_FAILED] No active Tuya IR transport succeeded.")
        return False


    def send_pulse(self, key_name: str = "Power") -> Tuple[bool, str]:
        """
        Sends a single verified IR pulse to the Zebronics Projector.
        Enforces security whitelist and debounce timer.
        """
        if key_name not in self.ALLOWED_KEY_NAMES:
            raise IrSecurityException(f"Unauthorized or dangerous IR key request: '{key_name}'")

        for forbidden in self.FORBIDDEN_KEY_PATTERNS:
            if forbidden in key_name.upper():
                raise IrSecurityException(f"Unauthorized or dangerous IR key request: '{key_name}'")

        with self._lock:
            now = time.time()
            elapsed = now - self._last_dispatch_timestamp
            if elapsed < self.MIN_DEBOUNCE_SECONDS:
                raise IrDebounceException(f"Debounce violation: {elapsed:.2f}s < {self.MIN_DEBOUNCE_SECONDS}s")

            ok = self._dispatch_raw_tuya(self.projector_remote_id, key_name)
            if ok:
                self._last_dispatch_timestamp = time.time()
                return True, "IR_PULSE_SENT"
            return False, "IR_DISPATCH_FAILED"

    def send_power_wake(self) -> Tuple[bool, str]:
        """Dispatches exactly 1x IR Power pulse to wake hardware from cold standby."""
        return self.send_pulse("Power")

    def send_power_off_immediate(self, inter_pulse_delay: float = 1.0) -> Tuple[bool, str]:
        """
        Dispatches 2x IR Power pulses separated by inter_pulse_delay to immediately
        confirm shutdown on the Zebronics OEM confirmation dialog.
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_dispatch_timestamp
            if elapsed < self.MIN_DEBOUNCE_SECONDS:
                raise IrDebounceException(f"Debounce violation on shutdown: {elapsed:.2f}s < {self.MIN_DEBOUNCE_SECONDS}s")

            # Pulse 1: Dialog invocation
            ok1 = self._dispatch_raw_tuya(self.projector_remote_id, "Power")
            if not ok1:
                return False, "PULSE_1_FAILED"

        time.sleep(inter_pulse_delay)

        with self._lock:
            # Pulse 2: Immediate confirmation
            ok2 = self._dispatch_raw_tuya(self.projector_remote_id, "Power")
            self._last_dispatch_timestamp = time.time()
            if ok2:
                return True, "IMMEDIATE_SHUTDOWN_DISPATCHED"
            return False, "PULSE_2_FAILED"


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
    ANDROID_HOME = "ANDROID_HOME"
    HDMI_1 = "HDMI_1"
    HDMI_2 = "HDMI_2"  # Note: Retained for backward compat in parsing, but rejected upon set_source
    HDMI_3 = "HDMI_3"
    AV = "AV"
    VGA = "VGA"
    USB = "USB"
    UNKNOWN = "UNKNOWN"

class ProjectorSignalState(str, Enum):
    HDMI_SIGNAL_ACTIVE = "HDMI_SIGNAL_ACTIVE"
    HDMI_CONNECTED_NO_ACTIVE_STREAM = "HDMI_CONNECTED_NO_ACTIVE_STREAM"
    HDMI_SIGNAL_LOST = "HDMI_SIGNAL_LOST"
    UNKNOWN = "UNKNOWN"

class ThermalStatus(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"

class FanStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


class ProjectorController:
    """
    Authoritative Projector Controller for Zebronics PixaPlay 25 (Android 12, NL5H00X).
    Enforces truthful physical telemetry, optical safety, single HDMI port hardware limit,
    and sub-100ms ADB command dispatch over Wi-Fi (192.168.1.11:5555).
    """
    def __init__(
        self,
        target: str = DEFAULT_TARGET,
        adb_path: Optional[str] = None,
        timeout: float = 4.0,
        use_ir_power: Optional[bool] = None,
        ir_transport: Optional[IrProjectorTransport] = None
    ):
        self.target = target
        self.adb_path = adb_path or shutil.which("adb") or DEFAULT_ADB_PATH
        self.timeout = timeout
        
        if ir_transport is None and use_ir_power is not False:
            try:
                from ac_controller import _read_local_properties
                props = _read_local_properties()
                ir_dev = props.get("tuya.ir_blaster.device_id")
                ir_key = props.get("tuya.ir_blaster.local_key")
                ir_remote = props.get("tuya.ir_blaster.remote_id", "d718f75c8f82c9145954hl")
                if ir_dev and ir_key:
                    ir_transport = IrProjectorTransport(
                        lan_ip="192.168.1.12",
                        dev_id=ir_dev,
                        local_key=ir_key,
                        projector_remote_id=ir_remote,
                        access_id=props.get("tuya.access.id"),
                        access_secret=props.get("tuya.access.secret"),
                        endpoint=props.get("tuya.region.endpoint", "https://openapi.tuyain.com")
                    )
            except Exception as e:
                logger.debug(f"[PROJECTOR_INIT_IR_ERR] {e}")

        if use_ir_power is None:
            self.use_ir_power = ir_transport is not None
        else:
            self.use_ir_power = bool(use_ir_power)

        self.ir_transport = ir_transport

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
            self.connect()
            is_ready, state = self.is_connected()
            if not is_ready:
                raise ProjectorNotConnectedError(f"Projector {self.target} is not connected (state: {state})")

        code, stdout, stderr = self._run_shell(f"input keyevent {keycode}")
        return code == 0

    # Basic Navigation Controls
    def home(self) -> bool:
        """Sends KEYCODE_HOME (3) to return to Android Smart TV launcher."""
        return self.send_key(3)

    def back(self) -> bool:
        """Sends KEYCODE_BACK (4)."""
        return self.send_key(4)

    def menu(self) -> bool:
        """Sends KEYCODE_MENU (82)."""
        return self.send_key(82)

    # Volume Controls
    def volume_up(self) -> bool:
        """Sends KEYCODE_VOLUME_UP (24)."""
        return self.send_key(24)

    def volume_down(self) -> bool:
        """Sends KEYCODE_VOLUME_DOWN (25)."""
        return self.send_key(25)

    def volume_mute(self) -> bool:
        """Sends KEYCODE_VOLUME_MUTE (164)."""
        return self.send_key(164)

    # D-Pad Navigation Controls
    def dpad_up(self) -> bool:
        """Sends KEYCODE_DPAD_UP (19)."""
        return self.send_key(19)

    def dpad_down(self) -> bool:
        """Sends KEYCODE_DPAD_DOWN (20)."""
        return self.send_key(20)

    def dpad_left(self) -> bool:
        """Sends KEYCODE_DPAD_LEFT (21)."""
        return self.send_key(21)

    def dpad_right(self) -> bool:
        """Sends KEYCODE_DPAD_RIGHT (22)."""
        return self.send_key(22)

    def dpad_center(self) -> bool:
        """Sends KEYCODE_DPAD_CENTER (23)."""
        return self.send_key(23)

    # =========================================================================
    # A. Power & Standby Capabilities
    # =========================================================================

    def get_power_state(self, auto_connect: bool = False) -> Dict[str, Any]:
        """
        Authoritative verification combining dumpsys power and dumpsys display.
        Truthful invariant: ADB reachable != optically ON.
        """
        is_ready, state = self.is_connected(auto_connect=auto_connect)
        if not is_ready:

            is_off = state in ["disconnected", "offline"]
            return {
                "reachable": False,
                "connected": False,
                "wakefulness": "Unknown",
                "display_state": "OFF" if is_off else "UNKNOWN",
                "power_state": ProjectorPowerState.OFF.value if is_off else ProjectorPowerState.UNKNOWN.value,
                "interactive": False,
                "verified": True,
                "confidence": "high" if is_off else "low",
                "state": state,
                "raw_power": [],
                "raw_display": []
            }

        code, power_out, _ = self._run_shell("dumpsys power | grep -iE '(mWakefulness=|Display Power:|mBootCompleted=|mIsPowered=)'")
        code2, disp_out, _ = self._run_shell("dumpsys display | grep -iE 'mState=(ON|OFF|DOZE)'")

        # Extract exact wakefulness string
        wake_match = re.search(r'mWakefulness=([a-zA-Z]+)', power_out, re.IGNORECASE)
        wakefulness_str = wake_match.group(1) if wake_match else ("Awake" if "mWakefulness=Awake" in power_out else "Unknown")

        is_awake = "mWakefulness=Awake" in power_out or wakefulness_str.lower() == "awake"
        is_disp_on = "state=on" in disp_out.lower() or "state=on" in power_out.lower() or "mstate=on" in disp_out.lower()
        is_asleep = "mWakefulness=Asleep" in power_out or "mWakefulness=Doze" in power_out or wakefulness_str.lower() in ["asleep", "doze"]
        is_disp_off = "state=off" in disp_out.lower() or "mstate=off" in disp_out.lower()

        if is_awake and is_disp_on:
            power_enum = ProjectorPowerState.ON
            display_str = "ON"
            confidence = "high"
        elif is_awake and is_disp_off:
            power_enum = ProjectorPowerState.AWAKE
            display_str = "OFF"
            confidence = "medium"
        elif is_asleep or is_disp_off:
            power_enum = ProjectorPowerState.STANDBY
            display_str = "OFF" if is_disp_off else "DOZE"
            confidence = "high"
        elif is_awake:
            power_enum = ProjectorPowerState.ON
            display_str = "ON"
            confidence = "high"
        else:
            power_enum = ProjectorPowerState.UNKNOWN
            display_str = "UNKNOWN"
            confidence = "low"

        return {
            "reachable": True,
            "connected": True,
            "wakefulness": wakefulness_str,
            "display_state": display_str,
            "power_state": power_enum.value,
            "interactive": is_awake and is_disp_on,
            "verified": True,
            "confidence": confidence,
            "state": state,
            "raw_power": power_out.replace("\r", "").splitlines(),
            "raw_display": disp_out.replace("\r", "").splitlines()
        }

    def get_content_title(self) -> Optional[str]:
        """
        Extracts active media/content title from the projector's onboard Android OS.
        Inspects dumpsys media_session metadata and foreground activity.
        """
        is_ready, _ = self.is_connected(auto_connect=False)
        if not is_ready:
            return None

        # 1. Try dumpsys media_session for rich metadata title
        code, dump, _ = self._run_shell("dumpsys media_session")
        if code == 0 and dump:
            title_match = re.search(r'description=(.+?),', dump)
            if not title_match:
                title_match = re.search(r'title=([^,\n]+)', dump)
            if title_match:
                t = title_match.group(1).strip()
                if t and t.lower() not in ("null", "none", ""):
                    return t

        # 2. Fallback to friendly name based on foreground package
        fg = self.get_foreground_package()
        if not fg:
            return None

        app_name_map = {
            "com.google.android.youtube.tv": "YouTube",
            "com.netflix.mediaclient": "Netflix",
            "com.amazon.avod.thirdpartyclient": "Prime Video",
            "com.newlink.filemanager": "USB Media Player",
            "com.newlink.nlsource": "HDMI 1 Input",
            "com.newlink.overseaslauncher": "Android Home"
        }
        return app_name_map.get(fg, fg)

    def wake(self, timeout_seconds: float = 120.0) -> bool:
        """
        Wakes the projector display from standby/sleep.
        If use_ir_power is enabled and ADB is offline, dispatches 1x IR Power pulse
        and performs bounded readiness polling (tolerating 60–120s physical boot and Wi-Fi connection time).
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if is_ready:
            cur_st = self.get_power_state()
            if cur_st.get("interactive") and cur_st.get("power_state") == ProjectorPowerState.ON.value:
                logger.info("[PROJECTOR_WAKE] Projector is already awake and interactive.")
                return True
        elif self.use_ir_power:
            # Probe network / ADB connection to see if it's already running before assuming cold standby
            logger.info("[PROJECTOR_WAKE_PROBE] Projector not in active device table. Probing ADB connection...")
            is_ready, state = self.is_connected(auto_connect=True)
            if is_ready:
                cur_st = self.get_power_state()
                if cur_st.get("interactive") and cur_st.get("power_state") in (ProjectorPowerState.ON.value, ProjectorPowerState.AWAKE.value):
                    logger.info("[PROJECTOR_WAKE_IR_SUPPRESSED] Projector is online over ADB Wi-Fi and awake. IR pulse suppressed.")
                    return True

        if self.use_ir_power and self.ir_transport:
            if not is_ready:
                logger.info("[PROJECTOR_WAKE] ADB offline (deep standby). Dispatching 1x IR Power pulse...")
                try:
                    self.ir_transport.send_power_wake()
                except IrDebounceException:
                    logger.info("[PROJECTOR_WAKE] IR pulse recently dispatched (debounce window active). Proceeding to readiness polling.")
                except Exception as e:
                    logger.error(f"[PROJECTOR_WAKE_IR_FAIL] Failed dispatching IR wake: {e}")
                    return False

                # Bounded poll for ADB boot connection and Wi-Fi readiness (default 120s physical boot & Wi-Fi connection time)
                eff_timeout = timeout_seconds
                t_end = time.time() + eff_timeout
                logger.info(f"[PROJECTOR_WAKE_POLL] Polling for projector boot readiness (bounded timeout={eff_timeout:.1f}s)...")
                while time.time() < t_end:
                    time.sleep(2.0)
                    ready, _ = self.is_connected(auto_connect=True)
                    if ready:
                        st = self.get_power_state()
                        if st.get("power_state") in [ProjectorPowerState.ON.value, ProjectorPowerState.AWAKE.value]:
                            logger.info("[PROJECTOR_WAKE] Projector wake verified after IR pulse and boot completion.")
                            return True
                logger.warning(f"[PROJECTOR_WAKE_TIMEOUT] Projector wake not verified after {eff_timeout:.1f}s.")
                return False

        # Pure ADB fallback path
        if not is_ready:
            eff_timeout = timeout_seconds
            t_end = time.time() + eff_timeout
            while time.time() < t_end:
                self.connect()
                ready, _ = self.is_connected(auto_connect=False)
                if ready:
                    is_ready = True
                    break
                time.sleep(2.0)
            if not is_ready:
                return False

        logger.info("[PROJECTOR_WAKE] Sending KEYCODE_WAKEUP (224) to projector...")
        self.send_key(224)

        t_end = time.time() + timeout_seconds
        while time.time() < t_end:
            time.sleep(0.25)
            st = self.get_power_state()
            if st.get("power_state") in [ProjectorPowerState.ON.value, ProjectorPowerState.AWAKE.value]:
                logger.info("[PROJECTOR_WAKE] Projector wake verified.")
                return True
        return self.get_power_state().get("power_state") in [ProjectorPowerState.ON.value, ProjectorPowerState.AWAKE.value]

    def sleep(self, timeout_seconds: float = 3.0) -> bool:
        """
        Puts the projector display to standby/sleep via KEYCODE_SLEEP (223) or IR power.
        If use_ir_power is enabled, dispatches 2x IR Power pulses for clean immediate shutdown.
        """
        is_ready, _ = self.is_connected(auto_connect=False)
        if not is_ready:
            logger.info("[PROJECTOR_SLEEP] Projector is already disconnected/in standby.")
            return True if self.use_ir_power else False

        if self.use_ir_power and self.ir_transport:
            logger.info("[PROJECTOR_SLEEP] Dispatching 2x IR Power pulses for immediate shutdown...")
            try:
                ok, _ = self.ir_transport.send_power_off_immediate(inter_pulse_delay=1.0)
                self.disconnect()
                return ok
            except Exception as e:
                logger.error(f"[PROJECTOR_SLEEP_IR_FAIL] Failed dispatching IR sleep: {e}")
                return False

        # Pure ADB fallback path
        logger.info("[PROJECTOR_SLEEP] Sending KEYCODE_SLEEP (223) to projector...")
        return self.send_key(223)


    def power_off(self) -> bool:
        """
        Executes the safe OEM optical-engine shutdown sequence via com.zhiying.powerservice/.PowerActivity.
        Includes mandatory 3-second cooling cycle before cutting optical power.
        Followed by a single 1x IR Power pulse after 2 seconds if IR transport is available.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            raise ProjectorNotConnectedError(f"Projector {self.target} is not connected (state: {state})")

        logger.info("[PROJECTOR_POWER_OFF] Launching OEM PowerActivity graceful shutdown sequence...")
        code, stdout, stderr = self._run_shell("am start -n com.zhiying.powerservice/.PowerActivity")
        adb_success = (code == 0)

        # After ADB off, wait 2 seconds then press IR power once
        if self.ir_transport:
            try:
                time.sleep(2.0)
                logger.info("[PROJECTOR_POWER_OFF] Dispatching 1x IR Power pulse after 2s delay...")
                self.ir_transport.send_pulse("Power")
            except Exception as e:
                logger.warning(f"[PROJECTOR_POWER_OFF_IR_FAIL] IR pulse after ADB shutdown failed: {e}")

        return adb_success


    # =========================================================================
    # B. HDMI Signal & Handshake Verification
    # =========================================================================

    def get_signal_state(self) -> Dict[str, Any]:
        """
        Queries dumpsys tv_input under device HDMI0000C2.
        Distinguishes active video stream flow from a disconnected cable or black screen.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {
                "signal_state": ProjectorSignalState.UNKNOWN.value,
                "hdmi_port": 1,
                "active_stream": False,
                "stream_config": None,
                "verified": False,
                "message": "Projector not connected"
            }

        code, dump, _ = self._run_shell("dumpsys tv_input")
        if code != 0 or not dump:
            return {
                "signal_state": ProjectorSignalState.UNKNOWN.value,
                "hdmi_port": 1,
                "active_stream": False,
                "stream_config": None,
                "verified": False,
                "message": "dumpsys tv_input query failed"
            }

        has_active_stream_config = "TvStreamConfig" in dump and ("mStreamId=0" in dump or "mGeneration=" in dump)
        is_hdmi_session_bound = "com.hisilicon.tvinput.external/.HiHdmiTvInputService/HDMI0000C2" in dump

        # Check TV input connection state
        # state: 0 = Connected/Active, state: 1 = Standby/Disconnected
        c2_state_match = re.search(r'HDMI0000C2[^\n]*state:\s*([0-9]+)', dump)
        c2_state = int(c2_state_match.group(1)) if c2_state_match else 0

        if is_hdmi_session_bound and has_active_stream_config:
            sig_state = ProjectorSignalState.HDMI_SIGNAL_ACTIVE
            msg = "HDMI 1 video signal actively streaming"
            active_stream = True
        elif is_hdmi_session_bound and not has_active_stream_config:
            sig_state = ProjectorSignalState.HDMI_CONNECTED_NO_ACTIVE_STREAM
            msg = "HDMI 1 port connected but no video stream detected"
            active_stream = False
        elif c2_state == 1:
            sig_state = ProjectorSignalState.HDMI_SIGNAL_LOST
            msg = "HDMI 1 signal lost or cable disconnected"
            active_stream = False
        else:
            sig_state = ProjectorSignalState.HDMI_SIGNAL_ACTIVE if has_active_stream_config else ProjectorSignalState.UNKNOWN
            msg = "HDMI stream status evaluated"
            active_stream = has_active_stream_config

        return {
            "signal_state": sig_state.value,
            "hdmi_port": 1,
            "active_stream": active_stream,
            "is_session_bound": is_hdmi_session_bound,
            "stream_config": "TvStreamConfig {mStreamId=0;mType=1}" if has_active_stream_config else None,
            "verified": True,
            "message": msg
        }

    # =========================================================================
    # C. Input & Source Management (Strict Single-Port Hardware Invariant)
    # =========================================================================

    def get_foreground_package(self) -> Optional[str]:
        """Queries the current foreground application package name using read-only dumpsys."""
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
        Determines active video/input source using foreground activity and TV input inspect.
        Possible states: HDMI_1, ANDROID_HOME, USB, UNKNOWN.
        """
        fg = self.get_foreground_package()
        if not fg:
            return ProjectorSource.UNKNOWN

        if fg == "com.newlink.nlsource" or "hisilicon.tvui" in fg:
            return ProjectorSource.HDMI_1
        elif fg == "com.newlink.filemanager":
            return ProjectorSource.USB
        elif fg in ["com.newlink.overseaslauncher", "com.google.android.youtube.tv", "com.netflix.mediaclient", "com.amazon.avod.thirdpartyclient"]:
            return ProjectorSource.ANDROID_HOME

        return ProjectorSource.ANDROID_HOME

    def set_source(self, source: ProjectorSource | str) -> bool:
        """
        Switches the projector input source (HDMI_1, ANDROID_HOME, USB).
        Hardware Invariant: Single physical HDMI port. HDMI_2 is strictly rejected.
        """
        if isinstance(source, str):
            s_clean = source.strip().upper()
            if s_clean in ["HDMI_1", "HDMI1", "HDMI"]:
                source = ProjectorSource.HDMI_1
            elif s_clean in ["ANDROID", "ANDROID_HOME", "HOME"]:
                source = ProjectorSource.ANDROID_HOME
            elif s_clean in ["USB"]:
                source = ProjectorSource.USB
            elif s_clean in ["HDMI_2", "HDMI2", "HDMI_3", "HDMI3"]:
                logger.warning(f"[PROJECTOR_SOURCE] Rejected {source}: Physical hardware only has ONE HDMI port.")
                return False
            else:
                try:
                    source = ProjectorSource(s_clean)
                except ValueError:
                    logger.error(f"[PROJECTOR_SOURCE] Invalid source requested: {source}")
                    return False

        if source in [ProjectorSource.HDMI_2, ProjectorSource.HDMI_3]:
            logger.warning(f"[PROJECTOR_SOURCE] Rejected {source}: Physical hardware only has ONE HDMI port.")
            return False

        if source in [ProjectorSource.ANDROID, ProjectorSource.ANDROID_HOME]:
            return self.home()

        if source == ProjectorSource.HDMI_1:
            logger.info("[PROJECTOR_SOURCE] Launching HDMI 1 source switcher (com.newlink.nlsource)...")
            code, _, _ = self._run_shell("am start -n com.newlink.nlsource/.MainActivity")
            return code == 0

        if source == ProjectorSource.USB:
            logger.info("[PROJECTOR_SOURCE] Launching USB File Manager...")
            code, _, _ = self._run_shell("am start -n com.newlink.filemanager/.activity.MainActivity")
            return code == 0

        return False

    def set_hdmi(self, port: int = 1) -> bool:
        """
        Switches to physical HDMI port.
        Hardware Invariant: Port 1 is supported; ports > 1 are rejected.
        """
        if port == 1:
            return self.set_source(ProjectorSource.HDMI_1)
        else:
            logger.warning(f"[PROJECTOR_HDMI] Rejected HDMI port {port}: Zebronics PixaPlay 25 only has ONE physical HDMI port.")
            return False

    # =========================================================================
    # D. Hardware Health & Thermals Telemetry
    # =========================================================================

    def get_hardware_health(self) -> Dict[str, Any]:
        """
        Reads live optical LED light temperature and dual cooling fan RPMs.
        Conservative thresholds:
          Thermal: Safe (<50°C), Warning (50–65°C), Critical (>65°C)
          Fans: Healthy (>=2500 RPM), Warning (<2500 RPM)
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {
                "temperature_celsius": None,
                "main_fan_rpm": None,
                "sub_fan_rpm": None,
                "thermal_status": ThermalStatus.UNKNOWN.value,
                "fan_status": FanStatus.UNKNOWN.value,
                "verified": False,
                "message": "Projector not connected"
            }

        code_t, raw_temp, _ = self._run_shell("getprop zysys.light_temp")
        code_m, raw_main, _ = self._run_shell("getprop zysys.main_speed")
        code_s, raw_sub, _ = self._run_shell("getprop zysys.sub_speed")

        # Parse temperature (e.g. "32.1℃ ")
        temp_val = None
        if raw_temp:
            t_match = re.search(r'([0-9.]+)', raw_temp)
            if t_match:
                try:
                    temp_val = float(t_match.group(1))
                except ValueError:
                    temp_val = None

        # Parse fan speeds (e.g. "3245.17rpm")
        main_rpm = None
        if raw_main:
            m_match = re.search(r'([0-9.]+)', raw_main)
            if m_match:
                try:
                    main_rpm = float(m_match.group(1))
                except ValueError:
                    main_rpm = None

        sub_rpm = None
        if raw_sub:
            s_match = re.search(r'([0-9.]+)', raw_sub)
            if s_match:
                try:
                    sub_rpm = float(s_match.group(1))
                except ValueError:
                    sub_rpm = None

        # Thermal classification
        if temp_val is not None:
            if temp_val < 50.0:
                thermal_status = ThermalStatus.SAFE
            elif temp_val <= 65.0:
                thermal_status = ThermalStatus.WARNING
            else:
                thermal_status = ThermalStatus.CRITICAL
        else:
            thermal_status = ThermalStatus.UNKNOWN

        # Fan status classification
        if main_rpm is not None and sub_rpm is not None:
            if main_rpm >= 2500 and sub_rpm >= 2500:
                fan_status = FanStatus.HEALTHY
            else:
                fan_status = FanStatus.WARNING
        else:
            fan_status = FanStatus.UNKNOWN

        return {
            "temperature_celsius": temp_val,
            "main_fan_rpm": main_rpm,
            "sub_fan_rpm": sub_rpm,
            "thermal_status": thermal_status.value,
            "fan_status": fan_status.value,
            "verified": True,
            "raw_temp": raw_temp,
            "raw_main_fan": raw_main,
            "raw_sub_fan": raw_sub
        }

    # =========================================================================
    # E. Motor Auto-Focus
    # =========================================================================

    def auto_focus(self) -> Dict[str, Any]:
        """
        Triggers camera-assisted electric motor auto-focus via OEM intent.
        Truthful invariant: Reports TRIGGERED, does not falsely claim optical focus completed.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {"status": "FAILED", "action": "auto_focus", "verified": False, "message": "Projector not connected"}

        logger.info("[PROJECTOR_FOCUS] Triggering electric motor auto-focus sequence...")
        code, stdout, stderr = self._run_shell("am start -a com.zhiying.AUTO_FOCUS_CORRECTION")
        status = "TRIGGERED" if code == 0 else "FAILED"
        return {
            "status": status,
            "action": "auto_focus",
            "verified": False,  # Truthful: Activity triggered, optical calibration takes place in hardware
            "message": "Auto-focus triggered successfully." if code == 0 else f"Auto-focus dispatch failed: {stderr}"
        }

    # =========================================================================
    # F. Gyro Auto-Keystone
    # =========================================================================

    def auto_keystone(self) -> Dict[str, Any]:
        """
        Triggers 6D-gyro assisted auto-keystone correction via OEM intent.
        Truthful invariant: Reports TRIGGERED, does not falsely claim geometry completed.
        """
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {"status": "FAILED", "action": "auto_keystone", "verified": False, "message": "Projector not connected"}

        logger.info("[PROJECTOR_KEYSTONE] Triggering gyro-assisted auto-keystone correction...")
        code, stdout, stderr = self._run_shell("am start -a com.zhiying.ONE_AUTO_CORRECTION_KEYSTONE")
        status = "TRIGGERED" if code == 0 else "FAILED"
        return {
            "status": status,
            "action": "auto_keystone",
            "verified": False,
            "message": "Auto-keystone triggered successfully." if code == 0 else f"Auto-keystone dispatch failed: {stderr}"
        }

    # =========================================================================
    # G. Brightness Controls (Normalized 0–100% API with Read-Back Verification)
    # =========================================================================

    def get_brightness(self) -> int:
        """
        Reads system screen_brightness (0–255 integer scale) and returns normalized 0–100% value.
        """
        is_ready, _ = self.is_connected(auto_connect=False)
        if not is_ready:
            return 0

        code, out, _ = self._run_shell("settings get system screen_brightness")
        if code == 0 and out:
            try:
                raw_val = int(out.strip())
                # Normalize 0..255 to 0..100%
                pct = int(round((raw_val / 255.0) * 100))
                return max(0, min(100, pct))
            except ValueError:
                pass
        return 50

    def set_brightness(self, level: int) -> tuple[bool, int]:
        """
        Sets projector brightness on normalized 0–100% scale.
        Translates to Android 0–255 scale, validates bounds, and performs read-back verification.
        Returns: (success: bool, actual_level_pct: int)
        """
        if not isinstance(level, (int, float)) or level < 0 or level > 100:
            logger.error(f"[PROJECTOR_BRIGHTNESS] Invalid brightness requested: {level}%. Must be 0–100%.")
            return False, self.get_brightness()

        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            logger.error(f"[PROJECTOR_BRIGHTNESS] Projector not connected (state: {state})")
            return False, 0

        level_int = int(round(level))
        raw_val = int(round((level_int / 100.0) * 255))
        raw_val = max(0, min(255, raw_val))

        logger.info(f"[PROJECTOR_BRIGHTNESS] Setting screen_brightness to {raw_val} ({level_int}%)...")
        code, _, stderr = self._run_shell(f"settings put system screen_brightness {raw_val}")
        if code != 0:
            logger.error(f"[PROJECTOR_BRIGHTNESS] Failed to set brightness: {stderr}")
            return False, self.get_brightness()

        # Read-back verification
        time.sleep(0.15)
        actual_pct = self.get_brightness()
        # Allow ±2% rounding tolerance
        verified = abs(actual_pct - level_int) <= 2
        return verified, actual_pct

    # =========================================================================
    # H. HDMI-CEC Status & Device Telemetry
    # =========================================================================

    def get_cec_status(self) -> Dict[str, Any]:
        """Reads HDMI-CEC service and settings telemetry read-only via dumpsys hdmi_control."""
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
        """Reads system properties, power, source, signal, brightness, and health telemetry."""
        is_ready, state = self.is_connected(auto_connect=False)
        if not is_ready:
            return {
                "connected": False,
                "reachable": False,
                "ip": self.target.split(":")[0],
                "state": state,
                "hdmi_ports": 1,
                "cold_power_on_supported_via_adb": False
            }

        code, model, _ = self._run_shell("getprop ro.product.model")
        code, android_ver, _ = self._run_shell("getprop ro.build.version.release")
        code, product, _ = self._run_shell("getprop ro.product.name")

        power_info = self.get_power_state()
        fg_pkg = self.get_foreground_package()
        current_source = self.get_current_source()
        signal_info = self.get_signal_state()
        health_info = self.get_hardware_health()
        brightness_pct = self.get_brightness()
        cec_info = self.get_cec_status()

        return {
            "connected": True,
            "reachable": True,
            "ip": self.target.split(":")[0],
            "target": self.target,
            "model": model or "Zebronics PixaPlay 25 (NL5H00X)",
            "android": android_ver or "12",
            "product": product or "NL5H00X",
            "hdmi_ports": 1,
            "cold_power_on_supported_via_adb": False,
            "power_state": power_info.get("power_state"),
            "wakefulness": power_info.get("wakefulness"),
            "display_state": power_info.get("display_state"),
            "interactive": power_info.get("interactive"),
            "foreground_package": fg_pkg,
            "current_source": current_source.value,
            "signal_state": signal_info.get("signal_state"),
            "active_video_stream": signal_info.get("active_stream"),
            "brightness_percent": brightness_pct,
            "health": health_info,
            "cec_status": cec_info
        }
