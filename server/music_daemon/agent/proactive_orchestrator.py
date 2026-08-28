"""
================================================================================
ANIMUS SMART ROOM — PROACTIVE AMBIENT INITIATIVE ORCHESTRATOR
================================================================================
Autonomous background cognitive monitor. Continuously perceives room conditions,
thermal metrics, time-of-day habits, and user fatigue to generate polite,
non-intrusive proactive vocal suggestions via en-GB-SoniaNeural.
================================================================================
"""

from __future__ import annotations
import os
import time
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("music_daemon.agent.proactive_orchestrator")


class ProactiveTriggerCategory:
    THERMAL_CARE = "THERMAL_CARE"
    LATE_NIGHT_FATIGUE = "LATE_NIGHT_FATIGUE"
    MORNING_GREETING = "MORNING_GREETING"
    IDLE_OPTICAL_PROTECTION = "IDLE_OPTICAL_PROTECTION"


class ProactiveOrchestrator:
    """
    Autonomous Proactive Room Intelligence.
    Monitors PerceptionCollector live telemetry and speaks up when helpful.
    """

    def __init__(
        self,
        tts_service: Optional[Any] = None,
        check_interval: float = 30.0,
        cooldown_seconds: float = 1800.0,  # 30 minute minimum cooldown per category
        enable_speech: bool = True
    ):
        self.tts_service = tts_service
        self.check_interval = check_interval
        self.cooldown_seconds = cooldown_seconds
        self.enable_speech = enable_speech

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_trigger_times: Dict[str, float] = {}
        self._pc_active_since: Optional[float] = None
        self._morning_greeted_today: Optional[str] = None
        self._idle_media_start: Optional[float] = None

    def start(self) -> None:
        """Starts the proactive cognitive background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="AnimusProactiveThread", daemon=True)
        self._thread.start()
        logger.info("[PROACTIVE_ORCHESTRATOR_STARTED] Proactive cognitive loop active.")

    def stop(self) -> None:
        """Stops the proactive cognitive background thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[PROACTIVE_ORCHESTRATOR_STOPPED] Proactive loop stopped.")

    def _run_loop(self) -> None:
        """Main background loop."""
        while self._running:
            try:
                self.evaluate_proactive_rules()
            except Exception as e:
                logger.error(f"[PROACTIVE_EVAL_ERROR] {e}")
            time.sleep(self.check_interval)

    # =========================================================================
    # Rule Evaluation Engine
    # =========================================================================

    def evaluate_proactive_rules(self, telemetry: Optional[Dict[str, Any]] = None) -> Optional[Tuple[str, str]]:
        """
        Evaluates all ambient rules against live room telemetry.
        Returns (category, message) if a rule fired, else None.
        """
        if telemetry is None:
            from room_state.perception_collector import get_perception_collector
            collector = get_perception_collector()
            telemetry = collector.get_live_telemetry()

        now = time.time()
        now_dt = datetime.now()
        hour = now_dt.hour
        today_str = now_dt.strftime("%Y-%m-%d")

        # 1. Check Morning Awakening (7:00 AM - 10:30 AM)
        if 7 <= hour < 11 and self._morning_greeted_today != today_str:
            if self._can_trigger(ProactiveTriggerCategory.MORNING_GREETING, now):
                ac_temp = telemetry.get("ac_ambient_temp", 24)
                msg = f"Good morning Sayan! The room is at {ac_temp} degrees. Shall I start your morning playlist and brief you on the day?"
                self._morning_greeted_today = today_str
                self._dispatch_suggestion(ProactiveTriggerCategory.MORNING_GREETING, msg)
                return ProactiveTriggerCategory.MORNING_GREETING, msg

        # 2. Check Late Night Work Fatigue (1:00 AM - 4:30 AM)
        if (hour >= 1 or hour < 5):
            pc_connected = telemetry.get("pc_online", True)
            if pc_connected:
                if self._pc_active_since is None:
                    self._pc_active_since = now
                elif (now - self._pc_active_since) > 5400:  # 90 minutes of late night work
                    if self._can_trigger(ProactiveTriggerCategory.LATE_NIGHT_FATIGUE, now):
                        msg = "Sayan, you've been working late tonight. Would you like me to dim the screen and queue a relaxing wind-down track?"
                        self._dispatch_suggestion(ProactiveTriggerCategory.LATE_NIGHT_FATIGUE, msg)
                        return ProactiveTriggerCategory.LATE_NIGHT_FATIGUE, msg
            else:
                self._pc_active_since = None
        else:
            self._pc_active_since = None

        # 3. Check Thermal Discomfort
        ambient_temp = telemetry.get("ac_ambient_temp")
        ac_power = telemetry.get("ac_power", False)
        if ambient_temp is not None:
            # Overheating rule (ambient >= 28°C while AC is off)
            if ambient_temp >= 28 and not ac_power:
                if self._can_trigger(ProactiveTriggerCategory.THERMAL_CARE, now):
                    msg = f"Sayan, the room is getting quite warm at {ambient_temp} degrees. Shall I turn on the AC to 24?"
                    self._dispatch_suggestion(ProactiveTriggerCategory.THERMAL_CARE, msg)
                    return ProactiveTriggerCategory.THERMAL_CARE, msg

            # Overchilling rule (ambient <= 19°C while AC is running)
            if ambient_temp <= 19 and ac_power:
                if self._can_trigger(ProactiveTriggerCategory.THERMAL_CARE, now):
                    msg = f"It's getting chilly in here ({ambient_temp} degrees). Would you like me to raise the AC temperature?"
                    self._dispatch_suggestion(ProactiveTriggerCategory.THERMAL_CARE, msg)
                    return ProactiveTriggerCategory.THERMAL_CARE, msg

        # 4. Check Idle Optical Protection (Projector ON but idle > 20 min)
        proj_on = telemetry.get("projector_power", False)
        media_playing = telemetry.get("media_playing", False)
        if proj_on and not media_playing:
            if self._idle_media_start is None:
                self._idle_media_start = now
            elif (now - self._idle_media_start) > 1200:  # 20 minutes idle
                if self._can_trigger(ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION, now):
                    msg = "The projector has been idle for 20 minutes. Would you like me to put it into standby to protect the optical lamp?"
                    self._dispatch_suggestion(ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION, msg)
                    return ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION, msg
        else:
            self._idle_media_start = None

        return None

    def _can_trigger(self, category: str, now: float) -> bool:
        """Checks cooldown invariants."""
        last_t = self._last_trigger_times.get(category, 0.0)
        return (now - last_t) >= self.cooldown_seconds

    def _dispatch_suggestion(self, category: str, message: str) -> None:
        """Records trigger timestamp and speaks message politely."""
        self._last_trigger_times[category] = time.time()
        logger.info(f"[PROACTIVE_TRIGGER] {category} ➔ {message}")

        if self.enable_speech and self.tts_service:
            try:
                self.tts_service.speak(message)
            except Exception as e:
                logger.error(f"[PROACTIVE_TTS_ERROR] {e}")


# Global singleton instance
_global_proactive: Optional[ProactiveOrchestrator] = None


def get_proactive_orchestrator() -> ProactiveOrchestrator:
    """Returns or initializes the global ProactiveOrchestrator singleton."""
    global _global_proactive
    if _global_proactive is None:
        _global_proactive = ProactiveOrchestrator()
    return _global_proactive
