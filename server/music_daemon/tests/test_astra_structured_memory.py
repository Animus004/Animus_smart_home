"""
================================================================================
ANIMUS SMART ROOM — ASTRA STRUCTURED PERSONAL MEMORY & EXPRESSION TESTS
================================================================================
Validates:
1. StructuredMemoryItem Schema & SQLite CRUD in LongTermMemoryStore.
2. Contextual Associative Retrieval (SQL query retrieves only SQL/work/milestone,
   movie query retrieves projector/soundbar/movie, avoiding context dumping).
3. Dynamic Prompt Synthesis with Relevant Memory Injection.
4. Closed-loop User Preference Learning from natural dialogue.
5. Multi-Modal Expression Formulation (Light + UI + Sound cues).
================================================================================
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agent.models import MemoryType, StructuredMemoryItem, AgentExpressionPayload
from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder
from agent.agent_decision_engine import AgentDecisionEngine, AgentDecisionResult


@pytest.fixture
def temp_memory():
    """Provides an isolated LongTermMemoryStore with fresh temporary SQLite DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_astra_memory.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


@pytest.fixture
def decision_engine(temp_memory):
    """Provides an AgentDecisionEngine wired to isolated memory and mocked hardware."""
    mock_pc = MagicMock()
    mock_pc.launch_allowlisted_app.return_value = (True, "Launched")
    mock_pc.send_save_keystrokes.return_value = (True, {"any_files_modified": True})
    mock_pc.close_apps.return_value = (True, "Closed")
    mock_pc.get_active_work_context.return_value = {}

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )
    return engine


def test_structured_memory_baseline_and_crud(temp_memory):
    """Proves baseline seeding and structured CRUD operations."""
    all_memories = temp_memory.get_all_structured_memories()
    assert len(all_memories) >= 10

    # Verify key baseline items exist
    subjects = {m["subject"] for m in all_memories}
    assert "work" in subjects
    assert "projector" in subjects
    assert "sql" in subjects
    assert "guitar" in subjects

    # Store a new personal memory
    stored = temp_memory.store_structured_memory(
        memory_type=MemoryType.PREFERENCE,
        subject="beverage",
        context="morning",
        value="black coffee with no sugar",
        confidence=1.0,
        source="user"
    )
    assert stored["id"] is not None
    assert stored["subject"] == "beverage"

    # Retrieve by ID
    retrieved = temp_memory.get_structured_memory(stored["id"])
    assert retrieved is not None
    assert retrieved["value"] == "black coffee with no sugar"

    # Update existing memory with higher confidence
    updated = temp_memory.store_structured_memory(
        memory_type=MemoryType.PREFERENCE,
        subject="beverage",
        context="morning",
        value="espresso with a dash of milk",
        confidence=1.0,
        source="user"
    )
    assert updated["id"] == stored["id"]
    assert updated["value"] == "espresso with a dash of milk"

    # Delete memory
    del_ok = temp_memory.delete_structured_memory(stored["id"])
    assert del_ok is True
    assert temp_memory.get_structured_memory(stored["id"]) is None


def test_contextual_associative_retrieval_work_sql(temp_memory):
    """
    Proves that when user says 'I'm going to work on SQL',
    Animus retrieves ONLY work/SQL/career memories,
    and ignores irrelevant projector and guitar memories.
    """
    hits = temp_memory.retrieve_relevant_structured_memories(
        query="I'm going to work on SQL.",
        active_mode="IDLE",
        limit=5,
        include_universal_constraints=False
    )

    retrieved_subjects = [m["subject"] for m in hits]
    # Work and SQL items must be present
    assert any(s in ["sql", "work", "career", "excel"] for s in retrieved_subjects)

    # Guitar and Projector must NOT be retrieved
    assert "guitar" not in retrieved_subjects
    assert "projector" not in retrieved_subjects


def test_contextual_associative_retrieval_movie(temp_memory):
    """
    Proves that when user asks for movie mode,
    Animus retrieves ONLY projector/soundbar/streaming/lighting memories,
    and ignores SQL and guitar memories.
    """
    hits = temp_memory.retrieve_relevant_structured_memories(
        query="Let's watch a movie on the projector.",
        active_mode="IDLE",
        limit=5,
        include_universal_constraints=False
    )

    retrieved_subjects = [m["subject"] for m in hits]
    assert any(s in ["projector", "soundbar", "streaming", "lighting", "ac"] for s in retrieved_subjects)
    assert "sql" not in retrieved_subjects
    assert "guitar" not in retrieved_subjects


def test_contextual_associative_retrieval_guitar(temp_memory):
    """
    Proves that when user asks for guitar practice,
    Animus retrieves guitar memories and excludes SQL and projector.
    """
    hits = temp_memory.retrieve_relevant_structured_memories(
        query="Time for some guitar practice.",
        active_mode="IDLE",
        limit=5,
        include_universal_constraints=False
    )

    retrieved_subjects = [m["subject"] for m in hits]
    assert "guitar" in retrieved_subjects
    assert "projector" not in retrieved_subjects
    assert "sql" not in retrieved_subjects


def test_dynamic_prompt_synthesis_relevance(temp_memory):
    """Proves that CognitivePromptBuilder injects only relevant memories into prompt context."""
    builder = CognitivePromptBuilder(memory_store=temp_memory)
    prompt = builder.build_prompt(
        user_utterance="I'm going to work on SQL.",
        active_mode="IDLE"
    )

    # Must contain relevant personal memories with SQL/work
    assert "relevant_personal_memories" in prompt
    assert "SQL" in prompt or "sql" in prompt
    # Ensure projector hardware details are NOT in relevant_personal_memories
    assert "PixaPlay 25" not in prompt


def test_closed_loop_user_preference_learning(decision_engine, temp_memory):
    """Proves that user natural preference statements are stored without hallucination."""
    # User states an AC movie preference
    res = decision_engine.decide_and_act("I prefer the AC at 21 when watching movies")
    assert "Sir" in res.response_message

    # Verify structured memory was stored
    memories = temp_memory.get_all_structured_memories(memory_type="preference")
    ac_movie_mems = [m for m in memories if m["subject"] == "ac" and m["context"] == "movie"]
    assert len(ac_movie_mems) == 1
    assert "21°C setpoint" in ac_movie_mems[0]["value"]
    assert ac_movie_mems[0]["confidence"] == 1.0
    assert ac_movie_mems[0]["source"] == "user"


def test_multi_modal_expression_formulation(decision_engine):
    """Proves that decisions formulate unified Voice + Action + Expression (Light/UI/Sound) payloads."""
    # 1. Start Work Mode
    res_work = decision_engine.decide_and_act("start work mode")
    assert res_work.expression_payload is not None
    expr = res_work.expression_payload
    assert expr["light_cue"] == "FOCUS_WARM"
    assert expr["ui_state"]["mode"] == "WORK"
    assert expr["sound_cue"] == "FOCUS_START"

    # 2. Wrap up Work
    res_wrapup = decision_engine.decide_and_act("wrap up work")
    assert res_wrapup.expression_payload is not None
    expr_wrap = res_wrapup.expression_payload
    assert expr_wrap["light_cue"] == "RELAX_AMBER"
    assert expr_wrap["ui_state"]["mode"] == "RELAX"
    assert expr_wrap["sound_cue"] == "RESTFUL_CHIME"
