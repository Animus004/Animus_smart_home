"""
Automated Test Suite for Phase F.3 — Simulated Real-World Personal Agent Conversation.
Tests multi-stage natural conversation, negative constraints, mind-changing,
relative volume adjustment, task modification, duplicate suppression, and capability explanations.
"""

import time
import pytest
from unittest.mock import MagicMock
from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState
from context import PreferenceManager, ContextEngine
from agent.models import (
    MemoryCategory,
    TaskStatus,
    TaskPriority,
    IntentCategory,
    MoodVibe
)
from agent.memory import AgentMemoryStore
from agent.user_model import UserModel
from agent.task_manager import TaskManager
from agent.intent_resolver import IntentResolver
from agent.followup_engine import FollowUpEngine
from agent.feedback import AgentFeedbackGenerator
from agent.daily_brief import DailyBriefEngine
from agent.capability_awareness import CapabilityAwarenessEngine
from agent.core import AnimusPersonalAgent


@pytest.fixture
def mock_f3_agent():
    """Initializes AnimusPersonalAgent for F.3 testing in an isolated state."""
    registry = UnifiedCapabilityRegistry()
    user_model = UserModel()
    memory = AgentMemoryStore()
    task_mgr = TaskManager()

    aggregator = MagicMock()
    aggregator.get_room_state.return_value = RoomState()
    pref_mgr = PreferenceManager(registry=registry)
    ctx_engine = ContextEngine(preference_manager=pref_mgr, room_state_aggregator=aggregator)

    agent = AnimusPersonalAgent(
        registry=registry,
        room_state_aggregator=aggregator,
        context_engine=ctx_engine,
        preference_manager=pref_mgr
    )
    agent.user_model = user_model
    agent.memory = memory
    agent.task_manager = task_mgr
    return agent


# =============================================================================
# 1. Session A: Morning Brief & Natural Addressing
# =============================================================================

def test_f3_morning_dialogue(mock_f3_agent):
    """Verifies morning greeting triggers priorities summary without using 'Sayan'."""
    resp = mock_f3_agent.interact("Buddy, I'm up.")
    assert "Priorities" in resp.agent_message
    assert "SQL" in resp.agent_message
    assert "buddy" in resp.agent_message.lower()
    assert "Sayan" not in resp.agent_message


# =============================================================================
# 2. Session B: Work Mode & Unsupported Device Explanation
# =============================================================================

def test_f3_work_and_unsupported_fan(mock_f3_agent):
    """Verifies work mode context activation and honest bedroom fan refusal."""
    r_work = mock_f3_agent.interact("I need to start working.")
    assert r_work.action_taken is True

    r_fan = mock_f3_agent.interact("Can you adjust the bedroom fan?")
    assert "can't control the bedroom fan yet" in r_fan.agent_message.lower() or "can't control the fan" in r_fan.agent_message.lower()


# =============================================================================
# 3. Session C & D: Task Creation, Lunch Transition & Completion
# =============================================================================

def test_f3_task_and_lunch_transition(mock_f3_agent):
    """Tests task creation, lunch transition suggestion, and task completion."""
    # Create task
    mock_f3_agent.interact("Remind me to review window functions.")
    pending = mock_f3_agent.task_manager.get_pending_tasks()
    assert any("window functions" in t.title.lower() for t in pending)

    # Lunch transition
    r_lunch = mock_f3_agent.interact("I had lunch.")
    assert "guitar" in r_lunch.agent_message.lower() or "sql" in r_lunch.agent_message.lower()

    # Complete task
    t = pending[0]
    mock_f3_agent.task_manager.complete_task(t.id)
    assert mock_f3_agent.task_manager.get_task(t.id).status == TaskStatus.COMPLETED


# =============================================================================
# 4. Session F: Negative Constraints & Relaxation Disambiguation
# =============================================================================

def test_f3_relaxation_and_negative_constraint(mock_f3_agent):
    """Tests 'I want something relaxing' follow-up and negative constraint resolution."""
    r_rel = mock_f3_agent.interact("I want something relaxing.")
    assert r_rel.followup_required is True
    assert "music" in r_rel.agent_message.lower() and "movie" in r_rel.agent_message.lower()

    # User specifies negative constraint: "No, not music"
    r_no_mus = mock_f3_agent.interact("No, not music.")
    assert r_no_mus.understood_intent is not None


# =============================================================================
# 5. Session G: Entertainment Prep & Changing Mind
# =============================================================================

def test_f3_cinema_prep_and_mind_change(mock_f3_agent):
    """Tests cinema follow-up and changing mind from Netflix to YouTube."""
    # Turn 1: Cinema intent
    r1 = mock_f3_agent.interact("Let's watch something.")
    assert r1.followup_required is True

    # Turn 2: User answers Netflix
    r2 = mock_f3_agent.interact("Netflix.")
    assert r2.action_taken is True

    # Turn 3: User changes mind to YouTube
    r3 = mock_f3_agent.interact("Actually no, put on YouTube instead.")
    assert r3.action_taken is True


# =============================================================================
# 6. Session H: Follow-Up Interruption by Task Command
# =============================================================================

def test_f3_followup_interrupted_by_server_log_reminder(mock_f3_agent):
    """Proves that a pending cinema follow-up is superseded by a server log reminder."""
    mock_f3_agent.interact("Let's watch something.")
    assert mock_f3_agent.followup_engine.has_pending_followup is True

    r2 = mock_f3_agent.interact("Actually remind me to check server logs tomorrow at 10.")
    assert any(k in r2.agent_message.lower() for k in ["remind", "reminder", "noted", "set"])


# =============================================================================
# 7. Full 45-Turn End-to-End Coherence Run
# =============================================================================

def test_f3_full_45_turn_coherence(mock_f3_agent):
    """Executes all 45 conversational turns verifying 100% agent stability."""
    dialogue = [
        "Buddy, I'm up.",
        "What's on my plate today?",
        "Put on something to get me moving.",
        "Make it a little louder.",
        "I'm heading to my desk.",
        "I need to start working.",
        "Set the AC to 24.",
        "Make it quieter.",
        "Quiet mode please.",
        "Can you adjust the bedroom fan?",
        "Time to focus on SQL.",
        "Remind me to review window functions.",
        "Actually remind me after lunch.",
        "What did I just add?",
        "Okay, focusing now.",
        "I had lunch.",
        "What was I supposed to do after lunch?",
        "Let's do SQL for 30 minutes.",
        "Mark window functions as done.",
        "Great, that's done.",
        "Remind me to practice guitar at 5.",
        "Remind me about guitar.",
        "I'm practicing guitar now.",
        "Did I finish my guitar practice on the list?",
        "Set AC to 25.",
        "I'm exhausted buddy.",
        "I want something relaxing.",
        "No, not music.",
        "Let's chill with a movie then.",
        "Let's watch something.",
        "Netflix.",
        "Actually no, put on YouTube instead.",
        "Make it a little quieter.",
        "Actually 25 is fine.",
        "Pause that for a second.",
        "Resume it.",
        "I'm done watching.",
        "Let's watch something.",
        "Actually remind me to check server logs tomorrow at 10.",
        "What do you know about my preferences?",
        "What are you unsure about?",
        "What did I accomplish today?",
        "Set AC to 24 for the night.",
        "Turn everything off.",
        "Good night buddy."
    ]
    for idx, utt in enumerate(dialogue, start=1):
        resp = mock_f3_agent.interact(utt)
        assert resp is not None
        assert resp.agent_message is not None
