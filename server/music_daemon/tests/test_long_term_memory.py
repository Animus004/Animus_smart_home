"""
Unit Test Suite for LongTermMemoryStore:
Verifies SQLite schema creation, CRUD operations, natural language fact extraction,
habit recording, episodic conversation indexing, and context prompt formatting.
"""

import os
import tempfile
from pathlib import Path
import pytest

from agent.long_term_memory import LongTermMemoryStore


@pytest.fixture
def temp_memory_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


def test_seed_core_identity(temp_memory_store):
    store = temp_memory_store
    name = store.get_fact("user_name")
    assert name == "Sayan Halder"
    assert store.get_fact("user_nickname") == "buddy"


def test_save_and_get_fact(temp_memory_store):
    store = temp_memory_store
    store.save_fact("favorite_director", "Christopher Nolan")
    val = store.get_fact("favorite_director")
    assert val == "Christopher Nolan"

    # Update fact
    store.save_fact("favorite_director", "Denis Villeneuve")
    assert store.get_fact("favorite_director") == "Denis Villeneuve"


def test_habit_recording(temp_memory_store):
    store = temp_memory_store
    store.record_habit_observation("movie_night", "set_ac", {"temp": 22})
    store.record_habit_observation("movie_night", "set_ac", {"temp": 22})

    habit = store.get_habit("movie_night")
    assert habit is not None
    assert habit["action"] == "set_ac"
    assert habit["parameters"]["temp"] == 22
    assert habit["count"] == 2


def test_natural_fact_extraction(temp_memory_store):
    store = temp_memory_store
    extracted = store.extract_facts_from_utterance("My favorite movie is Inception")
    assert len(extracted) > 0
    assert store.get_fact("favorite_movie") == "Inception"


def test_episodic_conversation_search(temp_memory_store):
    store = temp_memory_store
    store.record_conversation_turn(
        user_utterance="Can you play some Synthwave music?",
        agent_response="Playing synthwave playlist on LG Soundbar.",
        intent_category="ENTERTAINMENT"
    )

    results = store.search_past_conversations("synthwave")
    assert len(results) >= 1
    assert "Synthwave" in results[0]["user"]


def test_memory_context_prompt_formatting(temp_memory_store):
    store = temp_memory_store
    prompt = store.build_memory_context_prompt("movie")
    assert "[LONG-TERM EPITEMIC MEMORY]" in prompt
    assert "Sayan Halder" in prompt
