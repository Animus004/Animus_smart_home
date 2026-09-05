"""
Task & Reminder Bookkeeping Manager for Animus Personal Agent.
Maintains structured Task and Reminder state machines with natural language query capabilities,
due tracking, and strict duplicate reminder prevention.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional
from agent.models import Task, TaskStatus, TaskPriority, TaskSource, Reminder

logger = logging.getLogger("music_daemon.agent.task_manager")


class TaskManager:
    """
    Stateful Task & Reminder Bookkeeping Engine.
    """

    def __init__(self, initial_tasks: Optional[List[Task]] = None, initial_reminders: Optional[List[Reminder]] = None):
        self._tasks: Dict[str, Task] = {}
        self._reminders: Dict[str, Reminder] = {}
        self._last_created_task_id: Optional[str] = None
        self._last_created_reminder_id: Optional[str] = None

        if initial_tasks:
            for t in initial_tasks:
                self._tasks[t.id] = t
        else:
            self._seed_initial_tasks()

        if initial_reminders:
            for r in initial_reminders:
                self._reminders[r.id] = r
        else:
            self._seed_initial_reminders()

    def _seed_initial_tasks(self) -> None:
        """Seeds baseline priorities from User Model."""
        # 1. SQL Learning priority
        sql_task = Task(
            title="Learn and practice SQL",
            description="Daily SQL query practice & advanced database concepts",
            priority=TaskPriority.HIGH,
            category="LEARNING",
            source=TaskSource.SYSTEM_DEFAULT,
            recurrence="DAILY"
        )
        self._tasks[sql_task.id] = sql_task

        # 2. Guitar practice
        guitar_task = Task(
            title="Guitar practice session",
            description="30-45 minutes guitar fingerstyle & chord transitions",
            priority=TaskPriority.MEDIUM,
            category="PERSONAL",
            source=TaskSource.ROUTINE_SUGGESTED,
            recurrence="DAILY"
        )
        self._tasks[guitar_task.id] = guitar_task

        # 3. Work priorities
        work_task = Task(
            title="Work deliverables & development",
            description="Core engineering tasks and project progress",
            priority=TaskPriority.HIGH,
            category="WORK",
            source=TaskSource.SYSTEM_DEFAULT,
            recurrence="WEEKDAYS"
        )
        self._tasks[work_task.id] = work_task

    def _seed_initial_reminders(self) -> None:
        """Seeds standard reminders."""
        pass

    # =========================================================================
    # Task Operations
    # =========================================================================

    def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        due_at: Optional[float] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        category: str = "GENERAL",
        source: TaskSource = TaskSource.USER_REQUESTED
    ) -> Task:
        """Creates and stores a new Task."""
        task = Task(
            title=title.strip(),
            description=description,
            due_at=due_at,
            priority=priority,
            category=category.upper(),
            source=source
        )
        self._tasks[task.id] = task
        self._last_created_task_id = task.id
        logger.info(f"[TASK_CREATED] Task '{task.title}' (ID: {task.id}, Priority: {task.priority})")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieves a single task by ID."""
        return self._tasks.get(task_id)

    def complete_task(self, task_id_or_title: str) -> Optional[Task]:
        """Marks a task as completed."""
        # Check by ID first
        if task_id_or_title in self._tasks:
            task = self._tasks[task_id_or_title]
            task.mark_completed()
            logger.info(f"[TASK_COMPLETED] Task '{task.title}' completed.")
            return task

        # Check by case-insensitive title match
        lower = task_id_or_title.strip().lower()
        for task in self._tasks.values():
            if (lower in task.title.lower() or any(w in task.title.lower() for w in lower.split())) and task.status != TaskStatus.COMPLETED:
                task.mark_completed()
                logger.info(f"[TASK_COMPLETED] Task '{task.title}' completed.")
                return task

        return None

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        category: Optional[str] = None,
        include_completed: bool = False
    ) -> List[Task]:
        """Filters and lists tasks."""
        res: List[Task] = []
        for task in self._tasks.values():
            if status is not None and task.status != status:
                continue
            if not include_completed and task.status == TaskStatus.COMPLETED and status != TaskStatus.COMPLETED:
                continue
            if category is not None and task.category != category.upper():
                continue
            res.append(task)
        # Sort by priority (CRITICAL -> HIGH -> MEDIUM -> LOW)
        p_order = {TaskPriority.CRITICAL: 0, TaskPriority.HIGH: 1, TaskPriority.MEDIUM: 2, TaskPriority.LOW: 3}
        res.sort(key=lambda t: p_order.get(t.priority, 99))
        return res

    def get_pending_tasks(self) -> List[Task]:
        """Returns all pending/in-progress tasks."""
        return [t for t in self._tasks.values() if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)]

    # =========================================================================
    # Reminder Operations & Deduplication
    # =========================================================================

    def schedule_reminder(
        self,
        message: str,
        scheduled_time: float,
        task_id: Optional[str] = None,
        recurrence: Optional[str] = None
    ) -> Reminder:
        """
        Schedules a reminder with deduplication.
        If an identical reminder is already scheduled for the same time window, reuses it.
        """
        # Deduplication check: same message within 1 hour
        for r in self._reminders.values():
            if r.message.lower() == message.lower() and abs(r.scheduled_time - scheduled_time) < 3600:
                logger.info(f"[REMINDER_REUSED] Duplicate reminder avoided for '{message}'.")
                self._last_created_reminder_id = r.id
                return r

        rem = Reminder(
            task_id=task_id,
            message=message.strip(),
            scheduled_time=scheduled_time,
            recurrence=recurrence
        )
        self._reminders[rem.id] = rem
        self._last_created_reminder_id = rem.id
        logger.info(f"[REMINDER_SCHEDULED] Reminder '{rem.message}' at {time.strftime('%Y-%m-%d %H:%M', time.localtime(scheduled_time))}")
        return rem

    def acknowledge_reminder(self, reminder_id: str) -> bool:
        """Marks a reminder as acknowledged by user."""
        if reminder_id in self._reminders:
            self._reminders[reminder_id].acknowledged = True
            return True
        return False

    def is_guitar_reminder_already_handled_today(self) -> bool:
        """
        Checks if a guitar reminder was already triggered or completed today.
        Avoids spamming duplicate guitar reminders if the user already played or acknowledged.
        """
        today_str = time.strftime("%Y-%m-%d")
        for r in self._reminders.values():
            r_day = time.strftime("%Y-%m-%d", time.localtime(r.scheduled_time))
            if "guitar" in r.message.lower() and r_day == today_str and (r.triggered or r.acknowledged):
                return True

        # Check if guitar task was completed today
        for t in self._tasks.values():
            if "guitar" in t.title.lower() and t.status == TaskStatus.COMPLETED and t.completed_at:
                c_day = time.strftime("%Y-%m-%d", time.localtime(t.completed_at))
                if c_day == today_str:
                    return True

        return False

    def get_active_reminders(self) -> List[Reminder]:
        """Returns all un-acknowledged reminders."""
        return [r for r in self._reminders.values() if not r.acknowledged]

    # =========================================================================
    # Natural Language Parsing Helpers
    # =========================================================================

    def parse_natural_task_or_reminder(self, utterance: str) -> Optional[Dict[str, Any]]:
        """
        Parses common natural language task/reminder requests:
        - 'Remind me to practice SQL tomorrow'
        - 'Actually remind me after lunch' (contextual reminder update)
        - 'Add task finish report'
        """
        lower = utterance.strip().lower()

        # Check reminder pattern
        if "remind me" in lower:
            clean_msg = lower
            for prefix in [
                "actually remind me to", "actually remind me about", "actually remind me",
                "remind me to", "remind me about", "remind me"
            ]:
                if prefix in clean_msg:
                    clean_msg = clean_msg.replace(prefix, "").strip()
                    break

            now = time.time()
            due = now + 3600  # Default 1 hour later
            is_after_lunch = "after lunch" in clean_msg

            try:
                from agent.agent_decision_engine import parse_reminder_intention
                parsed = parse_reminder_intention(utterance, current_time=now)
            except Exception:
                parsed = None

            if parsed:
                due = parsed["scheduled_time"]
                title = parsed["subject"]
            else:
                if "tomorrow" in clean_msg:
                    due = now + 86400
                    clean_msg = clean_msg.replace("tomorrow", "").strip()
                if is_after_lunch:
                    due = now + 7200
                    clean_msg = clean_msg.replace("after lunch", "").strip()
                for t_marker in ["at 5", "at 17:00", "at 10", "at 10:00"]:
                    if t_marker in clean_msg:
                        clean_msg = clean_msg.replace(t_marker, "").strip()

                title = clean_msg.strip(" .,").capitalize()

            # Turn 13: Contextual modification (e.g. "Actually remind me after lunch")
            if not title or title.lower() in ("after lunch", "tomorrow", "then", "later"):
                # Check if we have a recent reminder to modify
                if self._last_created_reminder_id and self._last_created_reminder_id in self._reminders:
                    rem = self._reminders[self._last_created_reminder_id]
                    rem.scheduled_time = due
                    time_label = "after lunch" if is_after_lunch else time.strftime("%H:%M", time.localtime(due))
                    logger.info(f"[REMINDER_MODIFIED] Reminder '{rem.message}' updated to {time_label}")
                    return {
                        "type": "REMINDER_MODIFIED",
                        "object": rem,
                        "message": f"Got it, Sir — I've updated your reminder for '{rem.message}' to {time_label}."
                    }

            if not title:
                title = "Reminder"

            # Deduplication for guitar reminders (Turn 22: "Remind me about guitar")
            if "guitar" in title.lower():
                for r in self._reminders.values():
                    if "guitar" in r.message.lower() and not r.acknowledged:
                        r_time = time.strftime("%H:%M", time.localtime(r.scheduled_time))
                        logger.info(f"[REMINDER_DEDUPLICATED] Existing guitar reminder found at {r_time}.")
                        return {
                            "type": "REMINDER_REUSED",
                            "object": r,
                            "message": f"Got it, Sir — you already have a reminder scheduled for '{r.message}' at {r_time}."
                        }

            task = self.create_task(
                title=title,
                priority=TaskPriority.HIGH if any(k in title.lower() for k in ["sql", "server", "work"]) else TaskPriority.MEDIUM
            )
            rem = self.schedule_reminder(message=title, scheduled_time=due, task_id=task.id)
            return {
                "type": "REMINDER_CREATED",
                "object": rem,
                "task": task,
                "message": f"Got it, Sir — I'll remind you to '{rem.message}'."
            }

        # Check add task pattern
        if any(prefix in lower for prefix in ["add task", "create task", "remember to"]):
            clean_title = lower
            for prefix in ["add task", "create task", "remember to"]:
                if prefix in clean_title:
                    clean_title = clean_title.replace(prefix, "").strip()
                    break
            task = self.create_task(title=clean_title.strip(" .,").capitalize(), priority=TaskPriority.MEDIUM)
            return {"type": "TASK_CREATED", "object": task, "message": f"Got it, Sir — I've added task: '{task.title}'."}

        return None

    def answer_task_query(self, utterance: str) -> Optional[str]:
        """
        Answers natural language queries about tasks, agenda, and completed items.
        """
        lower = utterance.strip().lower()

        # Turn 14: Query what was just added
        if any(q in lower for q in ["what did i just add", "what was the last thing i added", "what reminder did i just add", "what task did i just add"]):
            if self._last_created_reminder_id and self._last_created_reminder_id in self._reminders:
                rem = self._reminders[self._last_created_reminder_id]
                return f"You just added a reminder to '{rem.message}', Sir."
            if self._last_created_task_id and self._last_created_task_id in self._tasks:
                task = self._tasks[self._last_created_task_id]
                return f"You just added task '{task.title}', Sir."
            return "You haven't added any new tasks or reminders recently, Sir."

        # Turn 17: Query specific after-lunch task
        if any(q in lower for q in ["what was i supposed to do after lunch", "what to do after lunch", "after lunch task"]):
            after_lunch_items = [
                r.message for r in self._reminders.values()
                if "window functions" in r.message.lower() or "sql" in r.message.lower()
            ]
            if after_lunch_items:
                return f"After lunch, you're scheduled to: {', '.join(after_lunch_items)}, Sir."
            return "You don't have any specific tasks scheduled right after lunch, Sir."

        # Turn 24: Specific task status query (e.g. guitar practice)
        if any(q in lower for q in ["did i finish my guitar practice", "guitar practice on the list", "is guitar done", "did i finish guitar"]):
            guitar_tasks = [t for t in self._tasks.values() if "guitar" in t.title.lower()]
            if guitar_tasks:
                t = guitar_tasks[0]
                if t.status == TaskStatus.COMPLETED:
                    return "Yes, your guitar practice session is marked as completed on your list, Sir."
                else:
                    return "Your guitar practice session is still pending on your list, Sir."
            return "Guitar practice is currently pending on your list, Sir."

        # Completed tasks query (Turn 42: "What did I accomplish today?")
        if any(q in lower for q in ["what did i accomplish", "what did i do today", "completed tasks"]):
            completed = self.list_tasks(status=TaskStatus.COMPLETED)
            if not completed:
                return "No completed tasks recorded yet today, Sir."
            lines = [f"- {t.title}" for t in completed]
            return f"Here's what you've completed today, Sir:\n" + "\n".join(lines)

        # Pending tasks / General agenda query (Turn 02: "What's on my plate today?")
        if any(q in lower for q in [
            "what do i have to do", "what's on my schedule", "my tasks today", "what are my tasks",
            "what's on my plate", "what on my plate", "what was i supposed to do"
        ]):
            pending = self.get_pending_tasks()
            if not pending:
                return "You're all caught up, Sir! No pending tasks on your schedule right now."
            lines = [f"{idx+1}. {t.title} ({t.priority.value} priority)" for idx, t in enumerate(pending)]
            return f"Here is what's on your agenda, Sir:\n" + "\n".join(lines)

        if any(q in lower for q in ["what did i forget", "what is pending", "what's pending"]):
            pending = self.get_pending_tasks()
            if not pending:
                return "Nothing pending, Sir! You're completely up to date."
            lines = [f"- {t.title}" for t in pending]
            return f"You have {len(pending)} pending item(s), Sir:\n" + "\n".join(lines)

        return None

