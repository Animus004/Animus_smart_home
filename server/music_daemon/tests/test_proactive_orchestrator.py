"""
Unit Test Suite for ProactiveOrchestrator:
Verifies thermal discomfort triggers, mode-gated work fatigue detection,
morning awakening greetings with "Sir" address, idle optical lamp protection,
cooldown safety invariants, and work mode gating.
"""

import time
from unittest.mock import MagicMock
import pytest

from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory


def test_thermal_overheating_trigger():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    # Telemetry: Room is 29°C and AC is OFF, non-morning hour
    telemetry = {
        "ac_ambient_temp": 29,
        "ac_power": False,
        "projector_power": False,
        "media_playing": False,
        "pc_online": True,
        "hour": 14,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.THERMAL_CARE
    assert "29" in msg
    assert "Sir" in msg
    assert mock_tts.speak.called


def test_cooldown_suppression():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    telemetry = {
        "ac_ambient_temp": 30,
        "ac_power": False,
        "hour": 14,
        "suppress_morning": True
    }

    # First trigger should fire
    res1 = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res1 is not None
    cat, msg = res1
    assert cat == ProactiveTriggerCategory.THERMAL_CARE

    # Immediate second check should be suppressed by cooldown
    res2 = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res2 is None


def test_thermal_overchilling_trigger():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    telemetry = {
        "ac_ambient_temp": 18,
        "ac_power": True,
        "hour": 14,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.THERMAL_CARE
    assert "18" in msg
    assert "Sir" in msg


def test_idle_optical_protection():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    # Projector is on, media is stopped
    telemetry = {
        "projector_power": True,
        "media_playing": False,
        "hour": 14,
        "suppress_morning": True
    }

    # Simulate 25 minutes of idle
    orch._idle_media_start = time.time() - 1500

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION
    assert "standby" in msg
    assert "Sir" in msg


def test_morning_greeting_trigger():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    telemetry = {
        "hour": 8,
        "pc_online": True,
        "pc_locked": False,
        "user_idle_seconds": 15.0,
        "ac_ambient_temp": 25,
        "suppress_morning": False
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.MORNING_GREETING
    assert "Good morning, Sir!" in msg
    assert "25" in msg
    assert mock_tts.speak.called

    # Same day subsequent check should not re-trigger
    res_repeat = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res_repeat is None


def test_work_session_fatigue_and_followup_staging():
    mock_tts = MagicMock()
    mock_followup = MagicMock()
    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        followup_engine=mock_followup,
        cooldown_seconds=60.0
    )

    now = time.time()
    telemetry = {
        "active_mode": "WORK",
        "pc_online": True,
        "pc_locked": False,
        "user_idle_seconds": 30.0,
        "ac_ambient_temp": 24,
        "ac_power": True,
        "projector_power": False,
        "media_playing": False,
        "hour": 14,
        "suppress_morning": True
    }

    # Simulate user working for 100 minutes (6000 seconds) in active WORK mode
    orch._pc_active_since = now - 6000

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat in (ProactiveTriggerCategory.WORK_SESSION_FATIGUE, ProactiveTriggerCategory.LATE_NIGHT_FATIGUE)
    assert "dim the lights" in msg or "soothing" in msg
    assert "Sir" in msg
    assert mock_tts.speak.called
    assert mock_followup.set_pending_followup.called


def test_work_fatigue_suppressed_outside_work_mode():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)

    now = time.time()
    # User is on PC for 100 minutes, but active_mode is IDLE / CASUAL (not WORK)
    orch._pc_active_since = now - 6000
    telemetry = {
        "active_mode": "IDLE",
        "pc_online": True,
        "pc_locked": False,
        "user_idle_seconds": 30.0,
        "ac_ambient_temp": 24,
        "ac_power": True,
        "hour": 14,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is None
    assert not mock_tts.speak.called
    assert orch._pc_active_since is None


def test_work_session_wrapup_detection():
    mock_tts = MagicMock()
    mock_followup = MagicMock()
    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        followup_engine=mock_followup,
        cooldown_seconds=60.0
    )

    now = time.time()
    # User worked for 80 minutes in WORK mode then locked workstation
    orch._pc_active_since = now - 4800

    telemetry = {
        "active_mode": "WORK",
        "pc_online": True,
        "pc_locked": True,
        "user_idle_seconds": 120.0,
        "ac_ambient_temp": 24,
        "ac_power": True,
        "projector_power": False,
        "media_playing": False,
        "hour": 14,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.WORK_SESSION_WRAPUP
    assert "wrapping up work" in msg
    assert "relax mode" in msg
    assert "Sir" in msg
    assert mock_followup.set_pending_followup.called
    # Active work time should be reset
    assert orch._pc_active_since is None


def test_followup_resolution_proactive_work_fatigue():
    from agent.models import UserProfile
    from agent.followup_engine import FollowUpEngine

    followup = FollowUpEngine(user_profile=UserProfile())
    followup.set_pending_followup("PROACTIVE_WORK_FATIGUE_TRANSITION")

    # 1. Affirmative response
    res1 = followup.resolve_followup_response("yes please, that would be great")
    assert res1["resolved"] is True
    assert res1["intent"] == "DIM_LIGHTS_AND_PLAY_SOOTHING_MEDIA"

    # 2. Lights only response
    followup.set_pending_followup("PROACTIVE_WORK_FATIGUE_TRANSITION")
    res2 = followup.resolve_followup_response("just dim the lights, no music")
    assert res2["resolved"] is True
    assert res2["intent"] == "DIM_LIGHTS_ONLY"

    # 3. Snooze response
    followup.set_pending_followup("PROACTIVE_WORK_FATIGUE_TRANSITION")
    res3 = followup.resolve_followup_response("not yet, give me 20 more minutes")
    assert res3["resolved"] is True
    assert res3["intent"] == "SNOOZE_WORK_FATIGUE"

    # 4. Reject response
    followup.set_pending_followup("PROACTIVE_WORK_FATIGUE_TRANSITION")
    res4 = followup.resolve_followup_response("no don't do that")
    assert res4["resolved"] is True
    assert res4["intent"] == "REJECT_PROACTIVE_SUGGESTION"
