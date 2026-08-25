"""
Comprehensive Test Battery for Phase F.1 — Animus Personal Agent Intelligence & User Model.
Tests User Profile, 9-Category Memory Taxonomy, Task Manager, Intent Resolution,
Follow-Up Question Engine, Feedback Generator, Daily Brief, Capability Awareness,
AC Semantic Independence, and REST Endpoints.
"""

import time
import pytest
from fastapi.testclient import TestClient

from capability_registry import UnifiedCapabilityRegistry
from room_state.models import (
    RoomState,
    ProjectorState,
    FireTvState,
    SoundbarState,
    AcState,
    PcState,
    AudioStreamState,
    ActiveAudioProducer,
    MediaPlaybackState
)
from room_state.aggregator import RoomStateAggregator
from context import PreferenceManager, ContextEngine
from planner import PlanValidator, GeminiPlannerClient, PlanExecutor
from main import app, animus_personal_agent
from agent.models import (
    MemoryCategory,
    TaskStatus,
    TaskPriority,
    TaskSource,
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
def mock_agent_suite(tmp_path):
    """Initializes isolated AnimusPersonalAgent components with temp storage."""
    registry = UnifiedCapabilityRegistry()
    user_model = UserModel()
    memory = AgentMemoryStore()
    task_mgr = TaskManager()
    intent_resolver = IntentResolver(user_profile=user_model.profile, registry=registry, memory=memory)
    followup_engine = FollowUpEngine(user_profile=user_model.profile)
    feedback_gen = AgentFeedbackGenerator(user_profile=user_model.profile)
    brief_engine = DailyBriefEngine(user_profile=user_model.profile, task_manager=task_mgr, memory=memory)
    cap_engine = CapabilityAwarenessEngine(registry=registry, user_profile=user_model.profile)

    return {
        "registry": registry,
        "user_model": user_model,
        "memory": memory,
        "task_mgr": task_mgr,
        "intent_resolver": intent_resolver,
        "followup_engine": followup_engine,
        "feedback_gen": feedback_gen,
        "brief_engine": brief_engine,
        "cap_engine": cap_engine
    }


# =============================================================================
# 1. User Profile & Addressing Tests
# =============================================================================

def test_user_identity_and_preferred_address(mock_agent_suite):
    """Validates user identity and preferred address ('buddy')."""
    user_model = mock_agent_suite["user_model"]
    assert user_model.identity.name == "Sayan Halder"
    assert user_model.preferred_address == "buddy"
    assert user_model.identity.location_pin == "741235"


def test_user_profile_updates(mock_agent_suite):
    """Validates updating user profile fields."""
    user_model = mock_agent_suite["user_model"]
    updated = user_model.update_profile({"thermal": {"preferred_ac_setpoint": 26}})
    assert updated.thermal.preferred_ac_setpoint == 26
    assert user_model.thermal.preferred_ac_setpoint == 26


# =============================================================================
# 2. Fact vs Assumption Separation in 9-Category Memory
# =============================================================================

def test_memory_fact_vs_assumption_separation(mock_agent_suite):
    """
    CRITICAL INVARIANT: Assumptions must NOT be treated as confirmed facts.
    """
    memory = mock_agent_suite["memory"]

    # 1. Stable Fact
    fact = memory.record_fact("favourite_genre", "sci-fi")
    assert fact.category == MemoryCategory.STABLE_USER_FACT
    assert fact.user_confirmed is True

    # 2. Agent Assumption
    assumption = memory.record_assumption("user_prefers_cooler_room_after_lunch", True)
    assert assumption.category == MemoryCategory.AGENT_ASSUMPTION
    assert assumption.user_confirmed is False
    assert assumption.confidence < 1.0

    # Ensure get_by_category strictly isolates them
    facts = memory.get_by_category(MemoryCategory.STABLE_USER_FACT)
    assumptions = memory.get_by_category(MemoryCategory.AGENT_ASSUMPTION)
    assert any(f.key == "favourite_genre" for f in facts)
    assert not any(f.key == "user_prefers_cooler_room_after_lunch" for f in facts)
    assert any(a.key == "user_prefers_cooler_room_after_lunch" for a in assumptions)

    # Confirm decision converts it
    decision = memory.confirm_decision("user_prefers_cooler_room_after_lunch", True, assumption_id=assumption.id)
    assert decision.category == MemoryCategory.USER_CONFIRMED_DECISION
    assert decision.user_confirmed is True
    assert len(memory.get_by_category(MemoryCategory.AGENT_ASSUMPTION)) == 0


# =============================================================================
# 3. Routine Recognition & Triggers
# =============================================================================

def test_lunch_transition_trigger(mock_agent_suite):
    """Validates recognition of 'I had lunch' and variants."""
    user_model = mock_agent_suite["user_model"]
    assert user_model.is_lunch_trigger("I had lunch") is True
    assert user_model.is_lunch_trigger("Just had lunch") is True
    assert user_model.is_lunch_trigger("I've had lunch") is True
    assert user_model.is_lunch_trigger("I have lunch") is True
    assert user_model.is_lunch_trigger("finished lunch") is True
    assert user_model.is_lunch_trigger("Let's watch a movie") is False


def test_work_and_quiet_hours(mock_agent_suite):
    """Validates work hours (11:00-17:00) quiet hour checks."""
    user_model = mock_agent_suite["user_model"]
    # During work (e.g. 14:00) -> in quiet hours
    assert user_model.is_in_quiet_hours("14:00") is True
    # Outside work (e.g. 09:30 or 19:00) -> not in quiet hours
    assert user_model.is_in_quiet_hours("09:30") is False
    assert user_model.is_in_quiet_hours("19:00") is False


# =============================================================================
# 4. AC Semantics & Subsystem Independence
# =============================================================================

def test_ac_semantic_independence_and_work_policy(mock_agent_suite):
    """
    Validates that AC is treated as an independent subsystem and not blindly mutated.
    """
    user_model = mock_agent_suite["user_model"]

    # 1. When AC is currently OFF, work mode policy leaves it OFF
    res_off = user_model.evaluate_ac_policy_for_work(current_ac_on=False)
    assert res_off["action_required"] is False
    assert "leaving untouched" in res_off["reason"]

    # 2. When AC is ON and already at 24°C, no action required
    res_on_same = user_model.evaluate_ac_policy_for_work(current_ac_on=True, current_ac_temp=24)
    assert res_on_same["action_required"] is False

    # 3. When AC is ON but at 28°C, adjust to 24°C
    res_on_diff = user_model.evaluate_ac_policy_for_work(current_ac_on=True, current_ac_temp=28)
    assert res_on_diff["action_required"] is True
    assert res_on_diff["target_temperature"] == 24


# =============================================================================
# 5. Task & Reminder Bookkeeping Engine
# =============================================================================

def test_task_creation_and_completion(mock_agent_suite):
    """Validates creating and completing tasks."""
    task_mgr = mock_agent_suite["task_mgr"]
    task = task_mgr.create_task(title="Practice advanced SQL joins", priority=TaskPriority.HIGH, category="LEARNING")
    assert task.status == TaskStatus.PENDING

    # Query pending
    pending = task_mgr.get_pending_tasks()
    assert any(t.id == task.id for t in pending)

    # Complete task
    completed = task_mgr.complete_task(task.id)
    assert completed is not None
    assert completed.status == TaskStatus.COMPLETED
    assert completed.completed_at is not None


def test_natural_language_task_and_reminder_queries(mock_agent_suite):
    """Validates natural language task parsing and agenda answering."""
    task_mgr = mock_agent_suite["task_mgr"]

    # Remind me query
    res = task_mgr.parse_natural_task_or_reminder("Remind me to review SQL indexing tomorrow")
    assert res is not None
    assert res["type"] == "REMINDER_CREATED"

    # Task query answer
    ans = task_mgr.answer_task_query("What do I have to do today?")
    assert "buddy" in ans.lower()
    assert "sql" in ans.lower()


def test_duplicate_guitar_reminder_prevention(mock_agent_suite):
    """Validates that duplicate guitar reminders are avoided once handled."""
    task_mgr = mock_agent_suite["task_mgr"]
    assert task_mgr.is_guitar_reminder_already_handled_today() is False

    # Schedule and acknowledge reminder
    rem = task_mgr.schedule_reminder(message="Time for guitar practice", scheduled_time=time.time())
    task_mgr.acknowledge_reminder(rem.id)

    # Now guitar reminder should report already handled
    assert task_mgr.is_guitar_reminder_already_handled_today() is True


# =============================================================================
# 6. Intent Resolution & 6-Class Classification
# =============================================================================

def test_intent_resolver_classification(mock_agent_suite):
    """Validates classification into 6 categories."""
    resolver = mock_agent_suite["intent_resolver"]

    # 1. Unsafe / Out-of-bounds
    res_unsafe = resolver.resolve_intent("Set AC temperature to 45")
    assert res_unsafe.category == IntentCategory.UNSAFE_NOT_AUTHORIZED

    # 2. Unsupported Device
    res_fan = resolver.resolve_intent("Turn on the bedroom fan")
    assert res_fan.category == IntentCategory.UNSUPPORTED_CAPABILITY

    # 3. Informational: Morning Brief
    res_morning = resolver.resolve_intent("Good morning")
    assert res_morning.category == IntentCategory.INFORMATIONAL_ONLY
    assert res_morning.mood_vibe == MoodVibe.WAKE_UP

    # 4. Ambiguous: Relaxation
    res_relax = resolver.resolve_intent("I'm tired, let's chill")
    assert res_relax.category == IntentCategory.AMBIGUOUS_REQUIRES_FOLLOW_UP
    assert res_relax.requires_followup is True

    # 5. Clear with Missing Non-Critical: Cinema
    res_cinema = resolver.resolve_intent("Let's watch something")
    assert res_cinema.category == IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL
    assert res_cinema.requires_followup is True

    # 6. Clear Executable: YouTube
    res_yt = resolver.resolve_intent("Put on YouTube")
    assert res_yt.category == IntentCategory.CLEAR_EXECUTABLE


# =============================================================================
# 7. Follow-Up Question Engine & Uncertainty Reduction
# =============================================================================

def test_followup_question_engine_flow(mock_agent_suite):
    """Validates multi-turn uncertainty reduction."""
    followup = mock_agent_suite["followup_engine"]
    resolver = mock_agent_suite["intent_resolver"]

    # Step 1: User says "Put on something relaxing"
    intent = resolver.resolve_intent("Put on something relaxing")
    q = followup.create_followup_for_intent(intent)
    assert "music" in q.lower() and "movie" in q.lower()
    assert followup.has_pending_followup is True

    # Step 2: User answers "Music"
    res = followup.resolve_followup_response("Music")
    assert res["resolved"] is True
    assert res["intent"] == "PLAY_RELAXING_MUSIC"
    assert followup.has_pending_followup is False


# =============================================================================
# 8. Feedback Generator Readback Verification
# =============================================================================

def test_agent_feedback_generator(mock_agent_suite):
    """Validates feedback generation from execution results."""
    from planner.models import ExecutionResult, StepExecutionResult, ExecutionStatus, OverallExecutionStatus

    feedback_gen = mock_agent_suite["feedback_gen"]

    # Success case
    exec_res = ExecutionResult(
        overall_status=OverallExecutionStatus.SUCCESS,
        success=True,
        total_steps=3,
        verified_steps_count=2,
        skipped_steps_count=1,
        steps=[
            StepExecutionResult(step_id=1, device="PROJECTOR", capability_id="PROJECTOR_POWER_WAKE", status=ExecutionStatus.VERIFIED, verified=True),
            StepExecutionResult(step_id=2, device="FIRE_TV", capability_id="FIRE_TV_POWER_WAKE", status=ExecutionStatus.VERIFIED, verified=True),
            StepExecutionResult(step_id=3, device="SOUNDBAR", capability_id="SOUNDBAR_ROUTE_TO_FIRE_TV", status=ExecutionStatus.SKIPPED, verified=True)
        ]
    )
    fb = feedback_gen.format_execution_feedback("Let's watch something", exec_res)
    assert "the projector" in fb
    assert "Fire TV" in fb
    assert "in place" in fb or "soundbar" in fb
    assert "buddy" in fb


# =============================================================================
# 9. Daily Brief Engine
# =============================================================================

def test_daily_brief_generation(mock_agent_suite):
    """Validates morning and evening briefing generation."""
    brief_engine = mock_agent_suite["brief_engine"]

    weather = {"available": True, "condition": "Partly Cloudy", "outdoor_temperature_c": 28.5}
    morning = brief_engine.generate_morning_brief(weather_info=weather)
    assert "Good morning, buddy" in morning
    assert "SQL" in morning
    assert "Guitar" in morning
    assert "741235" in morning

    evening = brief_engine.generate_evening_brief()
    assert "Good night, buddy" in evening


# =============================================================================
# 10. Capability Awareness Engine
# =============================================================================

def test_capability_awareness_queries(mock_agent_suite):
    """Validates answering capability inquiries and unsupported device explanations."""
    cap_engine = mock_agent_suite["cap_engine"]

    ans = cap_engine.answer_capability_query("What can you control?")
    assert "Projector" in ans
    assert "Fire TV" in ans
    assert "Soundbar" in ans
    assert "Air Conditioner" in ans

    unsupported = cap_engine.explain_unsupported_capability("microwave")
    assert "can't control the microwave yet" in unsupported.lower()


# =============================================================================
# 11. Full Conversational Interaction via AnimusPersonalAgent & FastAPI Client
# =============================================================================

def test_agent_interaction_pipeline():
    """Validates end-to-end agent interaction through FastAPI test client."""
    client = TestClient(app)

    # 1. Morning Greeting
    resp_morning = client.post("/api/agent/interact", json={"utterance": "Good morning"})
    assert resp_morning.status_code == 200
    data_m = resp_morning.json()
    assert "Good morning, buddy" in data_m["agent_message"]

    # 2. Lunch trigger
    resp_lunch = client.post("/api/agent/interact", json={"utterance": "I had lunch"})
    assert resp_lunch.status_code == 200
    data_l = resp_lunch.json()
    assert "guitar" in data_l["agent_message"].lower()

    # 3. Unsupported Device
    resp_fan = client.post("/api/agent/interact", json={"utterance": "Turn on the coffee machine"})
    assert resp_fan.status_code == 200
    data_f = resp_fan.json()
    assert "can't control the coffee" in data_f["agent_message"].lower()

    # 4. Out of bounds temperature
    resp_oob = client.post("/api/agent/interact", json={"utterance": "Set AC temperature to 50"})
    assert resp_oob.status_code == 200
    data_oob = resp_oob.json()
    assert "outside safe physical hardware bounds" in data_oob["agent_message"]

    # 5. Profile & Tasks endpoints
    resp_profile = client.get("/api/agent/profile")
    assert resp_profile.status_code == 200
    assert resp_profile.json()["identity"]["preferred_address"] == "buddy"

    resp_tasks = client.get("/api/agent/tasks")
    assert resp_tasks.status_code == 200
    assert len(resp_tasks.json()) >= 3

    resp_brief = client.get("/api/agent/brief")
    assert resp_brief.status_code == 200
    assert "brief" in resp_brief.json()

    resp_mem = client.get("/api/agent/memory")
    assert resp_mem.status_code == 200
    assert "STABLE_USER_FACT" in resp_mem.json()
