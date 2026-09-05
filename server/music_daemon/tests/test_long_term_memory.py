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
    assert store.get_fact("user_nickname") == "Sir"


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
    assert "[LONG-TERM EPISTEMIC MEMORY]" in prompt
    assert "Sayan Halder" in prompt


def test_persistent_goal_lifecycle(temp_memory_store):
    store = temp_memory_store
    subgoals = [
        {"id": 1, "title": "Configure BIOS", "completed": True, "is_current": False},
        {"id": 2, "title": "Verify BAT execution", "completed": False, "is_current": True},
        {"id": 3, "title": "Start LLM Server", "completed": False, "is_current": False}
    ]
    store.save_goal(
        goal_id="goal_startup_01",
        title="Get Animus SmartRoom running on startup",
        subgoals=subgoals,
        status="ACTIVE",
        notes="Testing startup pipeline",
        target_category="SYSTEM"
    )

    active = store.get_active_goal()
    assert active is not None
    assert active["id"] == "goal_startup_01"
    assert active["title"] == "Get Animus SmartRoom running on startup"
    assert len(active["subgoals"]) == 3
    assert active["subgoals"][0]["completed"] is True
    assert active["subgoals"][1]["is_current"] is True

    # Advance subgoal
    store.update_subgoal_status("goal_startup_01", subgoal_index=1, completed=True, is_current=False)
    store.update_subgoal_status("goal_startup_01", subgoal_index=2, completed=False, is_current=True)

    updated = store.get_active_goal()
    assert updated["subgoals"][1]["completed"] is True
    assert updated["subgoals"][2]["is_current"] is True

    # Complete goal
    store.complete_goal("goal_startup_01", notes="All steps verified")
    recent = store.get_recent_goals(limit=5)
    completed_goal = next((g for g in recent if g["id"] == "goal_startup_01"), None)
    assert completed_goal is not None
    assert completed_goal["status"] == "COMPLETED"


def test_user_task_lifecycle(temp_memory_store):
    store = temp_memory_store
    tasks = store.get_active_tasks()
    assert len(tasks) >= 1
    assert any("SQL" in t["title"] for t in tasks)

    # Complete SQL task
    completed_name = store.complete_task("SQL")
    assert completed_name is not None
    assert "SQL" in completed_name

    # Save new task
    store.save_task("task_01", "Build voice client", priority="HIGH", category="WORK")
    active_after = store.get_active_tasks()
    assert any(t["id"] == "task_01" for t in active_after)


