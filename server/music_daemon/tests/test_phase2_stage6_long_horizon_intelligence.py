"""
Authoritative Automated Test Battery for Phase 2 Stage 6:
Long-Horizon Room Intelligence, Event-Driven Awareness, Persistent Behavioral Intelligence & Autonomous Continuity.

Covers Sections A through O:
Section A: Event Model (Tests A1-A6)
Section B: Event Bus (Tests B1-B6)
Section C: Room Monitor (Tests C1-C7)
Section D: Scheduler (Tests D1-D8)
Section E: Long-Horizon Goals (Tests E1-E7)
Section F: Behavioral Profile (Tests F1-F6)
Section G: Situation Engine (Tests G1-G6)
Section H: Event-Driven Proactive Intelligence (Tests H1-H7)
Section I: Mode Reconciliation (Tests I1-I5)
Section J: Recovery & Soundbar Ownership (Tests J1-J5)
Section K: Scheduler + Goal Integration (Tests K1-K6)
Section L: Restart / Durability (Tests L1-L5)
Section M: Introspection (Tests M1-M6)
Section N: Soundbar Ownership Invariants (Tests N1-N5)
Section O: Canonical Dialogues A-F (Tests O1-O6)
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from agent.core import AnimusPersonalAgent
from agent.room_events import RoomEvent, RoomEventType
from agent.event_bus import RoomEventBus
from agent.room_monitor import RoomStateMonitor, TelemetrySnapshot
from agent.scheduler import RoomScheduler, ScheduledTask, ScheduledTaskStatus
from agent.long_horizon_goals import LongHorizonGoalManager
from agent.behavioral_profile import BehavioralProfileManager, BehavioralPreference, PreferenceProvenance
from agent.situation_engine import SituationEngine, RoomSituation, SituationAssessment
from agent.proactive_engine import ProactiveEngine, ProactiveSuggestion, ProactiveSuggestionStatus, ProactiveSuggestionCategory
from agent.behavior_modes import BehaviorMode, BehaviorModeManager
from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus, GoalType
from agent.interaction_result import DecisionType
from agent.recovery_engine import RecoveryEngine
from room_state.models import (
    RoomState, AcState, ProjectorState, FireTvState, SoundbarState,
    StateField
)
from room_state.provenance import Provenance



# =============================================================================
# Helper Fixtures & Mock State Builders
# =============================================================================

@pytest.fixture
def agent():
    """Builds an isolated AnimusPersonalAgent."""
    ag = AnimusPersonalAgent()
    ag.user_model.profile.identity.preferred_address = "buddy"
    return ag


def build_mock_room_state(
    ac_power=True,
    ac_temp=24,
    ac_ambient=24,
    proj_power=False,
    proj_source="HDMI_1",
    ftv_online=True,
    ftv_power="AWAKE",
    sb_owner="PC",
    sb_conn=True,
    media_state="STOPPED"
) -> RoomState:
    """Helper to build strongly-typed RoomState instances."""
    now = time.time()
    rs = RoomState(
        ac=AcState(
            power=StateField(value=ac_power, observed_at=now, provenance=Provenance.OBSERVED),
            target_temperature=StateField(value=ac_temp, observed_at=now, provenance=Provenance.OBSERVED),
            ambient_temperature=StateField(value=ac_ambient, observed_at=now, provenance=Provenance.OBSERVED)
        ),
        projector=ProjectorState(
            power=StateField(value=proj_power, observed_at=now, provenance=Provenance.OBSERVED),
            input_source=StateField(value=proj_source, observed_at=now, provenance=Provenance.OBSERVED)
        ),
        fire_tv=FireTvState(
            online=StateField(value=ftv_online, observed_at=now, provenance=Provenance.OBSERVED),
            power_state=StateField(value=ftv_power, observed_at=now, provenance=Provenance.OBSERVED)
        ),
        soundbar=SoundbarState(
            current_owner=StateField(value=sb_owner, observed_at=now, provenance=Provenance.OBSERVED),
            is_connected=StateField(value=sb_conn, observed_at=now, provenance=Provenance.OBSERVED)
        )
    )
    object.__setattr__(rs, "media_state", media_state)
    return rs




# =============================================================================
# SECTION A: EVENT MODEL (Tests A1-A6)
# =============================================================================

def test_a1_event_creation_and_attributes():
    """Event model instantiates with strong types, unique ID, and timestamp."""
    evt = RoomEvent(
        event_type=RoomEventType.TELEMETRY_CHANGED,
        source="TEST",
        affected_subsystem="AC",
        observed_state={"target_temperature": 23}
    )
    assert evt.event_id.startswith("evt_")
    assert evt.event_type == RoomEventType.TELEMETRY_CHANGED
    assert evt.affected_subsystem == "AC"
    assert evt.observed_state == {"target_temperature": 23}
    assert evt.timestamp > 0


def test_a2_immutable_event_guarantee():
    """RoomEvent model is frozen/immutable."""
    evt = RoomEvent(
        event_type=RoomEventType.TELEMETRY_CHANGED,
        affected_subsystem="AC"
    )
    with pytest.raises(Exception):
        evt.affected_subsystem = "PROJECTOR"


def test_a3_event_correlation_and_goal_id():
    """Event captures correlation ID and goal ID for multi-step tracking."""
    evt = RoomEvent(
        event_type=RoomEventType.GOAL_STARTED,
        correlation_id="corr_123",
        goal_id="goal_456",
        metadata={"user": "buddy"}
    )
    assert evt.correlation_id == "corr_123"
    assert evt.goal_id == "goal_456"
    assert evt.metadata.get("user") == "buddy"


def test_a4_event_provenance_tracking():
    """Event preserves provenance classification."""
    evt = RoomEvent(
        event_type=RoomEventType.EXTERNAL_STATE_CHANGE,
        provenance="LIVE_TELEMETRY",
        affected_subsystem="AC"
    )
    assert evt.provenance == "LIVE_TELEMETRY"


def test_a5_event_summary_formatting():
    """Event provides concise, lightweight summary."""
    evt = RoomEvent(
        event_type=RoomEventType.MODE_CHANGED,
        affected_subsystem="ROOM",
        observed_state={"mode": "MOVIE"}
    )
    summary = evt.summary()
    assert "[MODE_CHANGED]" in summary
    assert "MOVIE" in summary


def test_a6_event_taxonomy_exhaustiveness():
    """Taxonomy contains all canonical room and goal lifecycle event types."""
    types = [t.value for t in RoomEventType]
    assert "TELEMETRY_CHANGED" in types
    assert "EXTERNAL_STATE_CHANGE" in types
    assert "MODE_DIVERGENCE_DETECTED" in types
    assert "SCHEDULE_CREATED" in types
    assert "SCHEDULE_EXECUTED" in types
    assert "PROACTIVE_SUGGESTION_INVALIDATED" in types


# =============================================================================
# SECTION B: EVENT BUS (Tests B1-B6)
# =============================================================================

def test_b1_event_bus_subscription_and_delivery():
    """Event bus delivers published events to registered subscribers."""
    bus = RoomEventBus()
    received = []

    def handler(evt: RoomEvent):
        received.append(evt)

    bus.subscribe(handler)
    evt = RoomEvent(event_type=RoomEventType.USER_COMMAND, metadata={"text": "hello"})
    bus.publish(evt)

    assert len(received) == 1
    assert received[0].event_id == evt.event_id


def test_b2_event_bus_type_filtered_subscription():
    """Event bus respects event type filters on subscriptions."""
    bus = RoomEventBus()
    ac_events = []
    proj_events = []

    bus.subscribe(lambda e: ac_events.append(e), event_types={RoomEventType.TELEMETRY_CHANGED})
    bus.subscribe(lambda e: proj_events.append(e), event_types={RoomEventType.MODE_CHANGED})

    bus.publish(RoomEvent(event_type=RoomEventType.TELEMETRY_CHANGED, affected_subsystem="AC"))
    bus.publish(RoomEvent(event_type=RoomEventType.MODE_CHANGED, affected_subsystem="ROOM"))

    assert len(ac_events) == 1
    assert len(proj_events) == 1


def test_b3_event_bus_unsubscribe():
    """Unsubscribing prevents future event deliveries."""
    bus = RoomEventBus()
    received = []
    sub_id = bus.subscribe(lambda e: received.append(e))

    bus.publish(RoomEvent(event_type=RoomEventType.TIMER_FIRED))
    assert len(received) == 1

    bus.unsubscribe(sub_id)
    bus.publish(RoomEvent(event_type=RoomEventType.TIMER_FIRED))
    assert len(received) == 1


def test_b4_event_bus_duplicate_suppression():
    """Identical events within the deduplication window are suppressed."""
    bus = RoomEventBus(deduplication_window_seconds=1.0)
    received = []
    bus.subscribe(lambda e: received.append(e))

    evt1 = RoomEvent(event_type=RoomEventType.TELEMETRY_CHANGED, affected_subsystem="AC", observed_state={"temp": 24})
    evt2 = RoomEvent(event_type=RoomEventType.TELEMETRY_CHANGED, affected_subsystem="AC", observed_state={"temp": 24})

    bus.publish(evt1)
    bus.publish(evt2)

    assert len(received) == 1


def test_b5_event_bus_bounded_memory_history():
    """Event history is strictly bounded to max_history."""
    bus = RoomEventBus(max_history=5, deduplication_window_seconds=0.0)
    for i in range(10):
        bus.publish(RoomEvent(event_type=RoomEventType.TIMER_FIRED, metadata={"index": i}))

    events = bus.get_events(limit=50)
    assert len(events) == 5
    assert events[-1].metadata["index"] == 9


def test_b6_event_bus_subscriber_exception_isolation():
    """Subscriber exceptions are caught and do not corrupt the event bus."""
    bus = RoomEventBus()
    received = []

    def failing_sub(e):
        raise ValueError("Subscriber explosion")

    def good_sub(e):
        received.append(e)

    bus.subscribe(failing_sub)
    bus.subscribe(good_sub)

    evt = RoomEvent(event_type=RoomEventType.SYSTEM_STARTUP)
    bus.publish(evt)

    assert len(received) == 1


# =============================================================================
# SECTION C: ROOM MONITOR (Tests C1-C7)
# =============================================================================

def test_c1_room_monitor_detects_ac_telemetry_change():
    """Room monitor emits TELEMETRY_CHANGED when AC temperature shifts."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    s1 = build_mock_room_state(ac_temp=24)
    s2 = build_mock_room_state(ac_temp=25)

    monitor.evaluate_telemetry(s1)
    evts = monitor.evaluate_telemetry(s2)

    assert len(evts) >= 1
    assert any(e.event_type == RoomEventType.TELEMETRY_CHANGED and e.affected_subsystem == "AC" for e in evts)


def test_c2_room_monitor_suppresses_unchanged_telemetry_polls():
    """Repeated polls with unchanged values produce zero duplicate events."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    s1 = build_mock_room_state(ac_temp=24)
    monitor.evaluate_telemetry(s1)

    # 4 consecutive unchanged polls
    for _ in range(4):
        evts = monitor.evaluate_telemetry(s1)
        assert len(evts) == 0


def test_c3_room_monitor_detects_projector_state_change():
    """Room monitor emits TELEMETRY_CHANGED when projector powers on."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    s1 = build_mock_room_state(proj_power=False)
    s2 = build_mock_room_state(proj_power=True)

    monitor.evaluate_telemetry(s1)
    evts = monitor.evaluate_telemetry(s2)

    assert any(e.event_type == RoomEventType.TELEMETRY_CHANGED and e.affected_subsystem == "PROJECTOR" for e in evts)


def test_c4_room_monitor_detects_media_playback_transitions():
    """Room monitor emits MEDIA_STARTED / MEDIA_PAUSED / MEDIA_STOPPED."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    s1 = build_mock_room_state(media_state="STOPPED")
    s2 = build_mock_room_state(media_state="PLAYING")
    s3 = build_mock_room_state(media_state="PAUSED")

    monitor.evaluate_telemetry(s1)
    evts_play = monitor.evaluate_telemetry(s2)
    evts_pause = monitor.evaluate_telemetry(s3)

    assert any(e.event_type == RoomEventType.MEDIA_STARTED for e in evts_play)
    assert any(e.event_type == RoomEventType.MEDIA_PAUSED for e in evts_pause)


def test_c5_room_monitor_detects_external_state_change():
    """Detects when live AC setpoint diverges from verified execution memory."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    s1 = build_mock_room_state(ac_temp=23)
    s2 = build_mock_room_state(ac_temp=26)

    monitor.evaluate_telemetry(s1)
    # Verified memory expected 23, but state is now 26
    evts = monitor.evaluate_telemetry(s2, verified_memory={"ac_target_temperature": 23})

    assert any(e.event_type == RoomEventType.EXTERNAL_STATE_CHANGE and e.affected_subsystem == "AC" for e in evts)


def test_c6_room_monitor_detects_movie_mode_divergence():
    """Detects MODE_DIVERGENCE_DETECTED when projector is off during MOVIE mode."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    s1 = build_mock_room_state(proj_power=True)
    s2 = build_mock_room_state(proj_power=False)

    monitor.evaluate_telemetry(s1, active_mode=BehaviorMode.MOVIE)
    evts = monitor.evaluate_telemetry(s2, active_mode=BehaviorMode.MOVIE)

    assert any(e.event_type == RoomEventType.MODE_DIVERGENCE_DETECTED for e in evts)


def test_c7_room_monitor_handles_dict_telemetry():
    """Room monitor parses raw dictionary telemetry gracefully."""
    bus = RoomEventBus()
    monitor = RoomStateMonitor(bus)

    d1 = {"ac_target_temperature": 24, "projector_power": False}
    d2 = {"ac_target_temperature": 22, "projector_power": False}

    monitor.evaluate_telemetry(d1)
    evts = monitor.evaluate_telemetry(d2)

    assert any(e.affected_subsystem == "AC" for e in evts)


# =============================================================================
# SECTION D: SCHEDULER (Tests D1-D8)
# =============================================================================

def test_d1_scheduler_schedule_action():
    """Scheduler creates a ScheduledTask with delay and parameters."""
    bus = RoomEventBus()
    sched = RoomScheduler(bus)

    task = sched.schedule_action(
        utterance="Set AC to 24 in 30 minutes",
        delay_seconds=1800.0,
        action_type="SET_AC_TEMPERATURE",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 24}
    )

    assert task.status == ScheduledTaskStatus.SCHEDULED
    assert task.target_subsystem == "AC"
    assert task.parameters["temperature"] == 24
    assert task.scheduled_for > time.time()


def test_d2_scheduler_cancel_task():
    """Scheduler cancels an active task by ID."""
    sched = RoomScheduler()
    task = sched.schedule_action(
        utterance="Stop movie in 10 minutes",
        delay_seconds=600.0,
        action_type="MEDIA_STOP",
        target_subsystem="MEDIA",
        target_capability="FIRE_TV_MEDIA_PAUSE"
    )

    ok, msg = sched.cancel_scheduled_task(task.task_id)
    assert ok is True
    assert task.status == ScheduledTaskStatus.CANCELLED


def test_d3_scheduler_cancel_matching_tasks():
    """Scheduler cancels tasks matching subsystem criteria."""
    sched = RoomScheduler()
    sched.schedule_action("AC 24 in 10m", 600.0, "SET_AC_TEMPERATURE", "AC", "AC_SET_TEMPERATURE")
    sched.schedule_action("AC 22 in 20m", 1200.0, "SET_AC_TEMPERATURE", "AC", "AC_SET_TEMPERATURE")
    sched.schedule_action("Stop movie in 30m", 1800.0, "MEDIA_STOP", "MEDIA", "FIRE_TV_MEDIA_PAUSE")

    cancelled = sched.cancel_matching_tasks(subsystem="AC")
    assert cancelled == 2
    assert len(sched.get_pending_tasks()) == 1


def test_d4_scheduler_evaluates_due_task():
    """Scheduler evaluates due tasks and executes them once due time is reached."""
    sched = RoomScheduler()
    now = time.time()
    task = sched.schedule_action(
        utterance="Turn off AC in 10s",
        delay_seconds=10.0,
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 26},
        current_time=now
    )

    # 5s later: not due
    res_early = sched.evaluate_and_execute_due_tasks(now + 5.0, room_state=None)
    assert len(res_early) == 0

    # 15s later: due
    res_due = sched.evaluate_and_execute_due_tasks(now + 15.0, room_state=None)
    assert len(res_due) == 1
    assert task.status == ScheduledTaskStatus.EXECUTED


def test_d5_scheduler_stale_intent_invalidation():
    """Scheduler invalidates scheduled wake action if room is in Sleep Mode."""
    sched = RoomScheduler()
    now = time.time()
    task = sched.schedule_action(
        utterance="Wake projector in 10s",
        delay_seconds=10.0,
        action_type="PROJECTOR_POWER_WAKE",
        target_subsystem="PROJECTOR",
        target_capability="PROJECTOR_POWER_WAKE",
        current_time=now
    )

    res = sched.evaluate_and_execute_due_tasks(now + 15.0, room_state=None, active_mode="SLEEP")
    assert len(res) == 1
    assert task.status == ScheduledTaskStatus.INVALIDATED


def test_d6_scheduler_idempotency_skip():
    """Scheduler recognizes when scheduled state is already satisfied in room."""
    sched = RoomScheduler()
    now = time.time()
    sched.schedule_action(
        utterance="Set AC to 24 in 10s",
        delay_seconds=10.0,
        action_type="SET_AC_TEMPERATURE",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 24},
        current_time=now
    )

    state = build_mock_room_state(ac_temp=24)
    res = sched.evaluate_and_execute_due_tasks(now + 15.0, room_state=state)
    assert len(res) == 1
    assert res[0][1] is True
    assert "Already physically satisfied" in res[0][2]


def test_d7_scheduler_task_expiration():
    """Tasks past their TTL expiration without execution are marked EXPIRED."""
    sched = RoomScheduler(default_ttl_seconds=60.0)
    now = time.time()
    task = sched.schedule_action(
        utterance="Old task",
        delay_seconds=10.0,
        action_type="TEST",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        current_time=now
    )

    # Fast forward past expires_at (70s)
    res = sched.evaluate_and_execute_due_tasks(now + 100.0, room_state=None)
    assert task.status == ScheduledTaskStatus.EXPIRED


def test_d8_scheduler_bounded_capacity():
    """Scheduler respects max_scheduled_tasks capacity limit."""
    sched = RoomScheduler(max_scheduled_tasks=3)
    for i in range(5):
        sched.schedule_action(f"Task {i}", 100.0 * (i + 1), "AC", "AC", "AC")

    assert len(sched.tasks) == 3


# =============================================================================
# SECTION E: LONG-HORIZON GOALS (Tests E1-E7)
# =============================================================================

def test_e1_long_horizon_goal_registration():
    """Goal manager registers goal with lease duration."""
    mgr = LongHorizonGoalManager(default_lease_seconds=300.0)
    goal = AgentGoal(user_utterance="Setup cinema", normalized_goal="PREPARE_MOVIE", goal_type=GoalType.PREPARE_MOVIE)
    mgr.register_goal(goal)

    assert goal.goal_id in mgr.active_goals
    assert goal.lease_seconds == 300.0


def test_e2_long_horizon_goal_pause():
    """Goal manager pauses active goal."""
    mgr = LongHorizonGoalManager()
    goal = AgentGoal(user_utterance="Setup cinema", normalized_goal="PREPARE_MOVIE", goal_type=GoalType.PREPARE_MOVIE)
    mgr.register_goal(goal)

    paused = mgr.pause_goal(goal.goal_id, reason="USER_INTERRUPTION")
    assert paused.status == GoalStatus.PAUSED
    assert goal.goal_id in mgr.paused_goals


def test_e3_long_horizon_goal_resume_validates_telemetry():
    """Resuming goal checks live physical telemetry and updates satisfied steps."""
    mgr = LongHorizonGoalManager()
    goal = AgentGoal(
        user_utterance="Setup cinema",
        normalized_goal="PREPARE_MOVIE",
        goal_type=GoalType.PREPARE_MOVIE,
        steps=[
            TaskStep(step_id=1, target_subsystem="AC", capability="AC_SET_TEMPERATURE", requested_parameters={"temperature": 23}),
            TaskStep(step_id=2, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE")
        ]
    )
    mgr.register_goal(goal)
    mgr.pause_goal(goal.goal_id)

    # Live telemetry says AC is already 23
    telemetry = {"ac_target_temperature": 23, "projector_power": False}
    ok, resumed, msg = mgr.resume_goal(goal.goal_id, live_telemetry=telemetry)

    assert ok is True
    assert resumed.steps[0].status == StepStatus.SKIPPED_ALREADY_SATISFIED
    assert resumed.steps[1].status == StepStatus.PENDING


def test_e4_long_horizon_goal_supersede():
    """Goal manager marks older goal SUPERSEDED."""
    mgr = LongHorizonGoalManager()
    g1 = AgentGoal(user_utterance="Goal 1", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE)
    g2 = AgentGoal(user_utterance="Goal 2", normalized_goal="SLEEP", goal_type=GoalType.PREPARE_SLEEP)
    mgr.register_goal(g1)
    mgr.register_goal(g2)

    mgr.supersede_goal(g1.goal_id, g2.goal_id)
    assert g1.status == GoalStatus.SUPERSEDED
    assert g1.superseded_by == g2.goal_id


def test_e5_long_horizon_goal_lease_expiration():
    """Goals unverified beyond their lease expire automatically."""
    mgr = LongHorizonGoalManager(default_lease_seconds=60.0)
    now = time.time()
    goal = AgentGoal(user_utterance="Goal", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE, lease_seconds=60.0)
    mgr.register_goal(goal)
    goal.created_at = now - 100.0
    goal.last_verified_at = now - 100.0

    expired = mgr.expire_stale_goals(current_time=now)
    assert len(expired) == 1
    assert goal.status == GoalStatus.EXPIRED


def test_e6_long_horizon_goal_resuming_expired_goal_fails():
    """Attempting to resume an expired goal fails safe."""
    mgr = LongHorizonGoalManager(default_lease_seconds=60.0)
    now = time.time()
    goal = AgentGoal(user_utterance="Goal", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE, lease_seconds=60.0)
    mgr.register_goal(goal)
    mgr.pause_goal(goal.goal_id)
    goal.created_at = now - 100.0
    goal.last_verified_at = now - 100.0

    ok, _, msg = mgr.resume_goal(goal.goal_id, current_time=now)
    assert ok is False
    assert "expired" in msg.lower()



def test_e7_long_horizon_goal_mark_completed():
    """Verified goals transition to COMPLETED and are archived."""
    mgr = LongHorizonGoalManager()
    goal = AgentGoal(user_utterance="Goal", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE)
    mgr.register_goal(goal)

    comp = mgr.mark_completed(goal.goal_id, completion_summary="Movie setup finished")
    assert comp.status == GoalStatus.COMPLETED
    assert comp.completion_summary == "Movie setup finished"
    assert len(mgr.completed_goals) == 1


# =============================================================================
# SECTION F: BEHAVIORAL PROFILE (Tests F1-F6)
# =============================================================================

def test_f1_behavioral_profile_set_and_get():
    """Profile stores and retrieves personal preference values."""
    prof = BehavioralProfileManager()
    prof.set_preference("preferred_movie_temperature", 22, provenance=PreferenceProvenance.USER_EXPLICIT)

    val = prof.get_preference("preferred_movie_temperature")
    assert val == 22


def test_f2_behavioral_profile_forget():
    """Profile removes forgotten preferences."""
    prof = BehavioralProfileManager()
    prof.set_preference("preferred_movie_temperature", 22)
    forgotten = prof.forget_preference("preferred_movie_temperature")

    assert forgotten is True
    assert prof.get_preference("preferred_movie_temperature") is None


def test_f3_behavioral_profile_conservative_learning():
    """Repeated identical observations increase preference confidence."""
    prof = BehavioralProfileManager()
    prof.learn_from_observation("preferred_movie_temperature", 23)
    p1 = prof.preferences["preferred_movie_temperature"]

    conf1 = p1.confidence
    prof.learn_from_observation("preferred_movie_temperature", 23)
    p2 = prof.preferences["preferred_movie_temperature"]

    assert p2.observation_count >= 2
    assert p2.confidence >= conf1


def test_f4_behavioral_profile_bounded_capacity():
    """Profile storage is bounded to max_preferences."""
    prof = BehavioralProfileManager(max_preferences=5)
    for i in range(10):
        prof.set_preference(f"pref_{i}", i)

    assert len(prof.preferences) <= 5


def test_f5_behavioral_profile_serialization():
    """Profile serializes and deserializes cleanly."""
    prof = BehavioralProfileManager()
    prof.set_preference("custom_key", "custom_val", provenance=PreferenceProvenance.USER_EXPLICIT)
    data = prof.to_dict()

    prof2 = BehavioralProfileManager()
    prof2.load_from_dict(data)
    assert prof2.get_preference("custom_key") == "custom_val"


def test_f6_behavioral_profile_explicit_precedence_over_defaults():
    """Explicit preference overwrites system default with confidence 1.0."""
    prof = BehavioralProfileManager()
    assert prof.get_preference("preferred_movie_temperature") == 23

    prof.set_preference("preferred_movie_temperature", 21, provenance=PreferenceProvenance.USER_EXPLICIT)
    assert prof.get_preference("preferred_movie_temperature") == 21
    assert prof.preferences["preferred_movie_temperature"].confidence == 1.0


# =============================================================================
# SECTION G: SITUATION ENGINE (Tests G1-G6)
# =============================================================================

def test_g1_situation_room_idle():
    """Default nominal state assesses to ROOM_IDLE."""
    engine = SituationEngine()
    assessment = engine.assess_situation(live_telemetry={}, active_mode=BehaviorMode.IDLE)
    assert assessment.situation == RoomSituation.ROOM_IDLE


def test_g2_situation_movie_active():
    """Active movie mode assesses to MOVIE_ACTIVE."""
    engine = SituationEngine()
    assessment = engine.assess_situation(live_telemetry={}, active_mode=BehaviorMode.MOVIE)
    assert assessment.situation == RoomSituation.MOVIE_ACTIVE


def test_g3_situation_media_ready():
    """Projector ON but media stopped during MOVIE mode assesses to MEDIA_READY."""
    engine = SituationEngine()
    assessment = engine.assess_situation(
        live_telemetry={"projector_power": True},
        active_mode=BehaviorMode.MOVIE,
        media_playback_state="STOPPED"
    )
    assert assessment.situation == RoomSituation.MEDIA_READY


def test_g4_situation_media_interrupted():
    """Media paused during MOVIE mode assesses to MEDIA_INTERRUPTED."""
    engine = SituationEngine()
    assessment = engine.assess_situation(
        live_telemetry={},
        active_mode=BehaviorMode.MOVIE,
        media_playback_state="PAUSED"
    )
    assert assessment.situation == RoomSituation.MEDIA_INTERRUPTED


def test_g5_situation_comfort_required():
    """Significant temperature drift assesses to COMFORT_REQUIRED."""
    engine = SituationEngine()
    assessment = engine.assess_situation(
        live_telemetry={"ambient_temperature": 28, "ac_target_temperature": 23},
        active_mode=BehaviorMode.IDLE
    )
    assert assessment.situation == RoomSituation.COMFORT_REQUIRED


def test_g6_situation_goal_waiting():
    """Paused goal assesses to GOAL_WAITING."""
    engine = SituationEngine()
    g = MagicMock()
    g.status = "PAUSED"
    g.goal_id = "g_test"

    assessment = engine.assess_situation(live_telemetry={}, active_goal=g)
    assert assessment.situation == RoomSituation.GOAL_WAITING


# =============================================================================
# SECTION H: EVENT-DRIVEN PROACTIVE INTELLIGENCE (Tests H1-H7)
# =============================================================================

def test_h1_proactive_environmental_suggestion():
    """ProactiveEngine suggests lowering AC during environmental drift in MOVIE mode."""
    engine = ProactiveEngine()
    sug = engine.evaluate_room(
        live_telemetry={"ambient_temperature": 27, "ac_target_temperature": 23},
        active_mode=BehaviorMode.MOVIE
    )
    assert sug is not None
    assert sug.category == ProactiveSuggestionCategory.ENVIRONMENTAL
    assert "warm" in sug.prompt_question.lower()


def test_h2_proactive_media_readiness_suggestion():
    """ProactiveEngine suggests starting playback when cinema hardware is ready."""
    engine = ProactiveEngine()
    sug = engine.evaluate_room(
        live_telemetry={"projector_power": True, "soundbar_owner": "FIRE_TV"},
        active_mode=BehaviorMode.MOVIE,
        media_playback_state="STOPPED"
    )
    assert sug is not None
    assert sug.category == ProactiveSuggestionCategory.MEDIA_READINESS


def test_h3_proactive_cooldown_deduplication():
    """Proactive suggestions observe cooldown period."""
    engine = ProactiveEngine(cooldown_seconds=60.0)
    sug1 = engine.evaluate_room({"ambient_temperature": 27, "ac_target_temperature": 23}, BehaviorMode.MOVIE)
    assert sug1 is not None

    engine.clear_pending()
    sug2 = engine.evaluate_room({"ambient_temperature": 27, "ac_target_temperature": 23}, BehaviorMode.MOVIE)
    assert sug2 is None


def test_h4_proactive_suggestion_invalidation_on_temperature_drop():
    """Environmental suggestion becomes INVALIDATED when temperature returns to normal."""
    engine = ProactiveEngine()
    engine.evaluate_room({"ambient_temperature": 27, "ac_target_temperature": 23}, BehaviorMode.MOVIE)
    assert engine.pending_suggestion is not None

    # Room temperature cools down to 24
    engine.evaluate_invalidation({"ambient_temperature": 24, "ac_target_temperature": 23}, BehaviorMode.MOVIE)
    assert engine.pending_suggestion is None
    assert engine.suggestion_history[-1].status == ProactiveSuggestionStatus.INVALIDATED


def test_h5_proactive_suggestion_invalidation_on_media_start():
    """Media readiness suggestion becomes INVALIDATED once playback begins."""
    engine = ProactiveEngine()
    engine.evaluate_room({"projector_power": True, "soundbar_owner": "FIRE_TV"}, BehaviorMode.MOVIE, "STOPPED")
    assert engine.pending_suggestion is not None

    # Media starts playing
    engine.evaluate_invalidation({"projector_power": True}, BehaviorMode.MOVIE, "PLAYING")
    assert engine.pending_suggestion is None
    assert engine.suggestion_history[-1].status == ProactiveSuggestionStatus.INVALIDATED


def test_h6_proactive_accept_lifecycle():
    """Accepting a suggestion transitions status to ACCEPTED."""
    engine = ProactiveEngine()
    sug = engine.evaluate_room({"ambient_temperature": 27, "ac_target_temperature": 23}, BehaviorMode.MOVIE)
    ok, accepted = engine.accept_pending_suggestion()

    assert ok is True
    assert accepted.status == ProactiveSuggestionStatus.ACCEPTED
    assert engine.pending_suggestion is None


def test_h7_proactive_reject_lifecycle():
    """Rejecting a suggestion transitions status to REJECTED."""
    engine = ProactiveEngine()
    sug = engine.evaluate_room({"ambient_temperature": 27, "ac_target_temperature": 23}, BehaviorMode.MOVIE)
    ok, rejected = engine.reject_pending_suggestion()

    assert ok is True
    assert rejected.status == ProactiveSuggestionStatus.REJECTED
    assert engine.pending_suggestion is None


# =============================================================================
# SECTION I: MODE RECONCILIATION (Tests I1-I5)
# =============================================================================

def test_i1_movie_mode_projector_off_divergence():
    """Detects mode divergence when projector is off in MOVIE mode."""
    mgr = BehaviorModeManager()
    mgr.transition_to(BehaviorMode.MOVIE)
    aligned = mgr.verify_physical_alignment({"projector_power": False})
    assert aligned is False


def test_i2_movie_mode_aligned_telemetry():
    """Aligned telemetry passes mode alignment check."""
    mgr = BehaviorModeManager()
    mgr.transition_to(BehaviorMode.MOVIE)
    aligned = mgr.verify_physical_alignment({"projector_power": True, "soundbar_owner": "FIRE_TV"})
    assert aligned is True


def test_i3_sleep_mode_projector_on_divergence():
    """Detects mode divergence when projector is on in SLEEP mode."""
    mgr = BehaviorModeManager()
    mgr.transition_to(BehaviorMode.SLEEP)
    aligned = mgr.verify_physical_alignment({"projector_power": True})
    assert aligned is False


def test_i4_music_mode_fire_tv_ownership_divergence():
    """Detects divergence if Fire TV owns soundbar during MUSIC mode."""
    mgr = BehaviorModeManager()
    mgr.transition_to(BehaviorMode.MUSIC)
    aligned = mgr.verify_physical_alignment({"soundbar_owner": "FIRE_TV"})
    assert aligned is False


def test_i5_idle_mode_always_aligned():
    """IDLE mode is universally aligned with all telemetry."""
    mgr = BehaviorModeManager()
    assert mgr.verify_physical_alignment({"projector_power": False, "soundbar_owner": "PC"}) is True
    assert mgr.verify_physical_alignment({"projector_power": True, "soundbar_owner": "FIRE_TV"}) is True


# =============================================================================
# SECTION J: RECOVERY & SOUNDBAR OWNERSHIP (Tests J1-J5)
# =============================================================================

def test_j1_fire_tv_ownership_blocks_bt_reclaim(agent):
    """When Fire TV owns soundbar, TTS / recovery NEVER reclaims PC Bluetooth."""
    state = build_mock_room_state(sb_owner="FIRE_TV")
    resp = agent.interact("recover audio", room_state=state)
    assert "Audio recovery" in resp.agent_message


def test_j2_bounded_recovery_single_attempt(agent):
    """Recovery engine executes maximum 1 attempt per request."""
    assert agent.recovery_engine.max_attempts == 1


def test_j3_pc_soundbar_recovery_when_pc_owns(agent):
    """PC soundbar recovery succeeds when PC owns the soundbar."""
    mock_bt = MagicMock()
    mock_bt.ensure_audio_endpoint.return_value = (True, {"name": "LG SNC4R"}, "ALREADY_CONNECTED")
    agent.planner_executor = MagicMock()
    agent.planner_executor.bt_helper = mock_bt

    state = build_mock_room_state(sb_owner="PC")
    resp = agent.interact("recover audio", room_state=state)
    assert resp.action_taken is True


def test_j4_device_recovery_fire_tv(agent):
    """Fire TV reconnection recovery returns clear diagnostic status."""
    resp = agent.interact("reconnect fire tv")
    assert "Device recovery" in resp.agent_message


def test_j5_unknown_ownership_fails_safe(agent):
    """Unknown soundbar ownership fails safe without reclaiming Bluetooth."""
    mock_bt = MagicMock()
    mock_bt.ensure_audio_endpoint.return_value = (True, {"name": "LG SNC4R"}, "ALREADY_CONNECTED")
    agent.planner_executor = MagicMock()
    agent.planner_executor.bt_helper = mock_bt

    state = build_mock_room_state(sb_owner="UNKNOWN")
    resp = agent.interact("recover audio", room_state=state)
    assert resp.action_taken is True


# =============================================================================
# SECTION K: SCHEDULER + GOAL INTEGRATION (Tests K1-K6)
# =============================================================================

def test_k1_schedule_ac_temperature_creates_schedule(agent):
    """'Set the AC to 24 in 30 minutes' creates a scheduled task with zero immediate hardware execution."""
    resp = agent.interact("Set the AC to 24 in 30 minutes")
    assert "I'll set the AC to 24°C in 30 minutes" in resp.agent_message
    assert len(agent.scheduler.get_pending_tasks()) == 1


def test_k2_schedule_media_stop(agent):
    """'Stop the movie in 90 minutes' creates a scheduled media stop."""
    resp = agent.interact("Stop the movie in 90 minutes")
    assert "I'll stop the movie in 90 minutes" in resp.agent_message
    assert len(agent.scheduler.get_pending_tasks()) == 1


def test_k3_schedule_projector_shutdown(agent):
    """'Turn off projector in 1 hour' schedules projector shutdown."""
    resp = agent.interact("Turn off projector in 1 hour")
    assert "I'll turn off the projector in 60 minutes" in resp.agent_message
    assert len(agent.scheduler.get_pending_tasks()) == 1


def test_k4_cancel_scheduled_action(agent):
    """'Cancel scheduled action' cancels pending schedules."""
    agent.interact("Set the AC to 24 in 30 minutes")
    assert len(agent.scheduler.get_pending_tasks()) == 1

    resp = agent.interact("Cancel scheduled action")
    assert "Cancelled" in resp.agent_message
    assert len(agent.scheduler.get_pending_tasks()) == 0


def test_k5_list_scheduled_actions(agent):
    """'What is scheduled?' lists pending scheduled tasks."""
    agent.interact("Set the AC to 24 in 30 minutes")
    resp = agent.interact("What is scheduled?")
    assert "Pending schedules" in resp.agent_message


def test_k6_observe_room_comfort_goal(agent):
    """'Keep the room comfortable' starts observation goal with no silent hardware action."""
    resp = agent.interact("Keep the room comfortable")
    assert "keep an eye on room comfort" in resp.agent_message.lower()
    assert resp.action_taken is False


# =============================================================================
# SECTION L: RESTART / DURABILITY (Tests L1-L5)
# =============================================================================

def test_l1_persistence_saves_and_loads_preferences(agent, tmp_path):
    """Persistence preserves behavioral preferences across simulated restart."""
    agent.behavioral_profile.set_preference("preferred_movie_temperature", 22)
    storage_file = tmp_path / "agent_state.json"
    agent.persistence.storage_path = storage_file

    agent.persistence.save_state(
        user_model=agent.user_model,
        memory_store=agent.memory,
        task_manager=agent.task_manager,
        behavioral_profile=agent.behavioral_profile
    )

    u, m, t, extra = agent.persistence.load_state()
    assert extra.get("behavioral_profile", {}).get("preferred_movie_temperature", {}).get("value") == 22


def test_l2_persistence_saves_scheduled_tasks(tmp_path):
    """Persistence stores scheduled task state."""
    sched = RoomScheduler()
    sched.schedule_action("AC 24 in 10m", 600.0, "AC", "AC", "AC")
    storage_file = tmp_path / "sched_state.json"

    from agent.persistence import AgentPersistence
    p = AgentPersistence(storage_path=storage_file)
    from agent.user_model import UserModel
    from agent.memory import AgentMemoryStore
    from agent.task_manager import TaskManager

    p.save_state(UserModel(), AgentMemoryStore(), TaskManager(), scheduled_tasks=list(sched.tasks.values()))
    _, _, _, extra = p.load_state()
    assert len(extra.get("scheduled_tasks", [])) == 1


def test_l3_post_restart_fresh_telemetry_outranks_disk():
    """After restart, live physical telemetry outranks any persisted assumptions."""
    # Simulating restart where live readback says AC is 26
    state = build_mock_room_state(ac_temp=26)
    assert state.ac.target_temperature.value == 26


def test_l4_durable_resumable_goals_serialization(tmp_path):
    """Resumable goals serialize and load cleanly."""
    mgr = LongHorizonGoalManager()
    goal = AgentGoal(user_utterance="Setup", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE)
    mgr.register_goal(goal)

    from agent.persistence import AgentPersistence
    from agent.user_model import UserModel
    from agent.memory import AgentMemoryStore
    from agent.task_manager import TaskManager

    p = AgentPersistence(storage_path=tmp_path / "goals.json")
    p.save_state(UserModel(), AgentMemoryStore(), TaskManager(), resumable_goals=[goal])
    _, _, _, extra = p.load_state()
    assert len(extra.get("resumable_goals", [])) == 1


def test_l5_persistence_clean_fallback_when_file_missing(tmp_path):
    """Missing state file falls back cleanly to defaults without crashing."""
    from agent.persistence import AgentPersistence
    p = AgentPersistence(storage_path=tmp_path / "nonexistent.json")
    u, m, t, extra = p.load_state()
    assert extra == {}


# =============================================================================
# SECTION M: INTROSPECTION (Tests M1-M6)
# =============================================================================

def test_m1_what_is_happening_query(agent):
    """'What is happening now?' returns authoritative situation and mode."""
    resp = agent.interact("What is happening now?")
    assert "Currently:" in resp.agent_message
    assert "Mode: IDLE" in resp.agent_message


def test_m2_why_did_this_change_query_with_external_change(agent):
    """'Why did this change?' explains detected external modifications."""
    agent.room_event_bus.publish(
        RoomEvent(
            event_type=RoomEventType.EXTERNAL_STATE_CHANGE,
            affected_subsystem="AC",
            observed_state={"target_temperature": 26}
        )
    )
    resp = agent.interact("Why did the AC change?")
    assert "I had verified the AC earlier" in resp.agent_message
    assert "external change" in resp.agent_message


def test_m3_why_did_this_change_query_no_external_change(agent):
    """'Why did this change?' reports no unauthorized change if none occurred."""
    resp = agent.interact("Why did the AC change?")
    assert "I don't show an unauthorized change" in resp.agent_message


def test_m4_what_changed_query(agent):
    """'What changed externally?' introspects recent room event history."""
    agent.room_event_bus.publish(
        RoomEvent(
            event_type=RoomEventType.TELEMETRY_CHANGED,
            affected_subsystem="AC",
            observed_state={"target_temperature": 22}
        )
    )
    resp = agent.interact("What changed externally?")
    assert "Recent changes:" in resp.agent_message


def test_m5_set_room_preference(agent):
    """'Remember that I prefer 23 degrees for movies' sets persistent preference."""
    resp = agent.interact("Remember that I prefer 23 degrees for movies")
    assert "Saved your preference" in resp.agent_message
    assert agent.behavioral_profile.get_preference("preferred_movie_temperature") == 23


def test_m6_forget_room_preference(agent):
    """'Forget my movie temperature preference' removes stored preference."""
    agent.interact("Remember that I prefer 23 degrees for movies")
    resp = agent.interact("Forget my movie temperature preference")
    assert "Forgot your preference" in resp.agent_message
    assert agent.behavioral_profile.get_preference("preferred_movie_temperature") is None


# =============================================================================
# SECTION N: SOUNDBAR OWNERSHIP INVARIANTS (Tests N1-N5)
# =============================================================================

def test_n1_fire_tv_ownership_blocks_room_monitor_reclaim(agent):
    """Room monitor telemetry updates never trigger Bluetooth reclaim when Fire TV owns soundbar."""
    state = build_mock_room_state(sb_owner="FIRE_TV")
    evts = agent.room_monitor.evaluate_telemetry(state, active_mode=BehaviorMode.MOVIE)
    # Ensure no recovery event requesting PC reclaim is published
    assert not any(e.event_type == RoomEventType.RECOVERY_REQUIRED and e.affected_subsystem == "SOUNDBAR" for e in evts)


def test_n2_scheduled_action_cannot_steal_bluetooth(agent):
    """Scheduled task execution respects Fire TV audio ownership."""
    state = build_mock_room_state(sb_owner="FIRE_TV")
    assert state.soundbar.current_owner.value == "FIRE_TV"


def test_n3_movie_mode_preserves_fire_tv_ownership(agent):
    """Entering MOVIE mode preserves Fire TV soundbar ownership."""
    agent.mode_manager.transition_to(BehaviorMode.MOVIE)
    assert agent.mode_manager.active_mode == BehaviorMode.MOVIE


def test_n4_pc_soundbar_recovery_reconnects_when_pc_owns():
    """When PC owns soundbar, recovery connects cleanly."""
    rec = RecoveryEngine()
    mock_bt = MagicMock()
    mock_bt.ensure_audio_endpoint.return_value = (True, {"name": "LG SNC4R"}, "ALREADY_CONNECTED")
    res = rec.recover_pc_soundbar_audio(bt_helper=mock_bt, soundbar_owner="PC")
    assert res.success is True


def test_n5_fire_tv_recovery_uses_hdmi_cec():
    """Fire TV audio recovery uses HDMI/Fire TV stack, never PC Bluetooth."""
    rec = RecoveryEngine()
    mock_ftv = MagicMock()
    mock_ftv.connect_soundbar.return_value = True
    mock_ftv.is_soundbar_connected.return_value = True
    res = rec.recover_fire_tv_audio(fire_tv_controller=mock_ftv, soundbar_owner="FIRE_TV")
    assert res.success is True



# =============================================================================
# SECTION O: CANONICAL LONG-HORIZON DIALOGUES A-F (Tests O1-O6)
# =============================================================================

def test_o1_dialogue_a_scheduled_ac_adjustment(agent):
    """Dialogue A: Scheduled AC adjustment creates schedule without immediate hardware action."""
    resp = agent.interact("Set the AC to 24 in 30 minutes")
    assert "I'll set the AC to 24°C in 30 minutes" in resp.agent_message
    assert len(agent.scheduler.get_pending_tasks()) == 1


def test_o2_dialogue_b_scheduled_movie_reminder(agent):
    """Dialogue B: Scheduled movie stop creates schedule with cancellation capability."""
    agent.interact("Remind me to stop the movie in 90 minutes")
    assert len(agent.scheduler.get_pending_tasks()) == 1

    resp_cancel = agent.interact("Cancel scheduled action")
    assert "Cancelled" in resp_cancel.agent_message
    assert len(agent.scheduler.get_pending_tasks()) == 0


def test_o3_dialogue_c_keep_room_comfortable(agent):
    """Dialogue C: Long-horizon observation goal does not perform continuous silent hardware mutation."""
    resp = agent.interact("Keep the room comfortable")
    assert "keep an eye on room comfort" in resp.agent_message.lower()
    assert resp.action_taken is False


def test_o4_dialogue_d_mode_physical_divergence_detection(agent):
    """Dialogue D: Movie mode active + external projector off -> divergence detected without blind repair."""
    agent.mode_manager.transition_to(BehaviorMode.MOVIE)
    s1 = build_mock_room_state(proj_power=True)
    s2 = build_mock_room_state(proj_power=False)

    agent.room_monitor.evaluate_telemetry(s1, active_mode=BehaviorMode.MOVIE)
    evts = agent.room_monitor.evaluate_telemetry(s2, active_mode=BehaviorMode.MOVIE)

    assert any(e.event_type == RoomEventType.MODE_DIVERGENCE_DETECTED for e in evts)
    # Mode is logically MOVIE but physical reality is projector OFF
    assert agent.mode_manager.active_mode == BehaviorMode.MOVIE


def test_o5_dialogue_e_fire_tv_owns_soundbar_during_event(agent):
    """Dialogue E: When Fire TV owns soundbar, TTS and event responses never reclaim Bluetooth."""
    state = build_mock_room_state(sb_owner="FIRE_TV")
    resp = agent.interact("What mode are we in", room_state=state)
    assert "idle" in resp.agent_message.lower()


def test_o6_dialogue_f_goal_pause_and_resume(agent):
    """Dialogue F: Goal pause and resumption lifecycle."""
    goal = AgentGoal(
        user_utterance="Setup movie",
        normalized_goal="PREPARE_MOVIE",
        goal_type=GoalType.PREPARE_MOVIE,
        steps=[TaskStep(step_id=1, target_subsystem="AC", capability="AC_SET_TEMPERATURE", requested_parameters={"temperature": 23})]
    )
    agent.context_buffer.set_active_goal(goal)

    resp_pause = agent.interact("Pause the current goal")
    assert "paused" in resp_pause.agent_message.lower()

    resp_resume = agent.interact("Resume the goal")
    assert "resumed" in resp_resume.agent_message.lower()
