"""
Unit Test Suite for AgentDecisionEngine.
Verifies cognitive decision loop, tool dispatch, JSON cleaning, goal handling, and fallback behavior.
"""

from pathlib import Path
import tempfile
import pytest

from agent.agent_decision_engine import AgentDecisionEngine, AgentDecisionResult
from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder


@pytest.fixture
def mock_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_engine_memory.db"
        mem = LongTermMemoryStore(db_path=db_path)
        prompt_b = CognitivePromptBuilder(memory_store=mem)
        engine = AgentDecisionEngine(
            memory_store=mem,
            prompt_builder=prompt_b,
            planner_executor=None  # Isolated test
        )
        yield engine, mem


def test_clean_and_parse_json(mock_engine):
    engine, _ = mock_engine
    
    # 1. Clean markdown json fence
    raw_md = '```json\n{"thought": "test", "action_type": "CONVERSATION", "response_message": "hello"}\n```'
    parsed = engine._clean_and_parse_json(raw_md)
    assert parsed is not None
    assert parsed["thought"] == "test"
    assert parsed["response_message"] == "hello"

    # 2. Text with embedded JSON block
    raw_surrounded = 'Here is the decision:\n{"thought": "nested", "action_type": "TOOL_EXECUTION"}\nHope this helps!'
    parsed2 = engine._clean_and_parse_json(raw_surrounded)
    assert parsed2 is not None
    assert parsed2["thought"] == "nested"


def test_emergency_fallback_decision(mock_engine):
    engine, _ = mock_engine
    res = engine._emergency_fallback_decision("let's watch a movie")
    assert res["action_type"] == "TOOL_EXECUTION"
    assert len(res["tool_calls"]) > 0
    assert any(tc["tool"] == "PROJECTOR_POWER_ON" for tc in res["tool_calls"])


def test_emergency_fallback_work_mode(mock_engine):
    engine, _ = mock_engine
    res = engine._emergency_fallback_decision("let's start work mode")
    assert res["action_type"] == "TOOL_EXECUTION"
    assert any(tc["tool"] == "LAUNCH_WORK_MODE" for tc in res["tool_calls"])
    assert "Sir" in res["response_message"]


def test_emergency_fallback_work_wrapup(mock_engine):
    engine, _ = mock_engine
    res = engine._emergency_fallback_decision("i am done with work for today")
    assert res["action_type"] == "TOOL_EXECUTION"
    assert any(tc["tool"] == "WRAPUP_WORK_SESSION" for tc in res["tool_calls"])
    assert "Sir" in res["response_message"]


def test_autonomous_task_tools_execution(mock_engine):
    engine, mem = mock_engine

    # 1. CREATE_TASK
    res_create, st1 = engine._execute_tools([
        {"tool": "CREATE_TASK", "parameters": {"title": "Learn Window Functions in SQL", "priority": "HIGH", "category": "LEARNING"}}
    ])
    assert res_create[0]["status"] == "SUCCESS"
    assert st1 == "VERIFIED_SUCCESS"
    tasks = mem.get_pending_tasks()
    assert any("Learn Window Functions" in t["title"] for t in tasks)

    # 2. COMPLETE_TASK
    res_comp, st2 = engine._execute_tools([
        {"tool": "COMPLETE_TASK", "parameters": {"task_name_or_id": "Learn Window Functions in SQL"}}
    ])
    assert res_comp[0]["status"] == "SUCCESS"
    assert st2 == "VERIFIED_SUCCESS"

    # 3. SCHEDULE_REMINDER
    res_rem, st3 = engine._execute_tools([
        {"tool": "SCHEDULE_REMINDER", "parameters": {"message": "Review query planner", "time_or_offset": "30 minutes"}}
    ])
    assert res_rem[0]["status"] == "SUCCESS"
    assert st3 == "VERIFIED_SUCCESS"

    # 4. SET_ALARM
    res_alm, st4 = engine._execute_tools([
        {"tool": "SET_ALARM", "parameters": {"time_str": "07:30", "label": "Morning Wakeup"}}
    ])
    assert res_alm[0]["status"] == "SUCCESS"
    assert st4 == "VERIFIED_SUCCESS"


def test_decide_and_act_end_to_end(mock_engine):
    engine, mem = mock_engine
    
    # Run turn through live decision engine
    res = engine.decide_and_act("Hey Animus, what time is it and how are you?")
    assert isinstance(res, AgentDecisionResult)
    assert res.response_message != ""
    assert res.inference_source in ["LOCAL_OLLAMA (qwen3:4b-instruct)", "GEMINI_FALLBACK", "EMERGENCY_FALLBACK"]

    # Verify episodic recall was persisted
    recent_episodes = mem.search_past_conversations("time")
    assert len(recent_episodes) >= 1
