"""
Authoritative Context Engine for Animus Smart Room.
Compiles deterministic Temporal, Room Semantic, Environmental (PIN 741235),
and Preference Context into strongly-typed, sanitized ContextSnapshots for the Gemini Planner.
STRICT INVARIANT: Read-only context synthesis — zero hardware commands or autonomous loops.
"""

from __future__ import annotations
import datetime
import logging
import time
from typing import Any, Dict, Optional

from room_state.models import RoomState
from room_state.provenance import Provenance
from room_state.aggregator import RoomStateAggregator
from context.models import (
    ContextSnapshot,
    TemporalContext,
    RoomSemanticContext,
    WeatherContext,
    PrecedenceHierarchy,
    UserPreferences
)
from context.provenance import ContextProvenance, ContextProvenanceStatus
from context.preferences import PreferenceManager

logger = logging.getLogger("music_daemon.context.engine")


class BaseWeatherProvider:
    """Interface for external meteorological context providers."""

    def get_weather(self, pin: str = "741235") -> WeatherContext:
        """Retrieves weather telemetry for the specified postal PIN code."""
        raise NotImplementedError


class FallbackWeatherProvider(BaseWeatherProvider):
    """
    Default safe weather provider.
    Explicitly reports UNAVAILABLE status when no live external meteorological API is configured,
    preventing fabricated or hallucinated weather values.
    """

    def get_weather(self, pin: str = "741235") -> WeatherContext:
        return WeatherContext(
            location_pin=pin,
            available=False,
            condition=None,
            outdoor_temperature_c=None,
            outdoor_humidity_pct=None,
            provenance=ContextProvenance(
                source="WEATHER_PROVIDER_UNCONFIGURED",
                status=ContextProvenanceStatus.UNAVAILABLE,
                observed_at=time.time(),
                confidence=0.0
            )
        )


class ContextEngine:
    """
    Synthesizes multi-source environmental, temporal, physical room, and preference state.
    """

    def __init__(
        self,
        preference_manager: Optional[PreferenceManager] = None,
        room_state_aggregator: Optional[RoomStateAggregator] = None,
        weather_provider: Optional[BaseWeatherProvider] = None
    ):
        self.preference_manager = preference_manager or PreferenceManager()
        self.room_state_aggregator = room_state_aggregator
        self.weather_provider = weather_provider or FallbackWeatherProvider()

    def build_context_snapshot(
        self,
        room_state: Optional[RoomState] = None,
        current_time: Optional[float] = None,
        preference_overrides: Optional[Dict[str, Any]] = None
    ) -> ContextSnapshot:
        """
        Builds an immutable, complete context snapshot.
        """
        now = current_time if current_time is not None else time.time()

        # 1. Resolve User Preferences
        prefs = self.preference_manager.get_preferences()
        if preference_overrides:
            try:
                # Construct temporary override model without modifying global profile
                merged = prefs.model_dump()
                for k, v in preference_overrides.items():
                    if k in merged and isinstance(v, dict):
                        merged[k].update(v)
                    elif k in merged:
                        merged[k] = v
                prefs = self.preference_manager.validate_preferences(merged)
            except Exception as e:
                logger.warning(f"[CONTEXT_ENGINE] Preference overrides invalid ({e}), using active profile.")

        # 2. Temporal Context
        temporal = self.get_temporal_context(now, prefs)

        # 3. Canonical Room State & Semantic Extraction
        active_room_state = room_state
        if active_room_state is None and self.room_state_aggregator:
            active_room_state = self.room_state_aggregator.get_room_state(current_time=now)
        elif active_room_state is None:
            active_room_state = RoomState(timestamp=now)

        room_semantic = self.get_room_semantic_context(active_room_state)

        # 4. Environmental / Weather Context
        weather = self.get_weather_context()

        # 5. Precedence Hierarchy
        precedence = PrecedenceHierarchy()

        return ContextSnapshot(
            generated_at=now,
            temporal=temporal,
            room=room_semantic,
            weather=weather,
            preferences=prefs,
            precedence=precedence
        )

    def get_temporal_context(self, now_ts: float, prefs: UserPreferences) -> TemporalContext:
        """
        Derives local temporal, calendar, and quiet-hours classification from system time.
        """
        dt = datetime.datetime.fromtimestamp(now_ts)
        iso_str = dt.isoformat()
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%H:%M:%S")
        day_name = dt.strftime("%A")
        is_weekend = dt.weekday() >= 5  # Saturday (5), Sunday (6)

        # Day Period Classification
        hour = dt.hour
        if 5 <= hour < 12:
            period = "MORNING"
        elif 12 <= hour < 17:
            period = "AFTERNOON"
        elif 17 <= hour < 22:
            period = "EVENING"
        else:
            period = "NIGHT"

        # Quiet Hours Evaluation
        is_quiet = False
        if prefs.energy.quiet_hours_enabled:
            try:
                start_h, start_m = map(int, prefs.energy.quiet_hours_start.split(":"))
                end_h, end_m = map(int, prefs.energy.quiet_hours_end.split(":"))
                current_minutes = hour * 60 + dt.minute
                start_minutes = start_h * 60 + start_m
                end_minutes = end_h * 60 + end_m

                if start_minutes > end_minutes:
                    # Spans midnight (e.g. 23:00 to 07:00)
                    is_quiet = current_minutes >= start_minutes or current_minutes < end_minutes
                else:
                    is_quiet = start_minutes <= current_minutes < end_minutes
            except Exception as e:
                logger.warning(f"[CONTEXT_ENGINE] Quiet hours parsing error: {e}")

        return TemporalContext(
            timestamp=now_ts,
            iso_timestamp=iso_str,
            local_date=date_str,
            local_time=time_str,
            day_of_week=day_name,
            is_weekend=is_weekend,
            day_period=period,
            is_quiet_hours=is_quiet,
            provenance=ContextProvenance(
                source="SYSTEM_CLOCK",
                status=ContextProvenanceStatus.KNOWN,
                observed_at=now_ts,
                ttl_seconds=1.0
            )
        )

    def get_room_semantic_context(self, state: RoomState) -> RoomSemanticContext:
        """
        Derives high-level semantic status from authoritative physical RoomState.
        """
        # Projector Active Check
        proj_power = state.projector.power
        is_proj_active = (
            proj_power.provenance in (Provenance.OBSERVED, Provenance.DERIVED)
            and proj_power.value is True
        )

        # Audio Routing Owner
        audio_owner = str(state.soundbar.current_owner.value or "NONE").upper()

        # Room Mode
        room_mode = str(state.environment.room_mode.value or "IDLE").upper()

        # Media Playing Check
        is_media_playing = room_mode in ("CINEMA", "MUSIC", "MEDIA_PLAYING") or (
            state.fire_tv.foreground_app.value not in (None, "com.amazon.tv.launcher", "UNKNOWN")
            and is_proj_active
        )

        # Room Idle Check
        is_idle = not is_proj_active and not is_media_playing and state.ac.power.value is False

        return RoomSemanticContext(
            is_projector_active=is_proj_active,
            is_media_playing=is_media_playing,
            is_room_idle=is_idle,
            current_audio_owner=audio_owner,
            room_mode=room_mode,
            provenance=ContextProvenance(
                source="CANONICAL_ROOM_STATE",
                status=ContextProvenanceStatus.DERIVED,
                observed_at=state.timestamp,
                ttl_seconds=5.0
            )
        )

    def get_weather_context(self) -> WeatherContext:
        """Queries the configured weather provider."""
        try:
            return self.weather_provider.get_weather(pin="741235")
        except Exception as e:
            logger.warning(f"[CONTEXT_ENGINE] Weather provider query error: {e}")
            return WeatherContext(
                location_pin="741235",
                available=False,
                provenance=ContextProvenance(
                    source="WEATHER_PROVIDER_ERROR",
                    status=ContextProvenanceStatus.UNAVAILABLE,
                    observed_at=time.time()
                )
            )
