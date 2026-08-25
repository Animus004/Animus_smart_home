"""
Daily Brief Synthesizer for Animus Personal Agent.
Assembles concise, context-aware morning and evening briefings summarizing tasks,
reminders, learning priorities, and environmental status.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from agent.models import UserProfile, Task, TaskStatus
from agent.task_manager import TaskManager
from agent.memory import AgentMemoryStore
from room_state.models import RoomState

logger = logging.getLogger("music_daemon.agent.daily_brief")


class DailyBriefEngine:
    """
    Synthesizes conversational daily briefings.
    """

    def __init__(
        self,
        user_profile: UserProfile,
        task_manager: TaskManager,
        memory: AgentMemoryStore
    ):
        self.user_profile = user_profile
        self.task_manager = task_manager
        self.memory = memory

    def generate_morning_brief(
        self,
        room_state: Optional[RoomState] = None,
        weather_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates a concise, structured morning briefing.
        """
        addr = self.user_profile.identity.preferred_address
        lines: List[str] = [f"Good morning, {addr}! Here's your briefing for today:"]

        # 1. Today's Core Priorities
        priorities: List[str] = [
            f"Work session begins after {self.user_profile.routines.work_start_time}",
            f"Daily focus: {self.user_profile.routines.learning_priority}",
            f"Guitar practice session planned for ~{self.user_profile.routines.guitar_reminder_preferred_time}"
        ]
        lines.append("\nToday's Priorities:")
        for idx, p in enumerate(priorities, start=1):
            lines.append(f"  {idx}. {p}")

        # 2. Pending Tasks
        pending_tasks = self.task_manager.get_pending_tasks()
        if pending_tasks:
            lines.append(f"\nPending Tasks ({len(pending_tasks)} item{'s' if len(pending_tasks) > 1 else ''}):")
            for t in pending_tasks[:4]:
                lines.append(f"  - {t.title} [{t.priority.value}]")
            if len(pending_tasks) > 4:
                lines.append(f"  ... and {len(pending_tasks) - 4} more")

        # 3. Scheduled Reminders
        active_reminders = self.task_manager.get_active_reminders()
        if active_reminders:
            lines.append("\nScheduled Reminders:")
            for r in active_reminders:
                r_time = time.strftime("%H:%M", time.localtime(r.scheduled_time))
                lines.append(f"  - {r.message} at {r_time}")

        # 4. Weather & Room Note
        if weather_info and weather_info.get("available"):
            temp = weather_info.get("outdoor_temperature_c")
            cond = weather_info.get("condition")
            lines.append(f"\nLocal Weather (PIN {self.user_profile.identity.location_pin}): {cond}, {temp}°C.")

        # 5. Motivation Tune Offer
        if self.user_profile.routines.morning_motivation_tune_enabled:
            lines.append("\nWould you like me to put on some morning motivation music to start the day?")

        brief_text = "\n".join(lines)
        # Record in memory
        self.memory.record_observation("morning_brief_generated", time.time())
        return brief_text

    def generate_evening_brief(self) -> str:
        """
        Generates a calm evening / night routine summary.
        """
        addr = self.user_profile.identity.preferred_address
        pending = self.task_manager.get_pending_tasks()

        lines: List[str] = [f"Good night, {addr}!"]
        if pending:
            lines.append(f"You have {len(pending)} pending item{'s' if len(pending) > 1 else ''} saved for tomorrow.")
        else:
            lines.append("All tasks were completed today. Great job!")

        lines.append("Sleep well, buddy.")
        self.memory.record_observation("evening_brief_generated", time.time())
        return "\n".join(lines)
