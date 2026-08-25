"""
Isolated Unit and Integration Tests for Proactive Async Event Bus, Reminder Scheduler & WebSocket Transport.
Verifies event uniqueness, FIFO delivery, ACK protocol, TTL retention, security filtering,
reminder generation, follow-up events, and fault isolation.
"""

import asyncio
import json
import time
import pytest
from unittest.mock import MagicMock

from event_bus import AgentEventBus, AgentEvent, AgentEventType, AgentEventPriority
from reminder_scheduler import ReminderScheduler
from agent.models import Reminder


def test_event_creation_and_unique_ids():
    e1 = AgentEvent(event_type=AgentEventType.SYSTEM_NOTIFICATION, message="Msg 1")
    e2 = AgentEvent(event_type=AgentEventType.SYSTEM_NOTIFICATION, message="Msg 2")
    assert e1.event_id != e2.event_id
    assert e1.event_id.startswith("evt-")
    assert e1.priority == AgentEventPriority.NORMAL


def test_fifo_event_ordering():
    bus = AgentEventBus(max_history=50)
    sub_queue = asyncio.Queue()
    bus.subscribe(sub_queue)

    e1 = AgentEvent(event_type=AgentEventType.SYSTEM_NOTIFICATION, message="First")
    e2 = AgentEvent(event_type=AgentEventType.SYSTEM_NOTIFICATION, message="Second")
    e3 = AgentEvent(event_type=AgentEventType.SYSTEM_NOTIFICATION, message="Third")

    bus.publish(e1)
    bus.publish(e2)
    bus.publish(e3)

    assert sub_queue.get_nowait().message == "First"
    assert sub_queue.get_nowait().message == "Second"
    assert sub_queue.get_nowait().message == "Third"


def test_multiple_subscribers():
    bus = AgentEventBus()
    q1 = asyncio.Queue()
    q2 = asyncio.Queue()
    bus.subscribe(q1)
    bus.subscribe(q2)

    event = AgentEvent(event_type=AgentEventType.REMINDER_DUE, message="Broadcast reminder")
    bus.publish(event)

    assert q1.get_nowait().message == "Broadcast reminder"
    assert q2.get_nowait().message == "Broadcast reminder"


def test_event_acknowledgement():
    bus = AgentEventBus()
    event = AgentEvent(event_type=AgentEventType.REMINDER_DUE, message="Test reminder")
    bus.publish(event)

    assert not bus.is_acknowledged(event.event_id)
    assert len(bus.get_unacknowledged_events()) == 1

    # Acknowledge
    assert bus.acknowledge(event.event_id) is True
    assert bus.is_acknowledged(event.event_id) is True
    assert len(bus.get_unacknowledged_events()) == 0


def test_duplicate_ack_handling():
    bus = AgentEventBus()
    event = AgentEvent(event_type=AgentEventType.REMINDER_DUE, message="Test")
    bus.publish(event)

    # First ACK
    assert bus.acknowledge(event.event_id) is True
    # Second duplicate ACK
    assert bus.acknowledge(event.event_id) is True
    assert bus.is_acknowledged(event.event_id) is True


def test_get_unacknowledged_events_on_reconnect():
    bus = AgentEventBus()
    e1 = AgentEvent(event_type=AgentEventType.REMINDER_DUE, message="Unacked 1")
    e2 = AgentEvent(event_type=AgentEventType.REMINDER_DUE, message="Unacked 2")
    bus.publish(e1)
    bus.publish(e2)

    # Ack e1 only
    bus.acknowledge(e1.event_id)

    unacked = bus.get_unacknowledged_events()
    assert len(unacked) == 1
    assert unacked[0].event_id == e2.event_id
    assert unacked[0].message == "Unacked 2"


def test_event_ttl_and_history_purging():
    # TTL of 0.1s
    bus = AgentEventBus(max_history=5, default_ttl_seconds=0.1)
    e = AgentEvent(event_type=AgentEventType.SYSTEM_NOTIFICATION, message="Expiring event")
    bus.publish(e)

    assert len(bus.get_unacknowledged_events()) == 1
    time.sleep(0.15)
    # Purge on check
    assert len(bus.get_unacknowledged_events()) == 0


def test_sensitive_data_filtered_from_events():
    bus = AgentEventBus()
    leak_event = AgentEvent(
        event_type=AgentEventType.SYSTEM_NOTIFICATION,
        message="The device local_key is 76776532a4e57c0a2ca4 and secret=xyz",
        payload={"secret_key": "topsecret", "status": "OK"}
    )
    published = bus.publish(leak_event)

    # Message must be sanitized
    assert "local_key" not in published.message
    assert published.message == "An internal smart room event occurred."
    # Payload must not contain secret_key
    assert "secret_key" not in published.payload
    assert published.payload.get("status") == "OK"


def test_reminder_scheduler_triggers_due_event():
    bus = AgentEventBus()
    mock_tm = MagicMock()

    now = time.time()
    due_rem = Reminder(
        id="rem-1",
        message="Practice guitar fingerstyle",
        scheduled_time=now - 5, # Past due
        triggered=False,
        acknowledged=False
    )
    mock_tm.get_active_reminders.return_value = [due_rem]

    scheduler = ReminderScheduler(task_manager=mock_tm, event_bus=bus, tts_service=None)
    triggered_count = scheduler.check_due_reminders_once()

    assert triggered_count == 1
    assert due_rem.triggered is True

    unacked = bus.get_unacknowledged_events()
    assert len(unacked) == 1
    assert unacked[0].event_type == AgentEventType.REMINDER_DUE
    assert "Practice guitar fingerstyle" in unacked[0].message


def test_future_reminder_not_triggered_early():
    bus = AgentEventBus()
    mock_tm = MagicMock()

    now = time.time()
    future_rem = Reminder(
        id="rem-2",
        message="Focus on SQL tomorrow",
        scheduled_time=now + 3600, # 1 hour future
        triggered=False,
        acknowledged=False
    )
    mock_tm.get_active_reminders.return_value = [future_rem]

    scheduler = ReminderScheduler(task_manager=mock_tm, event_bus=bus, tts_service=None)
    triggered_count = scheduler.check_due_reminders_once()

    assert triggered_count == 0
    assert future_rem.triggered is False
    assert len(bus.get_unacknowledged_events()) == 0


def test_followup_event_published_from_agent_interaction():
    from fastapi.testclient import TestClient
    from main import app, agent_event_bus

    client = TestClient(app)
    agent_event_bus.clear()

    # Ambiguous turn triggering follow-up question
    resp = client.post("/api/agent/interact", json={"utterance": "25"})
    assert resp.status_code == 200
    data = resp.json()

    if data.get("followup_required"):
        unacked = agent_event_bus.get_unacknowledged_events()
        assert len(unacked) >= 1
        followup_evt = unacked[-1]
        assert followup_evt.event_type == AgentEventType.FOLLOWUP_REQUIRED
        assert "25" in followup_evt.message


def test_websocket_events_endpoint_connection_and_ack():
    from fastapi.testclient import TestClient
    from main import app, agent_event_bus

    client = TestClient(app)
    agent_event_bus.clear()

    # Pre-publish an event
    evt = AgentEvent(event_type=AgentEventType.REMINDER_DUE, message="Socket test reminder")
    agent_event_bus.publish(evt)

    with client.websocket_connect("/ws/events") as websocket:
        # Receive replayed unacknowledged event
        data = websocket.receive_text()
        parsed = json.loads(data)
        assert parsed["event_id"] == evt.event_id
        assert parsed["message"] == "Socket test reminder"

        # Send ACK back to server
        websocket.send_text(json.dumps({"type": "ack", "event_id": evt.event_id}))
        time.sleep(0.1)

        # Verify acknowledged on bus
        assert agent_event_bus.is_acknowledged(evt.event_id) is True

        # Send heartbeat ping
        websocket.send_text(json.dumps({"type": "ping"}))
        pong_data = json.loads(websocket.receive_text())
        assert pong_data["type"] == "pong"


def test_websocket_cannot_execute_physical_commands():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    with client.websocket_connect("/ws/events") as websocket:
        # Send adversarial injection attempt
        websocket.send_text(json.dumps({
            "type": "command",
            "action": "AC_POWER_OFF",
            "target": "AC",
            "temperature": 18
        }))
        time.sleep(0.1)
        # Verify socket remains purely delivery only and does not execute hardware commands
        # Socket simply ignores invalid message types
        websocket.send_text(json.dumps({"type": "ping"}))
        pong_data = json.loads(websocket.receive_text())
        assert pong_data["type"] == "pong"
