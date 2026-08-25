"""
Authoritative Room State Monitor for Animus Smart Room Stage 6.
Continuously or event-driven evaluates live room telemetry, filters out unchanged polling,
detects meaningful state deltas, discovers external hardware modifications, and identifies
mode-to-physical divergences without performing silent destructive repairs.

EPISTEMIC & SAFETY INVARIANTS:
1. Physical Reality Wins: Live readbacks determine physical truth.
2. Unchanged telemetry polls produce zero duplicate change events.
3. External changes are detected, reported, and reconciled without blind overwriting.
4. Mode divergences produce notifications/events (ASK/SUGGEST), never silent arbitrary actuations.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agent.room_events import RoomEvent, RoomEventType
from agent.event_bus import RoomEventBus
from agent.behavior_modes import BehaviorMode
from room_state.models import RoomState

logger = logging.getLogger("music_daemon.agent.room_monitor")


class TelemetrySnapshot(BaseModel):
    """Normalized comparable snapshot of critical physical room state."""
    ac_power: Optional[bool] = None
    ac_target_temperature: Optional[int] = None
    ac_ambient_temperature: Optional[int] = None
    projector_power: Optional[bool] = None
    projector_source: Optional[str] = None
    fire_tv_power_state: Optional[str] = None
    fire_tv_online: Optional[bool] = None
    soundbar_owner: Optional[str] = None
    soundbar_connected: Optional[bool] = None
    media_playback_state: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class RoomStateMonitor:
    """
    Evaluates live physical room state against last-known baseline,
    emitting typed RoomEvents through the event bus for meaningful transitions.
    """

    def __init__(self, event_bus: RoomEventBus):
        self.event_bus = event_bus
        self.last_snapshot: Optional[TelemetrySnapshot] = None
        self.last_mode: Optional[BehaviorMode] = None

    def evaluate_telemetry(
        self,
        room_state: Any,
        active_mode: Optional[BehaviorMode] = None,
        verified_memory: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> List[RoomEvent]:
        """
        Extracts snapshot, compares against baseline, and publishes relevant RoomEvents.
        """
        current_snapshot = self._extract_snapshot(room_state)
        events_emitted: List[RoomEvent] = []

        if self.last_snapshot is None:
            self.last_snapshot = current_snapshot
            self.last_mode = active_mode
            return events_emitted

        prev = self.last_snapshot

        # 1. AC State Changes
        if current_snapshot.ac_power != prev.ac_power or current_snapshot.ac_target_temperature != prev.ac_target_temperature:
            evt = RoomEvent(
                event_type=RoomEventType.TELEMETRY_CHANGED,
                source="ROOM_MONITOR",
                affected_subsystem="AC",
                previous_state={"power": prev.ac_power, "target_temperature": prev.ac_target_temperature},
                observed_state={"power": current_snapshot.ac_power, "target_temperature": current_snapshot.ac_target_temperature},
                correlation_id=correlation_id
            )
            self.event_bus.publish(evt)
            events_emitted.append(evt)

            # Check for external change against verified execution memory
            if verified_memory and "ac_target_temperature" in verified_memory:
                expected_temp = verified_memory["ac_target_temperature"]
                if current_snapshot.ac_target_temperature is not None and current_snapshot.ac_target_temperature != expected_temp:
                    ext_evt = RoomEvent(
                        event_type=RoomEventType.EXTERNAL_STATE_CHANGE,
                        source="ROOM_MONITOR",
                        affected_subsystem="AC",
                        previous_state={"target_temperature": expected_temp},
                        observed_state={"target_temperature": current_snapshot.ac_target_temperature},
                        metadata={"reason": "External temperature adjustment detected", "expected": expected_temp, "actual": current_snapshot.ac_target_temperature},
                        correlation_id=correlation_id
                    )
                    self.event_bus.publish(ext_evt)
                    events_emitted.append(ext_evt)

        # 2. Projector State Changes
        if current_snapshot.projector_power != prev.projector_power or current_snapshot.projector_source != prev.projector_source:
            evt = RoomEvent(
                event_type=RoomEventType.TELEMETRY_CHANGED,
                source="ROOM_MONITOR",
                affected_subsystem="PROJECTOR",
                previous_state={"power": prev.projector_power, "input_source": prev.projector_source},
                observed_state={"power": current_snapshot.projector_power, "input_source": current_snapshot.projector_source},
                correlation_id=correlation_id
            )
            self.event_bus.publish(evt)
            events_emitted.append(evt)

        # 3. Fire TV State Changes
        if current_snapshot.fire_tv_online != prev.fire_tv_online or current_snapshot.fire_tv_power_state != prev.fire_tv_power_state:
            evt_type = RoomEventType.DEVICE_CONNECTED if current_snapshot.fire_tv_online and not prev.fire_tv_online else (
                RoomEventType.DEVICE_DISCONNECTED if not current_snapshot.fire_tv_online and prev.fire_tv_online else RoomEventType.TELEMETRY_CHANGED
            )
            evt = RoomEvent(
                event_type=evt_type,
                source="ROOM_MONITOR",
                affected_subsystem="FIRE_TV",
                previous_state={"online": prev.fire_tv_online, "power_state": prev.fire_tv_power_state},
                observed_state={"online": current_snapshot.fire_tv_online, "power_state": current_snapshot.fire_tv_power_state},
                correlation_id=correlation_id
            )
            self.event_bus.publish(evt)
            events_emitted.append(evt)

        # 4. Soundbar State Changes
        if current_snapshot.soundbar_owner != prev.soundbar_owner or current_snapshot.soundbar_connected != prev.soundbar_connected:
            evt = RoomEvent(
                event_type=RoomEventType.TELEMETRY_CHANGED,
                source="ROOM_MONITOR",
                affected_subsystem="SOUNDBAR",
                previous_state={"current_owner": prev.soundbar_owner, "connected": prev.soundbar_connected},
                observed_state={"current_owner": current_snapshot.soundbar_owner, "connected": current_snapshot.soundbar_connected},
                correlation_id=correlation_id
            )
            self.event_bus.publish(evt)
            events_emitted.append(evt)

        # 5. Media Playback State Changes
        if current_snapshot.media_playback_state != prev.media_playback_state:
            m_state = current_snapshot.media_playback_state
            if m_state == "PLAYING":
                m_type = RoomEventType.MEDIA_STARTED if prev.media_playback_state == "STOPPED" else RoomEventType.MEDIA_RESUMED
            elif m_state == "PAUSED":
                m_type = RoomEventType.MEDIA_PAUSED
            elif m_state == "STOPPED":
                m_type = RoomEventType.MEDIA_STOPPED
            else:
                m_type = RoomEventType.TELEMETRY_CHANGED

            evt = RoomEvent(
                event_type=m_type,
                source="ROOM_MONITOR",
                affected_subsystem="MEDIA",
                previous_state={"playback_state": prev.media_playback_state},
                observed_state={"playback_state": current_snapshot.media_playback_state},
                correlation_id=correlation_id
            )
            self.event_bus.publish(evt)
            events_emitted.append(evt)

        # 6. Mode Divergence Detection (Active mode expectations violated by live physical reality)
        if active_mode:
            divergence = self._check_mode_divergence(active_mode, current_snapshot)
            if divergence:
                div_evt = RoomEvent(
                    event_type=RoomEventType.MODE_DIVERGENCE_DETECTED,
                    source="ROOM_MONITOR",
                    affected_subsystem=divergence.get("subsystem", "ROOM"),
                    observed_state=current_snapshot.model_dump(),
                    metadata={"mode": active_mode.value, "divergence_reason": divergence.get("reason")},
                    correlation_id=correlation_id
                )
                self.event_bus.publish(div_evt)
                events_emitted.append(div_evt)

        self.last_snapshot = current_snapshot
        self.last_mode = active_mode
        return events_emitted

    def _check_mode_divergence(self, mode: BehaviorMode, snapshot: TelemetrySnapshot) -> Optional[Dict[str, Any]]:
        """Validates if physical telemetry diverges from active behavioral mode expectations."""
        if mode == BehaviorMode.MOVIE:
            if snapshot.projector_power is False:
                return {"subsystem": "PROJECTOR", "reason": "Projector is OFF while MOVIE mode is active"}
            if snapshot.soundbar_owner == "PC":
                return {"subsystem": "SOUNDBAR", "reason": "Soundbar is connected to PC instead of Fire TV in MOVIE mode"}
        elif mode == BehaviorMode.SLEEP:
            if snapshot.projector_power is True:
                return {"subsystem": "PROJECTOR", "reason": "Projector is ON while SLEEP mode is active"}
        elif mode == BehaviorMode.MUSIC:
            if snapshot.soundbar_owner == "FIRE_TV":
                return {"subsystem": "SOUNDBAR", "reason": "Soundbar is connected to Fire TV during MUSIC mode"}
        return None

    def _extract_snapshot(self, room_state: Any) -> TelemetrySnapshot:
        """Extracts normalized, comparable fields from live room state."""
        if room_state is None:
            return TelemetrySnapshot()

        # Handle Dict room_state
        if isinstance(room_state, dict):
            return TelemetrySnapshot(
                ac_power=room_state.get("ac_power"),
                ac_target_temperature=room_state.get("ac_target_temperature") or room_state.get("target_temperature"),
                ac_ambient_temperature=room_state.get("ambient_temperature") or room_state.get("room_temperature"),
                projector_power=room_state.get("projector_power"),
                projector_source=room_state.get("projector_source"),
                fire_tv_power_state=room_state.get("fire_tv_power_state"),
                fire_tv_online=room_state.get("fire_tv_online"),
                soundbar_owner=room_state.get("soundbar_owner"),
                soundbar_connected=room_state.get("soundbar_connected"),
                media_playback_state=room_state.get("media_playback_state")
            )

        # Handle typed RoomState object
        ac_pwr = getattr(getattr(room_state, "ac", None), "power", None)
        ac_target = getattr(getattr(room_state, "ac", None), "target_temperature", None)
        ac_amb = getattr(getattr(room_state, "ac", None), "ambient_temperature", None)

        proj_pwr = getattr(getattr(room_state, "projector", None), "power", None)
        proj_src = getattr(getattr(room_state, "projector", None), "input_source", None)

        ftv_on = getattr(getattr(room_state, "fire_tv", None), "online", None)
        ftv_pow = getattr(getattr(room_state, "fire_tv", None), "power_state", None)

        sb_owner = getattr(getattr(room_state, "soundbar", None), "current_owner", None)
        sb_conn = getattr(getattr(room_state, "soundbar", None), "is_connected", None)

        media_state = getattr(getattr(room_state, "media_session", None), "playback_state", None) or getattr(room_state, "media_playback_state", None) or getattr(room_state, "media_state", None)

        return TelemetrySnapshot(
            ac_power=getattr(ac_pwr, "value", ac_pwr) if ac_pwr is not None else None,
            ac_target_temperature=getattr(ac_target, "value", ac_target) if ac_target is not None else None,
            ac_ambient_temperature=getattr(ac_amb, "value", ac_amb) if ac_amb is not None else None,
            projector_power=getattr(proj_pwr, "value", proj_pwr) if proj_pwr is not None else None,
            projector_source=getattr(proj_src, "value", proj_src) if proj_src is not None else None,
            fire_tv_power_state=getattr(ftv_pow, "value", ftv_pow) if ftv_pow is not None else None,
            fire_tv_online=getattr(ftv_on, "value", ftv_on) if ftv_on is not None else None,
            soundbar_owner=getattr(sb_owner, "value", sb_owner) if sb_owner is not None else None,
            soundbar_connected=getattr(sb_conn, "value", sb_conn) if sb_conn is not None else None,
            media_playback_state=getattr(media_state, "value", media_state) if media_state is not None else None
        )

