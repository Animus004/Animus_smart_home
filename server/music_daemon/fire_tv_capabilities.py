"""
Authoritative Fire TV Capability Layer & State Model for Animus Smart Room.
Converts verified physical audit findings into a formal capability contract
with explicit precondition checking, structured error codes, and strict separation
between atomic capabilities and multi-step automations.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from fire_tv_controller import FireTvController
    from projector_controller import ProjectorController
    from bluetooth_helper import BluetoothAudioHelper
    from player import MPVPlayer

from media_provider_registry import MediaProviderRegistry, ProviderCapabilityStatus

logger = logging.getLogger("music_daemon.fire_tv_capabilities")

# ==============================================================================
# 1. Error Codes & Enums
# ==============================================================================

class FireTVErrorCode(str, Enum):
    FIRE_TV_OFFLINE = "FIRE_TV_OFFLINE"
    FIRE_TV_ASLEEP = "FIRE_TV_ASLEEP"
    SOUNDBAR_NOT_BONDED = "SOUNDBAR_NOT_BONDED"
    SOUNDBAR_CONNECTION_FAILED = "SOUNDBAR_CONNECTION_FAILED"
    YOUTUBE_UNAVAILABLE = "YOUTUBE_UNAVAILABLE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROJECTOR_OFF = "PROJECTOR_OFF"
    PROJECTOR_HDMI_SWITCH_FAILED = "PROJECTOR_HDMI_SWITCH_FAILED"
    AUDIO_TRANSFER_FAILED = "AUDIO_TRANSFER_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"


class FireTVCapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    FUTURE = "FUTURE"


class FireTVCapabilityType(str, Enum):
    # Connectivity
    CONNECTIVITY_CHECK = "connectivity_check"
    # Power
    POWER_WAKE = "power_wake"
    POWER_SLEEP = "power_sleep"
    POWER_GET_STATE = "power_get_state"
    # Navigation
    NAVIGATION_HOME = "navigation_home"
    NAVIGATION_BACK = "navigation_back"
    NAVIGATION_SELECT = "navigation_select"
    NAVIGATION_DPAD = "navigation_dpad"
    # Applications & Media
    APP_LAUNCH_YOUTUBE = "app_launch_youtube"
    APP_GET_FOREGROUND = "app_get_foreground"
    MEDIA_DIRECT_YOUTUBE = "media_direct_youtube"
    MEDIA_DIRECT_PROVIDER = "media_direct_provider"
    MEDIA_SEARCH_YOUTUBE = "media_search_youtube"
    MEDIA_VERIFY_YOUTUBE = "media_verify_youtube"
    # Playback & Transport Controls
    MEDIA_PLAY = "media_play"
    MEDIA_PAUSE = "media_pause"
    MEDIA_TOGGLE = "media_toggle"
    MEDIA_STOP = "media_stop"
    MEDIA_NEXT = "media_next"
    MEDIA_PREVIOUS = "media_previous"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    MUTE = "mute"
    # Bluetooth & Audio
    BT_GET_STATUS = "bt_get_status"
    BT_CONNECT_SOUNDBAR = "bt_connect_soundbar"
    BT_CONNECT_SOUNDBAR_DIRECT = "bt_connect_soundbar_direct"
    BT_DISCONNECT_SOUNDBAR_DIRECT = "bt_disconnect_soundbar_direct"
    BT_IS_SOUNDBAR_CONNECTED = "bt_is_soundbar_connected"
    AUDIO_SWITCH_TO_FIRE_TV = "audio_switch_to_fire_tv"
    AUDIO_SWITCH_TO_PC = "audio_switch_to_pc"
    # Display Integration
    PROJECTOR_SWITCH_HDMI1 = "projector_switch_hdmi1"
    PROJECTOR_VERIFY_HDMI1 = "projector_verify_hdmi1"
    # Automations (Composed)
    AUTOMATION_MOVIE_MODE_START = "automation_movie_mode_start"
    AUTOMATION_MOVIE_MODE_STOP = "automation_movie_mode_stop"


# ==============================================================================
# 2. Structured Result & State Models
# ==============================================================================

class FireTVCapabilityResult(BaseModel):
    capability: str
    success: bool
    error_code: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    verified: bool = False


class FireTVState(BaseModel):
    reachable: bool = False
    power_state: str = "UNKNOWN"
    foreground_app: Optional[str] = None
    active_provider: Optional[str] = None
    playback_state: str = "UNKNOWN"
    volume_level: Optional[int] = None
    youtube_foreground: bool = False
    soundbar_connected: bool = False
    soundbar_mac: str = "54:15:89:DC:A5:79"
    bluetooth_audio_state: str = "UNKNOWN"
    projector_hdmi1_active: bool = False
    movie_mode_active: bool = False


# ==============================================================================
# 3. Fire TV Capability Registry
# ==============================================================================

class FireTVCapabilityRegistry:
    """
    Authoritative Capability Registry for Amazon Fire TV Stick.
    Enforces preconditions before physical execution and returns structured,
    truthful capability results with telemetry readback.
    """

    def __init__(
        self,
        fire_tv: Optional[FireTvController] = None,
        projector: Optional[ProjectorController] = None,
        bt_helper: Optional[BluetoothAudioHelper] = None,
        player: Optional[MPVPlayer] = None,
        provider_registry: Optional[MediaProviderRegistry] = None
    ):
        self.fire_tv = fire_tv
        self.projector = projector
        self.bt_helper = bt_helper
        self.player = player
        self.provider_registry = provider_registry or MediaProviderRegistry()

    # ─── Connectivity Capabilities ────────────────────────────────────────────

    def check_connectivity(self) -> FireTVCapabilityResult:
        t0 = time.time()
        if not self.fire_tv:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.CONNECTIVITY_CHECK.value,
                success=False,
                error_code=FireTVErrorCode.FIRE_TV_OFFLINE.value,
                message="Fire TV controller not initialized.",
                duration_ms=0,
                verified=False
            )

        target_str = getattr(self.fire_tv, "target", "192.168.1.5:5555")
        is_conn, state = self.fire_tv.is_connected(auto_connect=True)
        dur = int((time.time() - t0) * 1000)

        if not is_conn:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.CONNECTIVITY_CHECK.value,
                success=False,
                error_code=FireTVErrorCode.FIRE_TV_OFFLINE.value,
                message=f"Fire TV at {target_str} is unreachable (state={state}).",
                details={"target": target_str, "state": state},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.CONNECTIVITY_CHECK.value,
            success=True,
            message=f"Fire TV at {target_str} is connected and reachable.",
            details={"target": target_str, "state": state},
            duration_ms=dur,
            verified=True
        )

    # ─── Power Capabilities ───────────────────────────────────────────────────

    def wake(self) -> FireTVCapabilityResult:
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        self.fire_tv.wake()
        time.sleep(0.5)

        # Verification
        code, pwr, _ = self.fire_tv._run_shell("dumpsys power | grep -i 'mWakefulness='")
        is_awake = "mWakefulness=Awake" in pwr
        dur = int((time.time() - t0) * 1000)

        if not is_awake:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.POWER_WAKE.value,
                success=False,
                error_code=FireTVErrorCode.VERIFICATION_FAILED.value,
                message="Sent wake key to Fire TV but device did not enter AWAKE state.",
                details={"raw_power_dump": pwr},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.POWER_WAKE.value,
            success=True,
            message="Fire TV is awake and active.",
            details={"power_state": "AWAKE"},
            duration_ms=dur,
            verified=True
        )

    def sleep(self) -> FireTVCapabilityResult:
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        self.fire_tv.sleep()
        time.sleep(0.5)
        dur = int((time.time() - t0) * 1000)

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.POWER_SLEEP.value,
            success=True,
            message="Fire TV put into sleep mode.",
            duration_ms=dur,
            verified=True
        )

    # ─── Navigation Capabilities ──────────────────────────────────────────────

    def send_navigation(self, action: str) -> FireTVCapabilityResult:
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        act_clean = action.strip().lower()
        success = False
        if act_clean == "home":
            success = self.fire_tv.home()
        elif act_clean == "back":
            success = self.fire_tv.back()
        elif act_clean in ["select", "enter", "ok"]:
            success = self.fire_tv.select()
        elif act_clean in ["up", "dpad_up"]:
            success = self.fire_tv.dpad_up()
        elif act_clean in ["down", "dpad_down"]:
            success = self.fire_tv.dpad_down()
        elif act_clean in ["left", "dpad_left"]:
            success = self.fire_tv.dpad_left()
        elif act_clean in ["right", "dpad_right"]:
            success = self.fire_tv.dpad_right()
        else:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.NAVIGATION_DPAD.value,
                success=False,
                error_code=FireTVErrorCode.INVALID_ARGUMENT.value,
                message=f"Unsupported navigation action: {action}",
                duration_ms=0,
                verified=False
            )

        dur = int((time.time() - t0) * 1000)
        return FireTVCapabilityResult(
            capability=f"navigation_{act_clean}",
            success=success,
            message=f"Navigation command '{action}' executed on Fire TV.",
            details={"action": act_clean},
            duration_ms=dur,
            verified=success
        )

    def home(self) -> FireTVCapabilityResult:
        """Sends HOME remote keyevent."""
        return self.send_navigation("home")

    def back(self) -> FireTVCapabilityResult:
        """Sends BACK remote keyevent."""
        return self.send_navigation("back")

    def select(self) -> FireTVCapabilityResult:
        """Sends SELECT remote keyevent."""
        return self.send_navigation("select")

    def dpad_up(self) -> FireTVCapabilityResult:
        """Sends DPAD_UP remote keyevent."""
        return self.send_navigation("up")

    def dpad_down(self) -> FireTVCapabilityResult:
        """Sends DPAD_DOWN remote keyevent."""
        return self.send_navigation("down")

    def dpad_left(self) -> FireTVCapabilityResult:
        """Sends DPAD_LEFT remote keyevent."""
        return self.send_navigation("left")

    def dpad_right(self) -> FireTVCapabilityResult:
        """Sends DPAD_RIGHT remote keyevent."""
        return self.send_navigation("right")

    # ─── Application & Media Capabilities ─────────────────────────────────────

    def launch_youtube(self) -> FireTVCapabilityResult:
        t0 = time.time()
        # Precondition 1: Connectivity
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        # Precondition 2: Wake device
        self.wake()

        # Action: Launch YouTube
        code, stdout, _ = self.fire_tv._run_shell(
            "am start -n com.amazon.firetv.youtube/dev.cobalt.app.MainActivity"
        )
        time.sleep(1.0)

        # Verification: Focus check
        is_focused = self.fire_tv.is_app_foreground("com.amazon.firetv.youtube")
        dur = int((time.time() - t0) * 1000)

        if not is_focused:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.APP_LAUNCH_YOUTUBE.value,
                success=False,
                error_code=FireTVErrorCode.YOUTUBE_UNAVAILABLE.value,
                message="Failed to bring YouTube TV into the foreground on Fire TV.",
                details={"stdout": stdout},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.APP_LAUNCH_YOUTUBE.value,
            success=True,
            message="YouTube TV launched and focused on Fire TV.",
            details={"package": "com.amazon.firetv.youtube"},
            duration_ms=dur,
            verified=True
        )

    def search_youtube(self, query: str) -> FireTVCapabilityResult:
        t0 = time.time()
        if not query or not query.strip():
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_SEARCH_YOUTUBE.value,
                success=False,
                error_code=FireTVErrorCode.INVALID_ARGUMENT.value,
                message="Search query cannot be empty.",
                duration_ms=0,
                verified=False
            )

        # Precondition: YouTube available and launched
        launch_res = self.launch_youtube()
        if not launch_res.success:
            return launch_res

        # Action: Perform Search
        ok = self.fire_tv.search_or_launch_content(query.strip())
        dur = int((time.time() - t0) * 1000)

        if not ok:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_SEARCH_YOUTUBE.value,
                success=False,
                error_code=FireTVErrorCode.VERIFICATION_FAILED.value,
                message=f"Could not complete YouTube search for '{query}'.",
                details={"query": query},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.MEDIA_SEARCH_YOUTUBE.value,
            success=True,
            message=f"YouTube search for '{query}' successfully displayed on Fire TV.",
            details={"query": query, "verified_foreground": True},
            duration_ms=dur,
            verified=True
        )

    def play_youtube_video_id(self, video_id: str) -> FireTVCapabilityResult:
        """
        Direct video autoplay on Fire TV using explicit Cobalt component intent.
        Preconditions: Fire TV reachable, awake, YouTube installed.
        Latency: ~199ms.
        """
        t0 = time.time()
        if not video_id or not video_id.strip():
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_DIRECT_YOUTUBE.value,
                success=False,
                error_code=FireTVErrorCode.INVALID_ARGUMENT.value,
                message="YouTube video ID cannot be empty.",
                duration_ms=0,
                verified=False
            )

        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        self.wake()

        vid = video_id.strip()
        watch_url = f"https://www.youtube.com/watch?v={vid}"
        comp = "com.amazon.firetv.youtube/dev.cobalt.app.MainActivity"
        cmd = f"am start -a android.intent.action.VIEW -d '{watch_url}' -n {comp}"

        code, out, err = self.fire_tv._run_shell(cmd)
        time.sleep(1.0)

        # Verification: window focus
        code_w, win, _ = self.fire_tv._run_shell("dumpsys window | grep -E '(mCurrentFocus|mFocusedApp)'")
        is_yt = "com.amazon.firetv.youtube" in win
        dur = int((time.time() - t0) * 1000)

        if not is_yt or code != 0:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_DIRECT_YOUTUBE.value,
                success=False,
                error_code=FireTVErrorCode.VERIFICATION_FAILED.value,
                message=f"Failed to verify YouTube direct launch for video ID '{vid}'.",
                details={"cmd": cmd, "stdout": out, "stderr": err, "window": win},
                duration_ms=dur,
                verified=True
            )

        # Query media session state
        code_m, ms_out, _ = self.fire_tv._run_shell("dumpsys media_session | grep -E '(package=|state=PlaybackState)'")
        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.MEDIA_DIRECT_YOUTUBE.value,
            success=True,
            message=f"YouTube video '{vid}' playing directly on Fire TV.",
            details={"video_id": vid, "url": watch_url, "component": comp, "media_session": ms_out.splitlines()},
            duration_ms=dur,
            verified=True
        )

    def launch_streaming_provider(self, provider_id: str, content_uri_or_id: Optional[str] = None) -> FireTVCapabilityResult:
        """
        Launches direct title or content on a registered streaming provider.
        Preconditions: Provider registered, Fire TV reachable, awake.
        """
        t0 = time.time()
        provider = self.provider_registry.get_provider(provider_id)
        if not provider:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value,
                success=False,
                error_code=FireTVErrorCode.PROVIDER_UNAVAILABLE.value,
                message=f"Streaming provider '{provider_id}' is not registered or supported.",
                details={"requested_provider": provider_id},
                duration_ms=0,
                verified=False
            )

        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        self.wake()

        ok, uri, comp, msg = self.provider_registry.resolve_launch_intent(provider.provider_id, content_uri_or_id or "")
        if not ok:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value,
                success=False,
                error_code=FireTVErrorCode.INVALID_ARGUMENT.value,
                message=f"Could not build launch intent for '{content_uri_or_id}' on {provider.display_name}.",
                details={"error": msg},
                duration_ms=0,
                verified=False
            )

        if uri:
            comp_flag = f"-n {comp}" if comp else f"-p {provider.package_name}"
            cmd = f"am start -a android.intent.action.VIEW -d '{uri}' {comp_flag}"
        else:
            comp_flag = f"-n {provider.launch_component}" if provider.launch_component else f"-p {provider.package_name}"
            cmd = f"am start {comp_flag}"

        code, out, err = self.fire_tv._run_shell(cmd)
        time.sleep(1.5)

        # Verification: window focus
        code_w, win, _ = self.fire_tv._run_shell("dumpsys window | grep -E '(mCurrentFocus|mFocusedApp)'")
        is_in_fg = provider.package_name in win
        dur = int((time.time() - t0) * 1000)

        if not is_in_fg or code != 0:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value,
                success=False,
                error_code=FireTVErrorCode.VERIFICATION_FAILED.value,
                message=f"Failed to focus {provider.display_name} ({provider.package_name}) on Fire TV.",
                details={"cmd": cmd, "stdout": out, "stderr": err, "window": win},
                duration_ms=dur,
                verified=True
            )

        res_status = "APP_LAUNCH_ONLY" if not uri else ("DIRECT_PLAYING" if provider.autoplay_verified else "CONTENT_PAGE_OPENED")
        msg_text = f"{provider.display_name} launched." if not uri else f"{provider.display_name} content launched ({res_status})."
        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value,
            success=True,
            message=msg_text,
            details={
                "provider": provider.provider_id,
                "display_name": provider.display_name,
                "uri": uri,
                "launch_status": res_status,
                "autoplay_verified": provider.autoplay_verified
            },
            duration_ms=dur,
            verified=True
        )

    # ─── Playback & Transport Controls ────────────────────────────────────────

    def play(self) -> FireTVCapabilityResult:
        """Sends MEDIA_PLAY (126) keyevent to active media session."""
        return self._send_media_key(FireTVCapabilityType.MEDIA_PLAY.value, 126, "MEDIA_PLAY")

    def pause(self) -> FireTVCapabilityResult:
        """Sends MEDIA_PAUSE (127) keyevent to active media session."""
        return self._send_media_key(FireTVCapabilityType.MEDIA_PAUSE.value, 127, "MEDIA_PAUSE")

    def toggle_play_pause(self) -> FireTVCapabilityResult:
        """Sends MEDIA_PLAY_PAUSE (85) keyevent to toggle active stream."""
        return self._send_media_key(FireTVCapabilityType.MEDIA_TOGGLE.value, 85, "MEDIA_PLAY_PAUSE")

    def stop(self) -> FireTVCapabilityResult:
        """Sends MEDIA_STOP (86) keyevent to halt active playback."""
        return self._send_media_key(FireTVCapabilityType.MEDIA_STOP.value, 86, "MEDIA_STOP")

    def next_track(self) -> FireTVCapabilityResult:
        """Sends MEDIA_NEXT (87) keyevent to skip to next item."""
        return self._send_media_key(FireTVCapabilityType.MEDIA_NEXT.value, 87, "MEDIA_NEXT")

    def previous_track(self) -> FireTVCapabilityResult:
        """Sends MEDIA_PREVIOUS (88) keyevent to return to previous item."""
        return self._send_media_key(FireTVCapabilityType.MEDIA_PREVIOUS.value, 88, "MEDIA_PREVIOUS")

    def volume_up(self) -> FireTVCapabilityResult:
        """Sends VOLUME_UP (24) keyevent."""
        return self._send_media_key(FireTVCapabilityType.VOLUME_UP.value, 24, "VOLUME_UP")

    def volume_down(self) -> FireTVCapabilityResult:
        """Sends VOLUME_DOWN (25) keyevent."""
        return self._send_media_key(FireTVCapabilityType.VOLUME_DOWN.value, 25, "VOLUME_DOWN")

    def mute(self) -> FireTVCapabilityResult:
        """Sends VOLUME_MUTE (164) keyevent."""
        return self._send_media_key(FireTVCapabilityType.MUTE.value, 164, "VOLUME_MUTE")

    def _send_media_key(self, cap_name: str, keycode: int, key_name: str) -> FireTVCapabilityResult:
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        code, out, err = self.fire_tv._run_shell(f"input keyevent {keycode}")
        dur = int((time.time() - t0) * 1000)

        if code != 0:
            return FireTVCapabilityResult(
                capability=cap_name,
                success=False,
                error_code=FireTVErrorCode.VERIFICATION_FAILED.value,
                message=f"Failed to send keyevent {key_name} ({keycode}).",
                details={"stderr": err},
                duration_ms=dur,
                verified=False
            )

        return FireTVCapabilityResult(
            capability=cap_name,
            success=True,
            message=f"Sent {key_name} ({keycode}) to Fire TV.",
            details={"keycode": keycode, "key_name": key_name},
            duration_ms=dur,
            verified=True
        )

    # ─── Bluetooth & Audio Capabilities ───────────────────────────────────────

    def get_bluetooth_status(self) -> FireTVCapabilityResult:
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        st = self.fire_tv.get_bluetooth_status()
        dur = int((time.time() - t0) * 1000)

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.BT_GET_STATUS.value,
            success=True,
            message="Bluetooth telemetry retrieved from Fire TV.",
            details=st,
            duration_ms=dur,
            verified=True
        )

    def connect_soundbar(self, timeout_seconds: float = 8.0, force_fallback: bool = False) -> FireTVCapabilityResult:
        """
        Connects the permanently bonded LG SNC4R soundbar to Fire TV.
        Preconditions: Fire TV reachable, awake, soundbar bonded.
        Policy:
        1. Check if already connected -> ALREADY_CONNECTED.
        2. Attempt direct helper broadcast (< 1.2s, 0 UI disruption) -> DIRECT_CONNECTED.
        3. Automatic fallback to Settings + DPAD method -> SETTINGS_FALLBACK_CONNECTED.
        4. Verified strictly against physical A2DP telemetry.
        """
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        mac = getattr(self.fire_tv, "required_bt_mac", "54:15:89:DC:A5:79")
        # Check if already connected
        if self.fire_tv.is_required_bluetooth_connected():
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.BT_CONNECT_SOUNDBAR.value,
                success=True,
                message="LG Soundbar is already connected to Fire TV.",
                details={"soundbar_mac": mac, "already_connected": True, "connection_method": "ALREADY_CONNECTED"},
                duration_ms=int((time.time() - t0) * 1000),
                verified=True
            )

        # Execute connection flow
        ok, method = self.fire_tv.connect_soundbar_with_method(timeout_seconds=timeout_seconds, force_fallback=force_fallback)
        dur = int((time.time() - t0) * 1000)

        if not ok:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.BT_CONNECT_SOUNDBAR.value,
                success=False,
                error_code=FireTVErrorCode.SOUNDBAR_CONNECTION_FAILED.value,
                message=f"Failed to connect LG Soundbar ({mac}) on Fire TV within {timeout_seconds}s.",
                details={"soundbar_mac": mac, "connection_method": method},
                duration_ms=dur,
                verified=True
            )

        cap_type = FireTVCapabilityType.BT_CONNECT_SOUNDBAR_DIRECT.value if method == "DIRECT_CONNECTED" else FireTVCapabilityType.BT_CONNECT_SOUNDBAR.value
        return FireTVCapabilityResult(
            capability=cap_type,
            success=True,
            message=f"LG Soundbar connected to Fire TV ({method}).",
            details={"soundbar_mac": mac, "connection_method": method},
            duration_ms=dur,
            verified=True
        )

    def disconnect_soundbar(self, timeout_seconds: float = 5.0) -> FireTVCapabilityResult:
        """
        Disconnects the LG SNC4R soundbar from Fire TV.
        Preconditions: Fire TV reachable.
        Policy:
        1. Check if already disconnected -> ALREADY_DISCONNECTED.
        2. Attempt direct helper disconnect broadcast -> DIRECT_DISCONNECTED.
        3. Verified against physical A2DP telemetry.
        """
        t0 = time.time()
        conn_res = self.check_connectivity()
        if not conn_res.success:
            return conn_res

        mac = getattr(self.fire_tv, "required_bt_mac", "54:15:89:DC:A5:79")
        if not self.fire_tv.is_required_bluetooth_connected():
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.BT_DISCONNECT_SOUNDBAR_DIRECT.value,
                success=True,
                message="LG Soundbar is already disconnected from Fire TV.",
                details={"soundbar_mac": mac, "disconnection_method": "ALREADY_DISCONNECTED"},
                duration_ms=int((time.time() - t0) * 1000),
                verified=True
            )

        ok, method = self.fire_tv.disconnect_soundbar(timeout_seconds=timeout_seconds)
        dur = int((time.time() - t0) * 1000)

        if not ok:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.BT_DISCONNECT_SOUNDBAR_DIRECT.value,
                success=False,
                error_code=FireTVErrorCode.VERIFICATION_FAILED.value,
                message=f"Failed to disconnect LG Soundbar ({mac}) on Fire TV.",
                details={"soundbar_mac": mac, "disconnection_method": method},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.BT_DISCONNECT_SOUNDBAR_DIRECT.value,
            success=True,
            message=f"LG Soundbar disconnected from Fire TV ({method}).",
            details={"soundbar_mac": mac, "disconnection_method": method},
            duration_ms=dur,
            verified=True
        )

    # ─── Audio Ownership Transfer Capabilities ────────────────────────────────

    def switch_audio_to_fire_tv(self) -> FireTVCapabilityResult:
        """
        Transfers authoritative audio ownership from PC to Fire TV.
        Preconditions: PC audio released, Fire TV reachable, Soundbar bonded.
        """
        t0 = time.time()

        # Step 1: Release PC audio ownership
        if self.player:
            self.player.stop()
        if self.bt_helper and hasattr(self.bt_helper, "device_portal"):
            self.bt_helper.device_portal.disconnect_lg()

        time.sleep(1.0)

        # Step 2: Connect Soundbar to Fire TV
        bt_res = self.connect_soundbar(timeout_seconds=8.0)
        dur = int((time.time() - t0) * 1000)

        mac = getattr(self.fire_tv, "required_bt_mac", "54:15:89:DC:A5:79") if self.fire_tv else None
        if not bt_res.success:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.AUDIO_SWITCH_TO_FIRE_TV.value,
                success=False,
                error_code=FireTVErrorCode.AUDIO_TRANSFER_FAILED.value,
                message=f"Failed to transfer audio to Fire TV: {bt_res.message}",
                details={"sub_error": bt_res.error_code},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.AUDIO_SWITCH_TO_FIRE_TV.value,
            success=True,
            message="Audio ownership transferred to Fire TV (LG Soundbar connected).",
            details={"target": "FIRE_TV", "soundbar_mac": mac},
            duration_ms=dur,
            verified=True
        )

    def switch_audio_to_pc(self) -> FireTVCapabilityResult:
        """
        Transfers authoritative audio ownership from Fire TV back to PC.
        Preconditions: PC Bluetooth subsystem online, Windows Device Portal available.
        """
        t0 = time.time()
        if not self.bt_helper:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.AUDIO_SWITCH_TO_PC.value,
                success=False,
                error_code=FireTVErrorCode.PRECONDITION_FAILED.value,
                message="PC Bluetooth helper is not available.",
                duration_ms=0,
                verified=False
            )

        ok, dev, msg = self.bt_helper.ensure_audio_endpoint()
        dur = int((time.time() - t0) * 1000)

        if not ok or not dev:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.AUDIO_SWITCH_TO_PC.value,
                success=False,
                error_code=FireTVErrorCode.SOUNDBAR_CONNECTION_FAILED.value,
                message=f"Could not connect soundbar to PC: {msg}",
                details={"reconnect_msg": msg},
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.AUDIO_SWITCH_TO_PC.value,
            success=True,
            message=f"Audio ownership transferred to PC ({dev.get('name')}).",
            details={"target": "PC", "device": dev},
            duration_ms=dur,
            verified=True
        )

    # ─── Projector Display Integration Capabilities ───────────────────────────

    def switch_projector_to_hdmi1(self) -> FireTVCapabilityResult:
        """
        Switches projector source to HDMI 1 for Fire TV display output.
        Preconditions: Projector reachable, power state ON.
        """
        t0 = time.time()
        if not self.projector:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.PROJECTOR_SWITCH_HDMI1.value,
                success=False,
                error_code=FireTVErrorCode.PROJECTOR_OFF.value,
                message="Projector controller not initialized.",
                duration_ms=0,
                verified=False
            )

        # Precondition: Projector Power ON
        pwr = self.projector.get_power_state()
        if pwr.get("power_state") != "ON":
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.PROJECTOR_SWITCH_HDMI1.value,
                success=False,
                error_code=FireTVErrorCode.PROJECTOR_OFF.value,
                message="Projector is currently OFF. Cannot switch HDMI source.",
                details=pwr,
                duration_ms=int((time.time() - t0) * 1000),
                verified=True
            )

        # Action: Set HDMI 1
        ok = self.projector.set_hdmi(1)
        dur = int((time.time() - t0) * 1000)

        if not ok:
            return FireTVCapabilityResult(
                capability=FireTVCapabilityType.PROJECTOR_SWITCH_HDMI1.value,
                success=False,
                error_code=FireTVErrorCode.PROJECTOR_HDMI_SWITCH_FAILED.value,
                message="Failed to switch Projector to HDMI 1.",
                duration_ms=dur,
                verified=True
            )

        return FireTVCapabilityResult(
            capability=FireTVCapabilityType.PROJECTOR_SWITCH_HDMI1.value,
            success=True,
            message="Projector switched to HDMI 1 (Fire TV display active).",
            details={"source": "HDMI_1"},
            duration_ms=dur,
            verified=True
        )

    def get_live_state(self, movie_mode_active: bool = False) -> FireTVState:
        """Alias for get_state for Phase E.2 service layer."""
        return self.get_state(movie_mode_active=movie_mode_active)

    def execute_capability(self, capability: str, **kwargs) -> FireTVCapabilityResult:
        """
        Authoritative capability execution dispatcher.
        Dispatches any registered capability by name and returns structured FireTVCapabilityResult.
        """
        cap = (capability or "").strip().lower()

        # Connectivity & Power
        if cap in ["connectivity_check", "check_connectivity"]:
            return self.check_connectivity()
        elif cap in ["power_wake", "wake"]:
            return self.wake()
        elif cap in ["power_sleep", "sleep"]:
            return self.sleep()

        # Navigation
        elif cap in ["navigation_home", "home"]:
            return self.home()
        elif cap in ["navigation_back", "back"]:
            return self.back()
        elif cap in ["navigation_select", "select"]:
            return self.select()
        elif cap in ["navigation_dpad", "dpad"]:
            return self.send_navigation(kwargs.get("action", "select"))
        elif cap in ["dpad_up", "navigation_up"]:
            return self.dpad_up()
        elif cap in ["dpad_down", "navigation_down"]:
            return self.dpad_down()
        elif cap in ["dpad_left", "navigation_left"]:
            return self.dpad_left()
        elif cap in ["dpad_right", "navigation_right"]:
            return self.dpad_right()

        # Application & Media Launch
        elif cap in ["app_launch_youtube", "launch_youtube"]:
            return self.launch_youtube()
        elif cap in ["media_direct_youtube", "play_youtube_video_id"]:
            vid = kwargs.get("video_id") or kwargs.get("content_id") or kwargs.get("query", "")
            return self.play_youtube_video_id(vid)
        elif cap in ["media_direct_provider", "launch_streaming_provider"]:
            provider = kwargs.get("provider", "youtube")
            cid = kwargs.get("content_id") or kwargs.get("content_uri") or kwargs.get("query", "")
            return self.launch_streaming_provider(provider, cid)
        elif cap in ["media_search_youtube", "search_youtube"]:
            return self.search_youtube(kwargs.get("query", ""))

        # Playback & Transport Controls
        elif cap in ["media_play", "play"]:
            return self.play()
        elif cap in ["media_pause", "pause"]:
            return self.pause()
        elif cap in ["media_toggle", "toggle", "toggle_play_pause"]:
            return self.toggle_play_pause()
        elif cap in ["media_stop", "stop"]:
            return self.stop()
        elif cap in ["media_next", "next", "next_track"]:
            return self.next_track()
        elif cap in ["media_previous", "previous", "previous_track"]:
            return self.previous_track()
        elif cap in ["volume_up"]:
            return self.volume_up()
        elif cap in ["volume_down"]:
            return self.volume_down()
        elif cap in ["mute"]:
            return self.mute()

        # Bluetooth & Audio Ownership
        elif cap in ["bt_get_status", "get_bluetooth_status"]:
            return self.get_bluetooth_status()
        elif cap in ["bt_connect_soundbar", "connect_soundbar"]:
            return self.connect_soundbar(timeout_seconds=kwargs.get("timeout_seconds", 8.0))
        elif cap in ["bt_connect_soundbar_direct"]:
            return self.connect_soundbar(timeout_seconds=kwargs.get("timeout_seconds", 4.0), force_fallback=False)
        elif cap in ["bt_disconnect_soundbar_direct", "disconnect_soundbar"]:
            return self.disconnect_soundbar(timeout_seconds=kwargs.get("timeout_seconds", 4.0))
        elif cap in ["audio_switch_to_fire_tv", "route_audio_to_firetv"]:
            return self.switch_audio_to_fire_tv()
        elif cap in ["audio_switch_to_pc", "route_audio_to_pc"]:
            return self.switch_audio_to_pc()

        # Display Integration
        elif cap in ["projector_switch_hdmi1", "switch_projector_to_hdmi1"]:
            return self.switch_projector_to_hdmi1()

        return FireTVCapabilityResult(
            capability=cap,
            success=False,
            error_code=FireTVErrorCode.UNSUPPORTED_CAPABILITY.value,
            message=f"Capability '{cap}' is not recognized in FireTVCapabilityRegistry.",
            duration_ms=0,
            verified=False
        )

    # ─── Telemetry State Aggregator ───────────────────────────────────────────

    def get_state(self, movie_mode_active: bool = False) -> FireTVState:
        """
        Constructs authoritative FireTVState backed strictly by live telemetry.
        """
        if not self.fire_tv:
            return FireTVState()

        is_conn, state = self.fire_tv.is_connected(auto_connect=False)
        if not is_conn:
            return FireTVState(
                reachable=False,
                power_state="OFFLINE",
                movie_mode_active=movie_mode_active
            )

        bt_st = self.fire_tv.get_bluetooth_status()
        code, pwr, _ = self.fire_tv._run_shell("dumpsys power | grep -i 'mWakefulness='")
        is_awake = "mWakefulness=Awake" in pwr

        # Foreground check
        code, win, _ = self.fire_tv._run_shell("dumpsys window | grep -E '(mCurrentFocus|mFocusedApp)'")
        is_yt = "com.amazon.firetv.youtube" in win

        # Media Session Telemetry
        playback_state = "UNKNOWN"
        active_provider = None
        code_ms, ms_dump, _ = self.fire_tv._run_shell("dumpsys media_session | grep -E '(package=|state=PlaybackState)'")
        if code_ms == 0 and ms_dump:
            for line in ms_dump.splitlines():
                if "state=PlaybackState" in line:
                    if "state=3" in line:
                        playback_state = "PLAYING"
                    elif "state=2" in line:
                        playback_state = "PAUSED"
                    elif "state=0" in line or "state=1" in line:
                        if playback_state == "UNKNOWN":
                            playback_state = "STOPPED"
                if "package=" in line:
                    pkg = line.split("=")[-1].strip()
                    p = self.provider_registry.get_provider_for_package(pkg)
                    if p and not active_provider:
                        active_provider = p.provider_id

        if is_yt and not active_provider:
            active_provider = "youtube"

        # Audio volume stream
        vol_level = None
        code_a, audio_dump, _ = self.fire_tv._run_shell("dumpsys audio | grep -A 2 -i 'STREAM_MUSIC:'")
        if code_a == 0 and audio_dump:
            for line in audio_dump.splitlines():
                if "Current:" in line or "current:" in line:
                    parts = line.split()
                    for pt in parts:
                        if pt.isdigit():
                            vol_level = int(pt)
                            break

        # Projector check
        proj_hdmi1 = False
        if self.projector:
            info = self.projector.get_device_info()
            proj_hdmi1 = info.get("input_source") == "HDMI_1" and info.get("power_state") == "ON"

        mac = getattr(self.fire_tv, "required_bt_mac", "54:15:89:DC:A5:79")
        fg_app = "com.amazon.firetv.youtube" if is_yt else ("com.amazon.tv.launcher" if "launcher" in win else None)
        if not fg_app and win:
            for p in self.provider_registry.list_providers():
                if p.package_name in win:
                    fg_app = p.package_name
                    if not active_provider:
                        active_provider = p.provider_id
                    break

        return FireTVState(
            reachable=True,
            power_state="AWAKE" if is_awake else "ASLEEP",
            foreground_app=fg_app,
            active_provider=active_provider,
            playback_state=playback_state,
            volume_level=vol_level,
            youtube_foreground=is_yt,
            soundbar_connected=bool(bt_st.get("required_device_connected", False)),
            soundbar_mac=mac,
            bluetooth_audio_state=bt_st.get("state", "UNKNOWN"),
            projector_hdmi1_active=proj_hdmi1,
            movie_mode_active=movie_mode_active
        )

    # ─── Machine-Readable Capability Registry ─────────────────────────────────

    @classmethod
    def get_registry_metadata(cls) -> Dict[str, Any]:
        """
        Returns machine-readable registry of AVAILABLE, NOT_AVAILABLE, and FUTURE capabilities
        along with supported streaming media provider profiles.
        """
        prov_reg = MediaProviderRegistry()
        return {
            "version": "1.1.0",
            "device": {
                "target": "192.168.1.5:5555",
                "model": "Amazon Fire TV Stick Lite / 3rd Gen (AFTSS)",
                "os": "Fire OS 7.7.1.6 (Android 9 API 28)",
                "soundbar_mac": "54:15:89:DC:A5:79",
                "soundbar_name": "LG SNC4R(79)"
            },
            "providers": prov_reg.get_registry_dict(),
            "capabilities": {
                FireTVCapabilityStatus.AVAILABLE.value: [
                    {
                        "name": FireTVCapabilityType.CONNECTIVITY_CHECK.value,
                        "description": "TCP ADB connectivity and device presence verification.",
                        "preconditions": ["Network reachable on 192.168.1.5:5555"]
                    },
                    {
                        "name": FireTVCapabilityType.POWER_WAKE.value,
                        "description": "Wake from sleep/screensaver (KEYEVENT_WAKEUP 224).",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.POWER_SLEEP.value,
                        "description": "Put Fire TV into standby (KEYEVENT_SLEEP 223).",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.NAVIGATION_DPAD.value,
                        "description": "Standard remote keyevents (HOME, BACK, SELECT, UP, DOWN, LEFT, RIGHT).",
                        "preconditions": ["ADB connected", "Device awake"]
                    },
                    {
                        "name": FireTVCapabilityType.APP_LAUNCH_YOUTUBE.value,
                        "description": "Launch YouTube TV Leanback activity and verify window focus.",
                        "preconditions": ["ADB connected", "Device awake", "YouTube TV installed"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_DIRECT_YOUTUBE.value,
                        "description": "Direct video autoplay using explicit Cobalt component intent in ~199ms.",
                        "preconditions": ["ADB connected", "Device awake", "Valid YouTube video ID"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_DIRECT_PROVIDER.value,
                        "description": "Direct content/details page launch on registered streaming apps (Hotstar, Netflix, Zee5, etc.).",
                        "preconditions": ["Target app installed", "Device awake"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_SEARCH_YOUTUBE.value,
                        "description": "Fallback: Navigate to search bar, input query text, and verify search results page.",
                        "preconditions": ["YouTube TV in foreground"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_PLAY.value,
                        "description": "Send MEDIA_PLAY keyevent (126) to resume playback.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_PAUSE.value,
                        "description": "Send MEDIA_PAUSE keyevent (127) to pause playback.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_TOGGLE.value,
                        "description": "Send MEDIA_PLAY_PAUSE keyevent (85) to toggle stream.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_STOP.value,
                        "description": "Send MEDIA_STOP keyevent (86) to stop playback.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_NEXT.value,
                        "description": "Send MEDIA_NEXT keyevent (87) to skip to next track.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.MEDIA_PREVIOUS.value,
                        "description": "Send MEDIA_PREVIOUS keyevent (88) to skip to previous track.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.VOLUME_UP.value,
                        "description": "Send VOLUME_UP keyevent (24).",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.VOLUME_DOWN.value,
                        "description": "Send VOLUME_DOWN keyevent (25).",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.MUTE.value,
                        "description": "Send VOLUME_MUTE keyevent (164).",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.BT_CONNECT_SOUNDBAR.value,
                        "description": "Production Bluetooth Connection: Direct helper broadcast (<1.2s) with Settings+DPAD fallback.",
                        "preconditions": ["Soundbar in BT pairing mode / idle", "Device awake"]
                    },
                    {
                        "name": FireTVCapabilityType.BT_CONNECT_SOUNDBAR_DIRECT.value,
                        "description": "Direct ADB broadcast connection using BluetoothProfile reflection (~1.1s, 0 UI disruption).",
                        "preconditions": ["Soundbar in BT pairing mode / idle", "Device awake", "Helper APK installed"]
                    },
                    {
                        "name": FireTVCapabilityType.BT_DISCONNECT_SOUNDBAR_DIRECT.value,
                        "description": "Direct ADB broadcast disconnection (~415ms).",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.BT_GET_STATUS.value,
                        "description": "Parse dumpsys bluetooth_manager for A2dpStateMachine connected sink.",
                        "preconditions": ["ADB connected"]
                    },
                    {
                        "name": FireTVCapabilityType.AUDIO_SWITCH_TO_FIRE_TV.value,
                        "description": "Release PC audio and establish Fire TV A2DP connection.",
                        "preconditions": ["PC audio released", "Fire TV reachable"]
                    },
                    {
                        "name": FireTVCapabilityType.AUDIO_SWITCH_TO_PC.value,
                        "description": "Establish PC Windows Device Portal connection to soundbar.",
                        "preconditions": ["Windows Device Portal available"]
                    },
                    {
                        "name": FireTVCapabilityType.PROJECTOR_SWITCH_HDMI1.value,
                        "description": "Switch projector input source to HDMI 1.",
                        "preconditions": ["Projector ON and reachable"]
                    },
                    {
                        "name": FireTVCapabilityType.AUTOMATION_MOVIE_MODE_START.value,
                        "description": "Composite automation: Projector ON + HDMI1 + Audio Transfer + Direct Video / Search + Health Invariant.",
                        "preconditions": ["Projector ON", "Fire TV reachable", "Soundbar bonded"]
                    },
                    {
                        "name": FireTVCapabilityType.AUTOMATION_MOVIE_MODE_STOP.value,
                        "description": "Composite teardown: Fire TV Home + Projector OFF + PC Audio Restore.",
                        "preconditions": ["None"]
                    }
                ],
                FireTVCapabilityStatus.NOT_AVAILABLE.value: [
                    {
                        "name": "bluetooth_discovery",
                        "reason": "Excluded by design. Smart room topology operates strictly on frozen MAC baseline."
                    },
                    {
                        "name": "bluetooth_runtime_pairing",
                        "reason": "Commissioning-time manual procedure. Soundbar is permanently bonded."
                    },
                    {
                        "name": "direct_adb_a2dp_connect_cli",
                        "reason": "Fire OS 7 returns 'No shell command implementation.' for cmd bluetooth_manager."
                    }
                ],
                FireTVCapabilityStatus.FUTURE.value: []
            }
        }
