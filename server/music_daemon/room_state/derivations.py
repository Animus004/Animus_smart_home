"""
Deterministic State Derivations for Animus Smart Room.
Calculates DERIVED fields strictly from OBSERVED hardware telemetry without probabilistic guessing.
"""

import time
from typing import Optional
from room_state.models import StateField, SoundbarState
from room_state.provenance import Provenance


def derive_projector_signal_active(
    power_field: StateField[bool],
    input_source_field: StateField[str],
    raw_signal_obs: Optional[bool] = None,
    observed_at: Optional[float] = None
) -> StateField[bool]:
    """
    Deterministically derives projector.signal_active from physical power, source, and HAL activity.
    - If power is UNKNOWN -> signal_active is UNKNOWN.
    - If power is False -> signal_active is False (DERIVED).
    - If source is UNKNOWN -> signal_active is UNKNOWN.
    - If source is ANDROID_HOME -> signal_active is False (DERIVED, no external HDMI input active).
    - If source is HDMI_1 -> signal_active is raw_signal_obs if provided, else True (DERIVED).
    """
    ts = observed_at if observed_at is not None else time.time()
    source_tag = "DERIVATION_PROJECTOR_SIGNAL"

    # Power check
    if power_field.provenance == Provenance.UNKNOWN:
        return StateField.unknown(source=source_tag, observed_at=ts)

    if power_field.value is False:
        return StateField.derived(value=False, source=source_tag, observed_at=ts)

    # Source check
    if input_source_field.provenance == Provenance.UNKNOWN:
        return StateField.unknown(source=source_tag, observed_at=ts)

    src_val = str(input_source_field.value).upper()
    if src_val == "HDMI_1":
        active_val = bool(raw_signal_obs) if raw_signal_obs is not None else True
        return StateField.derived(value=active_val, source=source_tag, observed_at=ts)
    elif src_val in ("ANDROID_HOME", "HOME", "LAUNCHER"):
        return StateField.derived(value=False, source=source_tag, observed_at=ts)

    return StateField.derived(value=bool(raw_signal_obs), source=source_tag, observed_at=ts)


def derive_soundbar_state(
    pc_bt_connected_field: StateField[bool],
    pc_endpoint_field: StateField[str],
    fire_tv_online_field: StateField[bool],
    fire_tv_bt_field: StateField[bool],
    observed_at: Optional[float] = None
) -> SoundbarState:
    """
    Deterministically derives Soundbar ownership and connection state from PC and Fire TV observations.
    - If both PC and Fire TV queries failed -> Soundbar state is UNKNOWN.
    - If Fire TV is online and reports soundbar_connected == True -> Owner is FIRE_TV, connected = True.
    - Else if PC reports LG SNC4R connected or active in default audio endpoint -> Owner is PC, connected = True.
    - Else if both hosts are observable and report disconnected -> Owner is NONE, connected = False.
    """
    ts = observed_at if observed_at is not None else time.time()
    source_tag = "DERIVATION_SOUNDBAR_ROUTING"

    # Check if all sources are UNKNOWN
    all_unknown = (
        pc_bt_connected_field.provenance == Provenance.UNKNOWN
        and fire_tv_online_field.provenance == Provenance.UNKNOWN
    )
    if all_unknown:
        return SoundbarState(
            current_owner=StateField.unknown(source=source_tag, observed_at=ts),
            is_connected=StateField.unknown(source=source_tag, observed_at=ts)
        )

    # Check Fire TV ownership
    is_ftv_connected = (
        fire_tv_online_field.value is True
        and fire_tv_bt_field.value is True
        and fire_tv_bt_field.provenance != Provenance.UNKNOWN
    )

    # Check PC ownership
    endpoint_name = str(pc_endpoint_field.value or "").upper()
    is_pc_endpoint_snc = "LG" in endpoint_name and ("SNC" in endpoint_name or "79" in endpoint_name)
    is_pc_bt_connected = (pc_bt_connected_field.value is True) and (pc_bt_connected_field.provenance != Provenance.UNKNOWN)
    is_pc_connected = is_pc_bt_connected or is_pc_endpoint_snc

    if is_ftv_connected:
        return SoundbarState(
            current_owner=StateField.derived(value="FIRE_TV", source=source_tag, observed_at=ts),
            is_connected=StateField.derived(value=True, source=source_tag, observed_at=ts)
        )
    elif is_pc_connected:
        return SoundbarState(
            current_owner=StateField.derived(value="PC", source=source_tag, observed_at=ts),
            is_connected=StateField.derived(value=True, source=source_tag, observed_at=ts)
        )
    else:
        # Check if observations are valid to claim NONE
        return SoundbarState(
            current_owner=StateField.derived(value="NONE", source=source_tag, observed_at=ts),
            is_connected=StateField.derived(value=False, source=source_tag, observed_at=ts)
        )
