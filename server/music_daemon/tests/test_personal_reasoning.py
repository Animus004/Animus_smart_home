"""
================================================================================
ANIMUS SMART ROOM — PERSONAL SITUATIONAL REASONING TESTS (PHASE 2)
================================================================================
Validates:
1. Implicit Thermal/Climate Reasoning ("It's freezing" -> bumps AC from 20°C to 24°C).
2. Implicit Hot/Warm Reasoning ("Too warm in here" -> lowers AC to 22°C).
3. Wellbeing Respite Reasoning ("I have a bad headache" -> volume 10%, REST_AMBER, gentle response).
4. Contextual Routine Music during Work Hours (11:30 AM -> focus lofi at 15% volume).
5. Contextual Routine Music during Evening Routine (17:30 -> acoustic guitar chill).
6. Career & Project Mentorship Reasoning (Blinkit Dark Store SQL CTE & LAG() guidance).
7. Late-Night Quiet-Hours Conflict Arbitration (caps volume > 25% at night).
================================================================================
"""

import datetime
import tempfile
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.long_term_memory import LongTermMemoryStore
from agent.prompt_builder import CognitivePromptBuilder
from agent.agent_decision_engine import AgentDecisionEngine, AgentDecisionResult
from agent.personal_reasoner import PersonalReasoningEngine


@pytest.fixture
def temp_memory():
    """Provides an isolated LongTermMemoryStore with fresh temporary SQLite DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_personal_reasoning.db"
        store = LongTermMemoryStore(db_path=db_path)
        yield store


@pytest.fixture
def decision_engine(temp_memory):
    """Provides an AgentDecisionEngine with mocked hardware controllers."""
    mock_pc = MagicMock()
    mock_pc.launch_allowlisted_app.return_value = (True, "Launched")
    mock_pc.send_save_keystrokes.return_value = (True, {"any_files_modified": True})
    mock_pc.close_apps.return_value = (True, "Closed")
    mock_pc.get_active_work_context.return_value = {}

    engine = AgentDecisionEngine(
        memory_store=temp_memory,
        prompt_builder=CognitivePromptBuilder(memory_store=temp_memory),
        pc_controller=mock_pc
    )
    return engine


def test_implicit_cold_reasoning(decision_engine):
    """Proves that saying 'It's freezing in here' inspects current AC setpoint and raises it."""
    # Mock room state: AC is ON at 20°C
    room_state = {
        "ac": {
            "power": "ON",
            "target_temp_c": 20,
            "ambient_temp_c": 21.0,
            "mode": "COOL"
        }
    }

    res = decision_engine.decide_and_act("It's freezing in here", room_state=room_state)
    assert res.inference_source == "PERSONAL_SITUATIONAL_REASONING"
    assert "Sir" in res.response_message
    assert "20°C" in res.response_message
    assert "24°C" in res.response_message

    # Verify tool calls set temperature to 24°C
    temp_calls = [tc for tc in res.tool_calls if tc.get("tool") == "AC_SET_TEMPERATURE"]
    assert len(temp_calls) == 1
    assert temp_calls[0]["params"]["temperature"] == 24
    assert res.expression_payload is not None
    assert res.expression_payload.get("light_cue") == "CLIMATE_PULSE"


def test_implicit_hot_reasoning(decision_engine):
    """Proves that saying 'Too warm in here' inspects current AC setpoint and lowers it."""
    room_state = {
        "ac": {
            "power": "ON",
            "target_temp_c": 26,
            "ambient_temp_c": 27.5,
            "mode": "COOL"
        }
    }

    res = decision_engine.decide_and_act("Too warm in here", room_state=room_state, active_mode="WORK")
    assert res.inference_source == "PERSONAL_SITUATIONAL_REASONING"
    assert "Sir" in res.response_message
    assert "22°C" in res.response_message

    temp_calls = [tc for tc in res.tool_calls if tc.get("tool") == "AC_SET_TEMPERATURE"]
    assert len(temp_calls) == 1
    assert temp_calls[0]["params"]["temperature"] == 22


def test_wellbeing_headache_respite(decision_engine):
    """Proves that reporting a headache creates a low-sensory recovery environment."""
    res = decision_engine.decide_and_act("I have a bad headache today")
    assert res.inference_source == "PERSONAL_SITUATIONAL_REASONING"
    assert "Sir" in res.response_message
    assert "volume" in res.response_message.lower()

    # Tool calls should lower volume to 10
    vol_calls = [tc for tc in res.tool_calls if tc.get("tool") == "SET_VOLUME"]
    assert len(vol_calls) == 1
    assert vol_calls[0]["params"]["volume"] == 10

    # Expression should indicate REST_AMBER light cue
    assert res.expression_payload is not None
    assert res.expression_payload.get("light_cue") == "REST_AMBER"
    assert res.expression_payload.get("sound_cue") == "SILENT"


def test_contextual_music_work_hours(decision_engine):
    """Proves that ambiguous 'play something' at 11:30 AM chooses focus lofi at low volume."""
    # Fixed timestamp representing 11:30 AM local time today
    today_date = datetime.date.today()
    work_time = datetime.datetime.combine(today_date, datetime.time(11, 30, 0)).timestamp()

    with patch("time.time", return_value=work_time):
        res = decision_engine.decide_and_act("Play something", active_mode="WORK")
        assert res.inference_source == "PERSONAL_SITUATIONAL_REASONING"
        assert "lofi" in res.response_message.lower()
        assert "Sir" in res.response_message

        # Verify focus beats and 15% volume
        music_calls = [tc for tc in res.tool_calls if tc.get("tool") == "PLAY_MUSIC"]
        assert len(music_calls) == 1
        assert "lofi" in music_calls[0]["params"]["query"]

        vol_calls = [tc for tc in res.tool_calls if tc.get("tool") == "SET_VOLUME"]
        assert len(vol_calls) == 1
        assert vol_calls[0]["params"]["volume"] == 15

        assert res.expression_payload.get("light_cue") == "FOCUS_WARM"


def test_contextual_music_evening_routine(decision_engine):
    """Proves that ambiguous 'play something' at 5:30 PM chooses relaxed acoustic guitar chill."""
    today_date = datetime.date.today()
    evening_time = datetime.datetime.combine(today_date, datetime.time(17, 30, 0)).timestamp()

    with patch("time.time", return_value=evening_time):
        res = decision_engine.decide_and_act("Play something", active_mode="IDLE")
        assert res.inference_source == "PERSONAL_SITUATIONAL_REASONING"
        assert "acoustic" in res.response_message.lower() or "guitar" in res.response_message.lower()
        assert "Sir" in res.response_message

        music_calls = [tc for tc in res.tool_calls if tc.get("tool") == "PLAY_MUSIC"]
        assert len(music_calls) == 1
        assert "acoustic" in music_calls[0]["params"]["query"]

        assert res.expression_payload.get("light_cue") == "RELAX_AMBER"


def test_career_sql_mentorship(decision_engine):
    """Proves that reporting technical query hurdles triggers targeted Blinkit SQL mentorship."""
    res = decision_engine.decide_and_act("My query for the dark store stock-out duration isn't working")
    assert res.inference_source == "PERSONAL_SITUATIONAL_REASONING"
    assert "Sir" in res.response_message
    # Mentorship guidance must reference LAG() and dark store partitioning
    assert "lag()" in res.response_message.lower() or "lag" in res.response_message.lower()
    assert "dark store" in res.response_message.lower()
    assert res.expression_payload.get("light_cue") == "FOCUS_WARM"


def test_late_night_quiet_hours_volume_cap(decision_engine):
    """Proves that late-night volume requests (> 25%) are capped to 25% with polite notice."""
    today_date = datetime.date.today()
    night_time = datetime.datetime.combine(today_date, datetime.time(23, 30, 0)).timestamp()

    reasoner = decision_engine.personal_reasoner
    tool_calls = [{"tool": "SET_VOLUME", "params": {"volume": 75}}]
    msg = "Setting volume to 75%, Sir."

    sanitized, final_msg = reasoner.arbitrate_conflicts(
        tool_calls=tool_calls,
        response_message=msg,
        current_time=night_time
    )

    assert sanitized[0]["params"]["volume"] == 25
    assert "quiet hours" in final_msg.lower()
    assert "25%" in final_msg
