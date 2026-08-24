"""
Unit and Contract Test Suite for Phase E.7.5 Preferences & Context Engine.
Tests preference validation, capability bounds enforcement, temporal context derivation,
room semantic synthesis, weather provider interfaces, precedence ordering,
planner prompt payload assembly, and FastAPI diagnostic endpoints.
"""

import time
import datetime
import pytest
from unittest.mock import MagicMock, patch

from capability_registry import UnifiedCapabilityRegistry
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
from room_state.provenance import Provenance
from context import (
    PreferenceManager,
    ContextEngine,
    UserPreferences,
    ComfortPreferences,
    AudioPreferences,
    EntertainmentPreferences,
    ProjectorPreferences,
    EnergyAndBehaviorPreferences,
    ContextProvenance,
    ContextProvenanceStatus,
    TemporalContext,
    RoomSemanticContext,
    WeatherContext,
    PrecedenceHierarchy,
    ContextSnapshot,
    BaseWeatherProvider,
    FallbackWeatherProvider,
    PreferenceValidationError
)
from planner import (
    GeminiPlannerClient,
    GeminiStructuredPlan,
    PlanStep,
    PlanValidator
)


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def mock_room_state():
    """Constructs a deterministic, fresh canonical RoomState."""
    now = time.time()
    return RoomState(
        timestamp=now,
        is_consistent=True,
        projector=ProjectorState(
            power=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            input_source=StateField(value="HDMI_1", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            brightness=StateField(value=80, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            signal_active=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            health=StateField(value="OK", provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        ac=AcState(
            power=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            target_temperature=StateField(value=24, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            ambient_temperature=StateField(value=26, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            mode=StateField(value="COOL", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            fan_speed=StateField(value="MEDIUM", provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        fire_tv=FireTvState(
            online=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            power_state=StateField(value="AWAKE", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            foreground_app=StateField(value="com.amazon.tv.launcher", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            soundbar_connected=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        pc=PcState(
            online=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            master_volume=StateField(value=60, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            is_muted=StateField(value=False, provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            default_audio_endpoint=StateField(value="Realtek High Definition Audio", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            bluetooth_radio_active=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        soundbar=SoundbarState(
            current_owner=StateField(value="FIRE_TV", provenance=Provenance.OBSERVED, observed_at=now, source="TEST"),
            is_connected=StateField(value=True, provenance=Provenance.OBSERVED, observed_at=now, source="TEST")
        ),
        environment=RoomEnvironmentState(
            room_mode=StateField(value="CINEMA", provenance=Provenance.DERIVED, observed_at=now, source="TEST"),
            active_audio_route=StateField(value="FIRE_TV", provenance=Provenance.DERIVED, observed_at=now, source="TEST")
        )
    )


# =============================================================================
# 1. Preference Model & Validation Tests
# =============================================================================

def test_default_preferences():
    manager = PreferenceManager()
    prefs = manager.get_preferences()
    assert prefs.comfort.preferred_ac_temperature == 24
    assert prefs.comfort.preferred_ac_mode == "COOL"
    assert prefs.comfort.preferred_ac_fan_speed == "AUTO"
    assert prefs.audio.preferred_pc_volume == 50
    assert prefs.audio.preferred_soundbar_owner == "FIRE_TV"
    assert prefs.entertainment.preferred_default_media_device == "fire_tv"
    assert prefs.projector.preferred_brightness == 80


def test_valid_preference_update():
    manager = PreferenceManager()
    updated = manager.update_preferences({
        "preferred_ac_temperature": 21,
        "preferred_ac_mode": "AUTO",
        "preferred_pc_volume": 40
    })
    assert updated.comfort.preferred_ac_temperature == 21
    assert updated.comfort.preferred_ac_mode == "AUTO"
    assert updated.audio.preferred_pc_volume == 40


def test_invalid_ac_temperature_rejected():
    manager = PreferenceManager()
    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"preferred_ac_temperature": 14})  # Below 16

    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"preferred_ac_temperature": 35})  # Above 30


def test_invalid_pc_volume_rejected():
    manager = PreferenceManager()
    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"preferred_pc_volume": -5})

    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"preferred_pc_volume": 120})


def test_invalid_ac_mode_rejected():
    manager = PreferenceManager()
    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"preferred_ac_mode": "HEAT"})  # Unsupported hardware mode


def test_invalid_fan_speed_rejected():
    manager = PreferenceManager()
    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"preferred_ac_fan_speed": "TURBO_MAX"})


def test_unknown_preference_key_rejected():
    manager = PreferenceManager()
    with pytest.raises(PreferenceValidationError):
        manager.update_preferences({"arbitrary_unknown_key": 123})


def test_preference_serialization_to_dict():
    manager = PreferenceManager()
    d = manager.export_prompt_dict()
    assert "comfort" in d
    assert "audio" in d
    assert "entertainment" in d
    assert "projector" in d
    assert "energy" in d
    assert "provenance" in d
    assert d["comfort"]["preferred_ac_temperature"] == 24


# =============================================================================
# 2. Temporal & Context Engine Tests
# =============================================================================

def test_temporal_context_derivation():
    engine = ContextEngine()
    prefs = UserPreferences()

    # Create fixed timestamp: Monday, Oct 12, 2026 14:30:00
    test_dt = datetime.datetime(2026, 10, 12, 14, 30, 0)
    now_ts = test_dt.timestamp()

    temporal = engine.get_temporal_context(now_ts, prefs)
    assert temporal.local_date == "2026-10-12"
    assert temporal.local_time == "14:30:00"
    assert temporal.day_of_week == "Monday"
    assert temporal.is_weekend is False
    assert temporal.day_period == "AFTERNOON"
    assert temporal.is_quiet_hours is False


def test_weekend_and_night_detection():
    engine = ContextEngine()
    prefs = UserPreferences()

    # Create fixed timestamp: Sunday, Oct 18, 2026 23:45:00
    test_dt = datetime.datetime(2026, 10, 18, 23, 45, 0)
    now_ts = test_dt.timestamp()

    temporal = engine.get_temporal_context(now_ts, prefs)
    assert temporal.day_of_week == "Sunday"
    assert temporal.is_weekend is True
    assert temporal.day_period == "NIGHT"
    assert temporal.is_quiet_hours is True  # 23:45 is in 23:00-07:00


def test_quiet_hours_midnight_span():
    engine = ContextEngine()
    prefs = UserPreferences(
        energy=EnergyAndBehaviorPreferences(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="06:00"
        )
    )

    # 03:00 AM (inside quiet hours)
    dt_quiet = datetime.datetime(2026, 10, 12, 3, 0, 0)
    t_quiet = engine.get_temporal_context(dt_quiet.timestamp(), prefs)
    assert t_quiet.is_quiet_hours is True

    # 15:00 PM (outside quiet hours)
    dt_active = datetime.datetime(2026, 10, 12, 15, 0, 0)
    t_active = engine.get_temporal_context(dt_active.timestamp(), prefs)
    assert t_active.is_quiet_hours is False


# =============================================================================
# 3. Room Semantic Context & Weather Tests
# =============================================================================

def test_room_semantic_context_synthesis(mock_room_state):
    engine = ContextEngine()
    room_ctx = engine.get_room_semantic_context(mock_room_state)
    assert room_ctx.is_projector_active is True
    assert room_ctx.is_media_playing is True
    assert room_ctx.is_room_idle is False
    assert room_ctx.current_audio_owner == "FIRE_TV"
    assert room_ctx.room_mode == "CINEMA"


def test_fallback_weather_provider_unavailable():
    engine = ContextEngine(weather_provider=FallbackWeatherProvider())
    w = engine.get_weather_context()
    assert w.location_pin == "741235"
    assert w.available is False
    assert w.condition is None
    assert w.provenance.status == ContextProvenanceStatus.UNAVAILABLE


def test_custom_weather_provider():
    class MockLiveWeatherProvider(BaseWeatherProvider):
        def get_weather(self, pin: str = "741235") -> WeatherContext:
            return WeatherContext(
                location_pin=pin,
                available=True,
                condition="CLEAR_SUNNY",
                outdoor_temperature_c=31.5,
                outdoor_humidity_pct=65.0,
                provenance=ContextProvenance(
                    source="METEOROLOGICAL_STATION_TEST",
                    status=ContextProvenanceStatus.KNOWN,
                    observed_at=time.time(),
                    ttl_seconds=1800.0
                )
            )

    engine = ContextEngine(weather_provider=MockLiveWeatherProvider())
    w = engine.get_weather_context()
    assert w.available is True
    assert w.condition == "CLEAR_SUNNY"
    assert w.outdoor_temperature_c == 31.5
    assert w.provenance.is_fresh() is True


def test_context_snapshot_full_assembly(mock_room_state):
    engine = ContextEngine()
    snapshot = engine.build_context_snapshot(room_state=mock_room_state)
    d = snapshot.to_dict()

    assert "snapshot_id" in d
    assert "temporal" in d
    assert "room_summary" in d
    assert "weather" in d
    assert "preferences" in d
    assert "precedence_hierarchy" in d

    assert d["weather"]["location_pin"] == "741235"
    assert d["room_summary"]["is_projector_active"] is True
    assert len(d["precedence_hierarchy"]["precedence_order"]) == 6


# =============================================================================
# 4. Precedence Hierarchy Contract
# =============================================================================

def test_precedence_hierarchy_order():
    hierarchy = PrecedenceHierarchy()
    order = hierarchy.hierarchy
    assert "SAFETY" in order[0]
    assert "EXPLICIT USER REQUEST" in order[1]
    assert "CURRENT ROOM STATE" in order[2]
    assert "USER PREFERENCES" in order[3]
    assert "ENVIRONMENTAL CONTEXT" in order[4]
    assert "SAFE DEFAULTS" in order[5]


# =============================================================================
# 5. Gemini Prompt Payload Integration
# =============================================================================

def test_gemini_prompt_payload_includes_context_and_preferences(mock_room_state):
    client = GeminiPlannerClient(api_key="mock_key")
    engine = ContextEngine()
    snapshot = engine.build_context_snapshot(room_state=mock_room_state)

    payload_json = client.build_prompt_payload(
        user_request="Cool down the room",
        room_state=mock_room_state,
        context=snapshot.to_dict()["weather"],
        preferences=snapshot.to_dict()["preferences"]
    )
    assert "user_request" in payload_json
    assert "room_state" in payload_json
    assert "available_capabilities" in payload_json
    assert "context" in payload_json
    assert "preferences" in payload_json


# =============================================================================
# 6. FastAPI Read-Only Context & Preferences Endpoints
# =============================================================================

def test_fastapi_preferences_and_context_endpoints(mock_room_state):
    from fastapi.testclient import TestClient
    from main import app, preference_manager, context_engine

    client = TestClient(app)

    # GET /api/preferences
    r_pref = client.get("/api/preferences")
    assert r_pref.status_code == 200
    pref_data = r_pref.json()
    assert "comfort" in pref_data
    assert pref_data["comfort"]["preferred_ac_temperature"] == 24

    # GET /api/context
    r_ctx = client.get("/api/context")
    assert r_ctx.status_code == 200
    ctx_data = r_ctx.json()
    assert "temporal" in ctx_data
    assert "weather" in ctx_data
    assert ctx_data["weather"]["location_pin"] == "741235"
    assert "precedence_hierarchy" in ctx_data
