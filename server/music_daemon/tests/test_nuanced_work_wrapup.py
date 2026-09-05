"""
Comprehensive Automated Acceptance Tests for:
1. Physical Save Verification in PcController
2. Truthful Work Wrapup without Fake Milestones or Tasks
3. Strict Reminder Permission Gating (Never Autonomous)
4. Follow-Up Engine Deduplication
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from agent.long_term_memory import LongTermMemoryStore
from agent.agent_decision_engine import AgentDecisionEngine
from agent.models import UserProfile, UserIdentity, EntertainmentPreferencesModel, ResolvedIntent, IntentCategory, MoodVibe
from agent.followup_engine import FollowUpEngine
from pc_controller import PcController


@pytest.fixture
def clean_memory(tmp_path):
    db_file = tmp_path / "test_memory.db"
    store = LongTermMemoryStore(db_path=str(db_file))
    return store


@pytest.fixture
def decision_engine(clean_memory):
    engine = AgentDecisionEngine(
        memory_store=clean_memory,
        orchestrator=MagicMock()
    )
    return engine


def test_physical_save_verification_methods():
    """Verifies that PcController implements bring_work_windows_to_foreground and send_save_keystrokes safely."""
    ctrl = PcController()
    assert hasattr(ctrl, "bring_work_windows_to_foreground")
    assert hasattr(ctrl, "send_save_keystrokes")
    assert hasattr(ctrl, "get_work_session_duration")

    # Call send_save_keystrokes without windows open; should return verified telemetry dict
    ok, res = ctrl.send_save_keystrokes()
    assert ok is True
    assert res["action"] == "SEND_SAVE_KEYSTROKE"
    assert "doc_modified_on_disk" in res
    assert "any_files_modified" in res


def test_wrapup_zero_work_creates_no_fake_tasks(decision_engine, clean_memory):
    """Proves that wrapping up with zero work or rest creates 0 tasks and does not advance roadmap."""
    # Active subgoal initially
    sg_before = clean_memory.get_current_work_subgoal()
    assert sg_before is not None
    assert sg_before["completed"] is False
    initial_pending_count = len(clean_memory.get_pending_tasks())

    # User wraps up after doing nothing
    turn1 = decision_engine.decide_and_act("done with work, didn't do anything today")
    assert "All work progress saved and applications closed, Sir." in turn1.response_message
    assert "No milestone changes recorded" in turn1.response_message
    assert "Would you like me to set a reminder" in turn1.response_message

    # Verify zero new tasks and zero milestone advancements
    sg_after = clean_memory.get_current_work_subgoal()
    assert sg_after["id"] == sg_before["id"]
    assert sg_after["completed"] is False
    assert len(clean_memory.get_pending_tasks()) == initial_pending_count


def test_wrapup_reminder_declined_leaves_schedule_open(decision_engine, clean_memory):
    """Proves that declining the reminder sets zero reminders and leaves schedule open."""
    # Turn 1: Wrap up
    decision_engine.decide_and_act("wrap up work")
    assert decision_engine._wrapup_followup_state == "AWAITING_WORK_SUMMARY"

    # Turn 2: User says they took a break
    turn2 = decision_engine.decide_and_act("took a break")
    assert "No milestone changes recorded" in turn2.response_message
    assert "Would you like me to set a reminder" in turn2.response_message
    assert decision_engine._wrapup_followup_state == "AWAITING_REMINDER_DECISION"

    # Turn 3: User says NO to reminder
    turn3 = decision_engine.decide_and_act("no, leave it unscheduled")
    assert "Leaving your schedule open with no reminders set" in turn3.response_message
    assert decision_engine._wrapup_followup_state is None

    # Verify NO reminder tasks were created
    tasks = clean_memory.get_pending_tasks()
    assert not any(t.get("category") == "REMINDER" for t in tasks)


def test_wrapup_reminder_accepted_with_time(decision_engine, clean_memory):
    """Proves that reminders are ONLY set when the user explicitly provides a time."""
    # Turn 1: Wrap up
    decision_engine.decide_and_act("done with work, didn't study")

    # Turn 2: User requests reminder for 10:00 AM
    turn2 = decision_engine.decide_and_act("yes please, set reminder for 10 am")
    assert "Reminder set for tomorrow at" in turn2.response_message
    assert "10:00 am" in turn2.response_message.lower() or "10 am" in turn2.response_message.lower()
    assert decision_engine._wrapup_followup_state is None

    # Verify reminder task exists in memory
    tasks = clean_memory.get_pending_tasks()
    rem_tasks = [t for t in tasks if t.get("category") == "REMINDER"]
    assert len(rem_tasks) == 1
    assert "10:00 am" in rem_tasks[0]["description"].lower() or "10 am" in rem_tasks[0]["description"].lower()


def test_chatgpt_summary_completion_flow(decision_engine, clean_memory):
    """Proves that a completed summary advances milestone and asks for reminder preference."""
    sg_before = clean_memory.get_current_work_subgoal()

    summary = "Today I completed the SQL stock out analysis for Blinkit using LAG() and CTEs. Finished the queries."
    res = decision_engine.decide_and_act(summary)

    assert "Outstanding progress" in res.response_message
    assert "Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?" in res.response_message
    assert decision_engine._wrapup_followup_state == "AWAITING_REMINDER_DECISION"

    # Milestone advanced
    roadmap = clean_memory.get_career_roadmap()
    subgoals = roadmap["active_goal"]["subgoals"]
    matching_old = [s for s in subgoals if s["id"] == sg_before["id"]][0]
    assert matching_old["completed"] is True


def test_followup_engine_deduplication():
    """Proves that rapid duplicate requests to FollowUpEngine are debounced."""
    profile = UserProfile(
        identity=UserIdentity(preferred_address="Sir"),
        entertainment=EntertainmentPreferencesModel(preferred_streaming_services=["netflix", "prime_video"])
    )
    engine = FollowUpEngine(user_profile=profile)

    intent = ResolvedIntent(
        raw_query="movie mode",
        category=IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL,
        primary_intent="START_CINEMA_ENTERTAINMENT",
        mood_vibe=MoodVibe.MOVIE,
        target_subsystems=["PROJECTOR"],
        requires_followup=True
    )

    q1 = engine.create_followup_for_intent(intent)
    q2 = engine.create_followup_for_intent(intent)

    assert q1 == q2
    assert "Netflix" in q1
    assert "Sir" in q1
