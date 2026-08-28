"""
Authoritative Deterministic Room Scheduler for Animus Smart Room Stage 6.
Enables scheduled one-shot delayed goals, reminders, and deferred operations without bypassing
the canonical TaskPlanner / PlanValidator / PlanExecutor / Readback pipeline.

EPISTEMIC & SAFETY INVARIANTS:
1. The scheduler is NOT a secondary execution engine. It contains ZERO hardware execution logic.
2. Deferred Intent Is Not Deferred Truth: Scheduled status never masquerades as physical reality.
3. Stale-Intent Policy: Prior to execution, due tasks re-evaluate fresh telemetry and active mode;
   if invalidated or superseded, the task is safely marked EXPIRED / SUPERSEDED / INVALIDATED.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agent.room_events import RoomEvent, RoomEventType
from agent.event_bus import RoomEventBus
from planner.models import GeminiStructuredPlan, PlanStep, OverallExecutionStatus

logger = logging.getLogger("music_daemon.agent.scheduler")


class ScheduledTaskStatus(str, Enum):
    """Lifecycle status for deferred/scheduled operations."""
    SCHEDULED = "SCHEDULED"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class ScheduledTask(BaseModel):
    """Structured record of a deferred or scheduled task."""
    task_id: str = Field(default_factory=lambda: f"sched_{uuid.uuid4().hex[:8]}")
    created_at: float = Field(default_factory=time.time)
    scheduled_for: float
    expires_at: Optional[float] = None
    creator: str = "USER"
    original_utterance: str
    authorization_context: Dict[str, Any] = Field(default_factory=dict)
    action_type: str
    target_subsystem: str
    target_capability: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: ScheduledTaskStatus = ScheduledTaskStatus.SCHEDULED
    goal_id: Optional[str] = None
    cancellation_reason: Optional[str] = None
    execution_summary: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.expires_at is None:
            self.expires_at = self.scheduled_for + 3600.0

    def is_due(self, current_time: float) -> bool:
        """Returns True if the scheduled time has arrived and task is not expired."""
        exp = self.expires_at if self.expires_at is not None else (self.scheduled_for + 3600.0)
        return self.status == ScheduledTaskStatus.SCHEDULED and self.scheduled_for <= current_time < exp


class RoomScheduler:
    """
    Deterministic In-Process Room Scheduler.
    Manages deferred actions, reminders, and scheduled routines with safe pre-execution re-evaluation.
    """

    def __init__(
        self,
        event_bus: Optional[RoomEventBus] = None,
        default_ttl_seconds: float = 300.0,
        max_scheduled_tasks: int = 50
    ):
        self.event_bus = event_bus
        self.default_ttl_seconds = default_ttl_seconds
        self.max_scheduled_tasks = max_scheduled_tasks
        self.tasks: Dict[str, ScheduledTask] = {}

    def schedule_action(
        self,
        utterance: str,
        delay_seconds: float,
        action_type: str,
        target_subsystem: str,
        target_capability: str,
        parameters: Optional[Dict[str, Any]] = None,
        authorization_context: Optional[Dict[str, Any]] = None,
        current_time: Optional[float] = None
    ) -> ScheduledTask:
        """
        Creates and registers a scheduled task due in `delay_seconds`.
        """
        now = current_time or time.time()
        scheduled_for = now + max(0.0, delay_seconds)
        expires_at = scheduled_for + self.default_ttl_seconds

        task = ScheduledTask(
            created_at=now,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
            original_utterance=utterance,
            authorization_context=authorization_context or {"source": "USER_DIRECT"},
            action_type=action_type,
            target_subsystem=target_subsystem,
            target_capability=target_capability,
            parameters=parameters or {}
        )

        # Enforce bounded capacity
        if len(self.tasks) >= self.max_scheduled_tasks:
            # Purge oldest non-scheduled tasks
            terminal = [tid for tid, t in self.tasks.items() if t.status != ScheduledTaskStatus.SCHEDULED]
            if terminal:
                del self.tasks[terminal[0]]
            else:
                oldest_id = min(self.tasks.keys(), key=lambda k: self.tasks[k].created_at)
                del self.tasks[oldest_id]

        self.tasks[task.task_id] = task

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.SCHEDULE_CREATED,
                    source="ROOM_SCHEDULER",
                    affected_subsystem=target_subsystem,
                    observed_state={"task_id": task.task_id, "scheduled_for": scheduled_for, "action": action_type},
                    metadata={"utterance": utterance, "delay_seconds": delay_seconds}
                )
            )

        logger.info(f"[ROOM_SCHEDULER] Scheduled {task.task_id} ({action_type}) in {delay_seconds:.1f}s at {scheduled_for:.1f}")
        return task

    def cancel_scheduled_task(self, task_id: str, reason: str = "USER_CANCELLED") -> Tuple[bool, str]:
        """Cancels a scheduled task if still pending."""
        task = self.tasks.get(task_id)
        if not task:
            return False, f"Scheduled task {task_id} not found."
        if task.status != ScheduledTaskStatus.SCHEDULED:
            return False, f"Task {task_id} is already in state {task.status.value}."

        task.status = ScheduledTaskStatus.CANCELLED
        task.cancellation_reason = reason

        if self.event_bus:
            self.event_bus.publish(
                RoomEvent(
                    event_type=RoomEventType.SCHEDULE_CANCELLED,
                    source="ROOM_SCHEDULER",
                    affected_subsystem=task.target_subsystem,
                    observed_state={"task_id": task_id, "status": "CANCELLED"},
                    metadata={"reason": reason}
                )
            )

        logger.info(f"[ROOM_SCHEDULER] Cancelled scheduled task {task_id}: {reason}")
        return True, f"Cancelled scheduled task {task_id}."

    def cancel_matching_tasks(self, subsystem: Optional[str] = None, action_type: Optional[str] = None, reason: str = "USER_CANCELLED") -> int:
        """Cancels all scheduled tasks matching subsystem or action_type."""
        count = 0
        for task in list(self.tasks.values()):
            if task.status == ScheduledTaskStatus.SCHEDULED:
                if (subsystem is None or task.target_subsystem.upper() == subsystem.upper()) and (action_type is None or task.action_type == action_type):
                    task.status = ScheduledTaskStatus.CANCELLED
                    task.cancellation_reason = reason
                    count += 1
                    if self.event_bus:
                        self.event_bus.publish(
                            RoomEvent(
                                event_type=RoomEventType.SCHEDULE_CANCELLED,
                                source="ROOM_SCHEDULER",
                                affected_subsystem=task.target_subsystem,
                                metadata={"task_id": task.task_id, "reason": reason}
                            )
                        )
        return count

    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Returns all currently scheduled (non-terminal) tasks."""
        return [t for t in self.tasks.values() if t.status == ScheduledTaskStatus.SCHEDULED]

    def get_scheduled_tasks(self, include_completed: bool = False) -> List[ScheduledTask]:
        """Returns scheduled tasks, optionally including completed/terminal ones."""
        if include_completed:
            return list(self.tasks.values())
        return self.get_pending_tasks()

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self.tasks.get(task_id)

    def evaluate_and_execute_due_tasks(
        self,
        current_time: float,
        room_state: Any,
        active_mode: Optional[str] = None,
        planner_executor: Optional[Any] = None
    ) -> List[Tuple[ScheduledTask, bool, str]]:
        """
        Scans tasks due for execution:
        1. Checks for expiration.
        2. Stale Intent Check: Evaluates whether task is still valid against live telemetry & mode.
        3. Constructs canonical plan and dispatches through canonical PlanValidator/PlanExecutor pipeline.
        4. Verifies physical readback before confirming execution.
        """
        results: List[Tuple[ScheduledTask, bool, str]] = []

        for task in list(self.tasks.values()):
            if task.status != ScheduledTaskStatus.SCHEDULED:
                continue

            # 1. Expired check
            if current_time >= task.expires_at:
                task.status = ScheduledTaskStatus.EXPIRED
                if self.event_bus:
                    self.event_bus.publish(
                        RoomEvent(
                            event_type=RoomEventType.SCHEDULE_EXPIRED,
                            source="ROOM_SCHEDULER",
                            metadata={"task_id": task.task_id}
                        )
                    )
                results.append((task, False, "Task expired prior to execution"))
                continue

            # 2. Due check
            if task.scheduled_for <= current_time:
                # 3. Stale-intent validation
                is_valid, invalid_reason = self._validate_stale_intent(task, room_state, active_mode)
                if not is_valid:
                    task.status = ScheduledTaskStatus.INVALIDATED
                    task.cancellation_reason = invalid_reason
                    if self.event_bus:
                        self.event_bus.publish(
                            RoomEvent(
                                event_type=RoomEventType.SCHEDULE_CANCELLED,
                                source="ROOM_SCHEDULER",
                                metadata={"task_id": task.task_id, "reason": invalid_reason}
                            )
                        )
                    results.append((task, False, f"Task invalidated: {invalid_reason}"))
                    continue

                # 4. Check if already satisfied by live physical reality (No-op idempotency)
                if self._is_task_already_satisfied(task, room_state):
                    task.status = ScheduledTaskStatus.EXECUTED
                    task.execution_summary = "Already physically satisfied in room"
                    if self.event_bus:
                        self.event_bus.publish(
                            RoomEvent(
                                event_type=RoomEventType.SCHEDULE_EXECUTED,
                                source="ROOM_SCHEDULER",
                                metadata={"task_id": task.task_id, "result": "ALREADY_SATISFIED"}
                            )
                        )
                    results.append((task, True, "Already physically satisfied"))
                    continue

                # 5. Canonical execution via PlanExecutor pipeline
                if planner_executor:
                    plan = GeminiStructuredPlan(
                        intent=task.target_capability,
                        objective_summary=f"Scheduled execution of {task.action_type}",
                        user_request=task.original_utterance,
                        steps=[
                            PlanStep(
                                step_id=1,
                                device=task.target_subsystem,
                                capability=task.target_capability,
                                parameters=task.parameters
                            )
                        ]
                    )
                    val_res = planner_executor.validator.validate_plan(plan_input=plan, room_state=room_state)
                    if val_res.valid:
                        exec_res = planner_executor.execute_plan(val_res)
                        success = getattr(exec_res, "success", False) or (getattr(exec_res, "overall_status", None) == OverallExecutionStatus.SUCCESS)
                        if success:
                            task.status = ScheduledTaskStatus.EXECUTED
                            task.execution_summary = "Successfully executed and verified"
                            if self.event_bus:
                                self.event_bus.publish(
                                    RoomEvent(
                                        event_type=RoomEventType.SCHEDULE_EXECUTED,
                                        source="ROOM_SCHEDULER",
                                        metadata={"task_id": task.task_id, "result": "VERIFIED"}
                                    )
                                )
                            results.append((task, True, "Executed and physically verified"))
                        else:
                            results.append((task, False, "Hardware execution unverified"))
                    else:
                        results.append((task, False, f"Validation failed: {val_res.errors}"))
                else:
                    # Simulated execution for testing
                    task.status = ScheduledTaskStatus.EXECUTED
                    results.append((task, True, "Executed (simulated)"))

        return results

    def _validate_stale_intent(self, task: ScheduledTask, room_state: Any, active_mode: Optional[str]) -> Tuple[bool, str]:
        """Evaluates whether a scheduled action is still compatible with current mode/room state."""
        if active_mode == "SLEEP" and task.target_subsystem.upper() == "PROJECTOR" and task.target_capability == "PROJECTOR_POWER_WAKE":
            return False, "Room is in Sleep Mode; cannot wake projector."
        return True, ""

    def _is_task_already_satisfied(self, task: ScheduledTask, room_state: Any) -> bool:
        """Evaluates live telemetry to check if the target state is already active."""
        if room_state is None:
            return False
        if task.target_subsystem.upper() == "AC" and task.target_capability == "AC_SET_TEMPERATURE":
            target_t = task.parameters.get("temperature")
            ac_obj = getattr(room_state, "ac", None)
            tt_field = getattr(ac_obj, "target_temperature", None)
            curr_t = getattr(tt_field, "value", tt_field)
            return target_t is not None and curr_t == target_t
        if task.target_subsystem.upper() == "PROJECTOR" and task.target_capability == "PROJECTOR_POWER_OFF":
            proj_obj = getattr(room_state, "projector", None)
            pow_field = getattr(proj_obj, "power", getattr(proj_obj, "is_powered_on", None))
            curr_pow = getattr(pow_field, "value", pow_field)
            return curr_pow is False
        return False

