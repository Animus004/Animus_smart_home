"""
Automated unit tests for parse_reminder_intention and AgentDecisionEngine reminder handling.
Verifies target day ("today" vs "tomorrow"), time extraction, subject extraction,
and wrapup reminder flow.
"""

from pathlib import Path
import tempfile
import time
import pytest

from agent.agent_decision_engine import AgentDecisionEngine, parse_reminder_intention
from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder


def test_parse_reminder_intention_today():
    # User utterance: "remind me today at 5:00 PM to start work"
    res = parse_reminder_intention("remind me today at 5:00 PM to start work")
    assert res is not None
    assert res["day"] == "today"
    assert res["time_str"] == "5:00 pm"
    assert "start work" in res["subject"].lower()
    assert "at at" not in res["response_message"]
    assert "Reminder set for today at 5:00 pm to start work, Sir." in res["response_message"]


def test_parse_reminder_intention_tomorrow():
    # User utterance: "remind me tomorrow at 10 am to practice sql"
    res = parse_reminder_intention("remind me tomorrow at 10 am to practice sql")
    assert res is not None
    assert res["day"] == "tomorrow"
    assert res["time_str"] == "10:00 am"
    assert "practice sql" in res["subject"].lower()
    assert "at at" not in res["response_message"]
    assert "Reminder set for tomorrow at 10:00 am to practice sql, Sir." in res["response_message"]


def test_parse_reminder_intention_relative():
    # User utterance: "remind me in 30 minutes to check deployment"
    res = parse_reminder_intention("remind me in 30 minutes to check deployment")
    assert res is not None
    assert "30 minutes" in res["response_message"]
    assert "check deployment" in res["subject"].lower()


def test_wrapup_followup_reminder_today_intention():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_rem.db"
        mem = LongTermMemoryStore(db_path=db_path)
        pb = CognitivePromptBuilder(memory_store=mem)
        engine = AgentDecisionEngine(memory_store=mem, prompt_builder=pb)

        # Simulate state: wrapup was triggered and user took a break
        engine._wrapup_followup_state = "AWAITING_WORK_SUMMARY"
        turn1 = engine.decide_and_act("I took a break")
        assert engine._wrapup_followup_state == "AWAITING_REMINDER_DECISION"
        assert "Would you like me to set a reminder" in turn1.response_message

        # User responds: "remind me today at 5:00 PM to start work"
        turn2 = engine.decide_and_act("remind me today at 5:00 PM to start work")
        assert engine._wrapup_followup_state is None
        assert "Reminder set for today at 5:00 pm to start work, Sir." in turn2.response_message
        assert "tomorrow" not in turn2.response_message.lower()
        assert "at at" not in turn2.response_message

        # Verify task was created for today
        tasks = mem.get_pending_tasks()
        rem_tasks = [t for t in tasks if t["category"] == "REMINDER"]
        assert len(rem_tasks) == 1
        assert "Start work" in rem_tasks[0]["title"]
        assert "today" in rem_tasks[0]["description"].lower()


def test_standalone_reminder_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_rem2.db"
        mem = LongTermMemoryStore(db_path=db_path)
        pb = CognitivePromptBuilder(memory_store=mem)
        engine = AgentDecisionEngine(memory_store=mem, prompt_builder=pb)

        # Standalone command outside of wrapup
        res = engine.decide_and_act("remind me today at 5:00 PM to start work")
        assert res.action_type == "TOOL_EXECUTION"
        assert "Reminder set for today at 5:00 pm to start work, Sir." in res.response_message
        tasks = mem.get_pending_tasks()
        assert any("Start work" in t["title"] for t in tasks)
