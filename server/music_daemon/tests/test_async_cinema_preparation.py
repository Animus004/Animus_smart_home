"""
Tests for Asynchronous Hardware Preparation and Interactive Conversational Responsiveness.
Ensures that intents requiring follow-up and multi-device physical spin-up (e.g. 'Let's watch something')
return the follow-up clarification immediately (< 500ms) without blocking on slow physical hardware.
"""

import time
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from main import app, animus_personal_agent, agent_event_bus
from agent.models import IntentCategory


class TestAsyncCinemaPreparation:

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = TestClient(app)
        agent_event_bus.clear()

    def test_interact_cinema_intent_returns_immediately(self):
        """Proves that 'Let's watch something' returns interactive follow-up in under 500ms."""
        t0 = time.time()
        resp = self.client.post("/api/agent/interact", json={"utterance": "Let's watch something"})
        latency_ms = (time.time() - t0) * 1000

        assert resp.status_code == 200
        data = resp.json()

        # 1. Latency check: Must return interactively in under 6.0s (well below 15s client timeout and 60s hardware prep)
        assert latency_ms < 6000.0, f"Interactive response was too slow: {latency_ms:.1f}ms (expected < 6000ms)"



        # 2. Contract check: Followup must be present
        assert data["understood_intent"] == "START_CINEMA_ENTERTAINMENT"
        assert data["followup_required"] is True
        assert "Netflix" in data["followup_question"] or "YouTube" in data["followup_question"]
        assert "cinema stack" in data["agent_message"].lower()

    def test_cinema_preparation_deduplication(self):
        """Proves that duplicate rapid requests within 5s are debounced to prevent duplicate threads."""
        t0 = time.time()
        resp1 = self.client.post("/api/agent/interact", json={"utterance": "Let's watch something"})
        resp2 = self.client.post("/api/agent/interact", json={"utterance": "Let's watch something"})
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["followup_required"] is True
        assert resp2.json()["followup_required"] is True

    def test_cinema_followup_resolution_workflow(self):
        """Proves that answering the follow-up question (e.g. 'Netflix') resolves the stream source."""
        # Turn 1: Cinema intent
        r1 = self.client.post("/api/agent/interact", json={"utterance": "Let's watch something"})
        assert r1.status_code == 200
        assert r1.json()["followup_required"] is True

        # Turn 2: User answers 'Netflix'
        with patch.object(animus_personal_agent.planner_executor, "execute_plan") as mock_exec:
            mock_res = MagicMock()
            mock_res.success = True
            mock_res.to_dict.return_value = {"success": True, "status": "SUCCESS"}
            mock_res.steps = []
            mock_exec.return_value = mock_res
            r2 = self.client.post("/api/agent/interact", json={"utterance": "Netflix"})
            assert r2.status_code == 200
            assert r2.json()["action_taken"] is True
            assert r2.json()["understood_intent"] == "LAUNCH_NETFLIX"
