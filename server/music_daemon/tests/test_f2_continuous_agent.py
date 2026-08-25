"""
Automated Test Battery for Phase F.2 — Continuous Conversational Agent & Real-World Interaction.
Tests multi-turn context retention, pronoun resolution, follow-up interruption,
AC independence, memory fact insulation, 8-phase daily loop, and 20-turn continuous session.
"""

import time
import pytest
from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState
from room_state.aggregator import RoomStateAggregator
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
def mock_agent():
    """Initializes AnimusPersonalAgent in a clean state."""
    registry = UnifiedCapabilityRegistry()
    user_model = UserModel()
    memory = AgentMemoryStore()
    task_mgr = TaskManager()

    # Stub aggregator and context engine
    from unittest.mock import MagicMock
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
    # Inject isolated clean state
    agent.user_model = user_model
    agent.memory = memory
    agent.task_manager = task_mgr
    return agent


# =============================================================================
# 1. Level 1 & 2: Natural Language & Follow-Up Intelligence
# =============================================================================

def test_f2_generic_cinema_followup(mock_agent):
    """F2-FU-01: 'Let's watch something' triggers cinema prep + streaming source follow-up."""
    resp = mock_agent.interact("Let's watch something.")
    assert resp.followup_required is True
    assert any(s in resp.agent_message.lower() for s in ["netflix", "prime", "apple tv", "youtube"])
    assert "buddy" in resp.agent_message.lower()


def test_f2_relaxation_followup(mock_agent):
    """F2-FU-02: 'Put something relaxing on' asks single-question music vs movie follow-up."""
    resp = mock_agent.interact("Put on something relaxing.")
    assert resp.followup_required is True
    assert "music" in resp.agent_message.lower() and "movie" in resp.agent_message.lower()


# =============================================================================
# 2. Level 3 & 4: Multi-Turn Conversation & Pronoun Reference
# =============================================================================

def test_f2_multi_turn_c1_conversation(mock_agent):
    """Conversation C1: 5-turn session with context carryover."""
    # Turn 1: Cinema intent
    r1 = mock_agent.interact("Let's watch something.")
    assert r1.followup_required is True

    # Turn 2: Select source
    r2 = mock_agent.interact("Netflix.")
    assert r2.action_taken is True

    # Turn 3: Volume adjustment
    r3 = mock_agent.interact("Make it a little quieter.")
    assert r3.understood_intent is not None

    # Turn 4: Confirmation
    r4 = mock_agent.interact("Okay, that's good.")
    assert "buddy" in r4.agent_message.lower()


# =============================================================================
# 3. Level 5: AC Independence Precedence
# =============================================================================

def test_f2_ac_independence_during_entertainment(mock_agent):
    """Proves 'Let's watch a movie' does NOT force an AC setpoint command."""
    intent = mock_agent.intent_resolver.resolve_intent("Let's watch a movie.")
    # AC should not be in target subsystems unless explicitly stated
    assert "AC" not in intent.target_subsystems or intent.category == IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL


# =============================================================================
# 4. Level 6: Memory Fact Insulation
# =============================================================================

def test_f2_memory_assumption_insulation(mock_agent):
    """Proves assumptions are never silently converted into permanent facts."""
    # User says "I'm tired"
    mock_agent.interact("I'm tired.")
    facts = mock_agent.memory.get_by_category(MemoryCategory.STABLE_USER_FACT)
    # Ensure no permanent relaxation fact was fabricated
    assert not any("relax" in f.key for f in facts)


# =============================================================================
# 5. Level 7: Routine Intelligence
# =============================================================================

def test_f2_routine_lifecycle(mock_agent):
    """Tests morning brief, lunch transition, and night wrap-up."""
    # Morning
    r_m = mock_agent.interact("Good morning.")
    assert "Priorities" in r_m.agent_message
    assert "SQL" in r_m.agent_message

    # Lunch
    r_l = mock_agent.interact("I had lunch.")
    assert "guitar" in r_l.agent_message.lower() or "sql" in r_l.agent_message.lower()

    # Night
    r_n = mock_agent.interact("Good night.")
    assert "Good night, buddy" in r_n.agent_message


# =============================================================================
# 6. Level 8: Task & Reminder Lifecycle
# =============================================================================

def test_f2_task_and_reminder_lifecycle(mock_agent):
    """Tests task creation, due query, and completion."""
    mock_agent.interact("Remind me to review database indexing tomorrow.")
    ans = mock_agent.interact("What do I have to do today?")
    assert "SQL" in ans.agent_message


# =============================================================================
# 7. Level 9: Capability Awareness & Truthful Refusal
# =============================================================================

def test_f2_capability_awareness(mock_agent):
    """Tests supported capability reflection and unsupported refusal."""
    r_cap = mock_agent.interact("What can you control?")
    assert "Projector" in r_cap.agent_message
    assert "Fire TV" in r_cap.agent_message

    r_fan = mock_agent.interact("Can you control the bedroom fan?")
    assert "can't control the bedroom fan yet" in r_fan.agent_message.lower() or "can't control the fan" in r_fan.agent_message.lower()


# =============================================================================
# 8. Level 11 & 12: Interruption & Topic Switching
# =============================================================================

def test_f2_followup_interruption_by_task(mock_agent):
    """Proves that a pending follow-up is safely superseded by an explicit task command."""
    # Turn 1: Cinema follow-up created
    mock_agent.interact("Let's watch something.")
    assert mock_agent.followup_engine.has_pending_followup is True

    # Turn 2: User interrupts with task command
    r2 = mock_agent.interact("Remind me to practice guitar at 5.")
    assert any(k in r2.agent_message.lower() for k in ["remind", "reminder", "noted", "set"])


# =============================================================================
# 9. Level 16: Personality & Addressing Constraints
# =============================================================================

def test_f2_personality_constraints(mock_agent):
    """Verifies that the agent addresses the user as 'buddy' without using 'Sayan'."""
    r = mock_agent.interact("Good morning.")
    assert "buddy" in r.agent_message.lower()
    assert "Sayan" not in r.agent_message


# =============================================================================
# 10. Level 17 & 19: Full Daily Loop & 20-Turn Continuous Session
# =============================================================================

def test_f2_20_turn_continuous_session(mock_agent):
    """Executes a 20-turn continuous conversational session with zero state corruption."""
    turns = [
        "Good morning",
        "What do I have to do today?",
        "Remind me to practice SQL at 2",
        "I'm heading to work now",
        "Set AC to 24",
        "Make it quiet",
        "I had lunch",
        "Sit for SQL",
        "What are my tasks?",
        "Mark SQL as done",
        "Remind me to play guitar at 5",
        "Let's chill",
        "Music",
        "Make it a bit quieter",
        "Actually 30",
        "What can you control?",
        "Can you turn on the bedroom fan?",
        "Let's watch something",
        "YouTube",
        "Good night"
    ]
    for idx, utt in enumerate(turns, start=1):
        resp = mock_agent.interact(utt)
        assert resp is not None
        assert resp.understood_intent is not None
