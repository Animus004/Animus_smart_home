"""
Test Suite for Work-Mode-Only Camera-Presence Music Auto-Pause Invariants:
1. Outside Work Mode (e.g. IDLE, RELAX, NORMAL): Music NEVER auto-pauses on absence or mouse inactivity.
2. In Work Mode: Music NEVER auto-pauses due to mouse inactivity when camera is offline.
3. In Work Mode: Music ONLY auto-pauses when camera is online and user is absent for >= 20s.
4. In Work Mode: Music automatically resumes when user returns to the desk.
"""

import time
from unittest.mock import MagicMock
import pytest

from agent.proactive_orchestrator import ProactiveOrchestrator


class MockOrchestrator:
    def __init__(self, active_mode="WORK"):
        self.current_mode = active_mode
        self.current_state = "PC_PLAYING"
        self.safe_pause_called = 0
        self.safe_resume_called = 0
        self.player = MagicMock()
        self.player.get_status.return_value = {"status": "PLAYING"}

    def safe_pause(self):
        self.safe_pause_called += 1
        self.current_state = "PAUSED"
        return True

    def safe_resume(self):
        self.safe_resume_called += 1
        self.current_state = "PC_PLAYING"
        return True


class MockPcController:
    def __init__(self):
        self.lock_called = 0

    def lock_workstation(self):
        self.lock_called += 1
        return True


def test_outside_work_mode_never_pauses_music_on_mouse_inactivity():
    mock_orch = MockOrchestrator(active_mode="IDLE")
    mock_pc = MockPcController()
    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    now = time.time()
    # In IDLE mode, user inactive for 600 seconds, camera offline
    telemetry = {
        "active_mode": "IDLE",
        "camera_online": False,
        "desk_present": False,
        "user_idle_seconds": 600.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True,
        "suppress_evening": True,
        "last_seen_timestamp": now - 60.0
    }

    orch.evaluate_proactive_rules(telemetry=telemetry)
    assert mock_orch.safe_pause_called == 0
    assert mock_pc.lock_called == 0


def test_outside_work_mode_relax_never_pauses_music():
    mock_orch = MockOrchestrator(active_mode="RELAX")
    mock_pc = MockPcController()
    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    now = time.time()
    telemetry = {
        "active_mode": "RELAX",
        "camera_online": True,
        "desk_present": False,
        "user_idle_seconds": 300.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True,
        "suppress_evening": True,
        "last_seen_timestamp": now - 40.0
    }

    orch.evaluate_proactive_rules(telemetry=telemetry)
    assert mock_orch.safe_pause_called == 0
    assert mock_pc.lock_called == 0


def test_work_mode_does_not_pause_on_mouse_inactivity_when_camera_offline():
    mock_orch = MockOrchestrator(active_mode="WORK")
    mock_pc = MockPcController()
    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    now = time.time()
    # In WORK mode, but camera is offline (e.g. unplugged/error), mouse idle for 50s
    telemetry = {
        "active_mode": "WORK",
        "camera_online": False,
        "desk_present": False,
        "user_idle_seconds": 50.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True,
        "suppress_evening": True,
        "last_seen_timestamp": now - 35.0
    }

    orch.evaluate_proactive_rules(telemetry=telemetry)
    # Music MUST NOT pause based on mouse inactivity when camera is offline!
    assert mock_orch.safe_pause_called == 0


def test_work_mode_camera_presence_soft_pause_and_auto_resume():
    mock_orch = MockOrchestrator(active_mode="WORK")
    mock_pc = MockPcController()
    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    now = time.time()
    # Step 1: User is seated at desk in WORK mode with camera online and music playing
    t_present = {
        "active_mode": "WORK",
        "camera_online": True,
        "desk_present": True,
        "desk_seated_seconds": 120.0,
        "user_idle_seconds": 5.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True,
        "suppress_evening": True,
        "last_seen_timestamp": now
    }
    orch.evaluate_proactive_rules(telemetry=t_present)
    assert orch._music_played_while_present is True
    assert mock_orch.safe_pause_called == 0

    # Step 2: User steps away from camera for 25 seconds
    t_away = {
        "active_mode": "WORK",
        "camera_online": True,
        "desk_present": False,
        "desk_seated_seconds": 0.0,
        "user_idle_seconds": 25.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True,
        "suppress_evening": True,
        "last_seen_timestamp": now - 25.0
    }
    orch.evaluate_proactive_rules(telemetry=t_away)
    # Soft pause should trigger!
    assert mock_orch.safe_pause_called == 1
    assert orch._music_paused_by_departure is True

    # Step 3: User returns to desk in front of camera
    t_returned = {
        "active_mode": "WORK",
        "camera_online": True,
        "desk_present": True,
        "desk_seated_seconds": 5.0,
        "user_idle_seconds": 0.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True,
        "suppress_evening": True,
        "last_seen_timestamp": now + 30.0
    }
    orch.evaluate_proactive_rules(telemetry=t_returned)
    # Auto resume should trigger!
    assert mock_orch.safe_resume_called == 1
    assert orch._music_paused_by_departure is False
