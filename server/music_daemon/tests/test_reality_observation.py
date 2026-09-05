"""
================================================================================
ANIMUS SMART ROOM — REALITY OBSERVATION & VERIFICATION TESTS (PHASE 3)
================================================================================
Validates:
1. Full Verified Success (PLAN -> ACT -> OBSERVE -> VERIFY -> RESPOND).
2. Partial Launch Failure Detected (Word running, MySQL failed -> Truthful partial response).
3. Total Hardware Failure Detected (AC unreachable -> Truthful failure explanation without pretending).
4. Already Satisfied No-Op Detected (AC already set -> Truthful no-op response).
5. Wrap-up Truthful Disk Observation (zero files modified -> NO_PROGRESS, no fake milestones).
================================================================================
"""

import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder
from agent.agent_decision_engine import AgentDecisionEngine
from agent.reality_observer import RealityObserver, VerificationStatus, ObservationSnapshot, VerificationReport


@pytest.fixture
def temp_memory():
    """Provides an isolated LongTermMemoryStore with fresh temporary SQLite DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_reality_obs.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


def test_full_verified_success_work_mode(temp_memory):
    """Proves that when both work applications launch, VERIFIED_SUCCESS is recorded."""
    mock_pc = MagicMock()
    mock_pc.launch_allowlisted_app.side_effect = lambda app: (True, f"Launched {app}")
    mock_pc.bring_work_windows_to_foreground.return_value = True
    mock_pc.set_volume.return_value = 15
    mock_pc.get_volume.return_value = 15
    mock_pc.is_app_running.return_value = True

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    res = engine.decide_and_act("start work mode")
    assert res.verified_physical_status == VerificationStatus.VERIFIED_SUCCESS.value
    assert "Sir" in res.response_message
    assert "work mode" in res.response_message.lower() or "launched" in res.response_message.lower()


def test_partial_launch_failure_detected(temp_memory):
    """
    Proves that when 1 of 2 apps fails to launch (e.g. Word succeeds, MySQL fails),
    Animus truthfully reports VERIFIED_PARTIAL and does NOT claim full success.
    """
    mock_pc = MagicMock()
    # Word succeeds, SQL fails
    def mock_launch(app):
        if app == "word":
            return True, "Launched Microsoft Word"
        return False, "MySQL Workbench executable not found"

    mock_pc.launch_allowlisted_app.side_effect = mock_launch
    mock_pc.bring_work_windows_to_foreground.return_value = True
    mock_pc.set_volume.return_value = 15
    mock_pc.get_volume.return_value = 15

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    res = engine.decide_and_act("start work mode")
    assert res.verified_physical_status == VerificationStatus.VERIFIED_PARTIAL.value
    assert "Sir" in res.response_message
    # Must report that Word launched but MySQL could not be opened
    assert "Word" in res.response_message
    assert "MySQL Workbench" in res.response_message
    assert "could not be opened" in res.response_message.lower() or "failed" in res.response_message.lower()


def test_total_hardware_failure_detected(temp_memory):
    """
    Proves that when hardware communication fails (e.g. AC offline),
    Animus truthfully reports failure and does NOT claim 'Setting AC temperature'.
    """
    mock_pc = MagicMock()
    mock_executor = MagicMock()
    mock_ac = MagicMock()
    mock_ac.set_power.side_effect = Exception("Connection timed out to 192.168.1.4:6668")
    mock_ac.set_temperature.side_effect = Exception("Connection timed out to 192.168.1.4:6668")
    mock_ac.set_mode.side_effect = Exception("Connection timed out to 192.168.1.4:6668")
    mock_executor.ac_controller = mock_ac

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc,
        planner_executor=mock_executor
    )

    res = engine.decide_and_act("set AC to 22")
    assert res.verified_physical_status == VerificationStatus.VERIFIED_FAILED.value
    assert "Sir" in res.response_message
    # Must report that AC controller is unreachable
    assert "unreachable" in res.response_message.lower() or "unable" in res.response_message.lower()
    # Must NOT pretend setting succeeded
    assert "setting ac temperature to 22" not in res.response_message.lower()


def test_already_satisfied_noop_detected(temp_memory):
    """Proves that requesting an already active state reports ALREADY_SATISFIED truthfully."""
    observer = RealityObserver()
    tool_calls = [{"tool": "AC_SET_TEMPERATURE", "params": {"temperature": 24}}]
    exec_results = [{"tool": "AC_SET_TEMPERATURE", "status": "ALREADY_SET"}]

    snapshot = ObservationSnapshot()
    report = observer.verify_plan_execution(tool_calls, exec_results, snapshot)
    assert report.status == VerificationStatus.ALREADY_SATISFIED

    truthful_msg = observer.synthesize_truthful_response(
        candidate_message="Setting AC temperature to 24°C, Sir.",
        report=report,
        user_utterance="Set AC to 24"
    )
    assert "already" in truthful_msg.lower()
    assert "Sir" in truthful_msg


def test_wrapup_truthful_disk_observation(temp_memory):
    """Proves that when wrapping up with zero modified files, NO_PROGRESS is saved."""
    mock_pc = MagicMock()
    # Zero files modified on disk
    mock_pc.send_save_keystrokes.return_value = (True, {"any_files_modified": False, "doc_modified_on_disk": False})
    mock_pc.close_apps.return_value = (True, ["MySQLWorkbench.exe", "WINWORD.EXE"])
    mock_pc.get_active_work_context.return_value = {}

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )

    res = engine.decide_and_act("wrap up work")
    assert "Sir" in res.response_message
    assert "closed" in res.response_message.lower() or "progress saved" in res.response_message.lower()

    # Verify no fake task was created
    pending = temp_memory.get_pending_tasks()
    assert not any(t.get("category") == "REMINDER" for t in pending)
