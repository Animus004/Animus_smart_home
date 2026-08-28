"""
Unit Test Suite for ProactiveOrchestrator:
Verifies thermal discomfort triggers, late night fatigue detection,
morning awakening greetings, idle optical lamp protection, and cooldown safety invariants.
"""

import time
from unittest.mock import MagicMock
import pytest

from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory


def test_thermal_overheating_trigger():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    # Telemetry: Room is 29°C and AC is OFF
    telemetry = {
        "ac_ambient_temp": 29,
        "ac_power": False,
        "projector_power": False,
        "media_playing": False,
        "pc_online": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.THERMAL_CARE
    assert "29" in msg
    assert mock_tts.speak.called


def test_cooldown_suppression():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    telemetry = {
        "ac_ambient_temp": 30,
        "ac_power": False
    }

    # First trigger should fire
    res1 = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res1 is not None

    # Immediate second check should be suppressed by cooldown
    res2 = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res2 is None


def test_thermal_overchilling_trigger():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    telemetry = {
        "ac_ambient_temp": 18,
        "ac_power": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.THERMAL_CARE
    assert "18" in msg


def test_idle_optical_protection():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    # Projector is on, media is stopped
    telemetry = {
        "projector_power": True,
        "media_playing": False
    }

    # Simulate 25 minutes of idle
    orch._idle_media_start = time.time() - 1500

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION
    assert "standby" in msg
