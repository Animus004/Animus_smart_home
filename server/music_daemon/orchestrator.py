"""
Smart Room Orchestrator for Animus PC Daemon.
Provides high-level room audio state management, soundbar connection lifecycle,
deterministic playback queue management with continuous auto-advance, and Movie Mode orchestration.
"""

from enum import Enum
import logging
import threading
import time
from typing import Optional, Dict, Any, Tuple, List

from bluetooth_helper import BluetoothAudioHelper
from device_portal import WindowsDevicePortalBluetooth
from player import MpvPlayer
from queue_manager import PlaybackQueue, QueueTrack
from resolver import YouTubeMusicResolver
from fire_tv_controller import FireTvController, FireTvBluetoothState
from projector_controller import ProjectorController, ProjectorPowerState, ProjectorSource
from fire_tv_capabilities import FireTVCapabilityRegistry, FireTVCapabilityResult, FireTVState
from media_provider_registry import MediaProviderRegistry
from content_resolver import SmartRoomContentResolver, ResolvedContent

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


class RoomState(str, Enum):
    IDLE = "IDLE"
    PC_AUDIO_ACTIVE = "PC_AUDIO_ACTIVE"
    FIRE_TV_READY = "FIRE_TV_READY"
    MOVIE_PREPARING = "MOVIE_PREPARING"
    MOVIE_ACTIVE = "MOVIE_ACTIVE"
    MOVIE_PAUSED = "MOVIE_PAUSED"
    TRANSITIONING_TO_PC = "TRANSITIONING_TO_PC"
    TRANSITIONING_TO_FIRE_TV = "TRANSITIONING_TO_FIRE_TV"
    ERROR_RECOVERY = "ERROR_RECOVERY"


class SmartRoomOrchestrator:
    """
    High-level orchestration service managing room audio, soundbar connectivity,
    deterministic playback queue with EOF auto-advance, projector state,
    Fire TV Bluetooth invariants, and Movie Mode health.
    """
    def __init__(
        self,
        resolver: YouTubeMusicResolver,
        player: MpvPlayer,
        bt_helper: Optional[BluetoothAudioHelper] = None,
        projector: Optional[ProjectorController] = None,
        fire_tv: Optional[FireTvController] = None,
        queue: Optional[PlaybackQueue] = None
    ):
        self.resolver = resolver
        self.player = player
        self.bt_helper = bt_helper or player.bt_helper
        self.projector = projector
        self.fire_tv = fire_tv or FireTvController()
        self.queue = queue or PlaybackQueue(auto_radio=True)

        # Authoritative Provider Registry & Content Resolver
        self.provider_registry = MediaProviderRegistry()
        self.content_resolver = SmartRoomContentResolver(music_resolver=self.resolver, provider_registry=self.provider_registry)

        # Authoritative capability layer
        self.capabilities = FireTVCapabilityRegistry(
            fire_tv=self.fire_tv,
            projector=self.projector,
            bt_helper=self.bt_helper,
            player=self.player,
            provider_registry=self.provider_registry
        )

        self._current_state: RoomAudioState = RoomAudioState.DISCONNECTED
        self._last_error: Optional[str] = None
        self._last_action_duration_ms: int = 0
        self._in_movie_mode: bool = False
        self._in_alarm_mode: bool = False
        self._auto_advance_lock = threading.Lock()

        # Register continuous IPC EOF event callback
        self.player.register_eof_callback(self._handle_player_eof)

    @property
    def current_state(self) -> RoomAudioState:
        return self._current_state

    def _handle_player_eof(self, last_track: Optional[Dict[str, Any]], event_data: Dict[str, Any]):
        """
        Invoked when mpv reaches End Of File on current stream.
        Deterministically advances to the next track in the queue or triggers auto-radio resolution.
        Runs asynchronously in a background thread to prevent blocking the IPC listener.
        """
        logger.info(f"[ORCHESTRATOR_EOF_TRIGGER] Track completed (reason='{event_data.get('reason')}'). Evaluating auto-advance...")

        # 1. Guard against Movie Mode audio hijacking
        if self._in_movie_mode:
            logger.info("[ORCHESTRATOR_EOF_SUPPRESSED] Auto-advance suppressed: Movie Mode is active.")
            return

        # 2. Run auto-advance in a daemon worker thread
        threading.Thread(
            target=self._run_auto_advance_worker,
            args=(last_track,),
            name="AutoAdvanceWorker",
            daemon=True
        ).start()

    def _run_auto_advance_worker(self, last_track: Optional[Dict[str, Any]] = None):
        """Worker executing auto-advance under lock."""
        if not self._auto_advance_lock.acquire(blocking=False):
            logger.info("[ORCHESTRATOR_EOF_CONCURRENT] Auto-advance already in progress.")
            return

        try:
            # Check soundbar endpoint availability
            lg_dev, _ = self.bt_helper.scan_active_endpoints()
            if not lg_dev:
                logger.warning("[ORCHESTRATOR_EOF_ABORT] Cannot auto-advance: Soundbar is disconnected.")
                self._current_state = RoomAudioState.DISCONNECTED
                return

            # Advance to next song in thread-safe queue
            self._advance_next_track(last_track=last_track)
        finally:
            self._auto_advance_lock.release()

    def _advance_next_track(self, last_track: Optional[Dict[str, Any]] = None, max_retries: int = 2):
        """
        Fetches next track from queue or resolves related radio songs, then plays seamlessly.
        """
        next_track = self.queue.pop_next()

        # If queue is empty and auto-radio is enabled, fetch related tracks from seed
        if not next_track and self.queue.auto_radio:
            seed_vid = None
            if last_track and last_track.get("video_id"):
                seed_vid = last_track.get("video_id")
            elif self.queue.current_track and self.queue.current_track.video_id:
                seed_vid = self.queue.current_track.video_id

            if seed_vid:
                logger.info(f"[ORCHESTRATOR_AUTO_RADIO] Queue empty. Resolving related radio tracks for seed video_id={seed_vid}")
                related = self.resolver.get_related_tracks(seed_vid, limit=5)
                if related:
                    queue_tracks = [
                        QueueTrack(
                            video_id=t["video_id"],
                            title=t["title"],
                            artist=t["artist"],
                            duration=t.get("duration"),
                            thumbnail_url=t.get("thumbnail_url"),
                            source="radio"
                        )
                        for t in related
                    ]
                    self.queue.enqueue_multiple(queue_tracks)
                    next_track = self.queue.pop_next()

        if not next_track:
            logger.info("[ORCHESTRATOR_PLAYBACK_FINISHED] No more tracks in queue and auto-radio exhausted.")
            self._current_state = RoomAudioState.AUDIO_READY
            return

        logger.info(f"[ORCHESTRATOR_AUTO_PLAY] Auto-advancing to next track: '{next_track.title}' by '{next_track.artist}' (source={next_track.source})")

        # Resolve streaming URL
        resolved = self.resolver.resolve(
            title=next_track.title,
            artist=next_track.artist,
            direct_id=next_track.video_id
        )

        if not resolved:
            logger.warning(f"[ORCHESTRATOR_AUTO_PLAY_FAIL] Could not resolve '{next_track.title}'. Retrying next track...")
            if max_retries > 0:
                self._advance_next_track(last_track=last_track, max_retries=max_retries - 1)
            return

        # Play track via mpv
        played, error_reason = self.player.play(
            stream_url=resolved.stream_url,
            title=resolved.title,
            artist=resolved.artist,
            duration=resolved.duration,
            thumbnail_url=resolved.thumbnail_url
        )

        if played:
            self.queue.set_current_track(QueueTrack(
                video_id=resolved.video_id,
                title=resolved.title,
                artist=resolved.artist,
                duration=resolved.duration,
                stream_url=resolved.stream_url,
                thumbnail_url=resolved.thumbnail_url,
                is_authenticated=resolved.is_authenticated,
                source=next_track.source
            ))
            # Cache video_id on player's current track dictionary for EOF reference
            if hasattr(self.player, "current_track") and isinstance(self.player.current_track, dict):
                self.player.current_track["video_id"] = resolved.video_id
            self._current_state = RoomAudioState.PLAYING
            logger.info(f"[ORCHESTRATOR_AUTO_PLAY_CONFIRMED] '{resolved.title}' playing on '{self.player._active_audio_device_name}'")
        else:
            logger.error(f"[ORCHESTRATOR_AUTO_PLAY_FAILED] mpv playback failed for '{resolved.title}': {error_reason}")
            if max_retries > 0:
                self._advance_next_track(last_track=last_track, max_retries=max_retries - 1)

    def _prepopulate_radio_queue(self, seed_video_id: str):
        """Pre-fetches related radio tracks in the background to ensure instantaneous queue availability."""
        if self.queue.size() == 0 and self.queue.auto_radio:
            try:
                related = self.resolver.get_related_tracks(seed_video_id, limit=5)
                if related:
                    queue_tracks = [
                        QueueTrack(
                            video_id=t["video_id"],
                            title=t["title"],
                            artist=t["artist"],
                            duration=t.get("duration"),
                            thumbnail_url=t.get("thumbnail_url"),
                            source="radio"
                        )
                        for t in related
                    ]
                    self.queue.enqueue_multiple(queue_tracks)
                    logger.info(f"[ORCHESTRATOR_RADIO_PREPOPULATED] Pre-populated {len(queue_tracks)} upcoming tracks into queue.")
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR_PREPOPULATE_WARN] Could not pre-populate radio queue: {e}")

    def queue_track(
        self,
        title: str,
        artist: Optional[str] = None,
        direct_video_id: Optional[str] = None,
        play_next: bool = False
    ) -> Dict[str, Any]:
        """
        Enqueues a track for future playback.
        """
        track = QueueTrack(
            video_id=direct_video_id or "pending_resolution",
            title=title,
            artist=artist or "Unknown Artist",
            source="manual"
        )
        if play_next:
            new_len = self.queue.enqueue_next(track)
        else:
            new_len = self.queue.enqueue(track)

        return {
            "success": True,
            "title": title,
            "artist": artist,
            "queue_length": new_len,
            "play_next": play_next
        }

    def skip_next(self) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Skips currently playing song and immediately plays the next song from the queue.
        """
        logger.info("[ORCHESTRATOR_SKIP_NEXT] Manual skip next requested.")
        current_track = self.queue.current_track
        last_info = {
            "video_id": current_track.video_id if current_track else None,
            "title": current_track.title if current_track else None
        }
        self.player.stop()
        self._advance_next_track(last_track=last_info)
        st = self.player.get_status()
        return True, {
            "room_audio_state": self._current_state.value,
            "title": st.get("title"),
            "artist": st.get("artist"),
            "queue_length": self.queue.size()
        }, None

    def skip_previous(self) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Plays previous song from history if available.
        """
        logger.info("[ORCHESTRATOR_SKIP_PREV] Manual skip previous requested.")
        prev_track = self.queue.pop_previous()
        if not prev_track:
            return False, {}, "No previous track in history"

        self.player.stop()
        return self.safe_play(
            title=prev_track.title,
            artist=prev_track.artist,
            direct_video_id=prev_track.video_id if prev_track.video_id != "pending_resolution" else None
        )

    def clear_queue(self) -> Dict[str, Any]:
        self.queue.clear()
        return {"success": True, "message": "Queue cleared"}

    def get_queue_status(self) -> Dict[str, Any]:
        return self.queue.get_status()

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

        soundbar_ok = fire_tv_bt_ok or (lg_dev is not None)
        is_healthy = proj_on and source_hdmi1 and fire_tv_bt_ok

        return {
            "healthy": is_healthy,
            "projector_on": proj_on,
            "projector_source_hdmi1": source_hdmi1,
            "fire_tv": fire_tv_info,
            "soundbar_connected": soundbar_ok,
            "soundbar_name": "Speakers (LG SNC4R(79))" if soundbar_ok else None,
            "degradation_reason": None if is_healthy else (
                "Projector OFF" if not proj_on else (
                    "Projector not on HDMI_1" if not source_hdmi1 else "Fire TV Bluetooth Disconnected"
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
        queue_status = self.get_queue_status()

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
            "queue": queue_status,
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
        4. Enrolls track in deterministic PlaybackQueue.
        5. Returns structured playback result.
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

        # 4. Set active track in PlaybackQueue
        self.queue.set_current_track(QueueTrack(
            video_id=resolved.video_id,
            title=resolved.title,
            artist=resolved.artist,
            duration=resolved.duration,
            stream_url=resolved.stream_url,
            thumbnail_url=resolved.thumbnail_url,
            is_authenticated=resolved.is_authenticated,
            source="manual"
        ))
        if hasattr(self.player, "current_track") and isinstance(self.player.current_track, dict):
            self.player.current_track["video_id"] = resolved.video_id

        # 5. Eagerly pre-populate upcoming radio tracks into the queue in background
        if self.queue.auto_radio and resolved.video_id:
            threading.Thread(
                target=self._prepopulate_radio_queue,
                args=(resolved.video_id,),
                name="RadioQueuePrepopulateWorker",
                daemon=True
            ).start()

        self._current_state = RoomAudioState.PLAYING
        logger.info(f"[ORCHESTRATOR_PLAY_CONFIRMED] '{resolved.title}' playing on '{st.get('audio_device_name')}'")
        return True, {
            "room_audio_state": self._current_state.value,
            "title": resolved.title,
            "artist": resolved.artist,
            "duration": resolved.duration,
            "video_id": resolved.video_id,
            "thumbnail_url": resolved.thumbnail_url,
            "audio_output_status": st.get("audio_output_status") or (status_code if status_code else "CONNECTED"),
            "audio_device_id": st.get("audio_device_id") or (lg_dev.get("id") if isinstance(lg_dev, dict) else None),
            "audio_device_name": st.get("audio_device_name") or (lg_dev.get("name") if isinstance(lg_dev, dict) else None),
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

    def start_movie_mode(self, content: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Orchestrates starting Movie Mode by consuming the authoritative capability layer:
        1. Authoritative Pre-Flight Check: Validates Projector is ON.
           If Projector is OFF (and cannot be powered on automatically), fails gracefully
           with PROJECTOR_OFF_REQUIRES_MANUAL_ACTION without hijacking audio or waking Fire TV.
        2. Sets _in_movie_mode = True to suppress background music auto-advance.
        3. Releases PC audio ownership and transfers to Fire TV (LG SNC4R connection).
        4. Wakes Fire TV via capability.
        5. Switches Projector to HDMI_1 via capability.
        6. Resolves content: prioritizes direct video ID/provider launch (< 250ms), fallback to UI search.
        7. Validates full room health invariant.
        """
        t0 = time.time()
        logger.info(f"[ORCHESTRATOR_MOVIE_MODE_START] Starting Movie Mode workflow (content='{content}', provider='{provider}')...")

        # 0. Pre-Flight Physical Check: Projector Power State
        if self.projector:
            pwr = self.projector.get_power_state()
            if pwr.get("power_state") != ProjectorPowerState.ON.value:
                logger.warning(
                    f"[ORCHESTRATOR_MOVIE_MODE_BLOCKED] Projector is {pwr.get('power_state')}. "
                    "Cannot power on automatically. Aborting Movie Mode safely."
                )
                self._last_action_duration_ms = int((time.time() - t0) * 1000)
                feedback_msg = "The projector is currently off. I can't turn it on right now. Please turn on the projector manually."
                return {
                    "status": "PROJECTOR_OFF_REQUIRES_MANUAL_ACTION",
                    "success": False,
                    "content": content,
                    "content_launched": False,
                    "spoken_response": feedback_msg,
                    "message": feedback_msg,
                    "health": {
                        "healthy": False,
                        "projector_on": False,
                        "projector_source_hdmi1": False,
                        "fire_tv": self.fire_tv.get_status() if self.fire_tv else {},
                        "soundbar_connected": False,
                        "degradation_reason": "PROJECTOR_OFF_REQUIRES_MANUAL_ACTION"
                    },
                    "duration_ms": self._last_action_duration_ms
                }

        self._in_movie_mode = True

        # 1. Release PC audio ownership and stop active playback
        self.disconnect_soundbar()

        # 2. Wake Fire TV
        if self.fire_tv:
            self.fire_tv.wake()

        # 3. Ensure Projector is on HDMI_1
        if self.projector:
            self.projector.set_hdmi(1)

        # 4. Connect Fire TV to Soundbar
        if self.fire_tv:
            self.fire_tv.connect_soundbar(timeout_seconds=6.0)

        # 5. Launch content on Fire TV if title requested
        content_launched = False
        launch_type = None
        resolved_details = {}

        if content:
            # Resolve content target
            resolved = self.content_resolver.resolve_content(content, explicit_provider=provider)
            resolved_details = {
                "provider": resolved.provider_id,
                "resolution_type": resolved.resolution_type,
                "content_id": resolved.content_id,
                "confidence": resolved.confidence
            }

            if resolved.resolution_type == "DIRECT_VIDEO_ID" and self.capabilities:
                res = self.capabilities.play_youtube_video_id(resolved.content_id)
                content_launched = res.success
                launch_type = "DIRECT_VIDEO_AUTOPLAY"
            elif resolved.resolution_type in ("DIRECT_URI", "PROVIDER_DETAILS") and self.capabilities:
                res = self.capabilities.launch_streaming_provider(resolved.provider_id, resolved.direct_uri or resolved.content_id)
                content_launched = res.success
                launch_type = res.details.get("launch_status", "PROVIDER_DIRECT_LAUNCH")
            else:
                # Search fallback
                if self.fire_tv:
                    content_launched = self.fire_tv.search_or_launch_content(resolved.title or content)
                    launch_type = "SEARCH_UI_FALLBACK"

        # 6. Evaluate Health & Invariants
        health = self.get_movie_mode_health()
        if content and not content_launched:
            health["healthy"] = False
            health["content_launched"] = False
            if not health.get("degradation_reason"):
                health["degradation_reason"] = "Content Launch Failed"

        is_success = health["healthy"] and (not content or content_launched)
        self._last_action_duration_ms = int((time.time() - t0) * 1000)

        return {
            "status": "HEALTHY" if is_success else "DEGRADED",
            "success": is_success,
            "content": content,
            "content_launched": content_launched,
            "launch_type": launch_type,
            "resolution": resolved_details if content else None,
            "spoken_response": f"Starting Movie Mode for '{content}'" if content else "Starting Movie Mode",
            "message": f"Starting Movie Mode for '{content}'" if content else "Starting Movie Mode",
            "health": health,
            "duration_ms": self._last_action_duration_ms
        }

    def stop_movie_mode(self) -> Dict[str, Any]:
        """
        Orchestrates stopping Movie Mode:
        1. Re-enables PC music capability (_in_movie_mode = False).
        2. Sends home to Fire TV to release content.
        3. Stops PC audio playback.
        4. Safely powers off Projector using verified OEM PowerActivity.
        5. Disconnects Soundbar and verifies room state.
        """
        t0 = time.time()
        logger.info("[ORCHESTRATOR_MOVIE_MODE_STOP] Stopping Movie Mode workflow...")
        self._in_movie_mode = False

        if self.capabilities:
            try:
                self.capabilities.home()
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR_MOVIE_MODE_STOP] Fire TV home capability error: {e}")
        elif self.fire_tv:
            try:
                self.fire_tv.home()
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR_MOVIE_MODE_STOP] Fire TV home event ignored: {e}")

        self.safe_stop()

        if self.projector:
            try:
                self.projector.power_off()
            except Exception as e:
                logger.warning(f"[ORCHESTRATOR_MOVIE_MODE_STOP_ERR] Projector power off: {e}")

        self.disconnect_soundbar()
        self._last_action_duration_ms = int((time.time() - t0) * 1000)

        return {
            "success": True,
            "status": "OFF",
            "message": "Movie Mode stopped. Audio returned to the computer.",
            "spoken_response": "Movie Mode stopped. Audio returned to the computer.",
            "duration_ms": self._last_action_duration_ms
        }

    def fire_tv_playback_control(self, action: str) -> Dict[str, Any]:
        """
        Dispatches media playback transport controls (PLAY, PAUSE, TOGGLE, STOP, NEXT, PREVIOUS, VOLUME_UP, VOLUME_DOWN, MUTE)
        to Fire TV active media session.
        """
        act = action.strip().upper()
        if not self.capabilities:
            return {"success": False, "action": act, "error": "Fire TV capability layer not initialized"}

        action_map = {
            "PLAY": self.capabilities.play,
            "PAUSE": self.capabilities.pause,
            "TOGGLE": self.capabilities.toggle_play_pause,
            "STOP": self.capabilities.stop,
            "NEXT": self.capabilities.next_track,
            "PREVIOUS": self.capabilities.previous_track,
            "VOLUME_UP": self.capabilities.volume_up,
            "VOLUME_DOWN": self.capabilities.volume_down,
            "MUTE": self.capabilities.mute
        }

        handler = action_map.get(act)
        if not handler:
            return {"success": False, "action": act, "error": f"Unsupported playback action '{act}'"}

        res = handler()
        return {
            "success": res.success,
            "action": act,
            "message": res.message,
            "duration_ms": res.duration_ms,
            "details": res.details
        }

    def start_alarm(self) -> Dict[str, Any]:
        """
        Starts PC Alarm Audio:
        1. Checks Movie Mode invariant: if Movie Mode is active, refuse or yield so Movie Mode audio is not corrupted.
        2. Sets _in_alarm_mode = True.
        3. Plays alarm audio stream on connected Soundbar or PC system audio.
        """
        if self._in_movie_mode:
            logger.warning("[ORCHESTRATOR_ALARM_BLOCKED] Movie Mode is active. Yielding PC alarm to Android fallback.")
            return {
                "success": False,
                "status": "MOVIE_MODE_ACTIVE_BLOCKED",
                "message": "PC alarm deferred: Movie Mode owns soundbar."
            }

        self._in_alarm_mode = True
        alarm_url = "https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg"
        success, err = self.player.play(
            stream_url=alarm_url,
            title="Morning Alarm Chime",
            artist="Animus Smart Room",
            duration=60
        )
        st = self.player.get_status()
        self._current_state = RoomAudioState.PLAYING if success else self._current_state
        return {
            "success": success,
            "status": "PLAYING" if success else "FAILED",
            "source": "PC_DAEMON",
            "audio_device_name": st.get("audio_device_name"),
            "error": err
        }

    def stop_alarm(self) -> Dict[str, Any]:
        """
        Stops PC Alarm Audio.
        """
        self._in_alarm_mode = False
        success = self.safe_stop()
        return {
            "success": True,
            "status": "STOPPED",
            "source": "PC_DAEMON"
        }

    def get_alarm_status(self) -> Dict[str, Any]:
        return {
            "is_alarm_playing": self._in_alarm_mode and self.player.get_status().get("playback_status") == "PLAYING",
            "source": "PC_DAEMON"
        }

    # =========================================================================
    # REUSABLE SMART ROOM HIGH-VALUE AUTOMATIONS (PHASE 8 & 9)
    # =========================================================================

    def get_room_state(self) -> Dict[str, Any]:
        """
        Calculates and returns the authoritative RoomState across PC, Fire TV, Soundbar, and Projector.
        """
        p_status = self.player.get_status()
        lg_dev, _ = self.bt_helper.scan_active_endpoints() if self.bt_helper else (None, [])
        ftv_bt = self.fire_tv.get_bluetooth_status() if self.fire_tv else {}
        ftv_bt_connected = ftv_bt.get("required_device_connected", False)

        if self._in_movie_mode:
            ftv_ms = self.fire_tv.get_state() if hasattr(self.fire_tv, "get_state") else None
            # Check if paused
            state = RoomState.MOVIE_ACTIVE
        elif p_status.get("playback_status") == "PLAYING":
            state = RoomState.PC_AUDIO_ACTIVE
        elif ftv_bt_connected:
            state = RoomState.FIRE_TV_READY
        elif lg_dev:
            state = RoomState.IDLE
        else:
            state = RoomState.IDLE

        return {
            "room_state": state.value,
            "in_movie_mode": self._in_movie_mode,
            "pc_audio_playing": p_status.get("playback_status") == "PLAYING",
            "pc_soundbar_connected": lg_dev is not None,
            "fire_tv_soundbar_connected": ftv_bt_connected,
            "room_audio_state": self._current_state.value
        }

    # 1. StartMovieDirect
    def start_movie_direct(self, content: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        return self.start_movie_mode(content=content, provider=provider)

    # 2. StopMovieMode (Already defined as self.stop_movie_mode())

    # 3. PauseMovie
    def pause_movie(self) -> Dict[str, Any]:
        return self.fire_tv_playback_control("PAUSE")

    # 4. ResumeMovie
    def resume_movie(self) -> Dict[str, Any]:
        return self.fire_tv_playback_control("PLAY")

    # 5. SwitchMovieProvider
    def switch_movie_provider(self, provider: str, content: Optional[str] = None) -> Dict[str, Any]:
        if not self.capabilities:
            return {"success": False, "error": "Capabilities layer uninitialized"}
        res = self.capabilities.launch_streaming_provider(provider, content or "")
        return {"success": res.success, "provider": provider, "content": content, "details": res.details}

    # 6. WatchYouTubeContent
    def watch_youtube_content(self, query: str) -> Dict[str, Any]:
        return self.start_movie_mode(content=query, provider="youtube")

    # 7. WatchNetflixContent
    def watch_netflix_content(self, title: str) -> Dict[str, Any]:
        return self.start_movie_mode(content=title, provider="netflix")

    # 8. WatchPrimeContent
    def watch_prime_content(self, title: str) -> Dict[str, Any]:
        return self.start_movie_mode(content=title, provider="prime_video")

    # 9. WatchAppleTVContent
    def watch_apple_tv_content(self, title: str) -> Dict[str, Any]:
        return self.start_movie_mode(content=title, provider="apple_tv")

    # 10. WatchHotstarContent
    def watch_hotstar_content(self, title: str) -> Dict[str, Any]:
        return self.start_movie_mode(content=title, provider="hotstar")

    # 11. WatchZee5Content
    def watch_zee5_content(self, title: str) -> Dict[str, Any]:
        return self.start_movie_mode(content=title, provider="zee5")

    # 12. RouteAudioToFireTV
    def route_audio_to_fire_tv(self) -> Dict[str, Any]:
        self.disconnect_soundbar()
        if self.fire_tv:
            ok, method = self.fire_tv.connect_soundbar_with_method(timeout_seconds=6.0)
            return {"success": ok, "method": method, "target": "FIRE_TV"}
        return {"success": False, "error": "Fire TV uninitialized"}

    transfer_audio_to_fire_tv = route_audio_to_fire_tv

    # 13. RouteAudioToPC
    def route_audio_to_pc(self) -> Dict[str, Any]:
        if self.fire_tv:
            self.fire_tv.disconnect_soundbar(timeout_seconds=3.0)
        ok, state, msg = self.connect_soundbar(timeout_seconds=12.0)
        return {"success": ok, "room_audio_state": state.value, "target": "PC"}

    restore_audio_to_pc = route_audio_to_pc

    # 14. RecoverSoundbarConnection
    def recover_soundbar_connection(self, target: str = "PC") -> Dict[str, Any]:
        if target.upper() == "FIRE_TV":
            return self.route_audio_to_fire_tv()
        return self.route_audio_to_pc()

    # 15. RecoverFireTVConnection
    def recover_fire_tv_connection(self) -> Dict[str, Any]:
        if not self.fire_tv:
            return {"success": False, "error": "Fire TV uninitialized"}
        res = self.capabilities.check_connectivity() if self.capabilities else None
        return {"success": res.success if res else False, "details": res.details if res else {}}

    # 16. ProjectorFireTVMode
    def projector_fire_tv_mode(self) -> Dict[str, Any]:
        if self.projector:
            ok = self.projector.set_hdmi(1)
            return {"success": ok, "source": "HDMI_1"}
        return {"success": False, "error": "Projector uninitialized"}

    # 17. ProjectorPCMode
    def projector_pc_mode(self) -> Dict[str, Any]:
        if self.projector:
            ok = self.projector.set_hdmi(2)
            return {"success": ok, "source": "HDMI_2"}
        return {"success": False, "error": "Projector uninitialized"}

    # 18. SafeProjectorShutdown
    def safe_projector_shutdown(self) -> Dict[str, Any]:
        if self.projector:
            ok = self.projector.power_off()
            return {"success": ok, "power_state": "OFF"}
        return {"success": False, "error": "Projector uninitialized"}

    # 19. MusicToMovieTransition
    def music_to_movie_transition(self, content: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        self.safe_stop()
        return self.start_movie_mode(content=content, provider=provider)

    # 20. MovieToMusicTransition
    def movie_to_music_transition(self, song_query: str) -> Dict[str, Any]:
        self.stop_movie_mode()
        ok, res, err = self.safe_play(title=song_query)
        return {"success": ok, "track": res, "error": err}

    # 21. QuickBreak
    def quick_break(self) -> Dict[str, Any]:
        return self.fire_tv_playback_control("PAUSE")

    # 22. ResumeAfterBreak
    def resume_after_break(self) -> Dict[str, Any]:
        return self.fire_tv_playback_control("PLAY")

    # 23. Goodnight
    def goodnight_automation(self) -> Dict[str, Any]:
        self.stop_movie_mode()
        self.safe_stop()
        if self.fire_tv:
            self.fire_tv.sleep()
        if self.projector:
            self.projector.power_off()
        self.disconnect_soundbar()
        return {"success": True, "action": "GOODNIGHT_COMPLETE"}

    # 24. LeavingHome
    def leaving_home(self) -> Dict[str, Any]:
        return self.goodnight_automation()

    # 25. ArrivingHome
    def arriving_home(self) -> Dict[str, Any]:
        if self.fire_tv:
            self.fire_tv.wake()
        self.connect_soundbar(timeout_seconds=8.0)
        return {"success": True, "action": "ARRIVING_HOME_READY"}

    # 26. EmergencyMute
    def emergency_mute(self) -> Dict[str, Any]:
        self.player.set_volume(0)
        if self.capabilities:
            self.capabilities.mute()
        return {"success": True, "action": "EMERGENCY_MUTE"}

    # 27. RecoverAudio
    def recover_audio(self) -> Dict[str, Any]:
        return self.route_audio_to_pc()

    # 28. RecoverProjectorHDMI
    def recover_projector_hdmi(self) -> Dict[str, Any]:
        return self.projector_fire_tv_mode()

    # 29. RecoverADB
    def recover_adb(self) -> Dict[str, Any]:
        return self.recover_fire_tv_connection()

    # 30. TruthfulRoomStateSync
    def truthful_room_state_sync(self) -> Dict[str, Any]:
        return self.get_room_state()

    def execute_automation(self, automation_name: str, **kwargs) -> Dict[str, Any]:
        """
        Dispatches any named room automation dynamically.
        """
        automation_name_clean = automation_name.strip().lower().replace("_", "").replace("-", "")
        method_map = {
            "startmoviedirect": lambda: self.start_movie_direct(kwargs.get("content"), kwargs.get("provider")),
            "startmoviemode": lambda: self.start_movie_mode(kwargs.get("content"), kwargs.get("provider")),
            "stopmoviemode": self.stop_movie_mode,
            "pausemovie": self.pause_movie,
            "resumemovie": self.resume_movie,
            "switchmovieprovider": lambda: self.switch_movie_provider(kwargs.get("provider", "youtube"), kwargs.get("content")),
            "watchyoutubecontent": lambda: self.watch_youtube_content(kwargs.get("query", "")),
            "watchnetflixcontent": lambda: self.watch_netflix_content(kwargs.get("title", "")),
            "watchprimecontent": lambda: self.watch_prime_content(kwargs.get("title", "")),
            "watchappletvcontent": lambda: self.watch_apple_tv_content(kwargs.get("title", "")),
            "watchhotstarcontent": lambda: self.watch_hotstar_content(kwargs.get("title", "")),
            "watchzee5content": lambda: self.watch_zee5_content(kwargs.get("title", "")),
            "routeaudiotofiretv": self.route_audio_to_fire_tv,
            "routeaudiotopc": self.route_audio_to_pc,
            "recoversoundbarconnection": lambda: self.recover_soundbar_connection(kwargs.get("target", "PC")),
            "recoverfiretvconnection": self.recover_fire_tv_connection,
            "projectorfiretvmode": self.projector_fire_tv_mode,
            "projectorpcmode": self.projector_pc_mode,
            "safeprojectorshutdown": self.safe_projector_shutdown,
            "musictomovietransition": lambda: self.music_to_movie_transition(kwargs.get("content"), kwargs.get("provider")),
            "movietomusictransition": lambda: self.movie_to_music_transition(kwargs.get("song_query", "")),
            "quickbreak": self.quick_break,
            "resumeafterbreak": self.resume_after_break,
            "goodnight": self.goodnight_automation,
            "leavinghome": self.leaving_home,
            "arrivinghome": self.arriving_home,
            "emergencymute": self.emergency_mute,
            "recoveraudio": self.recover_audio,
            "recoverprojectorhdmi": self.recover_projector_hdmi,
            "recoveradb": self.recover_adb,
            "truthfulroomstatesync": self.truthful_room_state_sync,
        }

        handler = method_map.get(automation_name_clean)
        if not handler:
            return {"success": False, "error": f"Unknown automation: {automation_name}"}

        return handler()
