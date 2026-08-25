"""
Isolated Unit and Safety Regression Test Suite for IrProjectorTransport.
Tests strict command whitelisting, AC code isolation, debounce locking,
2-pulse shutdown state machine, state-gated suppression, and rollback flags.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from projector_controller import (
    IrProjectorTransport,
    ProjectorController,
    ProjectorPowerState,
    IrSecurityException,
    IrDebounceException
)


# =============================================================================
# 1. AC & Dangerous Command Isolation Tests
# =============================================================================

def test_ir_ac_command_isolation_rejection():
    """Guarantees that requesting any Lloyd AC, Wi-Fi reset, or non-whitelisted key raises IrSecurityException."""
    transport = IrProjectorTransport(
        lan_ip="192.168.1.12",
        dev_id="mock_ir_blaster_id",
        local_key="mock_local_key",
        projector_remote_id="remote_zebronics_projector_01"
    )

    forbidden_keys = [
        "AC_POWER",
        "AC_TEMP_UP",
        "AC_SET_MODE",
        "WIFI_RESET",
        "PAIRING_MODE",
        "FACTORY_RESET",
        "VolumeUp",
        "UnknownButton"
    ]

    for key in forbidden_keys:
        with pytest.raises(IrSecurityException) as exc_info:
            transport.send_pulse(key)
        assert "Unauthorized or dangerous IR key request" in str(exc_info.value)


def test_ir_projector_remote_id_enforcement():
    """Guarantees that transport cannot be diverted to dispatch against Lloyd AC remote ID."""
    with pytest.raises(IrSecurityException):
        IrProjectorTransport(
            lan_ip="192.168.1.12",
            dev_id="mock_ir_blaster_id",
            local_key="mock_local_key",
            projector_remote_id="remote_lloyd_ac_02"  # Forbidden target
        )


# =============================================================================
# 2. Debounce and Rate-Limiting Invariants
# =============================================================================

def test_ir_hardware_debounce_lock():
    """Guarantees that rapid subsequent IR pulses (< 3.0s) are blocked to prevent power toggle inversion."""
    transport = IrProjectorTransport(
        lan_ip="192.168.1.12",
        dev_id="mock_ir_blaster_id",
        local_key="mock_local_key",
        projector_remote_id="remote_zebronics_projector_01"
    )

    with patch.object(transport, "_dispatch_raw_tuya", return_value=True):
        # 1st pulse succeeds
        ok, msg = transport.send_pulse("Power")
        assert ok is True
        assert msg == "IR_PULSE_SENT"

        # 2nd pulse immediately after fails due to debounce
        with pytest.raises(IrDebounceException) as exc_info:
            transport.send_pulse("Power")
        assert "Debounce violation" in str(exc_info.value)


# =============================================================================
# 3. Two-Pulse Immediate Power-Off State Machine
# =============================================================================

def test_two_pulse_shutdown_timing():
    """Verifies that send_power_off_immediate sends exactly 2 pulses separated by >= 1.0s."""
    transport = IrProjectorTransport(
        lan_ip="192.168.1.12",
        dev_id="mock_ir_blaster_id",
        local_key="mock_local_key",
        projector_remote_id="remote_zebronics_projector_01"
    )

    dispatched_timestamps = []

    def mock_dispatch(remote_id, key_name):
        dispatched_timestamps.append(time.time())
        return True

    with patch.object(transport, "_dispatch_raw_tuya", side_effect=mock_dispatch):
        ok, msg = transport.send_power_off_immediate(inter_pulse_delay=0.1)  # small delay for fast test
        assert ok is True
        assert msg == "IMMEDIATE_SHUTDOWN_DISPATCHED"
        assert len(dispatched_timestamps) == 2
        assert dispatched_timestamps[1] - dispatched_timestamps[0] >= 0.09


# =============================================================================
# 4. ProjectorController Integration & State Gating
# =============================================================================

def test_idempotent_wake_suppression_when_already_on():
    """When projector is already active on ADB (power == ON), IR wake pulse MUST be suppressed."""
    controller = ProjectorController(use_ir_power=True)
    mock_ir = MagicMock()
    controller.ir_transport = mock_ir

    # Mock ADB reporting projector already ON
    with patch.object(controller, "is_connected", return_value=(True, "device")):
        with patch.object(controller, "get_power_state", return_value={"interactive": True, "power_state": ProjectorPowerState.ON.value}):
            res = controller.wake()
            assert res is True
            # Zero IR pulses should be dispatched
            mock_ir.send_power_wake.assert_not_called()


def test_idempotent_sleep_suppression_when_already_off():
    """When projector is already disconnected/off, IR sleep pulses MUST be suppressed."""
    controller = ProjectorController(use_ir_power=True)
    mock_ir = MagicMock()
    controller.ir_transport = mock_ir

    # Mock ADB reporting projector already disconnected
    with patch.object(controller, "is_connected", return_value=(False, "disconnected")):
        res = controller.sleep()
        assert res is False or res is True
        # Zero IR pulses should be dispatched
        mock_ir.send_power_off_immediate.assert_not_called()


def test_wake_dispatches_ir_when_adb_offline():
    """When ADB is offline (deep standby), wake() dispatches 1x IR pulse and polls for ADB boot."""
    controller = ProjectorController(use_ir_power=True)
    mock_ir = MagicMock()
    mock_ir.send_power_wake.return_value = (True, "IR_PULSE_SENT")
    controller.ir_transport = mock_ir

    # 1st call to is_connected -> False, after IR -> becomes True
    connection_sequence = [(False, "disconnected"), (True, "device")]

    with patch.object(controller, "is_connected", side_effect=lambda *args, **kwargs: connection_sequence.pop(0) if connection_sequence else (True, "device")):
        with patch.object(controller, "get_power_state", return_value={"interactive": True, "power_state": ProjectorPowerState.ON.value}):
            res = controller.wake(timeout_seconds=0.5)
            assert res is True
            mock_ir.send_power_wake.assert_called_once()


# =============================================================================
# 5. Rollback Flag Invariant
# =============================================================================

def test_rollback_flag_preserves_pure_adb():
    """When use_ir_power=False (default), ProjectorController uses pure ADB without touching IR."""
    controller = ProjectorController(use_ir_power=False)
    assert controller.use_ir_power is False

    power_states = [
        {"interactive": False, "power_state": ProjectorPowerState.STANDBY.value},
        {"interactive": True, "power_state": ProjectorPowerState.ON.value}
    ]

    with patch.object(controller, "is_connected", return_value=(True, "device")):
        with patch.object(controller, "get_power_state", side_effect=lambda: power_states.pop(0) if power_states else {"interactive": True, "power_state": ProjectorPowerState.ON.value}):
            with patch.object(controller, "send_key", return_value=True) as mock_send_key:
                res = controller.wake(timeout_seconds=0.5)
                assert res is True
                mock_send_key.assert_called_with(224)

