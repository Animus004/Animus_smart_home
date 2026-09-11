"""
================================================================================
ANIMUS SMART ROOM — VISUAL PRESENCE & EXECUTIVE BRIEFING INTEGRATION TESTS
================================================================================
Tests:
1. Physical desk presence (desk_present=True) triggers Morning Executive Briefing.
2. Conversational follow-up: "print it" dispatches print job to HP Ink Tank 310.
3. Conversational follow-up: "play music" routes soundbar to PC and plays focus music.
4. Conversational follow-up: rejection maintains quiet state respectfully.
5. Evening Debrief trigger and guitar practice conversational transition.
================================================================================
"""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder
from agent.agent_decision_engine import AgentDecisionEngine
from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory
from event_bus import AgentEventBus


@pytest.fixture
def temp_memory():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_visual_proactivity.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


def test_desk_presence_triggers_morning_briefing(temp_memory):
    """
    Proves that visual desk presence (desk_present=True) triggers the morning
    greeting even if the PC was locked or idle.
    """
    mock_tts = MagicMock()
    mock_pc = MagicMock()
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

    curr_sg = temp_memory.get_current_work_subgoal()
    assert curr_sg is not None
    sg_title = curr_sg["title"]

    # Telemetry: PC is locked and idle, but camera detects user at desk!
    telemetry = {
        "hour": 9,
        "pc_online": True,
        "pc_locked": True,
        "user_idle_seconds": 500.0,
        "desk_present": True,  # Visual presence from USB HD camera
        "ac_ambient_temp": 24,
        "suppress_morning": False
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.MORNING_GREETING
    assert "Good morning, Sir!" in msg
    assert sg_title in msg
    assert "HP Ink Tank 310" in msg
    assert mock_tts.speak.called

    # Verify staged in decision engine
    assert engine._proactive_followup_state is not None
    assert engine._proactive_followup_state["category"] == ProactiveTriggerCategory.MORNING_GREETING


def test_morning_briefing_affirmative_print_followup(temp_memory):
    """
    Proves that Sir replying "yes, print it" invokes the PRINTER_PRINT_FILE tool.
    """
    mock_pc = MagicMock()
    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    # Stage proactive morning briefing follow-up
    engine.set_pending_proactive_followup(
        category=ProactiveTriggerCategory.MORNING_GREETING,
        followup_context="PROACTIVE_MORNING_BRIEFING",
        message="Good morning, Sir! Shall I print your daily plan on the HP Ink Tank 310?"
    )

    # Sir replies affirmatively for printing
    res = engine.decide_and_act("yes please, print the plan")
    assert "Sir" in res.response_message
    assert "Printing your daily executive plan on the HP Ink Tank 310" in res.response_message

    # Verify tool calls executed
    assert len(res.tool_calls) >= 1
    assert any("PRINT" in tc.get("tool", "") for tc in res.tool_calls)

    # Verify state cleared
    assert engine._proactive_followup_state is None


def test_morning_briefing_music_followup(temp_memory):
    """
    Proves that Sir replying "start music" invokes soundbar and music playback tools.
    """
    mock_pc = MagicMock()
    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    # Stage proactive morning briefing follow-up
    engine.set_pending_proactive_followup(
        category=ProactiveTriggerCategory.MORNING_GREETING,
        followup_context="PROACTIVE_MORNING_BRIEFING",
        message="Good morning, Sir! Shall I start your morning playlist?"
    )

    # Sir requests music
    res = engine.decide_and_act("play morning focus playlist")
    assert "Sir" in res.response_message
    assert "Starting your morning focus playlist" in res.response_message
    assert any("PC_MEDIA_PLAY" in tc.get("tool", "") or "SOUNDBAR" in tc.get("tool", "") for tc in res.tool_calls)


def test_morning_briefing_rejection_maintains_quiet(temp_memory):
    """
    Proves that Sir declining the morning prompt maintains quiet state without actions.
    """
    mock_pc = MagicMock()
    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    engine.set_pending_proactive_followup(
        category=ProactiveTriggerCategory.MORNING_GREETING,
        followup_context="PROACTIVE_MORNING_BRIEFING",
        message="Good morning, Sir! Shall I start your morning playlist?"
    )

    res = engine.decide_and_act("no, not now")
    assert "Sir" in res.response_message
    assert len(res.tool_calls) == 0
    assert engine._proactive_followup_state is None


def test_evening_debrief_trigger_and_guitar_followup(temp_memory):
    """
    Proves that evening debrief triggers and Sir replying 'guitar' transitions the room.
    """
    mock_tts = MagicMock()
    mock_pc = MagicMock()
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

    # Evening telemetry at 18:00
    telemetry = {
        "hour": 18,
        "pc_online": True,
        "desk_present": True,
        "suppress_morning": True
    }

    res = orch.evaluate_proactive_rules(telemetry=telemetry)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.EVENING_DEBRIEF
    assert "Good evening, Sir." in msg
    assert "guitar practice session" in msg

    # Sir replies asking to practice guitar
    reply_res = engine.decide_and_act("yes, setting up for guitar practice")
    assert "Sir" in reply_res.response_message
    assert "guitar" in reply_res.response_message.lower()
    assert any("SET_ACTIVE_MODE" in tc.get("tool", "") for tc in reply_res.tool_calls)


def test_explicit_song_playback_bypasses_evening_debrief(temp_memory):
    """
    Regression test: Proves that when an evening debrief is staged,
    an explicit music playback command (e.g. 'play ki name deke ami bolbo tomake')
    supersedes the debrief, does NOT invoke the printer or guitar tools,
    and cleanly plays the requested song.
    """
    mock_pc = MagicMock()
    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    # Stage evening debrief
    engine.set_pending_proactive_followup(
        category=ProactiveTriggerCategory.EVENING_DEBRIEF,
        followup_context="PROACTIVE_EVENING_DEBRIEF",
        message="Good evening, Sir. Shall I print tomorrow's checklist on the HP Ink Tank 310, and cue your guitar practice session?"
    )

    # User issues a song playback command
    reply_res = engine.decide_and_act("play ki name deke ami bolbo tomake")
    assert "Sir" in reply_res.response_message
    assert "ki name deke ami bolbo tomake" in reply_res.response_message
    # Proves HP Ink Tank 310 printer was NOT triggered
    assert not any("PRINTER" in tc.get("tool", "") for tc in reply_res.tool_calls)
    assert not any("PRINT" in tc.get("tool", "") for tc in reply_res.tool_calls)
    # Proves media play was dispatched
    assert any(tc.get("tool", "") in ["PLAY_MUSIC", "PC_MEDIA_PLAY"] for tc in reply_res.tool_calls)
    # Proves proactive debrief state was cleared
    assert engine._proactive_followup_state is None

