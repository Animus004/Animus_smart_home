"""
Canonical RoomState Module for Animus Smart Room.
Authoritative physical state representation, provenance tracking, and hardware aggregation.
"""

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
    ENVIRONMENT_MODE_TTL
)
from room_state.models import (
    StateField,
    ProjectorState,
    AcState,
    FireTvState,
    PcState,
    SoundbarState,
    RoomEnvironmentState,
    RoomState
)
from room_state.derivations import (
    derive_projector_signal_active,
    derive_soundbar_state
)
from room_state.aggregator import RoomStateAggregator

__all__ = [
    "Provenance",
    "is_fresh",
    "resolve_provenance",
    "StateField",
    "ProjectorState",
    "AcState",
    "FireTvState",
    "PcState",
    "SoundbarState",
    "RoomEnvironmentState",
    "RoomState",
    "derive_projector_signal_active",
    "derive_soundbar_state",
    "RoomStateAggregator"
]
