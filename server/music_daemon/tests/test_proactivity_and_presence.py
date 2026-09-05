"""
================================================================================
ANIMUS SMART ROOM — PROACTIVITY & AMBIENT PRESENCE TESTS (PHASE 4)
================================================================================
Validates:
1. Work session fatigue detection grounded in active career milestone memory.
2. Conversational binding: affirmative ("Yes") executes break via RealityObserver.
3. Conversational binding: rejection ("No / not now") maintains work mode respectfully.
4. Evening routine anticipation (guitar practice at 17:30).
5. Ambient thermal care trigger and follow-up resolution.
6. Idle optical projector protection trigger and standby execution.
7. Real-time AgentEventBus multi-device broadcast.
8. Single question invariant (no compound or duplicate questions).
================================================================================
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder
from agent.agent_decision_engine import AgentDecisionEngine
from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory
from agent.reality_observer import VerificationStatus
from event_bus import AgentEventBus, AgentEventType


@pytest.fixture
def temp_memory():
    """Provides an isolated LongTermMemoryStore with fresh temporary SQLite DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_proactive_phase4.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


def test_proactive_work_fatigue_with_active_milestone(temp_memory):
    """
    Proves that proactive work fatigue mentions the user's real active milestone
    and stages a pending follow-up in AgentDecisionEngine.
    """
    mock_pc = MagicMock()
    mock_pc.set_volume.return_value = 10
    mock_pc.is_app_running.return_value = True

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    event_bus = AgentEventBus()
    mock_tts = MagicMock()

    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        memory_store=temp_memory,
        decision_engine=engine,
        event_bus=event_bus,
        cooldown_seconds=60.0
    )

    # Active subgoal from baseline is: "Blinkit SQL: Calculate lost revenue per out-of-stock SKU"
    curr_sg = temp_memory.get_current_work_subgoal()
    assert curr_sg is not None
    sg_title = curr_sg["title"]

    now = time.time()
    telemetry = {
        "active_mode": "WORK",
        "pc_online": True,
        "pc_locked": False,
        "user_idle_seconds": 20.0,
        "ac_ambient_temp": 24,
        "ac_power": True,
        "hour": 14,
        "suppress_morning": True
    }

    # Simulate 100 minutes of continuous focus at PC
    orch._pc_active_since = now - 6000

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.WORK_SESSION_FATIGUE
    assert "Sir" in msg
    assert sg_title in msg
    assert "dim the lights" in msg or "soothing" in msg
    assert mock_tts.speak.called

    # Verify staged in decision_engine
    assert engine._proactive_followup_state is not None
    assert engine._proactive_followup_state["category"] == ProactiveTriggerCategory.WORK_SESSION_FATIGUE


def test_affirmative_followup_executes_break(temp_memory):
    """
    Proves that when Sir replies 'yes' to a proactive break suggestion,
    Animus executes the volume reduction and relax transition with Zero Fake Success.
    """
    mock_pc = MagicMock()
    mock_pc.set_volume.return_value = 10

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    # Stage proactive fatigue suggestion
    engine.set_pending_proactive_followup(
        category=ProactiveTriggerCategory.WORK_SESSION_FATIGUE,
        followup_context="PROACTIVE_WORK_FATIGUE_TRANSITION",
        message="Sir, you've been focused in Work Mode on your project for a while. Shall I dim the lights and play something soothing for a quick break?"
    )

    # Sir replies affirmatively
    res = engine.decide_and_act("yes please, take a break")
    assert res.verified_physical_status == VerificationStatus.VERIFIED_SUCCESS.value
    assert "Sir" in res.response_message
    assert "relax mode" in res.response_message.lower() or "break" in res.response_message.lower()

    # Verify volume was reduced to 10%
    mock_pc.set_volume.assert_called_with(10)

    # Verify pending state was cleared
    assert engine._proactive_followup_state is None


def test_rejection_followup_maintains_work_mode(temp_memory):
    """
    Proves that when Sir replies 'no, not now' to a proactive break suggestion,
    Animus respects the decision and keeps Work Mode active without mutating devices.
    """
    mock_pc = MagicMock()

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    # Stage proactive fatigue suggestion
    engine.set_pending_proactive_followup(
        category=ProactiveTriggerCategory.WORK_SESSION_FATIGUE,
        followup_context="PROACTIVE_WORK_FATIGUE_TRANSITION",
        message="Sir, shall I dim the lights for a quick break?"
    )

    # Sir declines
    res = engine.decide_and_act("no, still working")
    assert "Sir" in res.response_message
    assert "keeping your work focus active" in res.response_message.lower()

    # Zero hardware mutations
    assert not mock_pc.set_volume.called

    # Verify pending state was cleared
    assert engine._proactive_followup_state is None


def test_evening_routine_anticipation(temp_memory):
    """
    Proves that learned evening routines (guitar practice around 5:30 PM)
    trigger proactive anticipation and affirmative conversational execution.
    """
    # Store guitar routine in structured memory
    temp_memory.store_structured_memory(
        memory_type="routine",
        subject="guitar",
        context="evening",
        value="guitar practice at 5:30 PM",
        confidence=0.95,
        source="user"
    )

    mock_pc = MagicMock()
    mock_tts = MagicMock()
    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        memory_store=temp_memory,
        decision_engine=engine,
        cooldown_seconds=60.0
    )

    # Telemetry: 5 PM (17:00), user at workstation
    telemetry = {
        "hour": 17,
        "pc_online": True,
        "pc_locked": False,
        "user_idle_seconds": 30.0,
        "ac_ambient_temp": 24,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.ROUTINE_ANTICIPATION
    assert "guitar" in msg.lower()
    assert "Sir" in msg

    # Affirmative response from Sir
    turn_res = engine.decide_and_act("guitar time")
    assert "Sir" in turn_res.response_message
    assert "guitar" in turn_res.response_message.lower()
    assert engine._proactive_followup_state is None


def test_proactive_thermal_care_followup(temp_memory):
    """Proves proactive thermal alert triggers and resolves upon user confirmation."""
    mock_pc = MagicMock()
    mock_executor = MagicMock()
    mock_ac = MagicMock()
    mock_executor.ac_controller = mock_ac

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc,
        planner_executor=mock_executor
    )

    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        decision_engine=engine,
        cooldown_seconds=60.0
    )

    # Telemetry: 29°C in room, AC off
    telemetry = {
        "ac_ambient_temp": 29,
        "ac_power": False,
        "hour": 15,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.THERMAL_CARE
    assert "29" in msg
    assert "Sir" in msg

    # Sir confirms: "Yes please turn on AC"
    turn_res = engine.decide_and_act("yes please turn on the ac")
    assert turn_res.verified_physical_status == VerificationStatus.VERIFIED_SUCCESS.value
    assert "Sir" in turn_res.response_message
    assert "24°c" in turn_res.response_message.lower()
    assert mock_ac.set_power.called


def test_idle_optical_protection_followup(temp_memory):
    """Proves projector idle warning triggers and turns off on user confirmation."""
    mock_pc = MagicMock()
    mock_executor = MagicMock()
    mock_proj = MagicMock()
    mock_executor.projector_controller = mock_proj

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc,
        planner_executor=mock_executor
    )

    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        decision_engine=engine,
        cooldown_seconds=60.0
    )

    telemetry = {
        "projector_power": True,
        "media_playing": False,
        "hour": 20,
        "suppress_morning": True
    }

    # Simulate 25 minutes of idle
    orch._idle_media_start = time.time() - 1500

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION
    assert "standby" in msg

    # Sir confirms: "Yes turn it off"
    turn_res = engine.decide_and_act("yes standby projector")
    assert turn_res.verified_physical_status == VerificationStatus.VERIFIED_SUCCESS.value
    assert "standby" in turn_res.response_message.lower() or "off" in turn_res.response_message.lower()
    assert mock_proj.turn_off.called


def test_proactive_event_bus_broadcast(temp_memory):
    """Proves that proactive suggestions are broadcast to AgentEventBus for mobile/websocket sync."""
    import queue
    event_bus = AgentEventBus()
    sub_q = queue.Queue()
    event_bus.subscribe(sub_q)

    mock_tts = MagicMock()
    orch = ProactiveOrchestrator(
        tts_service=mock_tts,
        event_bus=event_bus,
        cooldown_seconds=60.0
    )

    telemetry = {
        "ac_ambient_temp": 30,
        "ac_power": False,
        "hour": 14,
        "suppress_morning": True
    }

    orch.evaluate_proactive_rules(telemetry=telemetry)

    # Check event bus
    evt = sub_q.get(timeout=2.0)
    assert evt is not None
    assert evt.event_type == AgentEventType.AGENT_PROACTIVE_MESSAGE
    assert "30" in evt.message
    assert evt.payload["category"] == ProactiveTriggerCategory.THERMAL_CARE


def test_single_question_invariant_movie_mode(temp_memory):
    """Proves that movie mode activations produce exactly one single clear message with zero double questions."""
    mock_pc = MagicMock()
    mock_executor = MagicMock()
    mock_proj = MagicMock()
    mock_ac = MagicMock()
    mock_executor.projector_controller = mock_proj
    mock_executor.ac_controller = mock_ac

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc,
        planner_executor=mock_executor
    )

    res = engine.decide_and_act("movie mode")
    assert "Sir" in res.response_message
    # Must NOT have two question marks
    assert res.response_message.count("?") <= 1
    # Should cleanly say: Setting up movie mode, Sir.
    assert "movie mode" in res.response_message.lower()
