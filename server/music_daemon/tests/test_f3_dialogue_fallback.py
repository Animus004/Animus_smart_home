"""
Test Suite: F.3 Dialogue and Non-Hardware Intent Resolution
Verifies that all 14 previously falling-through conversational turns resolve to their
authoritative semantic intent and do not emit generic placeholder responses.
"""

import pytest
from agent.core import AnimusPersonalAgent
from agent.user_model import UserModel
from agent.task_manager import TaskManager
from agent.memory import AgentMemoryStore


@pytest.fixture
def agent():
    user_model = UserModel()
    task_manager = TaskManager()
    memory_store = AgentMemoryStore()
    return AnimusPersonalAgent(
        user_model=user_model,
        task_manager=task_manager,
        memory=memory_store
    )


def test_turn_03_motivational_music(agent):
    res = agent.interact("Put on something to get me moving.")
    assert res.understood_intent == "PLAY_MUSIC"
    assert "music" in res.agent_message.lower()


def test_turn_11_focus_sql(agent):
    res = agent.interact("Time to focus on SQL.")
    assert res.understood_intent == "ENTER_WORK_FOCUS_MODE"
    assert "focus" in res.agent_message.lower()


def test_turn_15_focusing_now(agent):
    res = agent.interact("Okay, focusing now.")
    assert res.understood_intent == "CONVERSATIONAL_ACK"
    assert "focus" in res.agent_message.lower()


def test_turn_20_great_thats_done(agent):
    res = agent.interact("Great, that's done.")
    assert res.understood_intent == "CONVERSATIONAL_ACK"
    assert res.agent_message != "Got it, buddy."


def test_turn_23_practicing_guitar_now(agent):
    res = agent.interact("I'm practicing guitar now.")
    assert res.understood_intent == "USER_STATE_UPDATE"
    assert "guitar" in res.agent_message.lower()


def test_turn_26_exhausted_buddy(agent):
    res = agent.interact("I'm exhausted buddy.")
    assert res.understood_intent == "USER_MOOD_STATEMENT"
    assert res.followup_required is True
    assert "music" in res.agent_message.lower() or "movie" in res.agent_message.lower()


def test_turn_28_negative_constraint_relaxation(agent):
    # First trigger relax follow-up
    agent.interact("I want something relaxing.")
    # Then provide negative constraint
    res = agent.interact("No, not music.")
    assert "movie" in res.agent_message.lower() or "quiet" in res.agent_message.lower()


def test_turn_35_36_media_pause_resume(agent):
    res_pause = agent.interact("Pause that for a second.")
    assert res_pause.understood_intent in ("PAUSE_MEDIA", "GENERAL_ROOM_COMMAND")

    res_resume = agent.interact("Resume it.")
    assert res_resume.understood_intent in ("RESUME_MEDIA", "GENERAL_ROOM_COMMAND")


def test_turn_14_recent_add_query(agent):
    agent.interact("Remind me to review window functions.")
    res = agent.interact("What did I just add?")
    assert res.understood_intent == "TASK_SCHEDULE_QUERY"
    assert "window functions" in res.agent_message.lower()


def test_turn_19_mark_task_done(agent):
    agent.interact("Remind me to review window functions.")
    res = agent.interact("Mark window functions as done.")
    assert res.understood_intent == "COMPLETE_TASK"
    assert "completed" in res.agent_message.lower()


def test_turn_24_guitar_completion_status(agent):
    agent.interact("Remind me to practice guitar at 5.")
    res = agent.interact("Did I finish my guitar practice on the list?")
    assert res.understood_intent == "TASK_SCHEDULE_QUERY"
    assert "guitar" in res.agent_message.lower()
    assert "pending" in res.agent_message.lower()


def test_turn_40_41_preference_and_uncertainty_audits(agent):
    res40 = agent.interact("What do you know about my preferences?")
    assert res40.understood_intent == "AUDIT_USER_PREFERENCES"
    assert "preferences" in res40.agent_message.lower()
    assert "setpoint" in res40.agent_message.lower() or "volume" in res40.agent_message.lower()

    res41 = agent.interact("What are you unsure about?")
    assert res41.understood_intent == "AUDIT_UNCERTAINTY"
    assert res41.agent_message != "Got it, buddy."

