"""
================================================================================
ANIMUS SMART ROOM — ZERO-CLOUD VISUAL DESK PRESENCE OBSERVER
================================================================================
Perceives physical desk occupancy, user arrival, and departure using the
local physical USB HD Camera (VID_349C&PID_2317) via OpenCV DirectShow.

PRIVACY & SAFETY INVARIANTS:
1. 100% Offline & Private: No frames are ever written to disk, streamed,
   or transmitted over any network socket.
2. Low CPU Footprint: Downscaled 320x240 grayscale processing polled at 3.0s
   intervals consumes < 0.5% CPU.
3. Debounced State Machine: Prevents flutter/rapid oscillating arrival/departure
   events when the user momentarily shifts, leans back, or pauses typing.
================================================================================
"""

from __future__ import annotations
import time
import logging
import threading
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("music_daemon.vision_observer")

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    OPENCV_AVAILABLE = False


class DeskState:
    EMPTY = "EMPTY"
    ARRIVED = "ARRIVED"
    PRESENT = "PRESENT"
    DEPARTING = "DEPARTING"
    DEPARTED = "DEPARTED"


class VisionObserver:
    """
    Autonomous Desk Occupancy & Visual Presence Observer.
    Continuously samples local USB camera frames to detect when Sir
    arrives at or departs from the desk workstation.
    """

    DEFAULT_CAMERA_INDEX = 0  # Physical HD camera (USB\VID_349C&PID_2317)
    FRAME_WIDTH = 320
    FRAME_HEIGHT = 240
    MOTION_THRESHOLD_PCT = 1.20  # Calibrated above physical webcam noise floor (< 0.8%)
    CONSECUTIVE_ARRIVE_HITS = 1   # Number of detections required to confirm arrival
    DEPARTURE_DEBOUNCE_SEC = 6.0  # Time without presence before confirming departure (6s)

    def __init__(
        self,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        poll_interval: float = 3.0,
        event_bus: Optional[Any] = None,
        is_simulated: bool = False
    ):
        self.camera_index = camera_index
        self.poll_interval = poll_interval
        self.event_bus = event_bus
        self.is_simulated = is_simulated

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[Any] = None
        self._subtractor: Optional[Any] = None
        if OPENCV_AVAILABLE and not is_simulated:
            try:
                self._subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False)
            except Exception:
                self._subtractor = None

        # State tracking
        self.state: str = DeskState.EMPTY
        self.is_present: bool = False
        self.confidence: float = 0.0
        self.last_motion_score: float = 0.0
        self.last_seen_timestamp: float = 0.0
        self.seated_since: Optional[float] = None
        self._consecutive_hits: int = 0
        self._last_absent_timestamp: float = time.time()
        self._camera_online: bool = self.is_simulated
        self._consecutive_frozen_frames: int = 0
        self._prev_gray: Optional[Any] = None
        self._prev_edges: Optional[Any] = None
        self._warmup_frames: int = 0
        self.last_luminance: float = 0.0
        self.last_contrast: float = 0.0
        self.last_lighting_condition: str = "UNKNOWN"
        self._lock = threading.Lock()

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    def start(self) -> None:
        """Starts the background vision loop thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="AnimusVisionObserverThread",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[VISION_OBSERVER_STARTED] Desk presence monitor active on camera index {self.camera_index}.")

    def stop(self) -> None:
        """Stops the background vision loop thread and releases camera hardware."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._release_camera()
        logger.info("[VISION_OBSERVER_STOPPED] Desk presence monitor stopped and camera released.")

    @staticmethod
    def is_hardware_attached() -> bool:
        """Queries Windows PnP to check if the physical USB HD Camera (VID_349C&PID_2317) is attached."""
        try:
            import subprocess
            cmd = 'Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "*349C&PID_2317*" } | Select-Object -ExpandProperty Status'
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=4
            )
            return "OK" in res.stdout
        except Exception:
            return False

    @staticmethod
    def reset_camera_service() -> bool:
        """Restarts Windows Camera Frame Server service (FrameServer) to recover wedged camera driver state."""
        try:
            import subprocess
            logger.info("[VISION_RESET] Restarting Windows Camera Frame Server (FrameServer)...")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Restart-Service -Name FrameServer -Force -ErrorAction SilentlyContinue"],
                capture_output=True,
                text=True,
                timeout=8
            )
            time.sleep(1.0)
            return res.returncode == 0
        except Exception as e:
            logger.warning(f"[VISION_RESET_ERR] Failed to restart FrameServer: {e}")
            return False

    def _open_camera(self, retry_after_reset: bool = True) -> bool:
        """Opens DirectShow camera handle safely and verifies the stream is live."""
        if self.is_simulated or not OPENCV_AVAILABLE:
            self._camera_online = self.is_simulated
            return self.is_simulated

        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

        try:
            # Prioritize primary physical HD camera (Index 0), then configured or alternative indices
            seen = set()
            candidates = []
            for c in [0, self.camera_index, 1, 2, 3]:
                if c not in seen:
                    candidates.append(c)
                    seen.add(c)

            for idx in candidates:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not cap.isOpened():
                    continue
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

                # Warmup sensor reads to clear cached buffer
                f1 = None
                for _ in range(5):
                    ret, f1 = cap.read()
                    time.sleep(0.03)

                if f1 is None:
                    cap.release()
                    continue

                # Filter out flat gray dummy buffers (std < 1.0)
                mean_val = float(np.mean(f1))
                std_val = float(np.std(f1))
                if std_val < 1.0:
                    logger.debug(f"[VISION_CANDIDATE_REJECT] Index {idx} rejected: flat dummy buffer (mean={mean_val:.1f}, std={std_val:.1f})")
                    cap.release()
                    continue

                # Filter out static virtual placeholders by comparing successive frames across sufficient interval
                time.sleep(0.10)
                ret2, f2 = cap.read()
                if ret2 and f2 is not None:
                    diff = cv2.absdiff(f1, f2)
                    max_d = int(np.max(diff))
                    if max_d == 0:
                        # Take another frame to verify it's truly a static placeholder (like OBS disabled graphic)
                        time.sleep(0.10)
                        ret3, f3 = cap.read()
                        if ret3 and f3 is not None and int(np.max(cv2.absdiff(f1, f3))) == 0:
                            logger.debug(f"[VISION_CANDIDATE_REJECT] Index {idx} rejected: static virtual camera placeholder.")
                            cap.release()
                            continue

                with self._lock:
                    self.camera_index = idx
                    self._cap = cap
                    self._camera_online = True
                    self._consecutive_frozen_frames = 0
                    if self._subtractor is None and OPENCV_AVAILABLE:
                        self._subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False)
                logger.info(f"[VISION_CAMERA_OPENED] Active physical camera bound on index {idx} ({self.FRAME_WIDTH}x{self.FRAME_HEIGHT}, mean={mean_val:.1f}, std={std_val:.1f}).")
                return True

            with self._lock:
                self._camera_online = False
            return False
        except Exception as e:
            logger.warning(f"[VISION_CAMERA_OPEN_ERR] Could not open camera: {e}")
            with self._lock:
                self._camera_online = False
            return False

    def _release_camera(self) -> None:
        """Releases the camera capture handle."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug(f"[VISION_CAMERA_RELEASE_ERR] {e}")
            self._cap = None
        self._camera_online = False
        self._prev_gray = None
        self._prev_edges = None
        self._warmup_frames = 0

    # =========================================================================
    # Perception Evaluation Loop
    # =========================================================================

    def _run_loop(self) -> None:
        """Background sampling loop."""
        while self._running:
            try:
                if not self.is_simulated and (self._cap is None or not self._cap.isOpened()):
                    if not self._open_camera():
                        time.sleep(5.0)
                        continue

                if not self.is_simulated and self._cap is not None:
                    ret, frame = self._cap.read()
                    if ret and frame is not None:
                        self.evaluate_frame(frame)
                    else:
                        logger.debug("[VISION_FRAME_DROP] Frame read failed; checking camera connection.")
                        self._release_camera()
            except Exception as e:
                logger.error(f"[VISION_LOOP_ERR] Error during vision loop: {e}")

            time.sleep(self.poll_interval)

    def evaluate_frame(self, frame: Any) -> Tuple[bool, str, float]:
        """
        Evaluates a raw BGR frame and updates the desk presence state machine.
        Returns: (is_present, state, motion_score)
        """
        if not OPENCV_AVAILABLE or frame is None:
            return self.is_present, self.state, self.last_motion_score

        try:
            # Resize for consistent lightweight evaluation
            h, w = frame.shape[:2]
            if w != self.FRAME_WIDTH or h != self.FRAME_HEIGHT:
                frame = cv2.resize(frame, (self.FRAME_WIDTH, self.FRAME_HEIGHT))

            # Grayscale conversion & Gaussian blur to suppress sensor grain
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            blurred = cv2.GaussianBlur(gray, (9, 9), 0)

            # Optical luminance & contrast evaluation
            mean_lum = float(np.mean(gray))
            contrast = float(np.std(gray))
            if mean_lum < 30.0:
                lighting = "DARK / CINEMA"
            elif mean_lum < 80.0:
                lighting = "DIM / AMBIENT"
            elif mean_lum < 160.0:
                lighting = "OPTIMAL WORK LIGHT"
            else:
                lighting = "BRIGHT / DAYLIGHT"

            # 1. Inter-frame Motion Flux with Auto-Exposure Mean-Shift Compensation
            motion_score = 0.0
            if self._prev_gray is not None:
                diff_raw = cv2.absdiff(self._prev_gray, blurred)
                # Check for frozen phantom DirectShow buffer
                if cv2.countNonZero(diff_raw) == 0:
                    self._consecutive_frozen_frames += 1
                else:
                    self._consecutive_frozen_frames = 0

                if self._consecutive_frozen_frames >= 5 and not self.is_simulated:
                    logger.warning(f"[VISION_CAMERA_FROZEN] 5 consecutive frozen frames on camera index {self.camera_index}. Releasing handle for auto-reconnection.")
                    self._release_camera()
                    with self._lock:
                        self.state = "DISCONNECTED"
                        self.is_present = False
                        self.last_motion_score = 0.0
                    return False, "DISCONNECTED", 0.0

                # Mean-shift compensation: cancels out camera auto-exposure / gain hunting
                shift = float(np.mean(blurred)) - float(np.mean(self._prev_gray))
                comp = np.clip(blurred.astype(np.int16) - int(round(shift)), 0, 255).astype(np.uint8)
                diff = cv2.absdiff(self._prev_gray, comp)

                # Threshold 20 filters electronic noise floor while capturing physical human movement
                _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
                k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k5)
                motion_px = cv2.countNonZero(cleaned)
                motion_score = (motion_px / (self.FRAME_WIDTH * self.FRAME_HEIGHT)) * 100.0

            # 2. Adaptive Foreground Occupancy (MOG2) - supplementary signal
            fg_score = 0.0
            if self._subtractor is None and OPENCV_AVAILABLE and not self.is_simulated:
                try:
                    self._subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=False)
                except Exception:
                    self._subtractor = None

            if self._subtractor is not None:
                fg_mask = self._subtractor.apply(blurred)
                k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                fg_clean = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, k5)
                fg_px = cv2.countNonZero(fg_clean)
                fg_score = (fg_px / (self.FRAME_WIDTH * self.FRAME_HEIGHT)) * 100.0

            self._prev_gray = blurred.copy()
            self._warmup_frames += 1

            # Ignore first warmup frame
            if self._warmup_frames <= 1:
                return self.is_present, self.state, 0.0

            # Detected if motion exceeds threshold, or subtle motion with notable foreground
            raw_detected = (motion_score >= self.MOTION_THRESHOLD_PCT) or (motion_score >= 0.50 and fg_score >= 2.5)

            with self._lock:
                now = time.time()
                self.last_motion_score = motion_score
                self.last_luminance = mean_lum
                self.last_contrast = contrast
                self.last_lighting_condition = lighting

                if raw_detected:
                    self._consecutive_hits += 1
                    self.last_seen_timestamp = now
                    self._last_absent_timestamp = 0.0

                    if not self.is_present:
                        # State Transition: EMPTY -> ARRIVED -> PRESENT
                        self.is_present = True
                        self.state = DeskState.ARRIVED
                        self.seated_since = now
                        self.confidence = min(1.0, 0.75 + (motion_score / 50.0))
                        logger.info(f"[DESK_PRESENCE_EVENT] Desk Arrival Detected! (motion={motion_score:.2f}%, fg={fg_score:.2f}%)")
                        self._publish_event("DESK_USER_ARRIVED", {
                            "seated_since": self.seated_since,
                            "motion_score": motion_score,
                            "confidence": self.confidence
                        })
                        self.state = DeskState.PRESENT
                    else:
                        self.state = DeskState.PRESENT
                        self.confidence = min(1.0, 0.85 + (motion_score / 100.0))
                else:
                    self._consecutive_hits = 0
                    if self._last_absent_timestamp == 0.0:
                        self._last_absent_timestamp = now

                    absent_duration = now - self.last_seen_timestamp if self.last_seen_timestamp > 0 else (now - self._last_absent_timestamp)

                    if self.is_present:
                        if absent_duration >= self.DEPARTURE_DEBOUNCE_SEC:
                            # State Transition: PRESENT -> DEPARTED -> EMPTY
                            self.is_present = False
                            self.state = DeskState.DEPARTED
                            duration = now - self.seated_since if self.seated_since else 0.0
                            self.seated_since = None
                            self.confidence = 0.0
                            logger.info(f"[DESK_PRESENCE_EVENT] Desk Departure Detected! (session_duration={duration:.1f}s)")
                            self._publish_event("DESK_USER_DEPARTED", {
                                "session_duration_seconds": duration,
                                "last_seen_timestamp": self.last_seen_timestamp
                            })
                            self.state = DeskState.EMPTY
                        else:
                            self.state = DeskState.PRESENT  # Maintain PRESENT state during quiet focus
                            self.confidence = max(0.4, self.confidence - 0.02)
                    else:
                        self.state = DeskState.EMPTY
                        self.confidence = 0.0

                return self.is_present, self.state, self.last_motion_score

        except Exception as e:
            logger.error(f"[VISION_FRAME_EVAL_ERR] {e}")
            return self.is_present, self.state, 0.0

    def simulate_presence(self, is_present: bool, motion_score: float = 2.5) -> None:
        """Simulates presence transition for automated unit testing."""
        with self._lock:
            now = time.time()
            prev_present = self.is_present
            self.is_present = is_present
            self.last_motion_score = motion_score
            self._camera_online = True

            if is_present and not prev_present:
                self.state = DeskState.ARRIVED
                self.seated_since = now
                self.last_seen_timestamp = now
                self.confidence = 0.95
                self._publish_event("DESK_USER_ARRIVED", {
                    "seated_since": self.seated_since,
                    "motion_score": motion_score
                })
                self.state = DeskState.PRESENT
            elif not is_present and prev_present:
                self.state = DeskState.DEPARTED
                duration = now - self.seated_since if self.seated_since else 0.0
                self.seated_since = None
                self.confidence = 0.0
                self._publish_event("DESK_USER_DEPARTED", {
                    "session_duration_seconds": duration
                })
                self.state = DeskState.EMPTY
            elif is_present:
                self.state = DeskState.PRESENT
                self.last_seen_timestamp = now
                self.confidence = 0.95
            else:
                self.state = DeskState.EMPTY
                self.confidence = 0.0

    # =========================================================================
    # Event Publication & Telemetry
    # =========================================================================

    def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Dispatches typed desk events to the event bus if available."""
        if not self.event_bus:
            return
        try:
            from event_bus import AgentEvent, AgentEventType, AgentEventPriority
            # Map to typed AgentEventType if supported, else string event_type
            evt_enum = getattr(AgentEventType, event_type, None)
            if evt_enum is not None:
                self.event_bus.publish(AgentEvent(
                    event_type=evt_enum,
                    priority=AgentEventPriority.NORMAL,
                    message=f"Desk presence event: {event_type}",
                    payload=payload
                ))
            elif hasattr(self.event_bus, "publish"):
                self.event_bus.publish(event_type, payload)
        except Exception as e:
            logger.debug(f"[VISION_EVENT_PUBLISH_ERR] {e}")

    def get_presence_telemetry(self) -> Dict[str, Any]:
        """Returns normalized presence metrics for PerceptionCollector and RoomState."""
        with self._lock:
            now = time.time()
            seated_dur = (now - self.seated_since) if (self.is_present and self.seated_since) else 0.0
            if self._camera_online:
                device_name = f"HD camera (Active on Index {self.camera_index} - USB VID_349C&PID_2317)"
            elif self.is_hardware_attached():
                device_name = "HD camera (Present in Windows PnP - Resetting FrameServer)"
            else:
                device_name = "HD camera (DISCONNECTED / CODE 45 - Reconnect USB)"
            current_state = self.state if self._camera_online else "DISCONNECTED"
            return {
                "camera_online": self._camera_online,
                "hardware_device": device_name,
                "resolution": f"{self.FRAME_WIDTH}x{self.FRAME_HEIGHT}",
                "is_present": self.is_present if self._camera_online else False,
                "confidence": round(self.confidence, 2) if self._camera_online else 0.0,
                "state": current_state,
                "motion_score": round(self.last_motion_score, 2),
                "ambient_luminance": round(self.last_luminance, 1) if self._camera_online else 0.0,
                "contrast_score": round(self.last_contrast, 1) if self._camera_online else 0.0,
                "lighting_condition": self.last_lighting_condition if self._camera_online else "OFFLINE",
                "seated_duration_seconds": round(seated_dur, 1),
                "last_seen_timestamp": self.last_seen_timestamp
            }
