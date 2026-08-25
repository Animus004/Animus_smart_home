"""
Authoritative Pydantic Data Models for Phase F.1 Animus Personal Agent Intelligence & User Model.
Provides strongly typed models for UserProfile, Memory Taxonomy, Tasks, Reminders,
Intent Resolution, Follow-Up Engine, and Agent Feedback.
"""

from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# 1. 9-Category Agent Memory Taxonomy
# =============================================================================

class MemoryCategory(str, Enum):
    """
    Authoritative 9-tier memory taxonomy for Animus Personal Agent.
    Prevents silent promotion of assumptions into permanent facts.
    """
    STABLE_USER_FACT = "STABLE_USER_FACT"               # e.g., preferred form of address is 'buddy'
    USER_PREFERENCE = "USER_PREFERENCE"                 # e.g., preferred streaming: Netflix, Apple TV, Prime Video
    ROUTINE = "ROUTINE"                                 # e.g., morning summary, work after 11 AM, guitar at 5 PM
    TASK = "TASK"                                       # e.g., learn SQL, work deliverables
    REMINDER = "REMINDER"                               # e.g., guitar practice at 17:00
    TEMPORARY_CONTEXT = "TEMPORARY_CONTEXT"             # e.g., user just reported lunch finished
    OBSERVATION = "OBSERVATION"                         # e.g., user said "I had lunch" at 13:45
    AGENT_ASSUMPTION = "AGENT_ASSUMPTION"               # e.g., user may want to relax after lunch (UNCONFIRMED)
    USER_CONFIRMED_DECISION = "USER_CONFIRMED_DECISION" # e.g., user explicitly chose Netflix for movie


class MemoryItem(BaseModel):
    """A discrete unit of structured agent memory."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: MemoryCategory
    key: str
    content: Any
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = "AGENT_OBSERVATION"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    expires_at: Optional[float] = None
    user_confirmed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


# =============================================================================
# 2. User Identity & Preferences
# =============================================================================

class UserIdentity(BaseModel):
    """Authoritative user identity profile."""
    name: str = "Sayan Halder"
    preferred_address: str = "buddy"
    location_pin: str = "741235"
    privacy_mode: str = "STANDARD_SAFEGUARDS"


class AcPreferenceModel(BaseModel):
    """
    Explicit thermal comfort and AC configuration model.
    CRITICAL DISTINCTION:
    - preferred_ac_setpoint: Target number for AC controller when AC is explicitly active.
    - comfort_preference: Subjective environment feeling (e.g. COOL, MODERATE).
    - work_mode_ac_policy: Thermal policy applied during work hours.
    - explicit_ac_command: Always takes highest precedence.
    """
    preferred_ac_setpoint: int = Field(default=24, ge=16, le=30, description="Stated AC temperature setpoint (16-30°C).")
    comfort_preference: str = Field(default="COOL", description="General thermal comfort (COOL, AUTO, DRY, FAN).")
    work_mode_ac_policy: str = Field(default="MAINTAIN_COMFORT", description="Policy during work (MAINTAIN_COMFORT, ECO, MANUAL_ONLY).")
    preferred_fan_speed: str = Field(default="AUTO", description="Preferred AC fan speed.")


class EntertainmentPreferencesModel(BaseModel):
    """Authoritative entertainment preferences."""
    preferred_movie_devices: List[str] = Field(
        default=["PROJECTOR", "FIRE_TV", "LG_SOUNDBAR"],
        description="Preferred cinema physical device stack."
    )
    preferred_streaming_services: List[str] = Field(
        default=["netflix", "apple_tv", "prime_video", "youtube"],
        description="Ordered preferred media streaming services."
    )
    preferred_volume: int = Field(default=30, ge=0, le=100, description="Default preferred listening volume (~30).")


class NotificationPreferencesModel(BaseModel):
    """Notification and quiet hours preferences."""
    preferred_categories: List[str] = Field(
        default=["alarms", "reminders"],
        description="Allowed proactive notification categories."
    )
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "11:00"  # During work hours
    quiet_hours_end: str = "17:00"
    allow_critical_alerts: bool = True
    allow_user_requested_reminders: bool = True


# =============================================================================
# 3. Daily Routines Model
# =============================================================================

class DailyRoutines(BaseModel):
    """
    Structured routine hints (behavioral preferences, NOT rigid hardcoded sequences).
    """
    morning_wake_enabled: bool = True
    morning_summary_requested: bool = True
    morning_motivation_tune_enabled: bool = True

    work_start_time: str = "11:00"
    learning_priority: str = "learn SQL"
    work_priority: str = "work"

    lunch_trigger_keywords: List[str] = Field(
        default=["i had lunch", "i've had lunch", "just had lunch", "i have lunch", "lunch done", "finished lunch"]
    )
    lunch_transition_suggestions: List[str] = Field(
        default=["guitar practice", "entertainment", "sql study", "music", "relaxation"]
    )

    guitar_reminder_preferred_time: str = "17:00"
    guitar_reminder_lunch_transition_enabled: bool = True

    night_routine_enabled: bool = True
    night_auto_shutdown_devices: bool = False  # DO NOT auto shut down unless explicitly configured


class UserProfile(BaseModel):
    """Authoritative composite user profile."""
    identity: UserIdentity = Field(default_factory=UserIdentity)
    thermal: AcPreferenceModel = Field(default_factory=AcPreferenceModel)
    entertainment: EntertainmentPreferencesModel = Field(default_factory=EntertainmentPreferencesModel)
    notifications: NotificationPreferencesModel = Field(default_factory=NotificationPreferencesModel)
    routines: DailyRoutines = Field(default_factory=DailyRoutines)


# =============================================================================
# 4. Task & Reminder Models
# =============================================================================

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    MISSED = "MISSED"
    SNOOZED = "SNOOZED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskSource(str, Enum):
    USER_REQUESTED = "USER_REQUESTED"
    ROUTINE_SUGGESTED = "ROUTINE_SUGGESTED"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"


class Task(BaseModel):
    """Native task model for bookkeeping and daily briefs."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    description: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    due_at: Optional[float] = None
    recurrence: Optional[str] = None  # None, "DAILY", "WEEKDAYS", "WEEKLY"
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    source: TaskSource = TaskSource.USER_REQUESTED
    user_confirmed: bool = True
    completed_at: Optional[float] = None
    category: str = "GENERAL"  # "WORK", "LEARNING", "PERSONAL", "GENERAL"

    def mark_completed(self) -> None:
        self.status = TaskStatus.COMPLETED
        self.completed_at = time.time()


class Reminder(BaseModel):
    """Scheduled reminder object."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_id: Optional[str] = None
    message: str
    scheduled_time: float
    recurrence: Optional[str] = None
    triggered: bool = False
    acknowledged: bool = False
    created_at: float = Field(default_factory=time.time)


# =============================================================================
# 5. Intent Resolution & Mood / Vibe Vocabulary
# =============================================================================

class IntentCategory(str, Enum):
    """6-tier intent classification."""
    CLEAR_EXECUTABLE = "CLEAR_EXECUTABLE"                                 # Directly map to plan & dispatch
    CLEAR_WITH_MISSING_NON_CRITICAL = "CLEAR_WITH_MISSING_NON_CRITICAL"   # Prepare deterministic room & ask parameter
    AMBIGUOUS_REQUIRES_FOLLOW_UP = "AMBIGUOUS_REQUIRES_FOLLOW_UP"         # Ask clarification before executing
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"                     # Truthfully explain limitation
    UNSAFE_NOT_AUTHORIZED = "UNSAFE_NOT_AUTHORIZED"                       # Fail closed with safety rejection
    INFORMATIONAL_ONLY = "INFORMATIONAL_ONLY"                             # Answer query (time, tasks, weather, capabilities)


class MoodVibe(str, Enum):
    """Controlled mood/vibe intent vocabulary."""
    RELAX = "RELAX"
    FOCUS = "FOCUS"
    ENTERTAINMENT = "ENTERTAINMENT"
    MOVIE = "MOVIE"
    MUSIC = "MUSIC"
    WORK = "WORK"
    SLEEP = "SLEEP"
    WAKE_UP = "WAKE_UP"
    SOCIAL = "SOCIAL"
    QUIET = "QUIET"


class ResolvedIntent(BaseModel):
    """Result of human intent analysis."""
    raw_query: str
    category: IntentCategory
    primary_intent: str
    mood_vibe: Optional[MoodVibe] = None
    target_subsystems: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    extracted_parameters: Dict[str, Any] = Field(default_factory=dict)
    missing_parameters: List[str] = Field(default_factory=list)
    requires_followup: bool = False
    followup_question: Optional[str] = None
    explanation: Optional[str] = None


# =============================================================================
# 6. Interaction & Feedback Models
# =============================================================================

class PhysicalActionAuditRecord(BaseModel):
    """
    Authoritative audit object required for every physical hardware mutation.
    Ensures full explainability of why and how a physical action occurred.
    """
    intent: str
    target: str
    capability: str
    requested_value: Dict[str, Any] = Field(default_factory=dict)
    authorization_source: str
    context_source: str = "CURRENT_TURN_DIRECT"
    confidence_or_resolution: str = "HIGH_CONFIDENCE_DIRECT"
    execution_result: str = "PENDING"
    readback_result: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class AgentInteractionResponse(BaseModel):
    """Structured response from Animus Personal Agent to the user."""
    understood_intent: str
    agent_message: str
    action_taken: bool = False
    deterministic_preparation_done: bool = False
    execution_summary: Optional[Dict[str, Any]] = None
    physical_audits: List[PhysicalActionAuditRecord] = Field(default_factory=list)
    followup_required: bool = False
    followup_question: Optional[str] = None
    task_updates: List[Dict[str, Any]] = Field(default_factory=list)
    memory_updates: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
