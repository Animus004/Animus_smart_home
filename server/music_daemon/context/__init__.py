"""
Preferences & Context Engine Subsystem for Animus Smart Room.
Provides strongly-typed, validated preferences and context snapshots for the Gemini Structured Planner.
"""

from context.errors import (
    ContextError,
    PreferenceValidationError,
    ContextUnavailableError
)
from context.provenance import (
    ContextProvenanceStatus,
    ContextProvenance
)
from context.models import (
    ComfortPreferences,
    AudioPreferences,
    EntertainmentPreferences,
    ProjectorPreferences,
    EnergyAndBehaviorPreferences,
    UserPreferences,
    TemporalContext,
    RoomSemanticContext,
    WeatherContext,
    PrecedenceHierarchy,
    ContextSnapshot
)
from context.preferences import PreferenceManager
from context.engine import (
    BaseWeatherProvider,
    FallbackWeatherProvider,
    ContextEngine
)

__all__ = [
    "ContextError",
    "PreferenceValidationError",
    "ContextUnavailableError",
    "ContextProvenanceStatus",
    "ContextProvenance",
    "ComfortPreferences",
    "AudioPreferences",
    "EntertainmentPreferences",
    "ProjectorPreferences",
    "EnergyAndBehaviorPreferences",
    "UserPreferences",
    "TemporalContext",
    "RoomSemanticContext",
    "WeatherContext",
    "PrecedenceHierarchy",
    "ContextSnapshot",
    "PreferenceManager",
    "BaseWeatherProvider",
    "FallbackWeatherProvider",
    "ContextEngine"
]
