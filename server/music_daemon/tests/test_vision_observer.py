"""
================================================================================
ANIMUS SMART ROOM — ZERO-CLOUD VISION OBSERVER UNIT TESTS
================================================================================
Tests:
1. VisionObserver initialization and safe shutdown.
2. Simulated desk presence transitions (EMPTY -> ARRIVED -> PRESENT -> DEPARTED).
3. Frame evaluation with inter-frame motion diffing.
4. EventBus publication of DESK_USER_ARRIVED and DESK_USER_DEPARTED events.
================================================================================
"""

import time
import numpy as np
import pytest
from unittest.mock import MagicMock

from vision_observer import VisionObserver, DeskState
from event_bus import AgentEventBus, AgentEventType


def test_vision_observer_initialization():
    vo = VisionObserver(camera_index=2, is_simulated=True)
    telem = vo.get_presence_telemetry()
    assert telem["state"] == DeskState.EMPTY
    assert telem["is_present"] is False
    assert telem["confidence"] == 0.0
    vo.stop()


def test_vision_observer_simulated_arrival_and_departure():
    import queue
    bus = AgentEventBus()
    q = queue.Queue()
    bus.subscribe(q)

    vo = VisionObserver(camera_index=2, event_bus=bus, is_simulated=True)

    # 1. Trigger simulated arrival
    vo.simulate_presence(True, motion_score=4.2)
    telem = vo.get_presence_telemetry()
    assert telem["is_present"] is True
    assert telem["state"] == DeskState.PRESENT
    assert telem["motion_score"] == 4.2
    assert telem["confidence"] >= 0.9

    # Verify event published
    evt_arrive = q.get_nowait()
    assert evt_arrive.event_type == AgentEventType.DESK_USER_ARRIVED

    # 2. Trigger simulated departure
    vo.simulate_presence(False)
    telem_depart = vo.get_presence_telemetry()
    assert telem_depart["is_present"] is False
    assert telem_depart["state"] == DeskState.EMPTY

    # Verify departure event published
    evt_depart = q.get_nowait()
    assert evt_depart.event_type == AgentEventType.DESK_USER_DEPARTED

    vo.stop()


def test_vision_observer_evaluate_synthetic_frames():
    vo = VisionObserver(camera_index=2, is_simulated=False)

    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    frame_with_motion = blank.copy()
    frame_with_motion[60:180, 80:240] = 180  # Significant block motion

    # Warmup and static frames
    vo.evaluate_frame(blank)
    vo.evaluate_frame(blank)
    vo.evaluate_frame(blank)
    assert vo.is_present is False
    assert vo.state == DeskState.EMPTY

    # Feed frames with motion
    vo.evaluate_frame(frame_with_motion)
    vo.evaluate_frame(blank)  # Second consecutive hit to confirm arrival
    assert vo.is_present is True
    assert vo.state == DeskState.PRESENT
    assert vo.last_motion_score > 0.40

    vo.stop()


def test_vision_observer_departure_after_debounce():
    import queue
    bus = AgentEventBus()
    q = queue.Queue()
    bus.subscribe(q)

    vo = VisionObserver(camera_index=2, event_bus=bus, is_simulated=False)
    vo.DEPARTURE_DEBOUNCE_SEC = 0.5  # Fast debounce for test

    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    frame_with_motion = blank.copy()
    frame_with_motion[60:180, 80:240] = 180

    # Warmup
    vo.evaluate_frame(blank)
    vo.evaluate_frame(blank)

    # Arrive
    vo.evaluate_frame(frame_with_motion)
    assert vo.is_present is True
    assert vo.state == DeskState.PRESENT

    # Drain arrival event
    evt_arr = q.get_nowait()
    assert evt_arr.event_type == AgentEventType.DESK_USER_ARRIVED

    # User departs (frame transitions back to blank, producing motion during transition)
    vo.evaluate_frame(blank)

    # Empty scene remains quiet exceeding debounce window
    vo.last_seen_timestamp = time.time() - 1.0
    vo.evaluate_frame(blank)

    # Must transition to empty/departed
    assert vo.is_present is False
    assert vo.state == DeskState.EMPTY

    # Departure event must be published
    evt_dep = q.get_nowait()
    assert evt_dep.event_type == AgentEventType.DESK_USER_DEPARTED
    assert "session_duration_seconds" in evt_dep.payload

    vo.stop()

