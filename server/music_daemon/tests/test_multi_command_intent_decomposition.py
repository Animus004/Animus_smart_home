"""
Test Suite for Multi-Command and Compound Intent Decomposition in AgentDecisionEngine:
1. Clause Splitting: Correctly decomposes compound sentences by conjunctions and punctuation.
2. Two-Command Compound Execution: AC power off + Projector power on.
3. Three-Command Compound Execution: AC power off + Projector power on + Play music.
4. Multi-Subsystem Climate + Audio: AC temperature + PC volume.
5. Zero Regression on Single Commands: Single commands with 'and' (e.g. "play rock and roll") preserve full single intent.
6. Narrative Protection: Work summaries and ChatGPT daily logs are not falsely fragmented.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

# Add daemon path
daemon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if daemon_dir not in sys.path:
    sys.path.insert(0, daemon_dir)

from agent.agent_decision_engine import AgentDecisionEngine


@pytest.fixture
def decision_engine():
    mock_mem = MagicMock()
    mock_mem.get_active_goal.return_value = None
    mock_mem.get_career_roadmap.return_value = {"tasks": [], "career_target": "Senior Data Analyst", "current_project": "Blinkit"}
    mock_mem.get_current_work_subgoal.return_value = {"title": "Blinkit SQL"}
    engine = AgentDecisionEngine(memory_store=mock_mem)
    return engine


def test_decompose_compound_utterance_basic(decision_engine):
    clauses = decision_engine._decompose_compound_utterance("Turn off the AC, turn on the projector, and play focus beats")
    assert len(clauses) == 3
    assert clauses[0].lower() == "turn off the ac"
    assert clauses[1].lower() == "turn on the projector"
    assert clauses[2].lower() == "play focus beats"


def test_decompose_compound_utterance_with_polite_prefixes(decision_engine):
    clauses = decision_engine._decompose_compound_utterance("Animus, please turn off the AC and kindly turn on the projector")
    assert len(clauses) == 2
    assert "turn off the ac" in clauses[0].lower()
    assert "turn on the projector" in clauses[1].lower()


def test_decompose_protects_work_summaries(decision_engine):
    summary = "Today I completed the SQL lag and lead CTE analysis for Blinkit project and fixed stakeholder requirements"
    clauses = decision_engine._decompose_compound_utterance(summary)
    assert len(clauses) == 1
    assert clauses[0] == summary


def test_compound_two_commands_ac_and_projector(decision_engine):
    utterance = "Turn off the AC and turn on the projector"
    res = decision_engine._try_fastpath_decision(utterance)
    assert res is not None
    assert res.get("action_type") == "TOOL_EXECUTION"
    tools = [tc["tool"] for tc in res.get("tool_calls", [])]
    assert "AC_POWER_OFF" in tools
    assert "PROJECTOR_POWER_ON" in tools
    assert "turning off the ac" in res.get("response_message", "").lower()
    assert "turning on the projector" in res.get("response_message", "").lower()


def test_compound_three_commands_ac_projector_music(decision_engine):
    utterance = "Turn off the AC, turn on the projector, and play focus beats"
    res = decision_engine._try_fastpath_decision(utterance)
    assert res is not None
    tools = [tc["tool"] for tc in res.get("tool_calls", [])]
    assert "AC_POWER_OFF" in tools
    assert "PROJECTOR_POWER_ON" in tools
    assert "PLAY_MUSIC" in tools
    music_call = next(tc for tc in res["tool_calls"] if tc["tool"] == "PLAY_MUSIC")
    assert music_call["params"]["query"] == "focus beats"


def test_compound_climate_and_volume(decision_engine):
    utterance = "Set AC to 22 and volume to 30"
    res = decision_engine._try_fastpath_decision(utterance)
    assert res is not None
    tools = [tc["tool"] for tc in res.get("tool_calls", [])]
    assert "AC_SET_TEMPERATURE" in tools
    assert "PC_SET_VOLUME" in tools
    ac_call = next(tc for tc in res["tool_calls"] if tc["tool"] == "AC_SET_TEMPERATURE")
    assert ac_call["params"]["temperature"] == 22
    vol_call = next(tc for tc in res["tool_calls"] if tc["tool"] == "PC_SET_VOLUME")
    assert vol_call["params"]["volume"] == 30


def test_single_command_with_and_not_broken(decision_engine):
    # 'play rock and roll' shouldn't be split into invalid fragments
    utterance = "Play rock and roll"
    res = decision_engine._try_fastpath_decision(utterance)
    assert res is not None
    tools = [tc["tool"] for tc in res.get("tool_calls", [])]
    assert tools == ["PLAY_MUSIC"]
    assert res["tool_calls"][0]["params"]["query"] == "rock and roll"
