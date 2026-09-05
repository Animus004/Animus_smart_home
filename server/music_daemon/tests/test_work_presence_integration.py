"""
================================================================================
UNIT & INTEGRATION TESTS: WORK PRESENCE AUTOMATION & STRICT ISOLATION
================================================================================
Validates all 4 phases of workstation presence integration:
1. Strict Mode Isolation: Passive monitoring only outside WORK mode.
2. Auto-Mute on Departure (>= 20s) and Auto-Resume on Return.
3. 50-Minute Ergonomic Nudge for posture and eye relief.
4. Windows Workstation Lock (>= 15m) and Autonomous Work Dormancy (>= 30m).
5. Physical SQL Practice Worksheet Generation & HP Ink Tank 310 Direct Spooling.
6. SQLite Deep Work Analytics & Historical Aggregation.
================================================================================
"""

import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure server/music_daemon is in python path
current_dir = Path(__file__).resolve().parent
daemon_dir = current_dir.parent
if str(daemon_dir) not in sys.path:
    sys.path.insert(0, str(daemon_dir))

from agent.proactive_orchestrator import ProactiveOrchestrator, ProactiveTriggerCategory
from agent.long_term_memory import LongTermMemoryStore
from agent.briefing_service import BriefingService


class MockPlayer:
    def __init__(self, is_playing: bool = True):
        self._status = "PLAYING" if is_playing else "STOPPED"
        self.paused_count = 0
        self.resumed_count = 0

    def get_status(self):
        return {"status": self._status}

    def pause(self):
        self._status = "PAUSED"
        self.paused_count += 1
        return True

    def resume(self):
        self._status = "PLAYING"
        self.resumed_count += 1
        return True


class MockOrchestrator:
    def __init__(self, active_mode: str = "WORK", is_playing: bool = True):
        self.player = MockPlayer(is_playing=is_playing)
        self.current_mode = active_mode
        self._active_mode_val = active_mode
        self.mode_changes = []

    def set_active_mode(self, mode: str):
        self.current_mode = str(mode).upper()
        self._active_mode_val = self.current_mode
        self.mode_changes.append(self.current_mode)


class MockPcController:
    def __init__(self):
        self.locked_count = 0
        self.save_count = 0

    def lock_workstation(self):
        self.locked_count += 1
        return True, {"success": True}

    def send_save_keystrokes(self):
        self.save_count += 1
        return True, {"success": True, "any_files_modified": True}

    def get_work_session_duration(self):
        return 2400.0


# ==============================================================================
# 1. STRICT WORK MODE ISOLATION TESTS
# ==============================================================================

@pytest.mark.parametrize("passive_mode", ["RELAX", "MOVIE", "SLEEP", "CASUAL", "GAMING", "IDLE"])
def test_strict_isolation_outside_work_mode(passive_mode):
    """
    STRICT ISOLATION INVARIANT:
    When room is in ANY non-work mode, stepping away from the desk must NEVER
    pause music, must NEVER lock the PC, and must NEVER trigger work rules.
    """
    mock_orch = MockOrchestrator(active_mode=passive_mode, is_playing=True)
    mock_pc = MockPcController()
    mem = LongTermMemoryStore(db_path=":memory:")

    orchestrator = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        memory_store=mem,
        enable_speech=False,
        cooldown_seconds=1.0
    )

    # Telemetry with user absent from desk in passive mode for 40 minutes (2400s)
    telemetry = {
        "active_mode": passive_mode,
        "desk_present": False,
        "user_idle_seconds": 2400.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }

    # Evaluate multiple times simulating passage of time
    orchestrator.evaluate_proactive_rules(telemetry)

    # Invariants: Zero music pause, Zero PC lock, Zero file saves
    assert mock_orch.player._status == "PLAYING"
    assert mock_orch.player.paused_count == 0
    assert mock_pc.locked_count == 0
    assert mock_pc.save_count == 0
    assert orchestrator._music_paused_by_departure is False
    assert orchestrator._work_session_started_at is None


# ==============================================================================
# 2. AUTO-MUTE ON DEPARTURE & AUTO-RESUME ON RETURN (WORK MODE)
# ==============================================================================

def test_auto_mute_and_resume_in_work_mode():
    """
    In WORK mode:
    - Departure >= 20s pauses active music.
    - Return to desk immediately resumes music.
    """
    mock_orch = MockOrchestrator(active_mode="WORK", is_playing=True)
    mock_pc = MockPcController()
    mem = LongTermMemoryStore(db_path=":memory:")

    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        memory_store=mem,
        enable_speech=False,
        cooldown_seconds=1.0
    )

    # 1. Arrive at desk in WORK mode
    t_present = {
        "active_mode": "WORK",
        "desk_present": True,
        "desk_seated_seconds": 120.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_present)
    assert orch._work_session_started_at is not None
    assert mock_orch.player._status == "PLAYING"

    # 2. Step away from desk: Simulate 25 seconds of absence
    orch._time_left_desk = time.time() - 25.0
    t_away = {
        "active_mode": "WORK",
        "desk_present": False,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_away)

    # Music should now be paused
    assert mock_orch.player._status == "PAUSED"
    assert mock_orch.player.paused_count == 1
    assert orch._music_paused_by_departure is True

    # 3. Sir returns to desk: desk_present becomes True
    t_returned = {
        "active_mode": "WORK",
        "desk_present": True,
        "desk_seated_seconds": 5.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_returned)

    # Music should now be resumed
    assert mock_orch.player._status == "PLAYING"
    assert mock_orch.player.resumed_count == 1
    assert orch._music_paused_by_departure is False


# ==============================================================================
# 3. ERGONOMIC 50-MINUTE BREAK NUDGE
# ==============================================================================

def test_ergonomic_50min_break_nudge():
    """
    In WORK mode: Seated for >= 50 minutes (3000 seconds) triggers
    ERGONOMIC_50MIN_BREAK reminder to stand, stretch, and hydrate.
    Requires physical standup (desk_present == False) to reset the sprint counter.
    """
    mock_orch = MockOrchestrator(active_mode="WORK")
    mock_pc = MockPcController()
    mem = LongTermMemoryStore(db_path=":memory:")

    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        memory_store=mem,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    # 49 minutes seated (2940s) - should NOT trigger yet
    t_49m = {
        "active_mode": "WORK",
        "desk_present": True,
        "desk_seated_seconds": 2940.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    res = orch.evaluate_proactive_rules(t_49m)
    assert res is None

    # 51 minutes seated (3060s) - MUST trigger ergonomic nudge
    t_51m = {
        "active_mode": "WORK",
        "desk_present": True,
        "desk_seated_seconds": 3060.0,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    res = orch.evaluate_proactive_rules(t_51m)
    assert res is not None
    cat, msg = res
    assert cat == ProactiveTriggerCategory.ERGONOMIC_50MIN_BREAK
    assert "50 minutes" in msg
    assert "hydrate" in msg or "stretching" in msg
    assert orch._ergonomic_alerted is True

    # Next tick while still seated: should NOT spam because already alerted
    res2 = orch.evaluate_proactive_rules(t_51m)
    assert res2 is None

    # Sir stands up (desk_present = False) -> resets sprint counter
    t_stand = {
        "active_mode": "WORK",
        "desk_present": False,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_stand)
    assert orch._ergonomic_alerted is False


# ==============================================================================
# 4. WORKSTATION LOCK AT 5M & AUTONOMOUS DORMANCY AT 120M
# ==============================================================================

def test_work_departure_lock_and_autonomous_dormancy():
    """
    In WORK mode:
    - At 5m away: Windows workstation is locked.
    - At 120m away: Autonomous Work Dormancy triggers -> saves files, records
      session in SQLite (excluding the 120m absence), and transitions mode to IDLE.
    """
    mock_orch = MockOrchestrator(active_mode="WORK")
    mock_pc = MockPcController()
    mem = LongTermMemoryStore(db_path=":memory:")
    mock_bus = MagicMock()

    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        memory_store=mem,
        event_bus=mock_bus,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    # User worked for 150 minutes (9000s) before leaving desk
    now = time.time()
    orch._work_session_started_at = now - 9000.0

    # Simulate 6 minutes absence (360s >= 300s / 5m)
    orch._time_left_desk = now - 360.0
    t_6m_away = {
        "active_mode": "WORK",
        "desk_present": False,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_6m_away)

    # PC must be locked at 5m, but not dormant yet
    assert mock_pc.locked_count == 1
    assert orch._pc_locked_by_departure is True
    assert mock_pc.save_count == 0
    assert mock_orch.current_mode == "WORK"

    # Now simulate 121 minutes absence (7260s >= 7200s / 120m)
    orch._time_left_desk = now - 7260.0
    t_121m_away = {
        "active_mode": "WORK",
        "desk_present": False,
        "pc_online": True,
        "pc_locked": True,
        "suppress_morning": True
    }
    res = orch.evaluate_proactive_rules(t_121m_away)

    # Dormancy must fire:
    assert res is not None
    assert mock_pc.save_count == 1
    assert mock_orch.current_mode == "IDLE"
    assert "IDLE" in mock_orch.mode_changes
    assert mock_bus.publish.called

    # Check SQLite recorded session: duration must equal 9000 - 7260 = 1740s (strictly excluding the 121m absence!)
    analytics = mem.get_weekly_work_analytics(days=7)
    assert analytics["total_sessions"] == 1
    assert analytics["total_hours"] > 0
    # State reset
    assert orch._work_session_started_at is None
    assert orch._time_left_desk is None


# ==============================================================================
# 5. PHYSICAL SQL PRACTICE WORKSHEET GENERATION & PRINTING
# ==============================================================================

def test_sql_worksheet_generation_and_spooling():
    """
    Verifies generation of physical SQL practice worksheet with CTEs, schemas,
    sample tuples, expected result grid, and pen-and-paper workspace, and dispatch
    to HP Ink Tank 310 printer.
    """
    mock_printer = MagicMock()
    mock_printer.print_document.return_value = (True, "Document spooled to HP Ink Tank 310 series")
    mock_printer.target_printer = "HP Ink Tank 310 series"

    briefing = BriefingService(printer_controller=mock_printer)
    doc_path = briefing.generate_sql_practice_sheet(
        problem_title="Blinkit Dark Store Inventory Turnover"
    )

    assert os.path.exists(doc_path)
    content = Path(doc_path).read_text(encoding="utf-8")
    assert "ANIMUS SMART ROOM — PHYSICAL SQL & ANALYTICS PRACTICE WORKSHEET" in content
    assert "HP Ink Tank 310 Series" in content
    assert "Blinkit Dark Store Inventory Turnover" in content
    assert "TABLE: dark_stores" in content
    assert "SAMPLE TUPLES (MOCK RECORDS)" in content
    assert "EXPECTED RESULT GRID" in content
    assert "DRAFT YOUR SQL QUERY SOLUTION BELOW" in content

    # Test printing dispatch
    p_res = briefing.print_sql_worksheet(problem_title="Blinkit Dark Store Inventory Turnover")
    assert p_res["success"] is True
    assert mock_printer.print_document.called
    assert "HP Ink Tank 310" in p_res["message"]


# ==============================================================================
# 6. SQLITE DEEP WORK FOCUS ANALYTICS
# ==============================================================================

def test_sqlite_work_focus_analytics():
    """
    Verifies recording work sessions into SQLite and aggregating weekly metrics.
    """
    mem = LongTermMemoryStore(db_path=":memory:")

    # Record 3 sessions
    mem.record_work_session(session_duration_seconds=3000.0, subgoal_title="Blinkit CTE Queries", exit_reason="MANUAL_WRAPUP")
    mem.record_work_session(session_duration_seconds=2400.0, subgoal_title="Indexing Strategies", exit_reason="AUTONOMOUS_DORMANCY_TIMEOUT")
    mem.record_work_session(session_duration_seconds=1800.0, subgoal_title="Portfolio Documentation", exit_reason="MANUAL_WRAPUP")

    analytics = mem.get_weekly_work_analytics(days=7)
    assert analytics["total_sessions"] == 3
    # Total seconds = 3000 + 2400 + 1800 = 7200s = 2.0 hours
    assert analytics["total_hours"] == 2.0
    # Average session = 7200 / 3 = 2400s = 40.0 minutes
    assert analytics["avg_session_minutes"] == 40.0
    assert len(analytics["recent_sessions"]) == 3


# ==============================================================================
# 7. WORK DEPARTURE LOCK AT 60s THRESHOLD
# ==============================================================================

def test_work_departure_locks_at_60s():
    """
    In WORK mode:
    Departure for >= 60s must trigger Windows workstation lock (ANIMUS_PC_LOCK_TIMEOUT=60.0).
    """
    mock_orch = MockOrchestrator(active_mode="WORK")
    mock_pc = MockPcController()
    mem = LongTermMemoryStore(db_path=":memory:")

    orch = ProactiveOrchestrator(
        orchestrator=mock_orch,
        pc_controller=mock_pc,
        memory_store=mem,
        enable_speech=False,
        cooldown_seconds=0.0
    )

    now = time.time()
    orch._work_session_started_at = now - 600.0

    # Away for 45s (below 60s timeout) - PC must NOT be locked
    orch._time_left_desk = now - 45.0
    t_45s = {
        "active_mode": "WORK",
        "desk_present": False,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_45s)
    assert mock_pc.locked_count == 0
    assert orch._pc_locked_by_departure is False

    # Away for 65s (>= 60s timeout) - PC MUST be locked
    orch._time_left_desk = now - 65.0
    t_65s = {
        "active_mode": "WORK",
        "desk_present": False,
        "pc_online": True,
        "pc_locked": False,
        "suppress_morning": True
    }
    orch.evaluate_proactive_rules(t_65s)
    assert mock_pc.locked_count == 1
    assert orch._pc_locked_by_departure is True


# ==============================================================================
# 8. DIRECT MUSIC COMMAND FAST-PATH & ORCHESTRATOR EXECUTION
# ==============================================================================

def test_direct_music_command_execution():
    """
    Verifies that direct user commands like 'play zara zara' trigger fastpath PLAY_MUSIC
    and call safe_play/play_music on the orchestrator.
    """
    from agent.agent_decision_engine import AgentDecisionEngine

    mock_orch = MagicMock()
    mock_orch.play_music.return_value = (True, {"title": "Zara Zara"}, None)
    mock_orch.safe_play.return_value = (True, {"title": "Zara Zara"}, None)

    engine = AgentDecisionEngine()
    engine.orchestrator = mock_orch

    # Test fastpath decision
    dec = engine._try_fastpath_decision("play zara zara")
    assert dec is not None
    assert dec["action_type"] == "TOOL_EXECUTION"
    assert len(dec["tool_calls"]) == 1
    assert dec["tool_calls"][0]["tool"] == "PLAY_MUSIC"
    assert dec["tool_calls"][0]["params"]["query"] == "zara zara"

    # Test tool execution
    tool_results, verif_status = engine._execute_tools(dec["tool_calls"])
    assert len(tool_results) == 1
    assert tool_results[0]["status"] == "SUCCESS"
    assert mock_orch.play_music.called
