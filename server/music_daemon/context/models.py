"""
Strongly typed Pydantic data models for Preferences, Environmental Context,
Temporal Context, Room Semantic Context, and Context Snapshots in Animus Smart Room.
Contains pure data structures with strict validation — zero hardware mutation.
"""

from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from context.provenance import ContextProvenance, ContextProvenanceStatus
from context.errors import PreferenceValidationError


# =============================================================================
# 1. User & Room Preference Sub-Models
# =============================================================================

class ComfortPreferences(BaseModel):
    """Thermal and environmental comfort preferences."""
    preferred_ac_temperature: int = Field(default=24, ge=16, le=30, description="Preferred AC target temperature in Celsius (16-30).")
    preferred_ac_mode: str = Field(default="COOL", description="Preferred AC operating mode (COOL, AUTO, DRY, FAN).")
    preferred_ac_fan_speed: str = Field(default="AUTO", description="Preferred AC fan speed (LOW, MEDIUM, HIGH, AUTO).")

    @field_validator("preferred_ac_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("COOL", "AUTO", "DRY", "FAN"):
            raise PreferenceValidationError(f"Invalid AC mode '{v}'. Must be one of COOL, AUTO, DRY, FAN.", field="preferred_ac_mode", invalid_value=v)
        return upper

    @field_validator("preferred_ac_fan_speed")
    @classmethod
    def validate_fan(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("LOW", "MEDIUM", "HIGH", "AUTO"):
            raise PreferenceValidationError(f"Invalid AC fan speed '{v}'. Must be one of LOW, MEDIUM, HIGH, AUTO.", field="preferred_ac_fan_speed", invalid_value=v)
        return upper


class AudioPreferences(BaseModel):
    """Audio routing and default volume preferences."""
    preferred_pc_volume: int = Field(default=50, ge=0, le=100, description="Default PC master volume percentage (0-100).")
    preferred_fire_tv_volume_behavior: str = Field(default="DEFAULT", description="Volume normalization behavior for Fire TV.")
    preferred_soundbar_owner: str = Field(default="FIRE_TV", description="Preferred soundbar routing endpoint (FIRE_TV, PC).")

    @field_validator("preferred_soundbar_owner")
    @classmethod
    def validate_soundbar_owner(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("FIRE_TV", "PC"):
            raise PreferenceValidationError(f"Invalid soundbar owner '{v}'. Must be FIRE_TV or PC.", field="preferred_soundbar_owner", invalid_value=v)
        return upper


class EntertainmentPreferences(BaseModel):
    """Media consumption and playback preferences."""
    preferred_media_provider: str = Field(default="youtube", description="Preferred media streaming source (youtube, smarttube, vlc, mpv).")
    preferred_video_quality: str = Field(default="1080p", description="Preferred playback stream quality.")
    preferred_default_media_device: str = Field(default="fire_tv", description="Default media player device (fire_tv, pc).")

    @field_validator("preferred_default_media_device")
    @classmethod
    def validate_device(cls, v: str) -> str:
        lower = v.strip().lower()
        if lower not in ("fire_tv", "pc"):
            raise PreferenceValidationError(f"Invalid default media device '{v}'. Must be fire_tv or pc.", field="preferred_default_media_device", invalid_value=v)
        return lower


class ProjectorPreferences(BaseModel):
    """
    Projector operating preferences.
    STRICT INVARIANT: Only registered capabilities are represented. No fabricated features (e.g. picture_mode).
    """
    preferred_brightness: int = Field(default=80, ge=1, le=100, description="Default projector brightness level (1-100).")
    auto_focus_on_wake: bool = Field(default=False, description="Automatically trigger auto-focus on wake.")
    auto_keystone_on_wake: bool = Field(default=False, description="Automatically trigger auto-keystone on wake.")


class EnergyAndBehaviorPreferences(BaseModel):
    """Eco priorities, sleep behaviors, and quiet-hours policy."""
    eco_priority: bool = Field(default=False, description="Prioritize energy efficiency over rapid cooling/full brightness.")
    quiet_hours_enabled: bool = Field(default=True, description="Enforce volume dampening during quiet hours.")
    quiet_hours_start: str = Field(default="23:00", description="Start of quiet hours in HH:MM 24h format.")
    quiet_hours_end: str = Field(default="07:00", description="End of quiet hours in HH:MM 24h format.")
    preferred_sleep_behavior: str = Field(default="SLEEP", description="Default standby action on room shutdown (SLEEP, POWER_OFF).")


class UserPreferences(BaseModel):
    """
    Authoritative composite user and room preferences model.
    """
    comfort: ComfortPreferences = Field(default_factory=ComfortPreferences)
    audio: AudioPreferences = Field(default_factory=AudioPreferences)
    entertainment: EntertainmentPreferences = Field(default_factory=EntertainmentPreferences)
    projector: ProjectorPreferences = Field(default_factory=ProjectorPreferences)
    energy: EnergyAndBehaviorPreferences = Field(default_factory=EnergyAndBehaviorPreferences)
    provenance: ContextProvenance = Field(
        default_factory=lambda: ContextProvenance(source="USER_PREFERENCES_PROFILE", status=ContextProvenanceStatus.KNOWN)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dictionary serialization for prompts and REST endpoints."""
        return {
            "comfort": self.comfort.model_dump(),
            "audio": self.audio.model_dump(),
            "entertainment": self.entertainment.model_dump(),
            "projector": self.projector.model_dump(),
            "energy": self.energy.model_dump(),
            "provenance": self.provenance.to_dict()
        }


# =============================================================================
# 2. Context Sub-Models
# =============================================================================

class TemporalContext(BaseModel):
    """
    Temporal context representing the current moment, calendar day, and circadian classification.
    """
    timestamp: float
    iso_timestamp: str
    local_date: str
    local_time: str
    day_of_week: str
    is_weekend: bool
    day_period: str
    is_quiet_hours: bool
    provenance: ContextProvenance = Field(
        default_factory=lambda: ContextProvenance(source="SYSTEM_CLOCK", status=ContextProvenanceStatus.KNOWN, ttl_seconds=1.0)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "iso_timestamp": self.iso_timestamp,
            "local_date": self.local_date,
            "local_time": self.local_time,
            "day_of_week": self.day_of_week,
            "is_weekend": self.is_weekend,
            "day_period": self.day_period,
            "is_quiet_hours": self.is_quiet_hours,
            "provenance": self.provenance.to_dict()
        }


class RoomSemanticContext(BaseModel):
    """
    Derived high-level semantic summary computed strictly from canonical RoomState.
    """
    is_projector_active: bool
    is_media_playing: bool
    is_room_idle: bool
    current_audio_owner: str
    room_mode: str
    active_audio_producer: str = "UNKNOWN"
    media_playback_state: str = "UNKNOWN"
    desired_audio_owner: Optional[str] = None
    soundbar_route_required: bool = False
    audio_routing_reason: str = "UNINITIALIZED"
    provenance: ContextProvenance = Field(
        default_factory=lambda: ContextProvenance(source="CANONICAL_ROOM_STATE", status=ContextProvenanceStatus.DERIVED, ttl_seconds=5.0)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_projector_active": self.is_projector_active,
            "is_media_playing": self.is_media_playing,
            "is_room_idle": self.is_room_idle,
            "current_audio_owner": self.current_audio_owner,
            "room_mode": self.room_mode,
            "active_audio_producer": self.active_audio_producer,
            "media_playback_state": self.media_playback_state,
            "desired_audio_owner": self.desired_audio_owner,
            "soundbar_route_required": self.soundbar_route_required,
            "audio_routing_reason": self.audio_routing_reason,
            "provenance": self.provenance.to_dict()
        }


class WeatherContext(BaseModel):
    """
    Meteorological context for reference location PIN 741235.
    If weather service is unavailable, degrades safely with explicit UNAVAILABLE provenance.
    """
    location_pin: str = "741235"
    available: bool = False
    condition: Optional[str] = None
    outdoor_temperature_c: Optional[float] = None
    outdoor_humidity_pct: Optional[float] = None
    provenance: ContextProvenance = Field(
        default_factory=lambda: ContextProvenance(source="WEATHER_PROVIDER", status=ContextProvenanceStatus.UNAVAILABLE)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_pin": self.location_pin,
            "available": self.available,
            "condition": self.condition,
            "outdoor_temperature_c": self.outdoor_temperature_c,
            "outdoor_humidity_pct": self.outdoor_humidity_pct,
            "provenance": self.provenance.to_dict()
        }


class PrecedenceHierarchy(BaseModel):
    """
    Deterministic rule hierarchy defining authority precedence for decision-making.
    Gemini must never decide precedence — it is strictly ordered by contract.
    """
    hierarchy: List[str] = [
        "1. SAFETY / HARDWARE CONSTRAINTS (Highest Priority)",
        "2. EXPLICIT USER REQUEST",
        "3. CURRENT ROOM STATE (Physical Telemetry)",
        "4. USER PREFERENCES",
        "5. ENVIRONMENTAL CONTEXT",
        "6. SAFE DEFAULTS (Lowest Priority)"
    ]

    def to_dict(self) -> Dict[str, Any]:
        return {"precedence_order": self.hierarchy}


# =============================================================================
# 3. Context Snapshot Aggregate
# =============================================================================

class ContextSnapshot(BaseModel):
    """
    Comprehensive, immutable context snapshot supplied to the Gemini Structured Planner.
    Serializes into a strictly sanitized, machine-readable dictionary with zero leaked objects.
    """
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: float = Field(default_factory=time.time)
    temporal: TemporalContext
    room: RoomSemanticContext
    weather: WeatherContext
    preferences: UserPreferences
    precedence: PrecedenceHierarchy = Field(default_factory=PrecedenceHierarchy)

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic JSON dictionary representation."""
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "temporal": self.temporal.to_dict(),
            "room_summary": self.room.to_dict(),
            "weather": self.weather.to_dict(),
            "preferences": self.preferences.to_dict(),
            "precedence_hierarchy": self.precedence.to_dict()
        }
