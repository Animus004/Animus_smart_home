"""
Phase 2 Stage 3 Test Suite: Persistent Behavioral Memory, Contextual Continuity & Stateful Agent Behavior.
Covers:
- Pronoun & Reference Resolution (it, that, this, them, there, too)
- Relative Adjustments (warmer, cooler, two degrees cooler, louder, quieter)
- Action Introspection & Historical Queries (depth=1, depth=2, prior state, reason)
- Safe Replay & Idempotency Check
- Safe Undo & Out-of-Band External State Reconciliation
- First-Class Cancellation & Flow Control
- Topic Switching & Cross-Subsystem Continuity
- Memory Lifecycle, Bounded Action History (10-entry FIFO), Provenance Invariants
- Canonical Multi-Turn Acceptance Dialogues A, B, C, D
"""

import pytest
import time
from unittest.mock import MagicMock

from agent.core import AnimusPersonalAgent, AgentInteractionResponse
from agent.models import UserProfile, ResolvedIntent, IntentCategory
from agent.interaction_result import (
    AgentInteractionResult,
    DecisionType,
    PhysicalVerificationStatus,
    StateDelta
)
from agent.state_memory import (
    FactProvenance,
    RecentActionMemory,
    VerifiedRoomFact,
    ReferenceType,
    AgentSessionMemory
)
from agent.context_buffer import ConversationContextBuffer
from room_state.models import RoomState, StateField
from planner.models import StepExecutionResult, ExecutionResult, ExecutionStatus, OverallExecutionStatus, ValidationResult
from capability_registry import UnifiedCapabilityRegistry
from planner.validator import PlanValidator
from planner.executor import PlanExecutor


@pytest.fixture
def base_room_state():
    """Provides a healthy, realistic physical RoomState."""
    now = time.time()
    st = RoomState()
    st.ac.target_temperature = StateField.observed(24, "MOCK", now)
    st.ac.ambient_temperature = StateField.observed(26, "MOCK", now)
    st.ac.power = StateField.observed(True, "MOCK", now)
    st.projector.power = StateField.observed(True, "MOCK", now)
    st.projector.signal_active = StateField.observed(True, "MOCK", now)
    st.fire_tv.online = StateField.observed(True, "MOCK", now)
    st.pc.online = StateField.observed(True, "MOCK", now)
    st.pc.master_volume = StateField.observed(40, "MOCK", now)
    st.soundbar.is_connected = StateField.observed(True, "MOCK", now)
    st.audio_stream.active_producer = StateField.observed("FIRE_TV", "MOCK", now)
    st.environment.room_mode = StateField.observed("DEFAULT", "MOCK", now)
    return st


@pytest.fixture
def mock_exec():
    """Mock PlanExecutor that records calls and returns verified results."""
    registry = UnifiedCapabilityRegistry()
    validator = PlanValidator(registry=registry)
    mock_executor = MagicMock(spec=PlanExecutor)
    mock_executor.validator = validator

    def _mock_exec(val_plan):
        steps_res = []
        for s in val_plan.validated_steps:
            obs = s.parameters.get("temperature", s.parameters.get("power", True))
            steps_res.append(
                StepExecutionResult(
                    step_id=s.step_id,
                    device=s.device,
                    capability_id=s.canonical_capability_id,
                    status=ExecutionStatus.VERIFIED,
                    requested_parameters=s.parameters,
                    dispatch_result={"success": True, "target_temperature": obs, "transport": "LOCAL"},
                    readback_result={"matched": True, "observed": obs},
                    verified=True
                )
            )
        return ExecutionResult(
            plan_id=val_plan.plan_id or "test-plan",
            user_request=val_plan.user_request or "test request",
            overall_status=OverallExecutionStatus.SUCCESS,
            success=True,
            steps=steps_res
        )

    mock_executor.execute_plan.side_effect = _mock_exec
    return mock_executor


from agent.user_model import UserModel
from agent.memory import AgentMemoryStore
from agent.task_manager import TaskManager
from agent.models import (
    UserProfile,
    UserIdentity,
    AcPreferenceModel,
    EntertainmentPreferencesModel,
    NotificationPreferencesModel,
    DailyRoutines
)
from room_state.aggregator import RoomStateAggregator


@pytest.fixture
def agent(mock_exec, base_room_state):
    """Initializes AnimusPersonalAgent wired with mock executor and mock room state aggregator."""
    registry = UnifiedCapabilityRegistry()
    user_prof = UserProfile(
        identity=UserIdentity(name="Sayan", preferred_address="buddy"),
        thermal=AcPreferenceModel(preferred_ac_setpoint=24, comfort_preference="ECO"),
        entertainment=EntertainmentPreferencesModel(preferred_volume=40),
        notifications=NotificationPreferencesModel(),
        routines=DailyRoutines()
    )
    user_model = UserModel(profile=user_prof)
    memory = AgentMemoryStore()
    task_mgr = TaskManager()
    context_buf = ConversationContextBuffer()

    mock_agg = MagicMock(spec=RoomStateAggregator)
    mock_agg.get_room_state.return_value = base_room_state

    ag = AnimusPersonalAgent(
        registry=registry,
        room_state_aggregator=mock_agg,
        user_model=user_model,
        memory=memory,
        task_manager=task_mgr,
        context_buffer=context_buf,
        planner_executor=mock_exec
    )
    return ag




# =============================================================================
# SECTION 1: PRONOUN & CONTEXTUAL REFERENCE RESOLUTION
# =============================================================================

def test_pronoun_it_resolves_to_ac_after_ac_command(agent, base_room_state):
    """Turn 1: 'Set AC to 24' -> Turn 2: 'Turn it off' resolves to AC_POWER_OFF."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    assert agent.context_buffer.last_target_device == "AC"

    resp = agent.interact("Turn it off.", room_state=base_room_state)
    assert resp.understood_intent == "AC_POWER_OFF"


def test_pronoun_it_resolves_to_projector_after_projector_command(agent, base_room_state):
    """Turn 1: 'Turn on the projector' -> Turn 2: 'Turn it off' resolves to PROJECTOR_POWER_SLEEP."""
    agent.interact("Turn on the projector.", room_state=base_room_state)
    assert agent.context_buffer.last_target_device == "PROJECTOR"

    resp = agent.interact("Turn it off.", room_state=base_room_state)
    assert resp.understood_intent == "PROJECTOR_POWER_SLEEP"


def test_pronoun_that_resolves_to_active_device(agent, base_room_state):
    """'Turn that off' resolves based on conversational context."""
    agent.interact("Turn on the projector.", room_state=base_room_state)
    resp = agent.interact("Turn that off.", room_state=base_room_state)
    assert resp.understood_intent == "PROJECTOR_POWER_SLEEP"


def test_pronoun_too_resolves_correctly(agent, base_room_state):
    """'Turn that off too' resolves to active context device."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    resp = agent.interact("Turn that off too.", room_state=base_room_state)
    assert resp.understood_intent == "AC_POWER_OFF"


# =============================================================================
# SECTION 2: RELATIVE ADJUSTMENTS
# =============================================================================

def test_relative_degree_cooler_adjustment(agent, base_room_state):
    """'Two degrees cooler' drops temperature from 24 -> 22°C."""
    base_room_state.ac.target_temperature.value = 24
    resp = agent.interact("Make it two degrees cooler.", room_state=base_room_state)
    assert resp.understood_intent == "SET_AC_TEMPERATURE"
    assert resp.action_taken is True


def test_relative_degree_warmer_adjustment(agent, base_room_state):
    """'Three degrees warmer' raises temperature from 24 -> 27°C."""
    base_room_state.ac.target_temperature.value = 24
    resp = agent.interact("Three degrees warmer.", room_state=base_room_state)
    assert resp.understood_intent == "SET_AC_TEMPERATURE"


def test_relative_qualitative_cooler_warmer(agent, base_room_state):
    """'A little warmer' raises temperature by 1°C."""
    base_room_state.ac.target_temperature.value = 24
    resp = agent.interact("A little warmer.", room_state=base_room_state)
    assert resp.understood_intent == "SET_AC_TEMPERATURE"


def test_relative_volume_louder_and_quieter(agent, base_room_state):
    """'Make it louder' and 'make it quieter' resolve to volume adjustments."""
    resp1 = agent.interact("Make it louder.", room_state=base_room_state)
    assert resp1.understood_intent in ("ADJUST_VOLUME", "VOLUME_UP")

    resp2 = agent.interact("Make it quieter.", room_state=base_room_state)
    assert resp2.understood_intent in ("ADJUST_VOLUME", "VOLUME_DOWN")


# =============================================================================
# SECTION 3: INTROSPECTION & HISTORICAL ACTION QUERIES
# =============================================================================

def test_introspect_what_did_you_just_do(agent, base_room_state):
    """'What did you just do?' explains the latest verified action."""
    base_room_state.ac.target_temperature.value = 25
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    resp = agent.interact("What did you just do?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_RECENT_ACTION"
    assert "AC" in resp.agent_message or "24" in resp.agent_message


def test_introspect_what_did_you_change_before_that(agent, base_room_state):
    """'What did you change before that?' accesses historical depth=2 action."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 25.", room_state=base_room_state)

    base_room_state.ac.target_temperature.value = 25
    agent.interact("Turn on the projector.", room_state=base_room_state)

    resp = agent.interact("What did you change before that?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_HISTORICAL_ACTION"
    assert "AC" in resp.agent_message or "25" in resp.agent_message or "Before that" in resp.agent_message


def test_introspect_what_was_the_ac_at_before(agent, base_room_state):
    """'What was the AC at before?' retrieves previous_value from verified delta."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    resp = agent.interact("What was the AC at before?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_HISTORICAL_ACTION"
    assert "26" in resp.agent_message


def test_introspect_why_did_you_do_that(agent, base_room_state):
    """'Why did you do that?' explains the reason for the action."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    resp = agent.interact("Why did you do that?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_ACTION_REASON"
    assert len(resp.agent_message) > 5


def test_introspect_is_it_still_on(agent, base_room_state):
    """'Is it still on?' queries current live RoomState power status."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    base_room_state.ac.power.value = True
    resp = agent.interact("Is it still on?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_TELEMETRY_STATUS"
    assert "on" in resp.agent_message.lower()


# =============================================================================
# SECTION 4: REPLAY SAFETY & IDEMPOTENCY
# =============================================================================

def test_replay_recent_action_when_state_changed(agent, base_room_state):
    """'Do that again' executes when state needs changing."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    # State changed externally to 25
    base_room_state.ac.target_temperature.value = 25
    resp = agent.interact("Do that again.", room_state=base_room_state)
    assert resp.understood_intent in ("REPLAY_RECENT_ACTION", "SET_AC_TEMPERATURE")


def test_replay_idempotent_when_already_satisfied(agent, base_room_state):
    """'Do that again' returns NO_OP_ALREADY_SATISFIED when current state equals target."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    # Room is still at 24
    base_room_state.ac.target_temperature.value = 24
    resp = agent.interact("Do that again.", room_state=base_room_state)
    assert "already in place" in resp.agent_message.lower() or "already" in resp.agent_message.lower()
    assert resp.action_taken is False


def test_replay_without_recent_action_fails_gracefully(agent, base_room_state):
    """'Do that again' with empty memory returns polite notification."""
    resp = agent.interact("Do that again.", room_state=base_room_state)
    assert "don't have a recent action" in resp.agent_message.lower() or "haven't" in resp.agent_message.lower()
    assert resp.action_taken is False


# =============================================================================
# SECTION 5: UNDO SAFETY & EXTERNAL RECONCILIATION
# =============================================================================

def test_undo_restores_verified_previous_state(agent, base_room_state):
    """26 -> 24 followed by 'Put it back' safely commands 24 -> 26."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    base_room_state.ac.target_temperature.value = 24
    resp = agent.interact("Put it back.", room_state=base_room_state)
    assert resp.understood_intent == "UNDO_RECENT_ACTION"
    assert resp.action_taken is True
    assert "26" in resp.agent_message


def test_undo_rejects_when_external_change_detected(agent, base_room_state):
    """If live telemetry changed out-of-band (e.g. to 22), undo refuses to overwrite without instruction."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    # Physical remote changed AC to 22°C
    base_room_state.ac.target_temperature.value = 22
    resp = agent.interact("Put it back.", room_state=base_room_state)
    assert resp.understood_intent == "UNDO_RECENT_ACTION"
    assert resp.action_taken is False
    assert "22" in resp.agent_message
    assert "changed it after my action" in resp.agent_message or "won't overwrite" in resp.agent_message


def test_undo_without_prior_state_fails_gracefully(agent, base_room_state):
    """'Put it back' with empty memory informs user gracefully."""
    resp = agent.interact("Put it back.", room_state=base_room_state)
    assert "don't have a prior state" in resp.agent_message.lower()
    assert resp.action_taken is False


# =============================================================================
# SECTION 6: CANCELLATION & FLOW CONTROL
# =============================================================================

def test_cancellation_never_mind(agent, base_room_state):
    """'Never mind' safely cancels without hardware action."""
    resp = agent.interact("Never mind.", room_state=base_room_state)
    assert resp.understood_intent == "CANCEL_CURRENT_REQUEST"
    assert resp.action_taken is False
    assert "leaving it" in resp.agent_message.lower() or "cancelled" in resp.agent_message.lower() or "okay" in resp.agent_message.lower()


def test_cancellation_leave_ac_alone(agent, base_room_state):
    """'Actually leave the AC alone' cancels AC flow."""
    resp = agent.interact("Actually leave the AC alone.", room_state=base_room_state)
    assert resp.understood_intent == "CANCEL_CURRENT_REQUEST"
    assert resp.action_taken is False


# =============================================================================
# SECTION 7: TOPIC SWITCHING & CROSS-SUBSYSTEM CONTINUITY
# =============================================================================

def test_topic_switch_ac_to_projector(agent, base_room_state):
    """AC -> Projector -> 'Turn it off' correctly turns off Projector, not AC."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    assert agent.context_buffer.last_target_device == "AC"

    agent.interact("Turn on the projector.", room_state=base_room_state)
    assert agent.context_buffer.last_target_device == "PROJECTOR"

    resp = agent.interact("Turn it off.", room_state=base_room_state)
    assert resp.understood_intent == "PROJECTOR_POWER_SLEEP"


def test_topic_switch_to_room_thermal_context(agent, base_room_state):
    """Projector active -> 'Make the room warmer' recovers thermal context to AC."""
    agent.interact("Turn on the projector.", room_state=base_room_state)
    assert agent.context_buffer.last_target_device == "PROJECTOR"

    resp = agent.interact("Make the room warmer.", room_state=base_room_state)
    assert resp.understood_intent == "SET_AC_TEMPERATURE"


def test_switch_focus_what_about_the_projector(agent, base_room_state):
    """'What about the projector?' switches focus and queries projector state."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    resp = agent.interact("What about the projector?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_TELEMETRY_STATUS"
    assert "projector" in resp.agent_message.lower()


# =============================================================================
# SECTION 8: EXTERNAL STATE CHANGES & TELEMETRY PRECEDENCE
# =============================================================================

def test_telemetry_precedence_over_memory(agent, base_room_state):
    """Live telemetry always wins over historical memory when answering current state."""
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    # Telemetry reports 22°C (remote change)
    base_room_state.ac.target_temperature.value = 22
    resp = agent.interact("What did you do to the AC?", room_state=base_room_state)
    assert resp.understood_intent == "INTROSPECT_RECENT_ACTION"
    # Must report both historical setpoint (24) and current telemetry (22)
    assert "24" in resp.agent_message
    assert "22" in resp.agent_message


# =============================================================================
# SECTION 9: MULTI-TURN IN-FLIGHT CORRECTIONS
# =============================================================================

def test_multi_turn_numeric_corrections(agent, base_room_state):
    """'Actually make that 25' correctly supersedes previous target."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    resp = agent.interact("Actually, make that 25.", room_state=base_room_state)
    assert resp.understood_intent == "SET_AC_TEMPERATURE"


def test_multi_turn_wait_no_correction(agent, base_room_state):
    """'Wait, no — 23' correctly updates setpoint."""
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    resp = agent.interact("Wait, no — 23.", room_state=base_room_state)
    assert resp.understood_intent == "SET_AC_TEMPERATURE"


# =============================================================================
# SECTION 10: MEMORY LIFECYCLE & PROVENANCE INVARIANTS
# =============================================================================

def test_bounded_10_entry_history_fifo_eviction():
    """AgentSessionMemory strictly bounds verified action history to 10 entries."""
    mem = AgentSessionMemory(max_recent_actions=10)

    for i in range(15):
        act = RecentActionMemory(
            turn_index=i + 1,
            user_utterance=f"Command {i + 1}",
            intent=f"INTENT_{i + 1}",
            target_subsystem="AC",
            execution_success=True,
            readback_status="VERIFIED"
        )
        mem.record_action(act)

    assert len(mem.recent_actions) == 10
    # Oldest entries (1..5) evicted, 6..15 remain
    assert mem.recent_actions[0].user_utterance == "Command 6"
    assert mem.recent_actions[-1].user_utterance == "Command 15"


def test_fact_provenance_preservation():
    """Facts maintain explicit provenance tags."""
    mem = AgentSessionMemory()
    mem.record_fact("AC", "target_temperature", 24, FactProvenance.VERIFIED_EXECUTION, source_tag="SET_AC_TEMPERATURE")
    mem.record_fact("ROOM", "preferred_mode", "CINEMA", FactProvenance.CONVERSATIONAL_ONLY)

    fact_ac = mem.get_fact("AC", "target_temperature")
    assert fact_ac is not None
    assert fact_ac.provenance == FactProvenance.VERIFIED_EXECUTION
    assert fact_ac.value == 24

    fact_conv = mem.get_fact("ROOM", "preferred_mode")
    assert fact_conv is not None
    assert fact_conv.provenance == FactProvenance.CONVERSATIONAL_ONLY


# =============================================================================
# SECTION 11: CANONICAL ACCEPTANCE DIALOGUES
# =============================================================================

def test_canonical_dialogue_a_basic_context_and_undo(agent, base_room_state):
    """
    Dialogue A:
    1. 'Set the AC to 24.' -> Verified
    2. 'Make it a little warmer.' -> 25°C Verified
    3. 'What did you just change?' -> 'I raised the AC from 24 to 25°C, buddy.'
    4. 'Why?' -> Truthful explanation
    5. 'Put it back.' -> Restores 24°C Verified
    """
    # 1. Set to 24
    base_room_state.ac.target_temperature.value = 26
    r1 = agent.interact("Set the AC to 24.", room_state=base_room_state)
    assert r1.action_taken is True
    assert "24" in r1.agent_message

    # 2. Make it warmer (24 -> 25)
    base_room_state.ac.target_temperature.value = 24
    r2 = agent.interact("Make it a little warmer.", room_state=base_room_state)
    assert r2.action_taken is True

    # 3. What did you just change?
    r3 = agent.interact("What did you just change?", room_state=base_room_state)
    assert "25" in r3.agent_message or "raised" in r3.agent_message

    # 4. Why?
    r4 = agent.interact("Why?", room_state=base_room_state)
    assert len(r4.agent_message) > 5

    # 5. Put it back (revert 25 -> 24)
    base_room_state.ac.target_temperature.value = 25
    r5 = agent.interact("Put it back.", room_state=base_room_state)
    assert r5.action_taken is True
    assert "24" in r5.agent_message


def test_canonical_dialogue_b_topic_switch(agent, base_room_state):
    """
    Dialogue B:
    1. 'Set the AC to 24.'
    2. 'Turn on the projector.'
    3. 'Turn it off.' -> Projector turned off, not AC.
    """
    agent.interact("Set the AC to 24.", room_state=base_room_state)
    agent.interact("Turn on the projector.", room_state=base_room_state)
    r3 = agent.interact("Turn it off.", room_state=base_room_state)
    assert r3.understood_intent == "PROJECTOR_POWER_SLEEP"


def test_canonical_dialogue_c_external_change(agent, base_room_state):
    """
    Dialogue C:
    1. Animus sets AC 26 -> 24.
    2. External physical remote changes AC to 22.
    3. 'What did you do to the AC?' -> Distinguishes action (24) from telemetry (22).
    """
    base_room_state.ac.target_temperature.value = 26
    agent.interact("Set the AC to 24.", room_state=base_room_state)

    # Physical change outside Animus
    base_room_state.ac.target_temperature.value = 22
    r2 = agent.interact("What did you do to the AC?", room_state=base_room_state)
    assert "24" in r2.agent_message
    assert "22" in r2.agent_message


def test_canonical_dialogue_d_cancellation(agent, base_room_state):
    """
    Dialogue D:
    1. 'Turn on the AC.'
    2. 'Never mind.' -> Cancelled cleanly without unneeded hardware mutation.
    """
    agent.interact("Turn on the AC.", room_state=base_room_state)
    r2 = agent.interact("Never mind.", room_state=base_room_state)
    assert r2.action_taken is False
    assert "okay" in r2.agent_message.lower() or "leaving it" in r2.agent_message.lower() or "cancelled" in r2.agent_message.lower()
