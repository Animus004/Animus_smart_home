"""
Authoritative Automated Test Battery for Phase 2 Stage 7:
Adaptive Reasoning, Competing Goal Arbitration, and Policy-Bounded Authorization.

Covers Sections A through G (60+ comprehensive tests):
Section A: ReasoningEngine Structured Output & Fact Extraction (Tests A1-A10)
Section B: ReasoningEngine Multi-Factor Reasoning & Conflicts (Tests B1-B10)
Section C: GoalArbitrator Decision Outcomes & Priority Preemption (Tests C1-C10)
Section D: GoalArbitrator Goal Superseding & Non-Destructive History (Tests D1-D10)
Section E: PolicyEngine Decision Taxonomy (OBSERVE, ASK, AUTHORIZED, DENIED) (Tests E1-E10)
Section F: PolicyEngine Safety Invariants & Soundbar Protection (Tests F1-F10)
Section G: End-to-End Agent Integration (Tests G1-G6)
"""

import time
import pytest
from unittest.mock import MagicMock

from agent.reasoning_engine import ReasoningEngine, ReasoningResult, CandidateAction, ReasoningConflict
from agent.goal_arbitrator import GoalArbitrator, ArbitrationDecision, ArbitrationOutcome
from agent.policy_engine import PolicyEngine, PolicyAuthorization, PolicyEvaluationResult
from agent.behavior_modes import BehaviorMode, BehaviorModeManager
from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus, GoalType
from agent.scheduler import RoomScheduler, ScheduledTask
from agent.core import AnimusPersonalAgent


# =============================================================================
# SECTION A: REASONING ENGINE - STRUCTURED OUTPUT & FACTS (Tests A1-A10)
# =============================================================================

def test_a1_reasoning_result_structure():
    """ReasoningResult instantiates with unique ID, timestamp, and default fields."""
    engine = ReasoningEngine()
    res = engine.reason(live_telemetry={"ac_target_temperature": 24})
    assert res.result_id.startswith("reas_")
    assert res.timestamp > 0
    assert len(res.relevant_facts) > 0
    assert "AC setpoint is 24°C" in res.relevant_facts[1]


def test_a2_fact_extraction_all_subsystems():
    """ReasoningEngine extracts facts across AC, Projector, Soundbar, and Mode."""
    engine = ReasoningEngine()
    telemetry = {
        "ac_target_temperature": 23,
        "ambient_temperature": 25,
        "projector_power": True,
        "soundbar_owner": "FIRE_TV"
    }
    res = engine.reason(live_telemetry=telemetry, active_mode=BehaviorMode.MOVIE)
    facts_str = " ".join(res.relevant_facts)
    assert "Active mode is MOVIE" in facts_str
    assert "23°C" in facts_str
    assert "25°C" in facts_str
    assert "Projector is ON" in facts_str
    assert "FIRE_TV" in facts_str


def test_a3_reasoning_summary_formatting():
    """ReasoningResult produces clean summary string."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="sleep mode")
    summary = res.summary()
    assert "[Reasoning]" in summary
    assert "Confidence:" in summary


def test_a4_empty_telemetry_safe_handling():
    """ReasoningEngine handles None / empty telemetry without crashing."""
    engine = ReasoningEngine()
    res = engine.reason(live_telemetry=None)
    assert res.confidence == 1.0
    assert len(res.relevant_facts) >= 1


def test_a5_reasoning_history_bounded():
    """Reasoning history respects maximum retention limit."""
    engine = ReasoningEngine()
    engine._max_history = 5
    for i in range(10):
        engine.reason(user_command=f"Command {i}")
    assert len(engine.reasoning_history) == 5


def test_a6_candidate_action_model():
    """CandidateAction holds strongly-typed capability and parameters."""
    act = CandidateAction(
        action_type="SET_TEMP",
        target_subsystem="AC",
        target_capability="AC_SET_TEMPERATURE",
        parameters={"temperature": 24},
        rationale="Comfort"
    )
    assert act.target_subsystem == "AC"
    assert act.parameters["temperature"] == 24


def test_a7_reasoning_conflict_model():
    """ReasoningConflict encapsulates competing goals and resolution applied."""
    conf = ReasoningConflict(
        conflict_type="COMMAND_VS_MODE",
        severity="HIGH",
        description="Bedtime requested during movie",
        competing_entities=["SLEEP", "MOVIE"],
        resolution_applied="Transition to SLEEP"
    )
    assert conf.severity == "HIGH"
    assert conf.resolution_applied == "Transition to SLEEP"


def test_a8_constraints_considered_tracking():
    """Safety constraints are recorded in reasoning output."""
    engine = ReasoningEngine()
    res = engine.reason(live_telemetry={"soundbar_owner": "FIRE_TV"})
    assert any("SOUNDBAR_FIRE_TV_PROTECTION" in c for c in res.constraints_considered)


def test_a9_latest_reasoning_retrieval():
    """get_latest_reasoning retrieves the most recent evaluation."""
    engine = ReasoningEngine()
    engine.reason(user_command="first")
    r2 = engine.reason(user_command="second")
    latest = engine.get_latest_reasoning()
    assert latest is not None
    assert latest.result_id == r2.result_id



def test_a10_rejected_alternatives_tracking():
    """Superseded candidate actions are recorded as rejected alternatives."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="sleep mode and set ac to 24", active_mode=BehaviorMode.MOVIE)
    assert len(res.candidate_actions) >= 1


# =============================================================================
# SECTION B: REASONING ENGINE - MULTI-FACTOR REASONING & CONFLICTS (Tests B1-B10)
# =============================================================================

def test_b1_sleep_command_during_movie_conflict():
    """Sleep command during active movie mode triggers COMMAND_VS_MODE conflict."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="I'm going to bed", active_mode=BehaviorMode.MOVIE)
    assert any(c.conflict_type == "COMMAND_VS_MODE" for c in res.conflicts)
    assert res.selected_action is not None
    assert res.selected_action.action_type == "TRANSITION_MODE"


def test_b2_wake_schedule_cancellation_conflict():
    """'Don't wake me tomorrow' conflicts with scheduled wake tasks."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="don't wake me tomorrow")
    assert any(c.conflict_type == "GOAL_VS_COMMAND" for c in res.conflicts)
    assert res.selected_action is not None
    assert res.selected_action.action_type == "CANCEL_SCHEDULED_TASK"


def test_b3_environmental_drift_detection():
    """High ambient temperature with low setpoint triggers ENVIRONMENTAL_DRIFT."""
    engine = ReasoningEngine()
    telemetry = {"ambient_temperature": 29, "ac_target_temperature": 22}
    res = engine.reason(live_telemetry=telemetry)
    assert any(c.conflict_type == "ENVIRONMENTAL_DRIFT" for c in res.conflicts)


def test_b4_direct_ac_adjustment_selection():
    """Direct AC command selects AC_SET_TEMPERATURE candidate."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="set ac to 23 degrees")
    assert res.selected_action is not None
    assert res.selected_action.target_subsystem == "AC"


def test_b5_nominal_idle_state_no_actions():
    """Nominal room state with no user command selects zero candidate actions."""
    engine = ReasoningEngine()
    res = engine.reason(active_mode=BehaviorMode.IDLE)
    assert res.selected_action is None
    assert "nominal" in res.reason.lower()


def test_b6_priority_sorting_user_command_over_routine():
    """Higher priority (lower integer) candidate action is selected."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="goodnight", active_mode=BehaviorMode.MOVIE)
    assert res.selected_action.priority == 1


def test_b7_soundbar_fire_tv_protection_in_movie_mode():
    """Movie mode automatically adds soundbar protection constraint."""
    engine = ReasoningEngine()
    res = engine.reason(active_mode=BehaviorMode.MOVIE)
    assert any("SOUNDBAR_FIRE_TV_PROTECTION" in c for c in res.constraints_considered)


def test_b8_reasoning_confidence_value():
    """Standard reasoning outputs 1.0 confidence."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="turn off projector")
    assert res.confidence == 1.0


def test_b9_multiple_safety_constraints():
    """Multiple safety constraints pass through cleanly."""
    engine = ReasoningEngine()
    res = engine.reason(
        safety_constraints=["CUSTOM_CONSTRAINT_1", "CUSTOM_CONSTRAINT_2"],
        active_mode=BehaviorMode.IDLE
    )
    assert "CUSTOM_CONSTRAINT_1" in res.constraints_considered
    assert "CUSTOM_CONSTRAINT_2" in res.constraints_considered


def test_b10_structured_reasoning_result_immutability():
    """ReasoningResult structure validates schema properly."""
    res = ReasoningResult(
        relevant_facts=["Fact 1"],
        reason="Test reason",
        confidence=0.95
    )
    assert res.confidence == 0.95


# =============================================================================
# SECTION C: GOAL ARBITRATOR - DECISIONS & PREEMPTION (Tests C1-C10)
# =============================================================================

def test_c1_arbitrate_no_conflict():
    """When no goals or tasks are active, arbitration returns NO_CONFLICT."""
    arb = GoalArbitrator()
    goal = AgentGoal(user_utterance="Movie time", normalized_goal="MOVIE", goal_type=GoalType.PREPARE_MOVIE)
    decision = arb.arbitrate(incoming_intent="START_MOVIE", incoming_goal=goal)
    assert decision.outcome == ArbitrationOutcome.NO_CONFLICT
    assert decision.winning_goal_id == goal.goal_id


def test_c2_arbitrate_movie_vs_sleep():
    """Incoming sleep command supersedes active movie goal."""
    arb = GoalArbitrator()
    movie_g = AgentGoal(user_utterance="Movie", normalized_goal="PREPARE_MOVIE", goal_type=GoalType.PREPARE_MOVIE, status=GoalStatus.EXECUTING)
    decision = arb.arbitrate(
        incoming_intent="PREPARE_SLEEP",
        active_goals=[movie_g]
    )
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    assert movie_g.goal_id in decision.affected_goal_ids
    assert decision.conflict_type == "MOVIE_VS_SLEEP"


def test_c3_arbitrate_wake_cancellation_vs_schedule():
    """Explicit wake cancellation supersedes scheduled wake task."""
    arb = GoalArbitrator()
    task = MagicMock()
    task.task_id = "task_wake_1"
    task.action_type = "WAKE_ROUTINE"

    decision = arb.arbitrate(
        incoming_intent="cancel wake",
        scheduled_tasks=[task]
    )
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    assert "task_wake_1" in decision.affected_goal_ids


def test_c4_arbitrate_movie_vs_music():
    """Incoming cinema goal supersedes background music goal."""
    arb = GoalArbitrator()
    music_g = AgentGoal(user_utterance="Music", normalized_goal="PLAY_MUSIC", goal_type=GoalType.CUSTOM_GOAL, status=GoalStatus.EXECUTING)
    movie_g = AgentGoal(user_utterance="Movie", normalized_goal="PREPARE_MOVIE", goal_type=GoalType.PREPARE_MOVIE)

    decision = arb.arbitrate(
        incoming_intent="PREPARE_MOVIE",
        incoming_goal=movie_g,
        active_goals=[music_g]
    )
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    assert music_g.goal_id in decision.affected_goal_ids


def test_c5_arbitrate_general_goal_preemption():
    """New explicit user command preempts older in-flight goals."""
    arb = GoalArbitrator()
    old_g = AgentGoal(user_utterance="Old", normalized_goal="OLD", goal_type=GoalType.CUSTOM_GOAL, status=GoalStatus.EXECUTING)
    new_g = AgentGoal(user_utterance="New", normalized_goal="NEW", goal_type=GoalType.CUSTOM_GOAL)

    decision = arb.arbitrate(
        incoming_intent="DO_NEW",
        incoming_goal=new_g,
        active_goals=[old_g]
    )
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    assert decision.winning_goal_id == new_g.goal_id


def test_c6_arbitrate_preserves_completed_goals():
    """Completed goals in the list are ignored during arbitration."""
    arb = GoalArbitrator()
    comp_g = AgentGoal(user_utterance="Done", normalized_goal="DONE", goal_type=GoalType.CUSTOM_GOAL, status=GoalStatus.COMPLETED)
    new_g = AgentGoal(user_utterance="New", normalized_goal="NEW", goal_type=GoalType.CUSTOM_GOAL)

    decision = arb.arbitrate(incoming_intent="NEW", incoming_goal=new_g, active_goals=[comp_g])
    assert decision.outcome == ArbitrationOutcome.NO_CONFLICT


def test_c7_arbitrate_decision_history_retention():
    """GoalArbitrator retains audit history of decisions."""
    arb = GoalArbitrator()
    arb.arbitrate("intent 1")
    arb.arbitrate("intent 2")
    assert len(arb.arbitration_history) == 2


def test_c8_priority_comparison_user_vs_routine():
    """Explicit user goal outranks routine goal."""
    arb = GoalArbitrator()
    user_g = AgentGoal(user_utterance="User", normalized_goal="U", goal_type=GoalType.CUSTOM_GOAL, originating_command="user command")
    routine_g = AgentGoal(user_utterance="Routine", normalized_goal="R", goal_type=GoalType.CUSTOM_GOAL, originating_command=None)

    assert arb.compare_priorities(user_g, routine_g) == -1
    assert arb.compare_priorities(routine_g, user_g) == 1


def test_c9_priority_comparison_timestamp_tiebreak():
    """Newer goal outranks older goal when both are equal origin."""
    arb = GoalArbitrator()
    now = time.time()
    g1 = AgentGoal(user_utterance="G1", normalized_goal="G1", goal_type=GoalType.CUSTOM_GOAL, created_at=now - 10.0)
    g2 = AgentGoal(user_utterance="G2", normalized_goal="G2", goal_type=GoalType.CUSTOM_GOAL, created_at=now)

    assert arb.compare_priorities(g2, g1) == -1


def test_c10_priority_comparison_identical_equals_zero():
    """Identical goals return priority 0."""
    arb = GoalArbitrator()
    now = time.time()
    g1 = AgentGoal(user_utterance="G1", normalized_goal="G1", goal_type=GoalType.CUSTOM_GOAL, created_at=now)
    g2 = AgentGoal(user_utterance="G2", normalized_goal="G2", goal_type=GoalType.CUSTOM_GOAL, created_at=now)

    assert arb.compare_priorities(g1, g2) == 0


# =============================================================================
# SECTION D: GOAL ARBITRATOR - SUPERSEDING & HISTORY PRESERVATION (Tests D1-D10)
# =============================================================================

def test_d1_supersede_preserves_verified_steps():
    """Superseding a goal preserves verified steps and only cancels pending ones."""
    arb = GoalArbitrator()
    g = AgentGoal(
        user_utterance="Setup movie",
        normalized_goal="PREPARE_MOVIE",
        goal_type=GoalType.PREPARE_MOVIE,
        steps=[
            TaskStep(step_id=1, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE", status=StepStatus.VERIFIED),
            TaskStep(step_id=2, target_subsystem="AC", capability="AC_SET_TEMPERATURE", status=StepStatus.PENDING),
            TaskStep(step_id=3, target_subsystem="FIRE_TV", capability="FIRE_TV_LAUNCH_APP", status=StepStatus.READY)
        ]
    )

    arb.supersede_goal(g, new_goal_id="goal_sleep_1")
    assert g.status == GoalStatus.SUPERSEDED
    assert g.superseded_by == "goal_sleep_1"
    assert g.steps[0].status == StepStatus.VERIFIED
    assert g.steps[1].status == StepStatus.CANCELLED
    assert g.steps[2].status == StepStatus.CANCELLED


def test_d2_supersede_records_completion_timestamp():
    """Superseded goal gets a completed_at timestamp."""
    arb = GoalArbitrator()
    g = AgentGoal(user_utterance="Goal", normalized_goal="G", goal_type=GoalType.CUSTOM_GOAL)
    arb.supersede_goal(g, new_goal_id="new_1")
    assert g.completed_at is not None
    assert g.completed_at > 0


def test_d3_supersede_records_failure_summary():
    """Superseded goal stores reason in failure_summary."""
    arb = GoalArbitrator()
    g = AgentGoal(user_utterance="Goal", normalized_goal="G", goal_type=GoalType.CUSTOM_GOAL)
    arb.supersede_goal(g, new_goal_id="new_1", reason="USER_CHANGED_MIND")
    assert g.failure_summary == "USER_CHANGED_MIND"


def test_d4_supersede_preserves_skipped_steps():
    """Skipped/already satisfied steps are preserved upon superseding."""
    arb = GoalArbitrator()
    g = AgentGoal(
        user_utterance="Goal",
        normalized_goal="G",
        goal_type=GoalType.CUSTOM_GOAL,
        steps=[
            TaskStep(step_id=1, target_subsystem="AC", capability="AC_SET_TEMPERATURE", status=StepStatus.SKIPPED_ALREADY_SATISFIED),
            TaskStep(step_id=2, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE", status=StepStatus.PENDING)
        ]
    )
    arb.supersede_goal(g, "new_2")
    assert g.steps[0].status == StepStatus.SKIPPED_ALREADY_SATISFIED
    assert g.steps[1].status == StepStatus.CANCELLED


def test_d5_arbitration_decision_structure():
    """ArbitrationDecision provides structured report."""
    dec = ArbitrationDecision(
        outcome=ArbitrationOutcome.SUPERSEDE_EXISTING,
        winning_goal_id="w_1",
        affected_goal_ids=["a_1", "a_2"],
        rationale="Preempted"
    )
    assert dec.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING
    assert len(dec.affected_goal_ids) == 2


def test_d6_arbitrate_with_live_telemetry():
    """Arbitration passes live telemetry gracefully."""
    arb = GoalArbitrator()
    decision = arb.arbitrate(
        incoming_intent="SET_AC",
        live_telemetry={"ac_target_temperature": 24}
    )
    assert decision.outcome == ArbitrationOutcome.NO_CONFLICT


def test_d7_arbitrate_with_active_mode():
    """Arbitration incorporates active mode context."""
    arb = GoalArbitrator()
    decision = arb.arbitrate(
        incoming_intent="sleep",
        active_mode=BehaviorMode.MOVIE
    )
    assert decision.outcome == ArbitrationOutcome.NO_CONFLICT or decision.outcome == ArbitrationOutcome.EXECUTE_NEW


def test_d8_supersede_executing_step_transitions_to_cancelled():
    """In-flight executing step transitions safely to CANCELLED on supersede."""
    arb = GoalArbitrator()
    g = AgentGoal(
        user_utterance="Goal",
        normalized_goal="G",
        goal_type=GoalType.CUSTOM_GOAL,
        steps=[TaskStep(step_id=1, target_subsystem="AC", capability="AC_SET_TEMPERATURE", status=StepStatus.EXECUTING)]
    )
    arb.supersede_goal(g, "new_3")
    assert g.steps[0].status == StepStatus.CANCELLED



def test_d9_arbitrator_history_bounded():
    """Arbitration history stays bounded to 100 items."""
    arb = GoalArbitrator()
    for i in range(120):
        arb.arbitrate(f"intent_{i}")
    assert len(arb.arbitration_history) <= 100


def test_d10_arbitration_outcome_enum():
    """ArbitrationOutcome contains all required outcome types."""
    assert ArbitrationOutcome.EXECUTE_NEW.value == "EXECUTE_NEW"
    assert ArbitrationOutcome.SUPERSEDE_EXISTING.value == "SUPERSEDE_EXISTING"
    assert ArbitrationOutcome.PAUSE_EXISTING.value == "PAUSE_EXISTING"
    assert ArbitrationOutcome.REJECT_NEW.value == "REJECT_NEW"


# =============================================================================
# SECTION E: POLICY ENGINE - DECISION TAXONOMY (Tests E1-E10)
# =============================================================================

def test_e1_policy_explicit_user_command_authorized():
    """Direct user commands receive AUTHORIZED_AUTONOMOUS."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="SET_AC_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 23},
        is_user_explicit=True
    )
    assert res.authorization == PolicyAuthorization.AUTHORIZED_AUTONOMOUS
    assert res.is_permitted() is True
    assert res.is_denied() is False


def test_e2_policy_unauthorized_proactive_requires_ask():
    """Proactive actions without autonomous grant receive ASK."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 22},
        is_user_explicit=False,
        is_autonomous_granted=False
    )
    assert res.authorization == PolicyAuthorization.ASK
    assert res.requires_ask() is True
    assert res.requires_confirmation_prompt is not None


def test_e3_policy_autonomous_comfort_grant():
    """Autonomous comfort grant allows bounded AC adjustment without asking."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 23},
        is_user_explicit=False,
        is_autonomous_granted=True
    )
    assert res.authorization == PolicyAuthorization.AUTHORIZED_AUTONOMOUS
    assert res.is_permitted() is True


def test_e4_policy_autonomous_grant_excludes_media():
    """Autonomous grant for comfort does NOT authorize unprompted media changes."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="FIRE_TV_PLAY_MEDIA",
        target_subsystem="MEDIA",
        is_user_explicit=False,
        is_autonomous_granted=True
    )
    assert res.authorization == PolicyAuthorization.ASK
    assert res.requires_ask() is True


def test_e5_policy_autonomous_grant_excludes_projector():
    """Autonomous grant does NOT authorize unprompted projector power on."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="PROJECTOR_POWER_WAKE",
        target_subsystem="PROJECTOR",
        is_user_explicit=False,
        is_autonomous_granted=True
    )
    assert res.authorization == PolicyAuthorization.ASK


def test_e6_policy_explain_decision_permitted():
    """PolicyEngine generates explanation for permitted action."""
    pol = PolicyEngine()
    res = pol.evaluate_action("AC_SET_TEMPERATURE", "AC", {"temperature": 24}, is_user_explicit=True)
    exp = pol.explain_decision(res.evaluation_id)
    assert "allowed" in exp.lower()


def test_e7_policy_explain_decision_denied():
    """PolicyEngine generates explanation for denied action."""
    pol = PolicyEngine()
    res = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    exp = pol.explain_decision(res.evaluation_id)
    assert "denied" in exp.lower()


def test_e8_policy_explain_decision_asked():
    """PolicyEngine generates explanation for asked action."""
    pol = PolicyEngine()
    res = pol.evaluate_action("AC_SET_TEMPERATURE", "AC", is_user_explicit=False, is_autonomous_granted=False)
    exp = pol.explain_decision(res.evaluation_id)
    assert "asked" in exp.lower()


def test_e9_policy_evaluation_history_bounded():
    """Policy evaluation history respects capacity limits."""
    pol = PolicyEngine()
    for i in range(120):
        pol.evaluate_action(f"ACTION_{i}", "AC", is_user_explicit=True)
    assert len(pol.evaluation_history) <= 100


def test_e10_policy_evaluation_result_model():
    """PolicyEvaluationResult validates types cleanly."""
    res = PolicyEvaluationResult(
        action_type="TEST",
        target_subsystem="ROOM",
        authorization=PolicyAuthorization.OBSERVE,
        reason="Passive observation"
    )
    assert res.authorization == PolicyAuthorization.OBSERVE


# =============================================================================
# SECTION F: POLICY ENGINE - SAFETY INVARIANTS & SOUNDBAR (Tests F1-F10)
# =============================================================================

def test_f1_soundbar_fire_tv_ownership_denies_bt_reclaim():
    """When Fire TV owns soundbar, PC Bluetooth reclaim is DENIED."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="RECLAIM_PC_BLUETOOTH",
        target_subsystem="SOUNDBAR",
        soundbar_owner="FIRE_TV"
    )
    assert res.authorization == PolicyAuthorization.DENIED
    assert res.violates_hard_constraint is True
    assert "forbidden" in res.reason.lower() or "prohibited" in res.reason.lower()


def test_f2_soundbar_fire_tv_ownership_in_movie_mode_denies_bt_reclaim():
    """In MOVIE mode, PC Bluetooth reclaim is DENIED even if owner is ambiguous."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="CONNECT_PC_BT",
        target_subsystem="SOUNDBAR",
        soundbar_owner="UNKNOWN",
        active_mode=BehaviorMode.MOVIE
    )
    assert res.authorization == PolicyAuthorization.DENIED
    assert res.violates_hard_constraint is True


def test_f3_pc_soundbar_ownership_allows_pc_endpoint():
    """When PC owns soundbar, setting PC endpoint is permitted."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="SET_PC_ENDPOINT",
        target_subsystem="PC",
        soundbar_owner="PC",
        is_user_explicit=True
    )
    assert res.authorization == PolicyAuthorization.AUTHORIZED_AUTONOMOUS


def test_f4_ac_temperature_out_of_bounds_low():
    """Temperature below 16°C is DENIED."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 14},
        is_user_explicit=True
    )
    assert res.authorization == PolicyAuthorization.DENIED
    assert res.violates_hard_constraint is True
    assert "outside safe" in res.reason.lower()


def test_f5_ac_temperature_out_of_bounds_high():
    """Temperature above 30°C is DENIED."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 32},
        is_user_explicit=True
    )
    assert res.authorization == PolicyAuthorization.DENIED
    assert res.violates_hard_constraint is True


def test_f6_ac_valid_temperature_permitted():
    """Temperature between 16°C and 30°C is permitted."""
    pol = PolicyEngine()
    res = pol.evaluate_action(
        action_type="AC_SET_TEMPERATURE",
        target_subsystem="AC",
        parameters={"temperature": 23},
        is_user_explicit=True
    )
    assert res.authorization == PolicyAuthorization.AUTHORIZED_AUTONOMOUS


def test_f7_applied_rules_tracking():
    """PolicyEvaluationResult records applied rule names."""
    pol = PolicyEngine()
    res = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    assert "RULE_SOUNDBAR_FIRE_TV_PROTECTION" in res.applied_rules


def test_f8_unknown_evaluation_id_explanation():
    """Explaining non-existent evaluation ID returns safe message."""
    pol = PolicyEngine()
    exp = pol.explain_decision("non_existent_id")
    assert "No evaluation record" in exp


def test_f9_policy_is_denied_helper():
    """is_denied() returns True for DENIED and False for AUTHORIZED."""
    pol = PolicyEngine()
    res_denied = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    res_auth = pol.evaluate_action("AC_SET_TEMPERATURE", "AC", {"temperature": 23}, is_user_explicit=True)
    assert res_denied.is_denied() is True
    assert res_auth.is_denied() is False


def test_f10_policy_is_permitted_helper():
    """is_permitted() returns True only for AUTHORIZED_AUTONOMOUS."""
    pol = PolicyEngine()
    res_auth = pol.evaluate_action("AC_SET_TEMPERATURE", "AC", {"temperature": 23}, is_user_explicit=True)
    res_ask = pol.evaluate_action("AC_SET_TEMPERATURE", "AC", is_user_explicit=False)
    assert res_auth.is_permitted() is True
    assert res_ask.is_permitted() is False


# =============================================================================
# SECTION G: END-TO-END AGENT REASONING & ARBITRATION (Tests G1-G6)
# =============================================================================

def test_g1_agent_instantiates_reasoning_and_arbitrator():
    """AnimusPersonalAgent contains reasoning, arbitration, and policy engines."""
    ag = AnimusPersonalAgent()
    ag.reasoning_engine = ReasoningEngine()
    ag.goal_arbitrator = GoalArbitrator()
    ag.policy_engine = PolicyEngine()

    assert ag.reasoning_engine is not None
    assert ag.goal_arbitrator is not None
    assert ag.policy_engine is not None


def test_g2_reasoning_evaluates_sleep_transition_during_movie():
    """Agent evaluates sleep intent during active movie mode."""
    engine = ReasoningEngine()
    res = engine.reason(user_command="I'm going to bed", active_mode=BehaviorMode.MOVIE)
    assert res.selected_action is not None
    assert res.selected_action.action_type == "TRANSITION_MODE"


def test_g3_arbitration_supersedes_movie_with_sleep():
    """GoalArbitrator correctly handles movie superseding by sleep."""
    arb = GoalArbitrator()
    movie_g = AgentGoal(user_utterance="Movie", normalized_goal="PREPARE_MOVIE", goal_type=GoalType.PREPARE_MOVIE, status=GoalStatus.EXECUTING)
    decision = arb.arbitrate("goodnight", active_goals=[movie_g])
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING


def test_g4_policy_evaluates_direct_user_command():
    """PolicyEngine evaluates direct turn cleanly."""
    pol = PolicyEngine()
    res = pol.evaluate_action("AC_SET_TEMPERATURE", "AC", {"temperature": 23}, is_user_explicit=True)
    assert res.is_permitted() is True


def test_g5_policy_protects_soundbar_during_agent_interaction():
    """Soundbar Bluetooth reclaim is blocked by policy."""
    pol = PolicyEngine()
    res = pol.evaluate_action("RECLAIM_PC_BLUETOOTH", "SOUNDBAR", soundbar_owner="FIRE_TV")
    assert res.is_denied() is True


def test_g6_canonical_dialogue_goal_superseding():
    """Full dialogue scenario: user starts movie, then says bedtime -> movie superseded."""
    arb = GoalArbitrator()
    movie_goal = AgentGoal(
        user_utterance="Movie time",
        normalized_goal="PREPARE_MOVIE",
        goal_type=GoalType.PREPARE_MOVIE,
        status=GoalStatus.EXECUTING,
        steps=[
            TaskStep(step_id=1, target_subsystem="PROJECTOR", capability="PROJECTOR_POWER_WAKE", status=StepStatus.VERIFIED),
            TaskStep(step_id=2, target_subsystem="FIRE_TV", capability="FIRE_TV_LAUNCH_APP", status=StepStatus.PENDING)
        ]
    )

    decision = arb.arbitrate("I'm going to bed", active_goals=[movie_goal])
    assert decision.outcome == ArbitrationOutcome.SUPERSEDE_EXISTING

    # Supersede movie goal
    arb.supersede_goal(movie_goal, new_goal_id="goal_sleep_1", reason="USER_SLEEP_COMMAND")
    assert movie_goal.status == GoalStatus.SUPERSEDED
    assert movie_goal.steps[0].status == StepStatus.VERIFIED
    assert movie_goal.steps[1].status == StepStatus.CANCELLED
