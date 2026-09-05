"""
================================================================================
ANIMUS SMART ROOM — EXECUTIVE BRIEFING & PRINTABLE SHEET TESTS
================================================================================
Tests:
1. Executive Morning Briefing synthesis with active Blinkit SQL milestone.
2. Executive Nightly Debrief synthesis with guitar practice cue.
3. Plain-text printable briefing sheet generation with checklists.
4. Print dispatch integration with PrinterController.
================================================================================
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from agent.briefing_service import BriefingService
from agent.long_term_memory import LongTermMemoryStore
from printer_controller import PrinterController


@pytest.fixture
def temp_memory():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_briefing.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


def test_morning_briefing_synthesis_with_active_milestone(temp_memory):
    mock_tm = MagicMock()
    mock_task1 = MagicMock()
    mock_task1.title = "Optimize Blinkit SQL join queries"
    mock_task2 = MagicMock()
    mock_task2.title = "Review product portfolio metrics"
    mock_tm.get_pending_tasks.return_value = [mock_task1, mock_task2]

    bs = BriefingService(memory_store=temp_memory, task_manager=mock_tm)

    curr_sg = temp_memory.get_current_work_subgoal()
    assert curr_sg is not None
    sg_title = curr_sg["title"]

    weather = {"outdoor_temperature_c": 28, "condition": "Sunny"}
    brief = bs.generate_morning_briefing(weather_info=weather)

    assert "Good morning, Sir!" in brief
    assert sg_title in brief
    assert "Optimize Blinkit SQL join queries" in brief
    assert "28°C" in brief
    assert "HP Ink Tank 310" in brief
    assert "5:30 PM" in brief


def test_nightly_debrief_synthesis(temp_memory):
    mock_tm = MagicMock()
    mock_task = MagicMock()
    mock_task.title = "Review query execution plan"
    mock_tm.get_pending_tasks.return_value = [mock_task]

    bs = BriefingService(memory_store=temp_memory, task_manager=mock_tm)
    debrief = bs.generate_nightly_debrief()

    assert "Good evening, Sir!" in debrief
    assert "1 task(s) queued for tomorrow" in debrief
    assert "guitar practice" in debrief.lower()
    assert "HP Ink Tank 310" in debrief


def test_executive_printable_sheet_generation(temp_memory):
    mock_tm = MagicMock()
    mock_task = MagicMock()
    mock_task.title = "Blinkit lost revenue indexing problem"
    mock_task.priority = "HIGH"
    mock_tm.get_pending_tasks.return_value = [mock_task]

    bs = BriefingService(memory_store=temp_memory, task_manager=mock_tm)
    file_path = bs.generate_executive_printable_sheet(sheet_type="MORNING_PLAN")

    assert os.path.exists(file_path)
    content = Path(file_path).read_text(encoding="utf-8")

    assert "ANIMUS EXECUTIVE DAILY BRIEFING SHEET" in content
    assert "Sayantan Roy (Sir)" in content
    assert "Blinkit lost revenue indexing problem" in content
    assert "[ ]" in content
    assert "HP INK TANK 310" in content

    # Clean up generated file
    try:
        os.remove(file_path)
    except Exception:
        pass


def test_print_dispatch_to_simulated_printer(temp_memory):
    mock_printer = PrinterController(is_simulated=True)
    bs = BriefingService(memory_store=temp_memory, printer_controller=mock_printer)

    res = bs.print_executive_sheet(sheet_type="MORNING_PLAN")
    assert res["success"] is True
    assert res["target_printer"] == "HP Ink Tank 310 series"
    assert os.path.exists(res["file_path"])

    # Clean up
    try:
        os.remove(res["file_path"])
    except Exception:
        pass
