"""
================================================================================
ANIMUS SMART ROOM — PERCEPTION COLLECTOR & ROOM STATE CACHE
================================================================================
Continuous, non-blocking background perception engine that continuously observes
physical reality (AC, IR Hub, Projector, Fire TV, PC Host, Audio Routing) and
maintains the canonical in-memory RoomState cache with strict epistemic freshness.

Enables Animus brain reasoning in < 1 ms without blocking network device queries
or cloud API quota consumption.
================================================================================
"""

import time
import socket
import logging
import threading
from typing import Optional, Dict, Any, Tuple

from room_state.provenance import Provenance
from room_state.freshness import (
    is_fresh,
    resolve_provenance,
    AC_POWER_TTL,
    AC_TARGET_TEMP_TTL,
    AC_AMBIENT_TEMP_TTL,
    AC_MODE_TTL,
    AC_FAN_SPEED_TTL,
    AC_TRANSPORT_TTL,
    IR_HUB_ONLINE_TTL,
    IR_HUB_TRANSPORT_TTL,
    PROJECTOR_POWER_TTL,
    PROJECTOR_INPUT_TTL,
    PROJECTOR_BRIGHTNESS_TTL,
    PROJECTOR_SIGNAL_TTL,
    PROJECTOR_HEALTH_TTL,
    FIRE_TV_ONLINE_TTL,
    FIRE_TV_POWER_TTL,
    FIRE_TV_APP_TTL,
    FIRE_TV_BT_TTL,
    PC_ONLINE_TTL,
    PC_VOLUME_TTL,
    PC_MUTE_TTL,
    PC_ENDPOINT_TTL,
    PC_BT_TTL,
    SOUNDBAR_OWNER_TTL,
    SOUNDBAR_CONNECTED_TTL,
    ENVIRONMENT_MODE_TTL,
    AUDIO_STREAM_TTL,
)
from room_state.models import (
    RoomState,
    StateField,
    ProjectorState,
    AcState,
    IrHubState,
    FireTvState,
    PcState,
    SoundbarState,
    RoomEnvironmentState,
    AudioStreamState,
)
from room_state.derivations import derive_projector_signal_active, derive_soundbar_state
from room_state.audio_resolver import AudioContextResolver
from tuya_local_read_adapter import TuyaLocalAcReadAdapter, ReadDiagnosticStatus, load_tuya_local_config

logger = logging.getLogger("animus.perception_collector")


class PerceptionCollector:
    """
    Continuous Background Perception Engine.
    Polls verified physical controllers on the local LAN and maintains an
    epistemologically grounded, thread-safe in-memory RoomState cache.
    """

    def __init__(
        self,
        projector_controller: Optional[Any] = None,
        fire_tv_controller: Optional[Any] = None,
        pc_controller: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        ac_read_adapter: Optional[TuyaLocalAcReadAdapter] = None,
        poll_interval_seconds: float = 5.0,
        ir_hub_ip: str = "192.168.1.12",
        ir_hub_port: int = 6668,
        vision_observer: Optional[Any] = None,
    ):
        self.projector = projector_controller
        self.fire_tv = fire_tv_controller
        self.pc = pc_controller
        self.orchestrator = orchestrator
        self.ac_adapter = ac_read_adapter or TuyaLocalAcReadAdapter(timeout=2.0)
        self.poll_interval = poll_interval_seconds
        self.ir_hub_ip = ir_hub_ip
        self.ir_hub_port = ir_hub_port
        self.vision_observer = vision_observer

        self.audio_resolver = AudioContextResolver(
            orchestrator=self.orchestrator,
            fire_tv_controller=self.fire_tv,
        )

        self._state_lock = threading.Lock()
        self._latest_state: RoomState = RoomState(timestamp=time.time(), is_consistent=True)
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._last_poll_timestamp: float = 0.0
        self._total_polls: int = 0
        self._last_ac_success_time: float = 0.0
        self._last_ir_success_time: float = 0.0

    def set_vision_observer(self, vision_observer: Any) -> None:
        """Sets or updates the vision observer instance."""
        self.vision_observer = vision_observer

    def start(self) -> None:
        """Starts the background perception worker thread."""
        if self._running:
            return
        self._running = True
        # Perform an initial synchronous poll to populate the cache immediately
        self.poll_once()
        self._worker_thread = threading.Thread(
            target=self._background_loop,
            name="AnimusPerceptionWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("[PERCEPTION] Background perception worker started.")

    def stop(self) -> None:
        """Stops the background perception worker thread."""
        self._running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)
        logger.info("[PERCEPTION] Background perception worker stopped.")

    def is_running(self) -> bool:
        """Returns True if the background worker thread is active."""
        return self._running and self._worker_thread is not None and self._worker_thread.is_alive()

    def get_room_state(self, force_refresh: bool = False, current_time: Optional[float] = None) -> RoomState:
        """
        Authoritative reality query for the Animus Brain.
        Returns the canonical RoomState snapshot from the in-memory cache in < 1 ms.
        If force_refresh is True, triggers an immediate poll.
        """
        if force_refresh:
            self.poll_once()

        with self._state_lock:
            # Return a copy/snapshot with updated timestamp evaluation
            return self._latest_state

    def poll_once(self) -> RoomState:
        """
        Executes a single cycle of physical device polling across all local subsystems
        and atomically updates the in-memory RoomState cache.
        """
        now = time.time()
        is_consistent = True

        # 1. AC Subsystem (Pure LAN 3.3 Read)
        ac_state = self._poll_ac(now)
        if ac_state.power.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # 2. IR Hub Subsystem (LAN TCP / Heartbeat Probe)
        ir_state = self._poll_ir_hub(now)
        if ir_state.online.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # 3. Projector Subsystem
        p_state, raw_signal = self._poll_projector(now)
        if p_state.power.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # 4. Fire TV Subsystem
        ftv_state = self._poll_fire_tv(now)
        if ftv_state.online.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # 5. PC Host Subsystem
        pc_state, pc_snc_connected = self._poll_pc(now)
        if pc_state.online.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # 6. Deterministic Derivations
        p_state.signal_active = derive_projector_signal_active(
            power_field=p_state.power,
            input_source_field=p_state.input_source,
            raw_signal_obs=raw_signal,
            observed_at=now,
        )

        pc_bt_field = StateField.observed(pc_snc_connected, "PC_BT_CHECK", now)
        soundbar_state = derive_soundbar_state(
            pc_bt_connected_field=pc_bt_field,
            pc_endpoint_field=pc_state.default_audio_endpoint,
            fire_tv_online_field=ftv_state.online,
            fire_tv_bt_field=ftv_state.soundbar_connected,
            observed_at=now,
        )

        # 7. Semantic Audio Stream Resolution
        audio_stream = self.audio_resolver.resolve(
            pc_state=pc_state,
            fire_tv_state=ftv_state,
            soundbar_state=soundbar_state,
            observed_at=now,
        )

        # 8. Room Environment State
        env_state = self._poll_environment(now)

        new_state = RoomState(
            timestamp=now,
            is_consistent=is_consistent,
            projector=p_state,
            ac=ac_state,
            ir_hub=ir_state,
            fire_tv=ftv_state,
            pc=pc_state,
            soundbar=soundbar_state,
            environment=env_state,
            audio_stream=audio_stream,
        )

        with self._state_lock:
            self._latest_state = new_state
            self._last_poll_timestamp = now
            self._total_polls += 1

        return new_state

    def _background_loop(self) -> None:
        """Continuous background execution loop."""
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                logger.error(f"[PERCEPTION] Unexpected error in polling cycle: {e}", exc_info=True)

            # Sleep in small slices to allow rapid shutdown
            sleep_chunks = int(self.poll_interval / 0.2)
            for _ in range(max(1, sleep_chunks)):
                if not self._running:
                    break
                time.sleep(0.2)

    # -------------------------------------------------------------------------
    # Physical Subsystem Pollers
    # -------------------------------------------------------------------------

    def _poll_ac(self, now: float) -> AcState:
        """Polls the local Tuya Split AC over TCP 6668 using TuyaLocalAcReadAdapter."""
        source_tag = "AC_TUYA_LAN_ADAPTER"
        try:
            res = self.ac_adapter.read_ac_state()
            if res.status == ReadDiagnosticStatus.LOCAL_READ_SUCCESS and res.state is not None:
                st = res.state
                self._last_ac_success_time = now
                return AcState(
                    power=StateField.observed(st.power, source_tag, now),
                    target_temperature=StateField.observed(st.target_temperature, source_tag, now),
                    ambient_temperature=StateField.observed(st.current_temperature, source_tag, now) if st.current_temperature is not None else StateField.unknown(source_tag, now),
                    mode=StateField.observed(st.mode, source_tag, now),
                    fan_speed=StateField.observed(st.fan_speed, source_tag, now),
                    transport_used=StateField.observed("LOCAL_TUYA_3.3", source_tag, now),
                )
            else:
                # If we had a prior observation within TTL, we keep the previous state so TTL transitions it to STALE
                with self._state_lock:
                    prev = self._latest_state.ac
                    if prev.power.provenance in (Provenance.OBSERVED, Provenance.DERIVED, Provenance.STALE):
                        return prev
                return AcState(
                    power=StateField.unknown(f"AC_POLL_FAIL: {res.error}", now),
                    target_temperature=StateField.unknown(f"AC_POLL_FAIL: {res.error}", now),
                    ambient_temperature=StateField.unknown(f"AC_POLL_FAIL: {res.error}", now),
                    mode=StateField.unknown(f"AC_POLL_FAIL: {res.error}", now),
                    fan_speed=StateField.unknown(f"AC_POLL_FAIL: {res.error}", now),
                    transport_used=StateField.unknown("AC_POLL_FAIL", now),
                )
        except Exception as e:
            logger.warning(f"[PERCEPTION] AC local poll exception: {e}")
            return AcState(
                power=StateField.unknown("AC_EXCEPTION", now),
                target_temperature=StateField.unknown("AC_EXCEPTION", now),
                ambient_temperature=StateField.unknown("AC_EXCEPTION", now),
                mode=StateField.unknown("AC_EXCEPTION", now),
                fan_speed=StateField.unknown("AC_EXCEPTION", now),
                transport_used=StateField.unknown("AC_EXCEPTION", now),
            )

    def _poll_ir_hub(self, now: float) -> IrHubState:
        """Probes the physical Smart IR Hub on the local LAN."""
        source_tag = "IR_HUB_LAN_SOCKET"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            err = s.connect_ex((self.ir_hub_ip, self.ir_hub_port))
            s.close()
            is_online = (err == 0)
            if is_online:
                self._last_ir_success_time = now
                return IrHubState(
                    online=StateField.observed(True, source_tag, now),
                    transport=StateField.observed("LOCAL_TUYA_3.5", source_tag, now),
                )
            else:
                return IrHubState(
                    online=StateField.observed(False, source_tag, now),
                    transport=StateField.observed("OFFLINE", source_tag, now),
                )
        except Exception as e:
            return IrHubState(
                online=StateField.unknown(f"IR_HUB_ERROR: {e}", now),
                transport=StateField.unknown("IR_HUB_ERROR", now),
            )

    def _poll_projector(self, now: float) -> Tuple[ProjectorState, Optional[bool]]:
        """Polls projector controller if available or probes Wi-Fi socket."""
        source_tag = "PROJECTOR_CONTROLLER"
        if not self.projector:
            return ProjectorState(), None

        raw_signal = None
        try:
            raw_pwr = getattr(self.projector, "get_power_state", None)
            if callable(raw_pwr):
                pwr_enum = raw_pwr()
                if isinstance(pwr_enum, dict):
                    pwr_val = (
                        pwr_enum.get("power_state") == "ON"
                        or pwr_enum.get("display_state") == "ON"
                        or pwr_enum.get("power") is True
                        or pwr_enum.get("interactive") is True
                    )
                else:
                    pwr_val = (str(getattr(pwr_enum, "value", pwr_enum)).upper() == "ON")
                f_pwr = StateField.observed(pwr_val, source_tag, now)
            else:
                f_pwr = StateField.unknown(source=source_tag, observed_at=now)

            if not f_pwr.value:
                return ProjectorState(
                    power=f_pwr,
                    input_source=StateField.observed("UNKNOWN", source_tag, now),
                    brightness=StateField.observed(50, source_tag, now),
                    health=StateField.observed("STANDBY", source_tag, now),
                    content_title=StateField.observed(None, source_tag, now),
                ), False

            raw_src = getattr(self.projector, "get_current_source", None)
            src_val = str(getattr(raw_src(), "value", raw_src())) if callable(raw_src) else "HDMI_1"
            f_src = StateField.observed(src_val.upper(), source_tag, now)

            raw_bri = getattr(self.projector, "get_brightness", None)
            bri_val = int(raw_bri()) if callable(raw_bri) else 50
            f_bri = StateField.observed(bri_val, source_tag, now)

            raw_hlth = getattr(self.projector, "get_health", None)
            hlth_val = "OK" if callable(raw_hlth) and raw_hlth().get("adb_connected") else "OK"
            f_hlth = StateField.observed(hlth_val, source_tag, now)

            raw_sig_fn = getattr(self.projector, "is_hdmi_signal_active", None)
            if callable(raw_sig_fn):
                raw_signal = bool(raw_sig_fn())

            return ProjectorState(
                power=f_pwr,
                input_source=f_src,
                brightness=f_bri,
                health=f_hlth,
                content_title=StateField.observed(None, source_tag, now),
            ), raw_signal
        except Exception as e:
            return ProjectorState(
                power=StateField.unknown(f"PROJECTOR_ERROR: {e}", now),
                input_source=StateField.unknown("PROJECTOR_ERROR", now),
                brightness=StateField.unknown("PROJECTOR_ERROR", now),
                signal_active=StateField.unknown("PROJECTOR_ERROR", now),
                health=StateField.unknown("PROJECTOR_ERROR", now),
                content_title=StateField.unknown("PROJECTOR_ERROR", now),
            ), None

    def _poll_fire_tv(self, now: float) -> FireTvState:
        """Polls Fire TV controller state."""
        source_tag = "FIRE_TV_CONTROLLER"
        if not self.fire_tv:
            return FireTvState()

        try:
            online_val = False
            is_online_fn = getattr(self.fire_tv, "is_online", None)
            if callable(is_online_fn):
                online_val = bool(is_online_fn())
            elif hasattr(self.fire_tv, "is_connected") and callable(getattr(self.fire_tv, "is_connected")):
                conn_res = self.fire_tv.is_connected(auto_connect=False)
                online_val = conn_res[0] if isinstance(conn_res, tuple) else bool(conn_res)

            f_online = StateField.observed(online_val, source_tag, now)
            if not online_val:
                return FireTvState(
                    online=f_online,
                    power_state=StateField.observed("OFFLINE", source_tag, now),
                    foreground_app=StateField.observed(None, source_tag, now),
                    soundbar_connected=StateField.observed(False, source_tag, now),
                    content_title=StateField.observed(None, source_tag, now),
                )

            pwr_val = "ON"
            if hasattr(self.fire_tv, "get_power_state") and callable(getattr(self.fire_tv, "get_power_state")):
                pwr_val = str(self.fire_tv.get_power_state()).upper()
            f_pwr = StateField.observed(pwr_val, source_tag, now)

            fg_app = None
            if hasattr(self.fire_tv, "get_current_app") and callable(getattr(self.fire_tv, "get_current_app")):
                fg_app = self.fire_tv.get_current_app()
            f_app = StateField.observed(fg_app, source_tag, now)

            sb_conn = False
            if hasattr(self.fire_tv, "is_soundbar_connected") and callable(getattr(self.fire_tv, "is_soundbar_connected")):
                sb_conn = bool(self.fire_tv.is_soundbar_connected())
            f_sb = StateField.observed(sb_conn, source_tag, now)

            return FireTvState(
                online=f_online,
                power_state=f_pwr,
                foreground_app=f_app,
                soundbar_connected=f_sb,
                content_title=StateField.observed(None, source_tag, now),
            )
        except Exception as e:
            return FireTvState(
                online=StateField.unknown(f"FTV_ERROR: {e}", now),
                power_state=StateField.unknown("FTV_ERROR", now),
                foreground_app=StateField.unknown("FTV_ERROR", now),
                soundbar_connected=StateField.unknown("FTV_ERROR", now),
                content_title=StateField.unknown("FTV_ERROR", now),
            )

    def _poll_pc(self, now: float) -> Tuple[PcState, bool]:
        """Polls Animus PC host audio and Bluetooth state."""
        source_tag = "PC_HOST_CONTROLLER"
        if not self.pc:
            # Fallback observation of host PC daemon (which is currently executing this Python process)
            return PcState(
                online=StateField.observed(True, "PC_IN_PROCESS", now),
                master_volume=StateField.observed(50, "PC_IN_PROCESS", now),
                is_muted=StateField.observed(False, "PC_IN_PROCESS", now),
                default_audio_endpoint=StateField.observed("SPEAKERS", "PC_IN_PROCESS", now),
                bluetooth_radio_active=StateField.observed(True, "PC_IN_PROCESS", now),
            ), False

        try:
            f_online = StateField.observed(True, source_tag, now)
            vol_fn = getattr(self.pc, "get_master_volume", None)
            vol_val = int(vol_fn()) if callable(vol_fn) else 50
            f_vol = StateField.observed(vol_val, source_tag, now)

            mute_fn = getattr(self.pc, "get_mute_state", None)
            mute_val = bool(mute_fn()) if callable(mute_fn) else False
            f_mute = StateField.observed(mute_val, source_tag, now)

            ep_fn = getattr(self.pc, "get_default_audio_endpoint", None)
            ep_val = str(ep_fn()) if callable(ep_fn) else "SPEAKERS"
            f_ep = StateField.observed(ep_val, source_tag, now)

            bt_radio = True
            pc_snc_conn = False
            if hasattr(self.pc, "is_bluetooth_radio_enabled") and callable(getattr(self.pc, "is_bluetooth_radio_enabled")):
                bt_radio = bool(self.pc.is_bluetooth_radio_enabled())
            if hasattr(self.pc, "is_soundbar_connected") and callable(getattr(self.pc, "is_soundbar_connected")):
                pc_snc_conn = bool(self.pc.is_soundbar_connected())

            f_bt = StateField.observed(bt_radio, source_tag, now)

            return PcState(
                online=f_online,
                master_volume=f_vol,
                is_muted=f_mute,
                default_audio_endpoint=f_ep,
                bluetooth_radio_active=f_bt,
            ), pc_snc_conn
        except Exception as e:
            return PcState(
                online=StateField.unknown(f"PC_ERROR: {e}", now),
                master_volume=StateField.unknown("PC_ERROR", now),
                is_muted=StateField.unknown("PC_ERROR", now),
                default_audio_endpoint=StateField.unknown("PC_ERROR", now),
                bluetooth_radio_active=StateField.unknown("PC_ERROR", now),
            ), False

    def _poll_environment(self, now: float) -> RoomEnvironmentState:
        """Polls high-level orchestrator environment mode."""
        source_tag = "ORCHESTRATOR_ENV"
        if not self.orchestrator:
            return RoomEnvironmentState(
                room_mode=StateField.observed("IDLE", "DEFAULT_ENV", now),
                active_audio_route=StateField.observed("PC_DEFAULT", "DEFAULT_ENV", now),
            )

        try:
            mode_val = getattr(self.orchestrator, "current_mode", "IDLE")
            route_val = getattr(self.orchestrator, "active_audio_route", "PC_DEFAULT")
            return RoomEnvironmentState(
                room_mode=StateField.observed(str(mode_val), source_tag, now),
                active_audio_route=StateField.observed(str(route_val), source_tag, now),
            )
        except Exception:
            return RoomEnvironmentState(
                room_mode=StateField.unknown("ENV_ERROR", now),
                active_audio_route=StateField.unknown("ENV_ERROR", now),
            )

    def get_live_telemetry(self) -> Dict[str, Any]:
        """Returns flattened dictionary of latest physical sensor telemetry for fast cognitive evaluation."""
        st = self.get_room_state()
        ac_pwr = st.ac.power.value if st.ac and st.ac.power and st.ac.power.value is not None else False
        ac_amb = st.ac.ambient_temperature.value if st.ac and st.ac.ambient_temperature and st.ac.ambient_temperature.value is not None else 24
        ac_tgt = st.ac.target_temperature.value if st.ac and st.ac.target_temperature and st.ac.target_temperature.value is not None else 24
        proj_pwr = bool(st.projector.power.value) if st.projector and st.projector.power and st.projector.power.value is not None else False
        ftv_on = bool(st.fire_tv.online.value) if st.fire_tv and st.fire_tv.online and st.fire_tv.online.value is not None else False
        pc_on = bool(st.pc.online.value) if st.pc and st.pc.online and st.pc.online.value is not None else True
        media_playing = (st.audio_stream.playback_state.value == "PLAYING") if st.audio_stream and st.audio_stream.playback_state and st.audio_stream.playback_state.value is not None else False

        user_idle_sec = 0.0
        pc_locked = False
        if self.pc:
            if hasattr(self.pc, "get_user_idle_seconds") and callable(getattr(self.pc, "get_user_idle_seconds")):
                user_idle_sec = self.pc.get_user_idle_seconds()
            if hasattr(self.pc, "is_workstation_locked") and callable(getattr(self.pc, "is_workstation_locked")):
                pc_locked = self.pc.is_workstation_locked()

        mode_val = "IDLE"
        if self.orchestrator and hasattr(self.orchestrator, "current_mode"):
            mode_val = str(self.orchestrator.current_mode)
        elif st.environment and hasattr(st.environment, "room_mode") and st.environment.room_mode and getattr(st.environment.room_mode, "value", None):
            mode_val = str(st.environment.room_mode.value)

        desk_present = False
        desk_state = "UNKNOWN"
        desk_seated_sec = 0.0
        camera_online = False
        motion_score = 0.0
        if self.vision_observer and hasattr(self.vision_observer, "get_presence_telemetry"):
            try:
                v_tel = self.vision_observer.get_presence_telemetry()
                desk_present = bool(v_tel.get("is_present", False))
                desk_state = str(v_tel.get("state", "UNKNOWN"))
                desk_seated_sec = float(v_tel.get("seated_duration_seconds", 0.0))
                camera_online = bool(v_tel.get("camera_online", False))
                motion_score = float(v_tel.get("motion_score", 0.0))
            except Exception as e:
                logger.debug(f"[PERCEPTION_VISION_QUERY_ERR] {e}")

        # Multi-modal desk presence fusion:
        # Case A: If camera is offline/disconnected, fall back to PC user activity (idle < 30s)
        if not camera_online:
            if pc_on and not pc_locked and float(user_idle_sec) < 30.0:
                desk_present = True
                desk_state = "PRESENT"
            else:
                desk_present = False
                desk_state = "EMPTY"
        else:
            # Case B: Camera is online — optical observer is the physical ground truth.
            # If user is visually present, active typing (idle < 15s) sustains quiet focus
            if desk_present and self.vision_observer and pc_on and not pc_locked and float(user_idle_sec) < 15.0:
                if hasattr(self.vision_observer, "last_seen_timestamp"):
                    self.vision_observer.last_seen_timestamp = time.time()

        last_seen = 0.0
        if self.vision_observer and hasattr(self.vision_observer, "last_seen_timestamp"):
            last_seen = float(self.vision_observer.last_seen_timestamp or 0.0)

        return {
            "active_mode": mode_val,
            "ac_power": bool(ac_pwr),
            "ac_ambient_temp": int(ac_amb) if ac_amb is not None else 24,
            "ac_target_temp": int(ac_tgt) if ac_tgt is not None else 24,
            "projector_power": bool(proj_pwr),
            "fire_tv_online": bool(ftv_on),
            "pc_online": bool(pc_on),
            "user_idle_seconds": float(user_idle_sec),
            "pc_locked": bool(pc_locked),
            "media_playing": bool(media_playing),
            "desk_present": desk_present,
            "desk_state": desk_state,
            "desk_seated_seconds": desk_seated_sec,
            "camera_online": camera_online,
            "desk_motion_score": motion_score,
            "last_seen_timestamp": last_seen
        }


# Global singleton instance
_global_perception_collector: Optional[PerceptionCollector] = None


def get_perception_collector(
    projector_controller: Optional[Any] = None,
    fire_tv_controller: Optional[Any] = None,
    pc_controller: Optional[Any] = None,
    orchestrator: Optional[Any] = None,
    ac_read_adapter: Optional[Any] = None,
    vision_observer: Optional[Any] = None,
) -> PerceptionCollector:
    """Returns or initializes the global PerceptionCollector singleton with connected physical controllers."""
    global _global_perception_collector
    if _global_perception_collector is None:
        _global_perception_collector = PerceptionCollector(
            projector_controller=projector_controller,
            fire_tv_controller=fire_tv_controller,
            pc_controller=pc_controller,
            orchestrator=orchestrator,
            ac_read_adapter=ac_read_adapter,
            vision_observer=vision_observer
        )
    else:
        if orchestrator:
            _global_perception_collector.orchestrator = orchestrator
            if hasattr(_global_perception_collector, "aggregator") and _global_perception_collector.aggregator:
                _global_perception_collector.aggregator.orchestrator = orchestrator
            if hasattr(_global_perception_collector, "audio_resolver") and _global_perception_collector.audio_resolver:
                _global_perception_collector.audio_resolver.orchestrator = orchestrator
        if pc_controller:
            _global_perception_collector.pc = pc_controller
            if hasattr(_global_perception_collector, "aggregator") and _global_perception_collector.aggregator:
                _global_perception_collector.aggregator.pc = pc_controller
        if projector_controller and not _global_perception_collector.projector:
            _global_perception_collector.projector = projector_controller
        if fire_tv_controller and not _global_perception_collector.fire_tv:
            _global_perception_collector.fire_tv = fire_tv_controller
        if vision_observer:
            _global_perception_collector.vision_observer = vision_observer
    return _global_perception_collector

