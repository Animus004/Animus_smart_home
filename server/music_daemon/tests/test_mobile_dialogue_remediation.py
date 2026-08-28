"""
Unit Test Suite for Mobile Screen Dialogue Remediation.
Tests:
1. 'it\'s chillig in my room' -> triggers EMPATHIC_ROOM_TOO_COLD (sets AC to 25)
2. 'set optimal temprature for my Ac' -> triggers OPTIMAL_TEMPERATURE (sets AC to 24)
3. 'the room Is great really cold' -> triggers EMPATHIC_ROOM_TOO_COLD
4. 'yes please do that' following agent's warming proposal -> executes EMPATHIC_ROOM_TOO_COLD
"""

from unittest.mock import MagicMock
import pytest

from agent.core import AnimusPersonalAgent
from agent.intent_resolver import IntentResolver
from agent.models import IntentCategory


@pytest.fixture
def agent():
    mock_planner_exec = MagicMock()
    mock_orchestrator = MagicMock()
    mock_orchestrator.set_ac_temperature.return_value = (True, {"temperature": 25})
    mock_orchestrator.set_ac_state.return_value = (True, {"power": True, "temperature": 25})
    return AnimusPersonalAgent(
        planner_executor=mock_planner_exec,
        orchestrator=mock_orchestrator
    )


def test_thermal_discomfort_empathy(agent):
    # Test 1: "it's chillig in my room"
    r1 = agent.interact("it's chillig in my room")
    assert r1.action_taken is True
    assert "ROOM_TOO_COLD" in r1.understood_intent
    assert "25 degrees" in r1.agent_message

    # Test 2: "set optimal temprature for my Ac"
    r2 = agent.interact("set optimal temprature for my Ac")
    assert r2.action_taken is True
    assert "OPTIMAL_TEMPERATURE" in r2.understood_intent
    assert "24 degrees" in r2.agent_message

    # Test 3: "the room Is great really cold"
    r3 = agent.interact("the room Is great really cold")
    assert r3.action_taken is True
    assert "ROOM_TOO_COLD" in r3.understood_intent


def test_conversational_affirmation_follows_suggestion(agent):
    # Simulate Sonia having suggested warming the room
    agent.context_buffer.record_animus_turn(
        utterance="Maybe I can adjust the thermostat a little warmer for you. 😊 buddy."
    )

    # User affirms: "yes please do that"
    resp = agent.interact("yes please do that")
    assert resp.action_taken is True
    assert "ROOM_TOO_COLD" in resp.understood_intent
    assert "25 degrees" in resp.agent_message
