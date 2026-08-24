"""
Authoritative RoomState Aggregator for Animus Smart Room.
Queries verified physical controllers and constructs the canonical RoomState snapshot
with honest provenance, error isolation, and deterministic derivations.
"""

import time
import logging
from typing import Optional, Dict, Any

from room_state.provenance import Provenance
from room_state.models import (
    RoomState,
    StateField,
    ProjectorState,
    AcState,
    FireTvState,
    PcState,
    SoundbarState,
    RoomEnvironmentState
)
from room_state.derivations import derive_projector_signal_active, derive_soundbar_state

logger = logging.getLogger("room_state.aggregator")


class RoomStateAggregator:
    """
    Constructs the canonical Authoritative RoomState by querying active hardware controllers.
    Enforces the fundamental axiom: Physical Observation != Planner Expectation.
    """
    def __init__(
        self,
        projector_controller: Optional[Any] = None,
        ac_controller: Optional[Any] = None,
        fire_tv_controller: Optional[Any] = None,
        pc_controller: Optional[Any] = None,
        orchestrator: Optional[Any] = None
    ):
        self.projector = projector_controller
        self.ac = ac_controller
        self.fire_tv = fire_tv_controller
        self.pc = pc_controller
        self.orchestrator = orchestrator

    def get_room_state(self, current_time: Optional[float] = None) -> RoomState:
        """
        Polls all available physical controllers and compiles the canonical RoomState.
        Faults in individual subsystems are isolated and marked UNKNOWN without crashing the aggregation.
        """
        now = current_time if current_time is not None else time.time()
        is_consistent = True

        # ---------------------------------------------------------------------
        # 1. Projector Subsystem Aggregation
        # ---------------------------------------------------------------------
        p_state, raw_signal = self._aggregate_projector(now)
        if p_state.power.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # ---------------------------------------------------------------------
        # 2. Air Conditioner Subsystem Aggregation
        # ---------------------------------------------------------------------
        ac_state = self._aggregate_ac(now)
        if ac_state.power.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # ---------------------------------------------------------------------
        # 3. Fire TV Subsystem Aggregation
        # ---------------------------------------------------------------------
        ftv_state = self._aggregate_fire_tv(now)
        if ftv_state.online.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # ---------------------------------------------------------------------
        # 4. PC Host Subsystem Aggregation
        # ---------------------------------------------------------------------
        pc_state, pc_snc_connected = self._aggregate_pc(now)
        if pc_state.online.provenance == Provenance.UNKNOWN:
            is_consistent = False

        # ---------------------------------------------------------------------
        # 5. Deterministic Derivations
        # ---------------------------------------------------------------------
        # Projector signal active
        p_state.signal_active = derive_projector_signal_active(
            power_field=p_state.power,
            input_source_field=p_state.input_source,
            raw_signal_obs=raw_signal,
            observed_at=now
        )

        # Soundbar ownership & connection
        sb_state = derive_soundbar_state(
            pc_bt_connected_field=StateField.observed(pc_snc_connected, "PC_BT_POLL", now),
            pc_endpoint_field=pc_state.default_audio_endpoint,
            fire_tv_online_field=ftv_state.online,
            fire_tv_bt_field=ftv_state.soundbar_connected,
            observed_at=now
        )

        # ---------------------------------------------------------------------
        # 6. Room Environment & Mode Tracking
        # ---------------------------------------------------------------------
        env_state = self._aggregate_environment(now, sb_state)

        return RoomState(
            timestamp=now,
            is_consistent=is_consistent,
            projector=p_state,
            ac=ac_state,
            fire_tv=ftv_state,
            pc=pc_state,
            soundbar=sb_state,
            environment=env_state
        )

    # =========================================================================
    # Internal Subsystem Aggregators
    # =========================================================================

    def _aggregate_projector(self, now: float) -> tuple[ProjectorState, Optional[bool]]:
        source_tag = "PROJECTOR_ADB_CONTROLLER"
        if not self.projector:
            return ProjectorState(), None

        raw_signal = None
        try:
            # Power
            raw_pwr = getattr(self.projector, "get_power_state", None)
            if callable(raw_pwr):
                pwr_enum = raw_pwr()
                pwr_val = (str(getattr(pwr_enum, "value", pwr_enum)).upper() == "ON")
                f_pwr = StateField.observed(pwr_val, source_tag, now)
            else:
                f_pwr = StateField.unknown(source=source_tag, observed_at=now)

            # Input Source
            raw_src = getattr(self.projector, "get_current_source", None)
            if callable(raw_src):
                src_enum = raw_src()
                src_val = str(getattr(src_enum, "value", src_enum)).upper()
                f_src = StateField.observed(src_val, source_tag, now)
            else:
                f_src = StateField.unknown(source=source_tag, observed_at=now)

            # Brightness
            raw_bri = getattr(self.projector, "get_brightness", None)
            if callable(raw_bri):
                bri_val = int(raw_bri())
                f_bri = StateField.observed(bri_val, source_tag, now)
            else:
                f_bri = StateField.unknown(source=source_tag, observed_at=now)

            # Health
            raw_hlth = getattr(self.projector, "get_health", None)
            if callable(raw_hlth):
                hlth_dict = raw_hlth()
                hlth_val = "OK" if hlth_dict.get("adb_connected") else "DEGRADED"
                f_hlth = StateField.observed(hlth_val, source_tag, now)
            else:
                f_hlth = StateField.unknown(source=source_tag, observed_at=now)

            # Signal activity raw check
            raw_sig_fn = getattr(self.projector, "is_hdmi_signal_active", None)
            if callable(raw_sig_fn):
                raw_signal = bool(raw_sig_fn())

            return ProjectorState(
                power=f_pwr,
                input_source=f_src,
                brightness=f_bri,
                health=f_hlth
            ), raw_signal

        except Exception as e:
            logger.warning(f"[ROOM_STATE_AGGREGATOR] Projector query failed: {e}")
            return ProjectorState(
                power=StateField.unknown(source="PROJECTOR_POLL_ERROR", observed_at=now),
                input_source=StateField.unknown(source="PROJECTOR_POLL_ERROR", observed_at=now),
                brightness=StateField.unknown(source="PROJECTOR_POLL_ERROR", observed_at=now),
                health=StateField.unknown(source="PROJECTOR_POLL_ERROR", observed_at=now)
            ), None

    def _aggregate_ac(self, now: float) -> AcState:
        source_tag = "AC_TUYA_CONTROLLER"
        if not self.ac:
            return AcState()

        try:
            status_fn = getattr(self.ac, "get_status", None)
            if callable(status_fn):
                st = status_fn()
                if st.get("verified"):
                    return AcState(
                        power=StateField.observed(bool(st.get("power")), source_tag, now),
                        target_temperature=StateField.observed(int(st.get("target_temperature", 24)), source_tag, now),
                        ambient_temperature=StateField.observed(st.get("ambient_temperature"), source_tag, now) if st.get("ambient_temperature") is not None else StateField.unknown(source_tag, now),
                        mode=StateField.observed(str(st.get("mode", "COOL")), source_tag, now),
                        fan_speed=StateField.observed(str(st.get("fan_speed", "AUTO")), source_tag, now),
                        transport_used=StateField.observed(str(st.get("transport_used", "LOCAL_TUYA_3.3")), source_tag, now)
                    )
            return AcState()
        except Exception as e:
            logger.warning(f"[ROOM_STATE_AGGREGATOR] AC query failed: {e}")
            return AcState(
                power=StateField.unknown("AC_POLL_ERROR", now),
                target_temperature=StateField.unknown("AC_POLL_ERROR", now),
                ambient_temperature=StateField.unknown("AC_POLL_ERROR", now),
                mode=StateField.unknown("AC_POLL_ERROR", now),
                fan_speed=StateField.unknown("AC_POLL_ERROR", now),
                transport_used=StateField.unknown("AC_POLL_ERROR", now)
            )

    def _aggregate_fire_tv(self, now: float) -> FireTvState:
        source_tag = "FIRE_TV_CONTROLLER"
        if not self.fire_tv:
            return FireTvState()

        try:
            is_online_fn = getattr(self.fire_tv, "is_online", None)
            online_val = bool(is_online_fn()) if callable(is_online_fn) else False
            f_online = StateField.observed(online_val, source_tag, now)

            if not online_val:
                return FireTvState(
                    online=f_online,
                    power_state=StateField.observed("OFFLINE", source_tag, now),
                    foreground_app=StateField.observed(None, source_tag, now),
                    soundbar_connected=StateField.observed(False, source_tag, now)
                )

            # Power state
            pwr_fn = getattr(self.fire_tv, "get_power_state", None)
            pwr_val = str(pwr_fn()) if callable(pwr_fn) else "UNKNOWN"
            f_pwr = StateField.observed(pwr_val, source_tag, now)

            # Foreground app
            app_fn = getattr(self.fire_tv, "get_foreground_app", None)
            app_val = app_fn() if callable(app_fn) else None
            f_app = StateField.observed(app_val, source_tag, now)

            # Soundbar connected
            bt_fn = getattr(self.fire_tv, "is_soundbar_connected", None)
            bt_val = bool(bt_fn()) if callable(bt_fn) else False
            f_bt = StateField.observed(bt_val, source_tag, now)

            return FireTvState(
                online=f_online,
                power_state=f_pwr,
                foreground_app=f_app,
                soundbar_connected=f_bt
            )
        except Exception as e:
            logger.warning(f"[ROOM_STATE_AGGREGATOR] Fire TV query failed: {e}")
            return FireTvState(
                online=StateField.unknown("FIRE_TV_POLL_ERROR", now),
                power_state=StateField.unknown("FIRE_TV_POLL_ERROR", now),
                foreground_app=StateField.unknown("FIRE_TV_POLL_ERROR", now),
                soundbar_connected=StateField.unknown("FIRE_TV_POLL_ERROR", now)
            )

    def _aggregate_pc(self, now: float) -> tuple[PcState, bool]:
        source_tag = "PC_COREAUDIO_BT_CONTROLLER"
        if not self.pc:
            return PcState(), False

        pc_snc_connected = False
        try:
            # Audio
            ast_fn = getattr(self.pc, "get_audio_status", None)
            if callable(ast_fn):
                ast = ast_fn()
                f_vol = StateField.observed(int(ast.get("master_volume", 0)), source_tag, now)
                f_mute = StateField.observed(bool(ast.get("is_muted", False)), source_tag, now)
                def_ep = ast.get("default_endpoint", {}).get("name", "Unknown")
                f_ep = StateField.observed(str(def_ep), source_tag, now)
            else:
                f_vol = StateField.unknown(source_tag, now)
                f_mute = StateField.unknown(source_tag, now)
                f_ep = StateField.unknown(source_tag, now)

            # Bluetooth
            bt_fn = getattr(self.pc, "get_bluetooth_status", None)
            if callable(bt_fn):
                bt_st = bt_fn()
                f_bt_rad = StateField.observed(bool(bt_st.get("radio_present", False)), source_tag, now)
                for d in bt_st.get("devices", []):
                    if "SNC" in d.get("name", "").upper() and d.get("connected"):
                        pc_snc_connected = True
            else:
                f_bt_rad = StateField.unknown(source_tag, now)

            pc_state = PcState(
                online=StateField.observed(True, source_tag, now),
                master_volume=f_vol,
                is_muted=f_mute,
                default_audio_endpoint=f_ep,
                bluetooth_radio_active=f_bt_rad
            )
            return pc_state, pc_snc_connected

        except Exception as e:
            logger.warning(f"[ROOM_STATE_AGGREGATOR] PC query failed: {e}")
            return PcState(
                online=StateField.unknown("PC_POLL_ERROR", now),
                master_volume=StateField.unknown("PC_POLL_ERROR", now),
                is_muted=StateField.unknown("PC_POLL_ERROR", now),
                default_audio_endpoint=StateField.unknown("PC_POLL_ERROR", now),
                bluetooth_radio_active=StateField.unknown("PC_POLL_ERROR", now)
            ), False

    def _aggregate_environment(self, now: float, soundbar_state: SoundbarState) -> RoomEnvironmentState:
        source_tag = "ORCHESTRATOR_ENVIRONMENT"
        mode_val = "IDLE"
        if self.orchestrator:
            try:
                orch_state_fn = getattr(self.orchestrator, "get_room_state", None)
                if callable(orch_state_fn):
                    mode_val = str(getattr(orch_state_fn(), "value", orch_state_fn()))
            except Exception:
                pass

        # Active audio route
        route_val = "NONE"
        if soundbar_state.current_owner.value == "FIRE_TV":
            route_val = "FIRE_TV_DIRECT"
        elif soundbar_state.current_owner.value == "PC":
            route_val = "PC_DIRECT"

        return RoomEnvironmentState(
            room_mode=StateField.derived(mode_val, source_tag, now),
            active_audio_route=StateField.derived(route_val, source_tag, now)
        )
