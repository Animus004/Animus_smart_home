"""
Unit Tests for CognitivePromptBuilder.
Verifies temporal context generation, 3-layer prompt structure, and tool definitions.
"""

import json
from pathlib import Path
import tempfile
import pytest

from agent.prompt_builder import CognitivePromptBuilder
from agent.long_term_memory import LongTermMemoryStore


@pytest.fixture
def test_prompt_builder():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_prompt_memory.db"
        mem = LongTermMemoryStore(db_path=db_path)
        builder = CognitivePromptBuilder(memory_store=mem)
        yield builder, mem


def test_temporal_context_generation():
    temporal = CognitivePromptBuilder.get_temporal_context()
    assert "formatted_time" in temporal
    assert "time_of_day" in temporal
    assert temporal["time_of_day"] in ["MORNING", "AFTERNOON", "EVENING", "NIGHT"]
    assert "daylight_state" in temporal
    assert "hour_24" in temporal


def test_build_prompt_contains_all_layers(test_prompt_builder):
    builder, mem = test_prompt_builder
    mem.save_fact("favorite_movie", "Interstellar")
    mem.save_goal(
        goal_id="g1",
        title="Setup Animus SmartRoom",
        subgoals=[{"id": 1, "title": "Configure PC", "completed": True, "is_current": False}]
    )

    prompt = builder.build_prompt(
        user_utterance="What is my active objective?",
        active_mode="WORK"
    )

    assert "### CONTEXT & CURRENT STATE" in prompt
    assert "### INSTRUCTIONS" in prompt
    assert "current_time" in prompt
    assert "Interstellar" in prompt
    assert "Setup Animus SmartRoom" in prompt
    assert "PROJECTOR_POWER_ON" in prompt
