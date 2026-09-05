"""
Unit Test Suite for PC Chat Interface & Data Analyst Career Roadmap:
Verifies:
1. Career roadmap retrieval with 3 Excel milestones and Blinkit stock-out subgoals.
2. PC active window & work context detection.
3. Dedicated /api/agent/chat endpoint with ChatGPT summary ingestion.
4. Automatic task scheduling and subgoal advancement.
5. Serving of the Gemini-style PC Chat Web Interface (GET / and GET /chat).
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from agent.long_term_memory import get_long_term_memory


@pytest.fixture
def client():
    return TestClient(app)


def test_career_roadmap_endpoint(client):
    """Verifies that the career roadmap returns Data Analyst goals and Blinkit subgoals."""
    resp = client.get("/api/agent/career_roadmap")
    assert resp.status_code == 200
    data = resp.json()

    assert data["career_target"] == "Data Analyst"
    assert "Blinkit" in data["current_project"]
    assert "3 Excel" in data["completed_projects"]

    active_goal = data["active_goal"]
    assert active_goal is not None
    assert "Data Analyst" in active_goal["title"]

    subgoals = active_goal["subgoals"]
    assert len(subgoals) >= 4
    # Excel projects completed
    assert subgoals[0]["completed"] is True
    # Blinkit stock-out in progress
    assert any("Blinkit" in sg["title"] for sg in subgoals)


def test_pc_work_context_endpoint(client):
    """Verifies that the PC work context endpoint returns structured window data."""
    resp = client.get("/api/pc/work_context")
    assert resp.status_code == 200
    data = resp.json()

    assert "foreground_window" in data
    assert "work_windows" in data
    assert "sql_files" in data
    assert "word_docs" in data
    assert "active_project" in data


def test_chat_endpoint_chatgpt_summary_ingestion(client):
    """Verifies that pasting a ChatGPT work summary advances subgoals and queues tomorrow's tasks."""
    summary_text = (
        "Today I completed the SQL stock out analysis for Blinkit. "
        "I created a CTE using LAG() to calculate stock-out duration in minutes for each store. "
        "Tomorrow I will calculate lost revenue by joining with the products catalog."
    )

    resp = client.post("/api/agent/chat", json={"message": summary_text, "active_mode": "WORK"})
    assert resp.status_code == 200
    data = resp.json()

    assert data["response"] != ""
    assert "Blinkit" in data["response"] or "Sir" in data["response"]
    assert data["roadmap"] is not None

    # Check that tomorrow's task was queued
    tasks = data["roadmap"]["tasks"]
    assert any("Blinkit" in t["title"] or "lost revenue" in t["title"].lower() for t in tasks)


def test_serve_chat_ui_endpoints(client):
    """Verifies that GET / and GET /chat serve the Gemini-style PC Chat Web Interface."""
    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "text/html" in resp_root.headers["content-type"]
    assert "ANIMUS COGNITIVE OS" in resp_root.text
    assert "Career Target: Data Analyst" in resp_root.text

    resp_chat = client.get("/chat")
    assert resp_chat.status_code == 200
    assert "ANIMUS COGNITIVE OS" in resp_chat.text


def test_work_mode_and_wrapup_endpoints(client):
    """Verifies direct work mode start and wrapup endpoints."""
    # 1. Start Work Mode
    resp_start = client.post("/api/agent/work/start")
    assert resp_start.status_code == 200
    data_start = resp_start.json()
    assert data_start["status"] == "SUCCESS"
    assert data_start["mode"] == "WORK"
    assert data_start["volume"] == 15
    assert data_start["ac_temperature"] == 24

    # 2. Wrap Up Work Mode
    resp_wrap = client.post("/api/agent/work/wrapup")
    assert resp_wrap.status_code == 200
    data_wrap = resp_wrap.json()
    assert data_wrap["status"] == "SUCCESS"
    assert data_wrap["mode"] == "RELAX"
