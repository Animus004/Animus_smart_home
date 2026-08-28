"""
Canonical RoomState Schema & Generic StateField Model for Animus Smart Room.
Authoritatively defines physical room state with strict provenance, timestamping, and device schemas.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import TypeVar, Generic, Optional, Dict, Any, List
from pydantic import BaseModel, Field

from room_state.provenance import Provenance
from room_state.freshness import (
    is_fresh,
    resolve_provenance,
    PROJECTOR_POWER_TTL,
    PROJECTOR_INPUT_TTL,
    PROJECTOR_BRIGHTNESS_TTL,
    PROJECTOR_SIGNAL_TTL,
    PROJECTOR_HEALTH_TTL,
    AC_POWER_TTL,
    AC_TARGET_TEMP_TTL,
    AC_AMBIENT_TEMP_TTL,
    AC_MODE_TTL,
    AC_FAN_SPEED_TTL,
    AC_TRANSPORT_TTL,
    IR_HUB_ONLINE_TTL,
    IR_HUB_TRANSPORT_TTL,
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
    AUDIO_STREAM_TTL
)

T = TypeVar("T")


class StateField(BaseModel, Generic[T]):
    """
    Epistemologically grounded state container.
    Wraps a value with explicit provenance, timestamp, and source information.
    """
    value: Optional[T] = None
    provenance: Provenance = Provenance.UNKNOWN
    observed_at: float = 0.0
    source: str = "UNINITIALIZED"

    def is_fresh(self, ttl_seconds: float, current_time: Optional[float] = None) -> bool:
        """Returns True if the observation is strictly within its freshness TTL window."""
        return is_fresh(self.observed_at, ttl_seconds, current_time)

    def effective_provenance(self, ttl_seconds: float, current_time: Optional[float] = None) -> Provenance:
        """Returns the effective provenance, transitioning OBSERVED/DERIVED to STALE if TTL expired."""
        return resolve_provenance(self.provenance, self.observed_at, ttl_seconds, current_time)

    def to_dict(self, ttl_seconds: Optional[float] = None, current_time: Optional[float] = None) -> Dict[str, Any]:
        """Serializes to a dictionary with effective provenance evaluation."""
        prov = self.effective_provenance(ttl_seconds, current_time) if ttl_seconds else self.provenance
        return {
            "value": self.value,
            "provenance": prov.value,
            "observed_at": self.observed_at,
            "source": self.source
        }

    @classmethod
    def observed(cls, value: T, source: str, observed_at: Optional[float] = None) -> StateField[T]:
        """Factory for direct hardware observations."""
        return cls(
            value=value,
            provenance=Provenance.OBSERVED,
            observed_at=observed_at if observed_at is not None else time.time(),
            source=source
        )

    @classmethod
    def derived(cls, value: T, source: str, observed_at: Optional[float] = None) -> StateField[T]:
        """Factory for deterministic derivations."""
        return cls(
            value=value,
            provenance=Provenance.DERIVED,
            observed_at=observed_at if observed_at is not None else time.time(),
            source=source
        )

    @classmethod
    def unknown(cls, source: str = "UNREACHABLE", observed_at: Optional[float] = None) -> StateField[T]:
        """Factory for missing or failed observations."""
        return cls(
            value=None,
            provenance=Provenance.UNKNOWN,
            observed_at=observed_at if observed_at is not None else time.time(),
            source=source
        )

    @classmethod
    def stale(cls, value: T, source: str, observed_at: float) -> StateField[T]:
        """Factory for explicitly stale fields."""
        return cls(
            value=value,
            provenance=Provenance.STALE,
            observed_at=observed_at,
            source=source
        )


# =============================================================================
# Subsystem State Models
# =============================================================================

class ProjectorState(BaseModel):
    """Authoritative Projector Subsystem State (Zebronics PixaPlay 25)."""
    power: StateField[bool] = Field(default_factory=lambda: StateField.unknown("PROJECTOR_UNINITIALIZED"))
    input_source: StateField[str] = Field(default_factory=lambda: StateField.unknown("PROJECTOR_UNINITIALIZED"))
    brightness: StateField[int] = Field(default_factory=lambda: StateField.unknown("PROJECTOR_UNINITIALIZED"))
    signal_active: StateField[bool] = Field(default_factory=lambda: StateField.unknown("PROJECTOR_UNINITIALIZED"))
    health: StateField[str] = Field(default_factory=lambda: StateField.unknown("PROJECTOR_UNINITIALIZED"))
    content_title: StateField[Optional[str]] = Field(default_factory=lambda: StateField.unknown("PROJECTOR_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "power": self.power.to_dict(PROJECTOR_POWER_TTL, current_time),
            "input_source": self.input_source.to_dict(PROJECTOR_INPUT_TTL, current_time),
            "brightness": self.brightness.to_dict(PROJECTOR_BRIGHTNESS_TTL, current_time),
            "signal_active": self.signal_active.to_dict(PROJECTOR_SIGNAL_TTL, current_time),
            "health": self.health.to_dict(PROJECTOR_HEALTH_TTL, current_time),
            "content_title": self.content_title.to_dict(PROJECTOR_INPUT_TTL, current_time),
        }


class AcState(BaseModel):
    """Authoritative Air Conditioner Subsystem State (Tuya Split AC)."""
    power: StateField[bool] = Field(default_factory=lambda: StateField.unknown("AC_UNINITIALIZED"))
    target_temperature: StateField[int] = Field(default_factory=lambda: StateField.unknown("AC_UNINITIALIZED"))
    ambient_temperature: StateField[Optional[int]] = Field(default_factory=lambda: StateField.unknown("AC_UNINITIALIZED"))
    mode: StateField[str] = Field(default_factory=lambda: StateField.unknown("AC_UNINITIALIZED"))
    fan_speed: StateField[str] = Field(default_factory=lambda: StateField.unknown("AC_UNINITIALIZED"))
    transport_used: StateField[str] = Field(default_factory=lambda: StateField.unknown("AC_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "power": self.power.to_dict(AC_POWER_TTL, current_time),
            "target_temperature": self.target_temperature.to_dict(AC_TARGET_TEMP_TTL, current_time),
            "ambient_temperature": self.ambient_temperature.to_dict(AC_AMBIENT_TEMP_TTL, current_time),
            "mode": self.mode.to_dict(AC_MODE_TTL, current_time),
            "fan_speed": self.fan_speed.to_dict(AC_FAN_SPEED_TTL, current_time),
            "transport_used": self.transport_used.to_dict(AC_TRANSPORT_TTL, current_time),
        }


class FireTvState(BaseModel):
    """Authoritative Amazon Fire TV Subsystem State."""
    online: StateField[bool] = Field(default_factory=lambda: StateField.unknown("FIRE_TV_UNINITIALIZED"))
    power_state: StateField[str] = Field(default_factory=lambda: StateField.unknown("FIRE_TV_UNINITIALIZED"))
    foreground_app: StateField[Optional[str]] = Field(default_factory=lambda: StateField.unknown("FIRE_TV_UNINITIALIZED"))
    soundbar_connected: StateField[bool] = Field(default_factory=lambda: StateField.unknown("FIRE_TV_UNINITIALIZED"))
    content_title: StateField[Optional[str]] = Field(default_factory=lambda: StateField.unknown("FIRE_TV_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "online": self.online.to_dict(FIRE_TV_ONLINE_TTL, current_time),
            "power_state": self.power_state.to_dict(FIRE_TV_POWER_TTL, current_time),
            "foreground_app": self.foreground_app.to_dict(FIRE_TV_APP_TTL, current_time),
            "soundbar_connected": self.soundbar_connected.to_dict(FIRE_TV_BT_TTL, current_time),
            "content_title": self.content_title.to_dict(FIRE_TV_APP_TTL, current_time),
        }


class PcState(BaseModel):
    """Authoritative Animus PC Host Subsystem State."""
    online: StateField[bool] = Field(default_factory=lambda: StateField.unknown("PC_UNINITIALIZED"))
    master_volume: StateField[int] = Field(default_factory=lambda: StateField.unknown("PC_UNINITIALIZED"))
    is_muted: StateField[bool] = Field(default_factory=lambda: StateField.unknown("PC_UNINITIALIZED"))
    default_audio_endpoint: StateField[str] = Field(default_factory=lambda: StateField.unknown("PC_UNINITIALIZED"))
    bluetooth_radio_active: StateField[bool] = Field(default_factory=lambda: StateField.unknown("PC_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "online": self.online.to_dict(PC_ONLINE_TTL, current_time),
            "master_volume": self.master_volume.to_dict(PC_VOLUME_TTL, current_time),
            "is_muted": self.is_muted.to_dict(PC_MUTE_TTL, current_time),
            "default_audio_endpoint": self.default_audio_endpoint.to_dict(PC_ENDPOINT_TTL, current_time),
            "bluetooth_radio_active": self.bluetooth_radio_active.to_dict(PC_BT_TTL, current_time),
        }


class SoundbarState(BaseModel):
    """Authoritative Soundbar Audio Routing State (LG SNC4R)."""
    current_owner: StateField[str] = Field(default_factory=lambda: StateField.unknown("SOUNDBAR_UNINITIALIZED"))
    is_connected: StateField[bool] = Field(default_factory=lambda: StateField.unknown("SOUNDBAR_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "current_owner": self.current_owner.to_dict(SOUNDBAR_OWNER_TTL, current_time),
            "is_connected": self.is_connected.to_dict(SOUNDBAR_CONNECTED_TTL, current_time),
        }


class ActiveAudioProducer(str, Enum):
    """Authoritative semantic classification of the device actively producing audio."""
    PC = "PC"
    FIRE_TV = "FIRE_TV"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class MediaPlaybackState(str, Enum):
    """Authoritative semantic classification of media playback state."""
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    BUFFERING = "BUFFERING"
    IDLE = "IDLE"
    UNKNOWN = "UNKNOWN"


class AudioStreamState(BaseModel):
    """
    Authoritative Semantic Audio Stream & Producer State.
    Captures live audio flow, media playback activity, and active audio route.
    """
    active_producer: StateField[str] = Field(default_factory=lambda: StateField.unknown("AUDIO_STREAM_UNINITIALIZED"))
    playback_state: StateField[str] = Field(default_factory=lambda: StateField.unknown("AUDIO_STREAM_UNINITIALIZED"))
    active_app_or_media_source: StateField[Optional[str]] = Field(default_factory=lambda: StateField.unknown("AUDIO_STREAM_UNINITIALIZED"))
    soundbar_route_active: StateField[bool] = Field(default_factory=lambda: StateField.unknown("AUDIO_STREAM_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "active_producer": self.active_producer.to_dict(AUDIO_STREAM_TTL, current_time),
            "playback_state": self.playback_state.to_dict(AUDIO_STREAM_TTL, current_time),
            "active_app_or_media_source": self.active_app_or_media_source.to_dict(AUDIO_STREAM_TTL, current_time),
            "soundbar_route_active": self.soundbar_route_active.to_dict(AUDIO_STREAM_TTL, current_time),
        }


class IrHubState(BaseModel):
    """Authoritative Smart IR Hub Subsystem State (Tuya IR Blaster)."""
    online: StateField[bool] = Field(default_factory=lambda: StateField.unknown("IR_HUB_UNINITIALIZED"))
    transport: StateField[str] = Field(default_factory=lambda: StateField.unknown("IR_HUB_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "online": self.online.to_dict(IR_HUB_ONLINE_TTL, current_time),
            "transport": self.transport.to_dict(IR_HUB_TRANSPORT_TTL, current_time),
        }


class RoomEnvironmentState(BaseModel):
    """High-Level Room Environment & Mode Tracking."""
    room_mode: StateField[str] = Field(default_factory=lambda: StateField.unknown("ENVIRONMENT_UNINITIALIZED"))
    active_audio_route: StateField[str] = Field(default_factory=lambda: StateField.unknown("ENVIRONMENT_UNINITIALIZED"))

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        return {
            "room_mode": self.room_mode.to_dict(ENVIRONMENT_MODE_TTL, current_time),
            "active_audio_route": self.active_audio_route.to_dict(ENVIRONMENT_MODE_TTL, current_time),
        }


# =============================================================================
# Top-Level Canonical RoomState
# =============================================================================

class RoomState(BaseModel):
    """
    Authoritative Canonical RoomState.
    Represents the unified physical snapshot of reality across all smart room subsystems.
    """
    timestamp: float = Field(default_factory=time.time)
    is_consistent: bool = True
    projector: ProjectorState = Field(default_factory=ProjectorState)
    ac: AcState = Field(default_factory=AcState)
    ir_hub: IrHubState = Field(default_factory=IrHubState)
    fire_tv: FireTvState = Field(default_factory=FireTvState)
    pc: PcState = Field(default_factory=PcState)
    soundbar: SoundbarState = Field(default_factory=SoundbarState)
    environment: RoomEnvironmentState = Field(default_factory=RoomEnvironmentState)
    audio_stream: AudioStreamState = Field(default_factory=AudioStreamState)

    def to_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """Serializes RoomState to structured JSON-compliant dict with live provenance checks."""
        now = current_time if current_time is not None else self.timestamp
        return {
            "timestamp": self.timestamp,
            "is_consistent": self.is_consistent,
            "projector": self.projector.to_dict(now),
            "ac": self.ac.to_dict(now),
            "ir_hub": self.ir_hub.to_dict(now),
            "fire_tv": self.fire_tv.to_dict(now),
            "pc": self.pc.to_dict(now),
            "soundbar": self.soundbar.to_dict(now),
            "environment": self.environment.to_dict(now),
            "audio_stream": self.audio_stream.to_dict(now),
        }

    def to_sanitized_prompt_dict(self, current_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Generates a sanitized, simplified dictionary suitable for LLM reasoning prompts.
        Only presents verified values, explicitly tagging STALE and UNKNOWN items without secret exposure.
        """
        raw = self.to_dict(current_time)
        sanitized: Dict[str, Any] = {
            "timestamp": raw["timestamp"],
            "is_consistent": raw["is_consistent"],
        }
        for sub, fields in raw.items():
            if not isinstance(fields, dict):
                continue
            sanitized[sub] = {}
            for fname, fdata in fields.items():
                if isinstance(fdata, dict) and "provenance" in fdata:
                    prov = fdata["provenance"]
                    val = fdata["value"]
                    if prov == Provenance.UNKNOWN.value:
                        sanitized[sub][fname] = "UNKNOWN"
                    elif prov == Provenance.STALE.value:
                        sanitized[sub][fname] = f"{val} (STALE)"
                    else:
                        sanitized[sub][fname] = val
                else:
                    sanitized[sub][fname] = fdata
        return sanitized

    def get_stale_fields(self, current_time: Optional[float] = None) -> List[str]:
        """Returns a list of dot-notated field names whose values are STALE."""
        stale_list = []
        raw = self.to_dict(current_time)
        for sub, fields in raw.items():
            if not isinstance(fields, dict):
                continue
            for fname, fdata in fields.items():
                if isinstance(fdata, dict) and fdata.get("provenance") == Provenance.STALE.value:
                    stale_list.append(f"{sub}.{fname}")
        return stale_list

    def get_unknown_fields(self, current_time: Optional[float] = None) -> List[str]:
        """Returns a list of dot-notated field names whose values are UNKNOWN."""
        unk_list = []
        raw = self.to_dict(current_time)
        for sub, fields in raw.items():
            if not isinstance(fields, dict):
                continue
            for fname, fdata in fields.items():
                if isinstance(fdata, dict) and fdata.get("provenance") == Provenance.UNKNOWN.value:
                    unk_list.append(f"{sub}.{fname}")
        return unk_list

    def to_brain_markdown_prompt(self, current_time: Optional[float] = None) -> str:
        """
        Formats canonical RoomState into an unambiguous structured perception block
        specifically designed for Gemini / LLM planner context injection.
        """
        now = current_time if current_time is not None else self.timestamp
        d = self.to_dict(now)
        
        lines = [
            "### CURRENT PHYSICAL REALITY",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}",
            f"System State Consistency: {'VALID' if self.is_consistent else 'DEGRADED / PARTIAL'}",
            "",
            "AC:",
            f"  power: {'ON' if d['ac']['power']['value'] is True else ('OFF' if d['ac']['power']['value'] is False else 'UNKNOWN')}",
            f"  target: {d['ac']['target_temperature']['value']}°C" if d['ac']['target_temperature']['value'] is not None else "  target: UNKNOWN",
            f"  mode: {d['ac']['mode']['value']}",
            f"  fan: {d['ac']['fan_speed']['value']}",
            f"  ambient: {d['ac']['ambient_temperature']['value']}°C" if d['ac']['ambient_temperature']['value'] is not None else "  ambient: N/A",
            f"  freshness: {'FRESH' if d['ac']['power']['provenance'] in ('OBSERVED', 'DERIVED') else d['ac']['power']['provenance']}",
            f"  provenance: {d['ac']['power']['provenance']}",
            f"  transport: {d['ac']['transport_used']['value']}",
            "",
            "SMART IR HUB:",
            f"  online: {'YES' if d['ir_hub']['online']['value'] is True else ('NO' if d['ir_hub']['online']['value'] is False else 'UNKNOWN')}",
            f"  freshness: {'FRESH' if d['ir_hub']['online']['provenance'] in ('OBSERVED', 'DERIVED') else d['ir_hub']['online']['provenance']}",
            f"  provenance: {d['ir_hub']['online']['provenance']}",
            f"  transport: {d['ir_hub']['transport']['value']}",
            "",
            "PROJECTOR:",
            f"  power: {'ON' if d['projector']['power']['value'] is True else ('OFF' if d['projector']['power']['value'] is False else 'UNKNOWN')}",
            f"  input_source: {d['projector']['input_source']['value']}",
            f"  signal_active: {'YES' if d['projector']['signal_active']['value'] is True else ('NO' if d['projector']['signal_active']['value'] is False else 'UNKNOWN')}",
            f"  freshness: {'FRESH' if d['projector']['power']['provenance'] in ('OBSERVED', 'DERIVED') else d['projector']['power']['provenance']}",
            f"  provenance: {d['projector']['power']['provenance']}",
            "",
            "FIRE TV:",
            f"  online: {'YES' if d['fire_tv']['online']['value'] is True else ('NO' if d['fire_tv']['online']['value'] is False else 'UNKNOWN')}",
            f"  power: {d['fire_tv']['power_state']['value']}",
            f"  foreground_app: {d['fire_tv']['foreground_app']['value']}",
            f"  soundbar_connected: {'YES' if d['fire_tv']['soundbar_connected']['value'] is True else ('NO' if d['fire_tv']['soundbar_connected']['value'] is False else 'UNKNOWN')}",
            f"  freshness: {'FRESH' if d['fire_tv']['online']['provenance'] in ('OBSERVED', 'DERIVED') else d['fire_tv']['online']['provenance']}",
            f"  provenance: {d['fire_tv']['online']['provenance']}",
            "",
            "PC AUDIO:",
            f"  volume: {d['pc']['master_volume']['value']}%" if d['pc']['master_volume']['value'] is not None else "  volume: UNKNOWN",
            f"  muted: {'YES' if d['pc']['is_muted']['value'] is True else ('NO' if d['pc']['is_muted']['value'] is False else 'UNKNOWN')}",
            f"  endpoint: {d['pc']['default_audio_endpoint']['value']}",
            f"  freshness: {'FRESH' if d['pc']['online']['provenance'] in ('OBSERVED', 'DERIVED') else d['pc']['online']['provenance']}",
            f"  provenance: {d['pc']['online']['provenance']}",
            "",
            "SOUNDBAR ROUTE:",
            f"  owner: {d['soundbar']['current_owner']['value']}",
            f"  connected: {'YES' if d['soundbar']['is_connected']['value'] is True else 'NO'}",
            f"  active_stream: {d['audio_stream']['active_producer']['value']}",
        ]
        return "\n".join(lines)
