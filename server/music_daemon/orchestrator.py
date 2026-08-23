"""
Smart Room Orchestrator for Animus PC Daemon.
Provides high-level room audio state management, soundbar connection lifecycle,
and safe media playback orchestration without exposing low-level Windows/AEP/WASAPI details.
"""

from enum import Enum
import logging
import time
from typing import Optional, Dict, Any, Tuple

from bluetooth_helper import BluetoothAudioHelper
from device_portal import WindowsDevicePortalBluetooth
from player import MpvPlayer
from resolver import YouTubeMusicResolver

logger = logging.getLogger("music_daemon.orchestrator")


class RoomAudioState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    WAITING_FOR_AUDIO_ENDPOINT = "WAITING_FOR_AUDIO_ENDPOINT"
    AUDIO_READY = "AUDIO_READY"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    DISCONNECTING = "DISCONNECTING"
    AUDIO_OUTPUT_UNAVAILABLE = "AUDIO_OUTPUT_UNAVAILABLE"


from fire_tv_controller import FireTvController, FireTvBluetoothState
from projector_controller import ProjectorController, ProjectorPowerState, ProjectorSource

class SmartRoomOrchestrator:
    """
    High-level orchestration service managing room audio, soundbar connectivity,
    projector state, Fire TV Bluetooth invariants, and Movie Mode health.
    """
    def __init__(
        self,
        resolver: YouTubeMusicResolver,
        player: MpvPlayer,
        bt_helper: Optional[BluetoothAudioHelper] = None,
        projector: Optional[ProjectorController] = None,
        fire_tv: Optional[FireTvController] = None
    ):
        self.resolver = resolver
        self.player = player
        self.bt_helper = bt_helper or player.bt_helper
        self.projector = projector
        self.fire_tv = fire_tv or FireTvController()
        self._current_state: RoomAudioState = RoomAudioState.DISCONNECTED
        self._last_error: Optional[str] = None
        self._last_action_duration_ms: int = 0

    @property
    def current_state(self) -> RoomAudioState:
        return self._current_state

    def get_movie_mode_health(self) -> Dict[str, Any]:
        """
        Validates the critical room invariant:
        MOVIE_MODE_HEALTHY = projector_on AND projector_source == HDMI_1
                             AND fire_tv_bluetooth_connected AND lg_soundbar_connected
        """
        proj_info = self.projector.get_device_info() if self.projector else {"power_state": "UNKNOWN", "current_source": "UNKNOWN"}
        fire_tv_info = self.fire_tv.get_status()
        lg_dev, _ = self.bt_helper.scan_active_endpoints()

        proj_on = proj_info.get("power_state") == ProjectorPowerState.ON.value
        source_hdmi1 = proj_info.get("current_source") in [ProjectorSource.HDMI_1.value, "HDMI_1"]
        
        # Check Fire TV Bluetooth health directly from structured status
        if "bluetooth" in fire_tv_info and isinstance(fire_tv_info["bluetooth"], dict):
            fire_tv_bt_ok = bool(fire_tv_info["bluetooth"].get("required_device_connected", False))
        else:
            fire_tv_bt_ok = bool(fire_tv_info.get("bluetooth_connected", False))
            
        soundbar_ok = lg_dev is not None

        is_healthy = proj_on and source_hdmi1 and fire_tv_bt_ok and soundbar_ok

        return {
            "healthy": is_healthy,
            "projector_on": proj_on,
            "projector_source_hdmi1": source_hdmi1,
            "fire_tv": fire_tv_info,
            "soundbar_connected": soundbar_ok,
            "soundbar_name": lg_dev["name"] if lg_dev else None,
            "degradation_reason": None if is_healthy else (
                "Projector OFF" if not proj_on else (
                    "Projector not on HDMI_1" if not source_hdmi1 else (
                        "Fire TV Bluetooth Disconnected" if not fire_tv_bt_ok else "LG Soundbar Disconnected"
                    )
                )
            )
        }

    def get_room_status(self) -> Dict[str, Any]:
        """
        Returns high-level status of the smart room audio system and Movie Mode health.
        """
        player_status = self.player.get_status()
        auth_info = self.resolver.get_auth_status()
        lg_dev, _ = self.bt_helper.scan_active_endpoints()
        movie_health = self.get_movie_mode_health()

        if player_status.get("status") == "PLAYING":
            self._current_state = RoomAudioState.PLAYING
        elif player_status.get("status") == "PAUSED":
            self._current_state = RoomAudioState.PAUSED
        elif lg_dev:
            self._current_state = RoomAudioState.AUDIO_READY
        else:
            if self._current_state not in (RoomAudioState.CONNECTING, RoomAudioState.WAITING_FOR_AUDIO_ENDPOINT):
                self._current_state = RoomAudioState.DISCONNECTED

        return {
            "room_audio_state": self._current_state.value,
            "soundbar_name": lg_dev["name"] if lg_dev else None,
            "soundbar_endpoint_id": lg_dev["id"] if lg_dev else None,
            "is_audio_ready": lg_dev is not None,
            "playback": player_status,
            "authentication": auth_info,
            "device_portal_available": self.bt_helper.device_portal.is_available(),
            "movie_mode_health": movie_health,
            "last_action_duration_ms": self._last_action_duration_ms,
            "last_error": self._last_error
        }

    def connect_soundbar(self, timeout_seconds: float = 12.0) -> Tuple[bool, RoomAudioState, str]:
        """
        Orchestrates soundbar connection:
        1. Checks if already ready.
        2. Dispatches Device Portal connect request.
        3. Polls Windows audio graph for endpoint emergence.
        4. Reports AUDIO_READY or AUDIO_OUTPUT_UNAVAILABLE.
        """
        t0 = time.time()
        logger.info("[ORCHESTRATOR_CONNECT] High-level connect soundbar requested.")

        # Check existing state
        lg_dev, _ = self.bt_helper.scan_active_endpoints()
        if lg_dev:
            self._current_state = RoomAudioState.AUDIO_READY
            self._last_action_duration_ms = int((time.time() - t0) * 1000)
            logger.info(f"[ORCHESTRATOR_ALREADY_READY] Soundbar '{lg_dev['name']}' is already AUDIO_READY.")
            return True, self._current_state, "ALREADY_CONNECTED"

        self._current_state = RoomAudioState.CONNECTING
        dp_success, dp_msg = self.bt_helper.request_device_portal_connect()

        if not dp_success:
            logger.warning(f"[ORCHESTRATOR_CONNECT_FALLBACK] Device Portal returned {dp_msg}, triggering WinRT probe...")
            self.bt_helper.trigger_windows_bluetooth_wake()

        self._current_state = RoomAudioState.WAITING_FOR_AUDIO_ENDPOINT
        while time.time() - t0 < timeout_seconds:
            time.sleep(0.5)
            lg_dev, _ = self.bt_helper.scan_active_endpoints()
            if lg_dev:
                self._current_state = RoomAudioState.AUDIO_READY
                self._last_action_duration_ms = int((time.time() - t0) * 1000)
                logger.info(f"[ORCHESTRATOR_AUDIO_READY] Soundbar '{lg_dev['name']}' became AUDIO_READY in {self._last_action_duration_ms}ms.")
                return True, self._current_state, "AUDIO_READY"

        self._current_state = RoomAudioState.AUDIO_OUTPUT_UNAVAILABLE
        self._last_error = "Connection timed out waiting for audio endpoint"
        self._last_action_duration_ms = int((time.time() - t0) * 1000)
        logger.error(f"[ORCHESTRATOR_CONNECT_TIMEOUT] Connection failed after {self._last_action_duration_ms}ms. Guarding against monitor fallback.")
        return False, self._current_state, "AUDIO_OUTPUT_UNAVAILABLE"

    def disconnect_soundbar(self) -> Tuple[bool, RoomAudioState, str]:
        """
        Orchestrates soundbar disconnection:
        1. Stops active playback.
        2. Dispatches Device Portal disconnect request.
        3. Verifies endpoint disappearance.
        4. Reports DISCONNECTED.
        """
        t0 = time.time()
        logger.info("[ORCHESTRATOR_DISCONNECT] High-level disconnect soundbar requested.")
        self._current_state = RoomAudioState.DISCONNECTING

        # Stop active playback if running
        self.player.stop()

        success, msg, code = self.bt_helper.device_portal.disconnect_lg()
        time.sleep(1.0)

        lg_dev, _ = self.bt_helper.scan_active_endpoints()
        if not lg_dev:
            self._current_state = RoomAudioState.DISCONNECTED
            self._last_action_duration_ms = int((time.time() - t0) * 1000)
            logger.info(f"[ORCHESTRATOR_DISCONNECTED] Soundbar disconnected in {self._last_action_duration_ms}ms.")
            return True, self._current_state, "DISCONNECTED"

        self._current_state = RoomAudioState.AUDIO_READY
        self._last_error = f"Device still in audio graph after disconnect attempt ({msg})"
        self._last_action_duration_ms = int((time.time() - t0) * 1000)
        return False, self._current_state, "DISCONNECT_FAILED"

    def safe_play(
        self,
        title: str,
        artist: Optional[str] = None,
        direct_video_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Safe playback orchestration:
        1. Resolves YouTube Music stream.
        2. Ensures soundbar is in AUDIO_READY state (auto-connecting if necessary).
        3. Binds mpv exclusively to LG WASAPI endpoint.
        4. Returns structured playback result.
        """
        t0 = time.time()
        logger.info(f"[ORCHESTRATOR_PLAY] Safe play requested: title='{title}', artist='{artist}'")

        # 1. Resolve track
        resolved = self.resolver.resolve(title=title, artist=artist, direct_id=direct_video_id)
        if not resolved:
            self._last_error = f"Could not resolve track '{title}'"
            logger.error(f"[ORCHESTRATOR_RESOLVE_FAILED] {self._last_error}")
            return False, {}, self._last_error

        # 2. Check and ensure audio endpoint is ready
        ready, lg_dev, status_code = self.bt_helper.ensure_audio_endpoint()
        if not ready or not lg_dev:
            self._current_state = RoomAudioState.AUDIO_OUTPUT_UNAVAILABLE
            self._last_error = "AUDIO_OUTPUT_UNAVAILABLE"
            logger.error("[ORCHESTRATOR_PLAY_ABORT] Cannot play: soundbar unavailable. Guarding against monitor audio.")
            return False, {
                "room_audio_state": self._current_state.value,
                "audio_output_status": "DISCONNECTED"
            }, "AUDIO_OUTPUT_UNAVAILABLE"

        # 3. Play stream through mpv
        played, error_reason = self.player.play(
            stream_url=resolved.stream_url,
            title=resolved.title,
            artist=resolved.artist,
            duration=resolved.duration,
            thumbnail_url=resolved.thumbnail_url
        )

        st = self.player.get_status()
        self._last_action_duration_ms = int((time.time() - t0) * 1000)

        if not played:
            self._current_state = RoomAudioState.AUDIO_OUTPUT_UNAVAILABLE
            self._last_error = error_reason or "Engine playback failure"
            return False, {
                "room_audio_state": self._current_state.value,
                "audio_output_status": st.get("audio_output_status", "DISCONNECTED")
            }, self._last_error

        self._current_state = RoomAudioState.PLAYING
        logger.info(f"[ORCHESTRATOR_PLAY_CONFIRMED] '{resolved.title}' playing on '{st.get('audio_device_name')}'")
        return True, {
            "room_audio_state": self._current_state.value,
            "title": resolved.title,
            "artist": resolved.artist,
            "duration": resolved.duration,
            "video_id": resolved.video_id,
            "thumbnail_url": resolved.thumbnail_url,
            "audio_output_status": st.get("audio_output_status"),
            "audio_device_id": st.get("audio_device_id"),
            "audio_device_name": st.get("audio_device_name"),
            "is_authenticated": resolved.is_authenticated
        }, None

    def safe_pause(self) -> bool:
        success = self.player.pause()
        if success:
            self._current_state = RoomAudioState.PAUSED
        return success

    def safe_resume(self) -> bool:
        success = self.player.resume()
        if success:
            self._current_state = RoomAudioState.PLAYING
        return success

    def safe_stop(self) -> bool:
        success = self.player.stop()
        lg_dev, _ = self.bt_helper.scan_active_endpoints()
        self._current_state = RoomAudioState.AUDIO_READY if lg_dev else RoomAudioState.DISCONNECTED
        return success

    def safe_set_volume(self, volume: int) -> int:
        return self.player.set_volume(volume)

    def start_movie_mode(self) -> Dict[str, Any]:
        """
        Orchestrates starting Movie Mode:
        1. Stops active PC music playback if running (Resource Arbitration).
        2. Wakes Fire TV.
        3. Ensures Projector is ON and on HDMI_1.
        4. Connects LG SNC4R soundbar.
        5. Validates full room health invariant.
        """
        t0 = time.time()
        logger.info("[ORCHESTRATOR_MOVIE_MODE_START] Starting Movie Mode workflow...")

        # 0. Stop active PC playback to yield audio ownership to Fire TV
        if self.player:
            self.player.stop()

        # 1. Wake Fire TV
        if self.fire_tv:
            self.fire_tv.wake()

        # 2. Ensure Projector is ON and on HDMI_1
        if self.projector:
            pwr = self.projector.get_power_state()
            if pwr.get("power_state") != ProjectorPowerState.ON.value:
                logger.info("[ORCHESTRATOR_MOVIE_MODE] Projector not fully ON, waiting for CEC / wake...")
                time.sleep(2.0)
            self.projector.set_hdmi(1)

        # 3. Connect Soundbar
        self.connect_soundbar(timeout_seconds=8.0)

        # 4. Evaluate Health
        health = self.get_movie_mode_health()
        self._last_action_duration_ms = int((time.time() - t0) * 1000)

        return {
            "status": "HEALTHY" if health["healthy"] else "DEGRADED",
            "health": health,
            "duration_ms": self._last_action_duration_ms
        }

    def stop_movie_mode(self) -> Dict[str, Any]:
        """
        Orchestrates stopping Movie Mode:
        1. Stops PC audio playback.
        2. Safely powers off Projector using verified OEM PowerActivity.
        3. Disconnects Soundbar.
        """
        t0 = time.time()
        logger.info("[ORCHESTRATOR_MOVIE_MODE_STOP] Stopping Movie Mode workflow...")

        self.safe_stop()

        if self.projector:
            try:
                self.projector.power_off()
            except Exception as e:
                logger.error(f"[ORCHESTRATOR_MOVIE_MODE_STOP_ERR] Projector power off error: {e}")

        self.disconnect_soundbar()
        self._last_action_duration_ms = int((time.time() - t0) * 1000)

        return {
            "status": "OFF",
            "duration_ms": self._last_action_duration_ms
        }

