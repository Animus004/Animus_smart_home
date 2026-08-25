"""
Test Suite: F.3 Task and Memory Bookkeeping
Verifies task and memory state transitions:
- Turn 12 & 13: Contextual reminder update for window functions.
- Turn 14: Query last added item.
- Turn 17: Query after-lunch task.
- Turn 19: Mark window functions as completed.
- Turn 21 & 22: Deduplicate guitar reminder.
- Turn 24: Query guitar practice completion status.
- Turn 42: Completed tasks accomplishment summary.
"""

import pytest
from agent.core import AnimusPersonalAgent
from agent.user_model import UserModel
from agent.task_manager import TaskManager
from agent.memory import AgentMemoryStore
from agent.models import TaskStatus


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


def test_contextual_reminder_update_and_query(agent):
    """Turns 12, 13, 14: Add reminder, update to after lunch, query recent add."""
    # Turn 12: Add reminder
    res12 = agent.interact("Remind me to review window functions.")
    assert "review window functions" in res12.agent_message.lower()

    # Turn 13: Actually remind me after lunch (contextual update)
    res13 = agent.interact("Actually remind me after lunch.")
    assert "after lunch" in res13.agent_message.lower()
    assert "review window functions" in res13.agent_message.lower()

    # Turn 14: What did I just add?
    res14 = agent.interact("What did I just add?")
    assert "window functions" in res14.agent_message.lower()


def test_after_lunch_query_and_completion(agent):
    """Turns 17, 19, 42: Query after lunch task, mark as done, verify accomplishments."""
    agent.interact("Remind me to review window functions.")
    agent.interact("Actually remind me after lunch.")

    # Turn 17: What was I supposed to do after lunch?
    res17 = agent.interact("What was I supposed to do after lunch?")
    assert "window functions" in res17.agent_message.lower()

    # Turn 19: Mark window functions as done.
    res19 = agent.interact("Mark window functions as done.")
    assert "completed" in res19.agent_message.lower()

    # Verify TaskManager state
    completed_tasks = agent.task_manager.list_tasks(status=TaskStatus.COMPLETED)
    assert any("window functions" in t.title.lower() for t in completed_tasks)

    # Turn 42: What did I accomplish today?
    res42 = agent.interact("What did I accomplish today?")
    assert "window functions" in res42.agent_message.lower()


def test_guitar_reminder_deduplication_and_status(agent):
    """Turns 21, 22, 24: Add guitar reminder, deduplicate, query status."""
    # Turn 21: Remind me to practice guitar at 5.
    res21 = agent.interact("Remind me to practice guitar at 5.")
    assert "practice guitar" in res21.agent_message.lower()

    # Turn 22: Remind me about guitar (should deduplicate)
    res22 = agent.interact("Remind me about guitar.")
    assert "already have a reminder" in res22.agent_message.lower()

    # Turn 24: Did I finish my guitar practice on the list?
    res24 = agent.interact("Did I finish my guitar practice on the list?")
    assert "pending" in res24.agent_message.lower()
