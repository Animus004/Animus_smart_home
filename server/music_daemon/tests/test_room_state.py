"""
Unit and Contract Test Suite for Phase E.7.1 Canonical RoomState Foundation.
Verifies RoomState schema, StateField provenance, TTL freshness, deterministic derivations,
and RoomStateAggregator error isolation.
"""

import time
import pytest
from unittest.mock import MagicMock

from room_state.provenance import Provenance
from room_state.freshness import (
    is_fresh,
    resolve_provenance,
    PROJECTOR_POWER_TTL,
    AC_TARGET_TEMP_TTL,
    FIRE_TV_ONLINE_TTL,
    PC_VOLUME_TTL
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


# =============================================================================
# 1. StateField & Provenance Unit Tests
# =============================================================================

def test_state_field_factories():
    t0 = 1000.0
    f_obs = StateField.observed(True, "HW_TEST", observed_at=t0)
    assert f_obs.value is True
    assert f_obs.provenance == Provenance.OBSERVED
    assert f_obs.observed_at == t0
    assert f_obs.source == "HW_TEST"

    f_der = StateField.derived("HDMI_1", "DERIVE_TEST", observed_at=t0)
    assert f_der.value == "HDMI_1"
    assert f_der.provenance == Provenance.DERIVED

    f_unk = StateField.unknown("FAIL_TEST", observed_at=t0)
    assert f_unk.value is None
    assert f_unk.provenance == Provenance.UNKNOWN

    f_stl = StateField.stale(24, "STALE_TEST", observed_at=t0)
    assert f_stl.value == 24
    assert f_stl.provenance == Provenance.STALE


def test_state_field_freshness_and_stale_transition():
    t0 = 1000.0
    ttl = 5.0

    f_obs = StateField.observed("ON", "TEST", observed_at=t0)

    # Within TTL (fresh)
    assert f_obs.is_fresh(ttl, current_time=1004.0) is True
    assert f_obs.effective_provenance(ttl, current_time=1004.0) == Provenance.OBSERVED

    # Exactly at boundary
    assert f_obs.is_fresh(ttl, current_time=1005.0) is True
    assert f_obs.effective_provenance(ttl, current_time=1005.0) == Provenance.OBSERVED

    # Past TTL (stale)
    assert f_obs.is_fresh(ttl, current_time=1006.0) is False
    assert f_obs.effective_provenance(ttl, current_time=1006.0) == Provenance.STALE

    # UNKNOWN field never becomes STALE
    f_unk = StateField.unknown("TEST", observed_at=t0)
    assert f_unk.effective_provenance(ttl, current_time=1020.0) == Provenance.UNKNOWN


# =============================================================================
# 2. Deterministic Derivation Tests
# =============================================================================

def test_derive_projector_signal_active():
    t0 = 1000.0

    # 1. Power UNKNOWN -> Signal UNKNOWN
    f_pwr_unk = StateField.unknown("ADB_ERR", t0)
    f_src = StateField.observed("HDMI_1", "ADB", t0)
    sig_res = derive_projector_signal_active(f_pwr_unk, f_src, observed_at=t0)
    assert sig_res.provenance == Provenance.UNKNOWN
    assert sig_res.value is None

    # 2. Power False -> Signal False (DERIVED)
    f_pwr_off = StateField.observed(False, "ADB", t0)
    sig_res2 = derive_projector_signal_active(f_pwr_off, f_src, observed_at=t0)
    assert sig_res2.provenance == Provenance.DERIVED
    assert sig_res2.value is False

    # 3. Power True, Source ANDROID_HOME -> Signal False (DERIVED)
    f_pwr_on = StateField.observed(True, "ADB", t0)
    f_src_home = StateField.observed("ANDROID_HOME", "ADB", t0)
    sig_res3 = derive_projector_signal_active(f_pwr_on, f_src_home, observed_at=t0)
    assert sig_res3.provenance == Provenance.DERIVED
    assert sig_res3.value is False

    # 4. Power True, Source HDMI_1 -> Signal True (DERIVED)
    sig_res4 = derive_projector_signal_active(f_pwr_on, f_src, raw_signal_obs=True, observed_at=t0)
    assert sig_res4.provenance == Provenance.DERIVED
    assert sig_res4.value is True


def test_derive_soundbar_state():
    t0 = 1000.0

    # 1. Fire TV connected
    pc_bt = StateField.observed(False, "PC_BT", t0)
    pc_ep = StateField.observed("2270W (NVIDIA High Definition Audio)", "PC_COM", t0)
    ftv_on = StateField.observed(True, "FTV_ADB", t0)
    ftv_bt = StateField.observed(True, "FTV_ADB", t0)

    sb_ftv = derive_soundbar_state(pc_bt, pc_ep, ftv_on, ftv_bt, observed_at=t0)
    assert sb_ftv.current_owner.value == "FIRE_TV"
    assert sb_ftv.current_owner.provenance == Provenance.DERIVED
    assert sb_ftv.is_connected.value is True

    # 2. PC connected via Bluetooth / CoreAudio endpoint
    ftv_bt_off = StateField.observed(False, "FTV_ADB", t0)
    pc_ep_snc = StateField.observed("Speakers (LG SNC4R(79))", "PC_COM", t0)

    sb_pc = derive_soundbar_state(pc_bt, pc_ep_snc, ftv_on, ftv_bt_off, observed_at=t0)
    assert sb_pc.current_owner.value == "PC"
    assert sb_pc.current_owner.provenance == Provenance.DERIVED
    assert sb_pc.is_connected.value is True

    # 3. Neither connected
    sb_none = derive_soundbar_state(pc_bt, pc_ep, ftv_on, ftv_bt_off, observed_at=t0)
    assert sb_none.current_owner.value == "NONE"
    assert sb_none.current_owner.provenance == Provenance.DERIVED
    assert sb_none.is_connected.value is False

    # 4. All sources UNKNOWN
    pc_bt_unk = StateField.unknown("ERR", t0)
    ftv_on_unk = StateField.unknown("ERR", t0)
    sb_unk = derive_soundbar_state(pc_bt_unk, pc_ep, ftv_on_unk, ftv_bt_off, observed_at=t0)
    assert sb_unk.current_owner.provenance == Provenance.UNKNOWN
    assert sb_unk.is_connected.provenance == Provenance.UNKNOWN


# =============================================================================
# 3. Canonical RoomState Serialization & Sanitization
# =============================================================================

def test_room_state_serialization_and_stale_tracking():
    t0 = 1000.0
    now = 1010.0  # 10s later

    # Create RoomState with mixture of fresh and stale fields
    state = RoomState(
        timestamp=now,
        is_consistent=True,
        projector=ProjectorState(
            power=StateField.observed(True, "ADB", observed_at=t0),           # 10s old, TTL=5s -> STALE
            input_source=StateField.observed("HDMI_1", "ADB", observed_at=t0), # 10s old, TTL=10s -> FRESH
            brightness=StateField.observed(80, "ADB", observed_at=t0),       # 10s old, TTL=30s -> FRESH
            signal_active=StateField.derived(True, "DERIVE", observed_at=now), # 0s old -> FRESH
            health=StateField.observed("OK", "ADB", observed_at=now)
        ),
        ac=AcState(
            power=StateField.observed(True, "TUYA", observed_at=now),
            target_temperature=StateField.observed(24, "TUYA", observed_at=now),
            ambient_temperature=StateField.observed(28, "TUYA", observed_at=t0), # 10s old, TTL=30s -> FRESH
            mode=StateField.observed("COOL", "TUYA", observed_at=now),
            fan_speed=StateField.observed("AUTO", "TUYA", observed_at=now),
            transport_used=StateField.observed("LOCAL_TUYA_3.3", "TUYA", observed_at=now)
        ),
        fire_tv=FireTvState(
            online=StateField.observed(True, "ADB", observed_at=now),
            power_state=StateField.observed("AWAKE", "ADB", observed_at=now),
            foreground_app=StateField.observed("com.netflix.ninja", "ADB", observed_at=now),
            soundbar_connected=StateField.observed(True, "ADB", observed_at=now)
        ),
        pc=PcState(
            online=StateField.observed(True, "DAEMON", observed_at=now),
            master_volume=StateField.observed(80, "COM", observed_at=t0),     # 10s old, TTL=2s -> STALE
            is_muted=StateField.observed(False, "COM", observed_at=now),
            default_audio_endpoint=StateField.observed("2270W", "COM", observed_at=now),
            bluetooth_radio_active=StateField.observed(True, "BT", observed_at=now)
        ),
        soundbar=SoundbarState(
            current_owner=StateField.derived("FIRE_TV", "DERIVE", observed_at=now),
            is_connected=StateField.derived(True, "DERIVE", observed_at=now)
        ),
        environment=RoomEnvironmentState(
            room_mode=StateField.derived("MOVIE_ACTIVE", "ORCH", observed_at=now),
            active_audio_route=StateField.derived("FIRE_TV_DIRECT", "ORCH", observed_at=now)
        )
    )

    stale_fields = state.get_stale_fields(current_time=now)
    assert "projector.power" in stale_fields
    assert "pc.master_volume" in stale_fields
    assert "ac.target_temperature" not in stale_fields

    prompt_dict = state.to_sanitized_prompt_dict(current_time=now)
    assert prompt_dict["projector"]["power"] == "True (STALE)"
    assert prompt_dict["projector"]["input_source"] == "HDMI_1"
    assert prompt_dict["ac"]["target_temperature"] == 24
    assert prompt_dict["soundbar"]["current_owner"] == "FIRE_TV"


# =============================================================================
# 4. RoomStateAggregator Unit Tests & Error Isolation
# =============================================================================

def test_aggregator_full_healthy_mock():
    t_now = 2000.0

    mock_proj = MagicMock()
    mock_proj.get_power_state.return_value = MagicMock(value="ON")
    mock_proj.get_current_source.return_value = MagicMock(value="HDMI_1")
    mock_proj.get_brightness.return_value = 85
    mock_proj.get_health.return_value = {"adb_connected": True}
    mock_proj.is_hdmi_signal_active.return_value = True

    mock_ac = MagicMock()
    mock_ac.get_status.return_value = {
        "power": True,
        "target_temperature": 23,
        "ambient_temperature": 27,
        "mode": "COOL",
        "fan_speed": "LOW",
        "transport_used": "LOCAL_TUYA_3.3",
        "verified": True
    }

    mock_ftv = MagicMock()
    mock_ftv.is_online.return_value = True
    mock_ftv.get_power_state.return_value = "AWAKE"
    mock_ftv.get_foreground_app.return_value = "com.google.android.youtube.tv"
    mock_ftv.get_content_title.return_value = "YouTube - Interstellar Trailer"
    mock_ftv.is_soundbar_connected.return_value = True

    mock_pc = MagicMock()
    mock_pc.get_audio_status.return_value = {
        "master_volume": 75,
        "is_muted": False,
        "default_endpoint": {"name": "2270W (NVIDIA High Definition Audio)"},
        "verified": True
    }
    mock_pc.get_bluetooth_status.return_value = {
        "radio_present": True,
        "devices": []
    }

    mock_orch = MagicMock()
    mock_orch.get_room_state.return_value = MagicMock(value="MOVIE_ACTIVE")

    agg = RoomStateAggregator(
        projector_controller=mock_proj,
        ac_controller=mock_ac,
        fire_tv_controller=mock_ftv,
        pc_controller=mock_pc,
        orchestrator=mock_orch
    )

    rs = agg.get_room_state(current_time=t_now)
    assert rs.is_consistent is True

    # Projector
    assert rs.projector.power.value is True
    assert rs.projector.power.provenance == Provenance.OBSERVED
    assert rs.projector.input_source.value == "HDMI_1"
    assert rs.projector.brightness.value == 85
    assert rs.projector.signal_active.value is True
    assert rs.projector.signal_active.provenance == Provenance.DERIVED
    assert rs.projector.content_title.value == "YouTube - Interstellar Trailer"

    # AC
    assert rs.ac.power.value is True
    assert rs.ac.target_temperature.value == 23
    assert rs.ac.ambient_temperature.value == 27
    assert rs.ac.mode.value == "COOL"

    # Fire TV
    assert rs.fire_tv.online.value is True
    assert rs.fire_tv.foreground_app.value == "com.google.android.youtube.tv"
    assert rs.fire_tv.content_title.value == "YouTube - Interstellar Trailer"

    # PC
    assert rs.pc.master_volume.value == 75
    assert rs.pc.is_muted.value is False

    # Soundbar
    assert rs.soundbar.current_owner.value == "FIRE_TV"
    assert rs.soundbar.is_connected.value is True


def test_aggregator_partial_hardware_failure_isolation():
    t_now = 2000.0

    # Projector throws exception
    mock_proj = MagicMock()
    mock_proj.get_power_state.side_effect = TimeoutError("ADB connection timed out")

    # AC returns unverified / error
    mock_ac = MagicMock()
    mock_ac.get_status.side_effect = RuntimeError("Tuya socket unreachable")

    # Fire TV is offline
    mock_ftv = MagicMock()
    mock_ftv.is_online.return_value = False

    # PC is healthy
    mock_pc = MagicMock()
    mock_pc.get_audio_status.return_value = {
        "master_volume": 60,
        "is_muted": False,
        "default_endpoint": {"name": "Speakers (High Definition Audio Device)"},
        "verified": True
    }
    mock_pc.get_bluetooth_status.return_value = {"radio_present": True, "devices": []}

    agg = RoomStateAggregator(
        projector_controller=mock_proj,
        ac_controller=mock_ac,
        fire_tv_controller=mock_ftv,
        pc_controller=mock_pc
    )

    rs = agg.get_room_state(current_time=t_now)

    # Must not crash, but must flag is_consistent as False
    assert rs.is_consistent is False

    # Projector fields must be UNKNOWN (never fabricated)
    assert rs.projector.power.provenance == Provenance.UNKNOWN
    assert rs.projector.power.value is None
    assert rs.projector.signal_active.provenance == Provenance.UNKNOWN

    # AC fields must be UNKNOWN (never fabricated)
    assert rs.ac.power.provenance == Provenance.UNKNOWN
    assert rs.ac.power.value is None
    assert rs.ac.target_temperature.provenance == Provenance.UNKNOWN
    assert rs.ac.target_temperature.value is None

    # Fire TV must reflect OFFLINE
    assert rs.fire_tv.online.value is False
    assert rs.fire_tv.power_state.value == "OFFLINE"

    # PC must reflect healthy observation
    assert rs.pc.online.value is True
    assert rs.pc.master_volume.value == 60

    # Soundbar must be NONE (since Fire TV is offline and PC is disconnected)
    assert rs.soundbar.current_owner.value == "NONE"
    assert rs.soundbar.is_connected.value is False


# =============================================================================
# 5. FastAPI /api/room/state Endpoint Contract Test
# =============================================================================

def test_fastapi_room_state_endpoint():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # Mock aggregator's get_room_state
    mock_rs = RoomState(
        timestamp=3000.0,
        is_consistent=True,
        projector=ProjectorState(
            power=StateField.observed(True, "ADB", 3000.0),
            input_source=StateField.observed("HDMI_1", "ADB", 3000.0),
            brightness=StateField.observed(90, "ADB", 3000.0),
            signal_active=StateField.derived(True, "DERIVE", 3000.0),
            health=StateField.observed("OK", "ADB", 3000.0)
        ),
        ac=AcState(
            power=StateField.observed(True, "TUYA", 3000.0),
            target_temperature=StateField.observed(22, "TUYA", 3000.0),
            ambient_temperature=StateField.observed(26, "TUYA", 3000.0),
            mode=StateField.observed("COOL", "TUYA", 3000.0),
            fan_speed=StateField.observed("MEDIUM", "TUYA", 3000.0),
            transport_used=StateField.observed("LOCAL_TUYA_3.3", "TUYA", 3000.0)
        ),
        fire_tv=FireTvState(
            online=StateField.observed(True, "ADB", 3000.0),
            power_state=StateField.observed("AWAKE", "ADB", 3000.0),
            foreground_app=StateField.observed("com.amazon.tv.launcher", "ADB", 3000.0),
            soundbar_connected=StateField.observed(False, "ADB", 3000.0)
        ),
        pc=PcState(
            online=StateField.observed(True, "DAEMON", 3000.0),
            master_volume=StateField.observed(70, "COM", 3000.0),
            is_muted=StateField.observed(False, "COM", 3000.0),
            default_audio_endpoint=StateField.observed("2270W", "COM", 3000.0),
            bluetooth_radio_active=StateField.observed(True, "BT", 3000.0)
        ),
        soundbar=SoundbarState(
            current_owner=StateField.derived("NONE", "DERIVE", 3000.0),
            is_connected=StateField.derived(False, "DERIVE", 3000.0)
        ),
        environment=RoomEnvironmentState(
            room_mode=StateField.derived("IDLE", "ORCH", 3000.0),
            active_audio_route=StateField.derived("NONE", "ORCH", 3000.0)
        )
    )

    with patch("main.room_state_aggregator.get_room_state", return_value=mock_rs):
        res = client.get("/api/room/state")
        assert res.status_code == 200
        data = res.json()
        assert data["timestamp"] == 3000.0
        assert data["is_consistent"] is True

        assert data["projector"]["input_source"]["value"] == "HDMI_1"
        assert data["ac"]["target_temperature"]["value"] == 22
        assert data["fire_tv"]["online"]["value"] is True
        assert data["pc"]["master_volume"]["value"] == 70
        assert data["soundbar"]["current_owner"]["value"] == "NONE"


