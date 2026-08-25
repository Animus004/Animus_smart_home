"""
Background Scheduler Worker for Authoritative Reminder & Task Due Event Generation.
Polls TaskManager state machine, detects due reminders, marks them triggered,
and publishes structured AgentEvents to the EventBus and RoomTtsService.
"""

import logging
import threading
import time
from typing import Any, Optional

from event_bus import AgentEventBus, AgentEvent, AgentEventType, AgentEventPriority

logger = logging.getLogger("music_daemon.reminder_scheduler")


class ReminderScheduler:
    """
    Background worker that regularly inspects the authoritative TaskManager
    and triggers due reminders.
    """
    def __init__(
        self,
        task_manager: Any,
        event_bus: AgentEventBus,
        tts_service: Optional[Any] = None,
        poll_interval_seconds: float = 1.0
    ):
        self.task_manager = task_manager
        self.event_bus = event_bus
        self.tts_service = tts_service
        self.poll_interval_seconds = poll_interval_seconds

        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def start(self):
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._scheduler_loop,
            name="ReminderSchedulerWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info(f"[REMINDER_SCHEDULER] Background worker started (poll_interval={self.poll_interval_seconds}s)")

    def stop(self):
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.5)
        logger.info("[REMINDER_SCHEDULER] Background worker stopped.")

    def check_due_reminders_once(self) -> int:
        """
        Executes a single pass over active reminders.
        Returns the number of due reminders triggered.
        """
        if not self.task_manager:
            return 0

        now = time.time()
        triggered_count = 0

        try:
            active_reminders = self.task_manager.get_active_reminders()
            for rem in active_reminders:
                if rem.scheduled_time <= now and not rem.triggered:
                    rem.triggered = True
                    triggered_count += 1
                    logger.info(f"[REMINDER_DUE_TRIGGERED] Reminder id='{rem.id}', message='{rem.message}'")

                    msg = f"Buddy, here is your reminder: {rem.message}."
                    event = AgentEvent(
                        event_type=AgentEventType.REMINDER_DUE,
                        priority=AgentEventPriority.NORMAL,
                        message=msg,
                        payload={
                            "reminder_id": rem.id,
                            "reminder_message": rem.message,
                            "scheduled_time": rem.scheduled_time
                        }
                    )
                    # 1. Publish to EventBus for WebSocket delivery to Android
                    self.event_bus.publish(event)

                    # 2. Proactive Room TTS Audio Announcement (if enabled)
                    if self.tts_service and self.tts_service.is_enabled():
                        try:
                            self.tts_service.speak_async(msg)
                        except Exception as e:
                            logger.error(f"[REMINDER_TTS_DISPATCH_FAIL] Failed to speak reminder: {e}")
        except Exception as e:
            logger.error(f"[REMINDER_SCHEDULER_ERROR] Error checking reminders: {e}", exc_info=True)

        return triggered_count

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            self.check_due_reminders_once()
            time.sleep(self.poll_interval_seconds)
