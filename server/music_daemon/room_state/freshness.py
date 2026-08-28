"""
Deterministic Freshness & TTL Strategy for Animus Smart Room.
Enforces the authoritative TTL table from the E.6 Architecture Contract.
"""

import time
from typing import Optional
from room_state.provenance import Provenance

# -----------------------------------------------------------------------------
# Authoritative Freshness TTL Table (E.6 Architecture Contract Section 4.2)
# -----------------------------------------------------------------------------

# Projector
PROJECTOR_POWER_TTL = 5.0        # ADB socket probe
PROJECTOR_INPUT_TTL = 10.0       # Activity/window dump
PROJECTOR_BRIGHTNESS_TTL = 30.0   # Settings DB / UI
PROJECTOR_SIGNAL_TTL = 5.0       # HDMI HAL signal derivation
PROJECTOR_HEALTH_TTL = 10.0      # Socket latency & error rate

# Air Conditioner & IR Hub
AC_POWER_TTL = 15.0              # Tuya DP 1
AC_TARGET_TEMP_TTL = 15.0        # Tuya DP 2
AC_AMBIENT_TEMP_TTL = 30.0       # Tuya DP 3 (Physical indoor temperature sensor)
AC_MODE_TTL = 15.0               # Tuya DP 4
AC_FAN_SPEED_TTL = 15.0          # Tuya DP 5
AC_TRANSPORT_TTL = 30.0          # Transport flag
IR_HUB_ONLINE_TTL = 15.0         # Tuya LAN Socket / Heartbeat
IR_HUB_TRANSPORT_TTL = 30.0      # Transport flag

# Fire TV
FIRE_TV_ONLINE_TTL = 5.0         # ADB TCP socket
FIRE_TV_POWER_TTL = 5.0          # ADB dumpsys power
FIRE_TV_APP_TTL = 5.0            # ADB dumpsys window
FIRE_TV_BT_TTL = 5.0             # ADB dumpsys bluetooth_manager

# PC Host
PC_ONLINE_TTL = 2.0              # In-process daemon check
PC_VOLUME_TTL = 2.0              # CoreAudio COM scalar readback
PC_MUTE_TTL = 2.0                # CoreAudio COM boolean readback
PC_ENDPOINT_TTL = 2.0            # CoreAudio COM endpoint collection
PC_BT_TTL = 3.0                  # Windows 64-bit BluetoothApis

# Soundbar & Environment
SOUNDBAR_OWNER_TTL = 3.0         # Joint PC/Fire TV routing derivation
SOUNDBAR_CONNECTED_TTL = 3.0     # A2DP sink connection state
ENVIRONMENT_MODE_TTL = 5.0       # Orchestrator state
AUDIO_STREAM_TTL = 5.0           # Semantic audio stream & active producer state


def is_fresh(observed_at: float, ttl_seconds: float, current_time: Optional[float] = None) -> bool:
    """
    Returns True if elapsed time since observed_at is strictly within ttl_seconds.
    """
    if observed_at <= 0 or ttl_seconds <= 0:
        return False
    now = current_time if current_time is not None else time.time()
    return (now - observed_at) <= ttl_seconds


def resolve_provenance(
    base_provenance: Provenance,
    observed_at: float,
    ttl_seconds: float,
    current_time: Optional[float] = None
) -> Provenance:
    """
    Computes effective provenance considering elapsed time against TTL.
    - If base_provenance is UNKNOWN, remains UNKNOWN.
    - If base_provenance is OBSERVED or DERIVED, transitions to STALE if TTL expired.
    - If already STALE, remains STALE.
    """
    if base_provenance == Provenance.UNKNOWN:
        return Provenance.UNKNOWN

    if base_provenance in (Provenance.OBSERVED, Provenance.DERIVED):
        if is_fresh(observed_at, ttl_seconds, current_time):
            return base_provenance
        return Provenance.STALE

    return Provenance.STALE
