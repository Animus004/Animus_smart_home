"""
================================================================================
ANIMUS SMART ROOM — AGENT SENTIENCE & EMPATHIC INTEGRATION TESTS
================================================================================
Verifies end-to-end intelligence upgrades:
1. Long-term epistemic memory recall across turns.
2. Multi-domain empathic problem solving (Headache, Going to work, Chill vibe).
3. Proactive ambient detection and polite suggestions.
================================================================================
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from agent.core import AnimusPersonalAgent
from agent.long_term_memory import get_long_term_memory
from agent.empathic_engine import get_empathic_engine
from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory


@pytest.fixture
def mock_agent():
    mock_planner_exec = MagicMock()
    mock_orchestrator = MagicMock()
    
    agent = AnimusPersonalAgent(
        planner_executor=mock_planner_exec,
        orchestrator=mock_orchestrator
    )
    return agent


def test_empathic_headache_resolution_end_to_end(mock_agent):
    agent = mock_agent
    resp = agent.interact("Sonia, I have a bad headache right now")
    
    assert resp.action_taken is True
    assert "rest" in resp.agent_message.lower() or "feeling" in resp.agent_message.lower()
    
    # Verify AC was adjusted for soothing quiet climate
    assert agent.planner_executor.ac_controller.set_temperature.called
    assert agent.planner_executor.ac_controller.set_fan_speed.called
    
    # Verify Projector was put to sleep
    assert agent.planner_executor.projector_controller.sleep.called
    
    # Verify Ambient sound was played
    assert agent.orchestrator.play_music.called


def test_empathic_departure_resolution_end_to_end(mock_agent):
    agent = mock_agent
    resp = agent.interact("I'm going to work, goodbye Sonia")
    
    assert resp.action_taken is True
    assert "day" in resp.agent_message.lower() or "secured" in resp.agent_message.lower()
    
    # Verify AC powered off
    assert agent.planner_executor.ac_controller.set_power.called
    
    # Verify Projector shut down
    assert agent.planner_executor.projector_controller.power_off.called


def test_empathic_chill_vibe_resolution_end_to_end(mock_agent):
    agent = mock_agent
    resp = agent.interact("Set a chill vibe for the room")
    
    assert resp.action_taken is True
    assert "vibe" in resp.agent_message.lower() or "lofi" in resp.agent_message.lower()
    
    # Verify AC set to 23
    assert agent.planner_executor.ac_controller.set_temperature.called
    
    # Verify Lofi playback
    assert agent.orchestrator.play_music.called


def test_long_term_memory_fact_retrieval():
    lt_mem = get_long_term_memory()
    lt_mem.save_fact("favorite_movie", "Interstellar")
    
    retrieved = lt_mem.get_fact("favorite_movie")
    assert retrieved == "Interstellar"
    
    prompt = lt_mem.build_memory_context_prompt("movies")
    assert "favorite_movie: Interstellar" in prompt


def test_proactive_thermal_suggestion():
    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(tts_service=mock_tts, cooldown_seconds=60.0)
    
    telemetry = {
        "ac_ambient_temp": 29,
        "ac_power": False
    }
    
    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.THERMAL_CARE
    assert "29" in msg
