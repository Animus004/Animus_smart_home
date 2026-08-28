"""
================================================================================
ANIMUS SMART ROOM — PERCEPTION COLLECTOR & FRESHNESS TEST SUITE
================================================================================
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from room_state.provenance import Provenance
from room_state.models import RoomState, StateField, AcState, IrHubState
from room_state.freshness import is_fresh, resolve_provenance, AC_POWER_TTL
from room_state.perception_collector import PerceptionCollector
from tuya_local_read_adapter import (
    TuyaLocalAcReadAdapter,
    LocalReadResult,
    ReadDiagnosticStatus,
    DecodedAcState,
)


def test_sub_millisecond_cache_retrieval():
    """Validates that get_room_state() accesses in-memory cache in strictly < 1.0 ms."""
    collector = PerceptionCollector()
    
    # Measure 100 cache queries
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        state = collector.get_room_state(force_refresh=False)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)

    assert avg_latency < 0.5, f"Expected sub-millisecond average latency, got {avg_latency:.4f} ms"
    assert max_latency < 2.0, f"Expected sub-2ms max latency, got {max_latency:.4f} ms"
    assert isinstance(state, RoomState)


def test_ttl_freshness_transitions():
    """
    Validates that observations older than their TTL cleanly transition from
    OBSERVED -> STALE without data loss or exceptions.
    """
    t_base = 1000.0
    field = StateField.observed(False, "AC_TUYA_LAN_ADAPTER", observed_at=t_base)
    
    # 1. Immediate check (t = 1000.0) -> OBSERVED
    assert field.is_fresh(AC_POWER_TTL, current_time=t_base) is True
    assert field.effective_provenance(AC_POWER_TTL, current_time=t_base) == Provenance.OBSERVED

    # 2. Within TTL (t = 1010.0, elapsed = 10s <= 15s) -> OBSERVED
    assert field.is_fresh(AC_POWER_TTL, current_time=t_base + 10.0) is True
    assert field.effective_provenance(AC_POWER_TTL, current_time=t_base + 10.0) == Provenance.OBSERVED

    # 3. Beyond TTL (t = 1020.0, elapsed = 20s > 15s) -> STALE
    assert field.is_fresh(AC_POWER_TTL, current_time=t_base + 20.0) is False
    assert field.effective_provenance(AC_POWER_TTL, current_time=t_base + 20.0) == Provenance.STALE

    # 4. Serialization tags STALE in dictionary
    d = field.to_dict(ttl_seconds=AC_POWER_TTL, current_time=t_base + 20.0)
    assert d["provenance"] == "STALE"
    assert d["value"] is False


def test_epistemic_distinction_off_vs_unobserved_vs_stale():
    """
    Validates the fundamental epistemic rule:
    'AC is OFF' != 'Haven't observed AC for 30s' != 'AC is UNKNOWN'
    """
    now = time.time()
    
    # Reality 1: Actively Observed OFF
    state_off = RoomState(
        ac=AcState(
            power=StateField.observed(False, "AC_TUYA_LAN_ADAPTER", observed_at=now),
            target_temperature=StateField.observed(24, "AC_TUYA_LAN_ADAPTER", observed_at=now),
        )
    )
    prompt_dict_1 = state_off.to_sanitized_prompt_dict(current_time=now)
    assert prompt_dict_1["ac"]["power"] is False

    # Reality 2: Stale Observation (observed 45s ago)
    state_stale = RoomState(
        ac=AcState(
            power=StateField.observed(False, "AC_TUYA_LAN_ADAPTER", observed_at=now - 45.0),
            target_temperature=StateField.observed(24, "AC_TUYA_LAN_ADAPTER", observed_at=now - 45.0),
        )
    )
    prompt_dict_2 = state_stale.to_sanitized_prompt_dict(current_time=now)
    assert prompt_dict_2["ac"]["power"] == "False (STALE)"
    assert "ac.power" in state_stale.get_stale_fields(current_time=now)

    # Reality 3: Unreachable / Failed
    state_unk = RoomState(
        ac=AcState(
            power=StateField.unknown("AC_SOCKET_TIMEOUT", observed_at=now),
            target_temperature=StateField.unknown("AC_SOCKET_TIMEOUT", observed_at=now),
        )
    )
    prompt_dict_3 = state_unk.to_sanitized_prompt_dict(current_time=now)
    assert prompt_dict_3["ac"]["power"] == "UNKNOWN"
    assert "ac.power" in state_unk.get_unknown_fields(current_time=now)


def test_fault_isolation_in_perception_cycle():
    """Validates that a failure in one subsystem does not break or block other subsystems."""
    mock_ac = MagicMock(spec=TuyaLocalAcReadAdapter)
    mock_ac.read_ac_state.return_value = LocalReadResult(
        status=ReadDiagnosticStatus.LOCAL_READ_FAILED,
        error="Socket connection reset",
        latency_ms=10.0,
    )

    collector = PerceptionCollector(ac_read_adapter=mock_ac)
    
    with patch("socket.socket") as mock_sock:
        # Mock IR Hub reachable
        sock_instance = MagicMock()
        sock_instance.connect_ex.return_value = 0
        mock_sock.return_value = sock_instance

        state = collector.poll_once()

        # AC is marked failed/unknown cleanly
        assert state.ac.power.provenance == Provenance.UNKNOWN
        # IR Hub is still observed as online
        assert state.ir_hub.online.value is True
        assert state.ir_hub.online.provenance == Provenance.OBSERVED
        # Overall state consistency is false because AC was unknown
        assert state.is_consistent is False


def test_perception_collector_lifecycle():
    """Validates starting, continuous background polling, and clean stopping."""
    mock_ac = MagicMock(spec=TuyaLocalAcReadAdapter)
    mock_ac.read_ac_state.return_value = LocalReadResult(
        status=ReadDiagnosticStatus.LOCAL_READ_SUCCESS,
        state=DecodedAcState(
            power=False,
            target_temperature=24,
            current_temperature=None,
            mode="AUTO",
            fan_speed="AUTO",
            raw_dps={},
            latency_ms=15.0,
            timestamp=time.time(),
        ),
        latency_ms=15.0,
    )

    collector = PerceptionCollector(ac_read_adapter=mock_ac, poll_interval_seconds=0.1)
    
    with patch("socket.socket") as mock_sock:
        sock_inst = MagicMock()
        sock_inst.connect_ex.return_value = 0
        mock_sock.return_value = sock_inst

        assert collector.is_running() is False
        collector.start()
        assert collector.is_running() is True
        
        time.sleep(0.35)
        
        # Verify multiple background polls occurred
        assert collector._total_polls >= 2
        state = collector.get_room_state()
        assert state.ac.power.value is False
        assert state.ac.target_temperature.value == 24
        assert state.ir_hub.online.value is True

        collector.stop()
        assert collector.is_running() is False


def test_to_brain_markdown_prompt_formatting():
    """Validates that to_brain_markdown_prompt formats a clean, unambiguous LLM perception block."""
    now = time.time()
    state = RoomState(
        timestamp=now,
        is_consistent=True,
        ac=AcState(
            power=StateField.observed(False, "AC_TUYA_LAN_ADAPTER", now),
            target_temperature=StateField.observed(24, "AC_TUYA_LAN_ADAPTER", now),
            mode=StateField.observed("AUTO", "AC_TUYA_LAN_ADAPTER", now),
            fan_speed=StateField.observed("AUTO", "AC_TUYA_LAN_ADAPTER", now),
            transport_used=StateField.observed("LOCAL_TUYA_3.3", "AC_TUYA_LAN_ADAPTER", now),
        ),
        ir_hub=IrHubState(
            online=StateField.observed(True, "IR_HUB_LAN_SOCKET", now),
            transport=StateField.observed("LOCAL_TUYA_3.3", "IR_HUB_LAN_SOCKET", now),
        ),
    )

    md = state.to_brain_markdown_prompt(current_time=now)
    
    assert "### CURRENT PHYSICAL REALITY" in md
    assert "AC:" in md
    assert "power: OFF" in md
    assert "target: 24°C" in md
    assert "mode: AUTO" in md
    assert "fan: AUTO" in md
    assert "freshness: FRESH" in md
    assert "provenance: OBSERVED" in md
    assert "SMART IR HUB:" in md
    assert "online: YES" in md
    assert "transport: LOCAL_TUYA_3.3" in md
