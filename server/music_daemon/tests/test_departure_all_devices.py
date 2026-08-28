"""
Unit test verifying full multi-device coordination on departure ('I am leaving the room').
"""

from unittest.mock import MagicMock
import pytest

from agent.core import AnimusPersonalAgent


def test_departure_all_devices_coordinated():
    mock_planner_exec = MagicMock()
    mock_planner_exec.ac = MagicMock()
    mock_planner_exec.projector = MagicMock()
    mock_planner_exec.fire_tv = MagicMock()
    mock_planner_exec.pc = MagicMock()

    mock_orchestrator = MagicMock()

    agent = AnimusPersonalAgent(
        planner_executor=mock_planner_exec,
        orchestrator=mock_orchestrator
    )

    resp = agent.interact("I am leaving the room")
    assert resp.action_taken is True
    assert "DEPARTURE_ALL_OFF" in resp.understood_intent

    # Verify AC turned off
    mock_planner_exec.ac.set_power.assert_called_with(False)

    # Verify Projector powered off
    mock_planner_exec.projector.power_off.assert_called_once()

    # Verify Fire TV put to sleep
    mock_planner_exec.fire_tv.sleep.assert_called_once()

    # Verify Audio stopped
    mock_orchestrator.stop.assert_called_once()

    # Verify PC locked
    mock_planner_exec.pc.lock_workstation.assert_called_once()
