"""
================================================================================
ANIMUS SMART ROOM — AGENT DECISION & REASONING ENGINE
================================================================================
Implements the core cognitive loop:
PERCEIVE (Time + Room State + Memory RAG)
  ↓
REASON (Local Ollama Qwen 4B Instruct with Gemini Cloud Fallback)
  ↓
VALIDATE (Deterministic Hardware Bounds & Safety Rules)
  ↓
ACT (Idempotent Sequential Physical Execution)
  ↓
OBSERVE (Fresh Physical Telemetry Readback Verification)
  ↓
REMEMBER & TRACK (Epistemic Facts & Continuous Goals Persistence)
  ↓
RESPOND (Concise, Truthful Conversational Feedback)
================================================================================
"""

from __future__ import annotations
import datetime
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
import requests
from pydantic import BaseModel, Field

from agent.prompt_builder import CognitivePromptBuilder
from agent.long_term_memory import LongTermMemoryStore, get_long_term_memory
from room_state.models import RoomState
from planner.models import GeminiStructuredPlan, PlanStep, FailurePolicy, ExecutionMode

logger = logging.getLogger("music_daemon.agent.decision_engine")


def parse_reminder_intention(
    utterance: str,
    current_time: Optional[float] = None,
    default_subject: Optional[str] = None,
    default_day: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Intelligently extracts:
    - day: 'today' | 'tomorrow' | 'relative'
    - time_str: formatted time e.g. '5:00 pm', '10:00 am'
    - subject: what the reminder is for e.g. 'Start work', 'Practice SQL'
    - scheduled_time: Unix timestamp of the target alarm/reminder
    - response_message: e.g. 'Reminder set for today at 5:00 pm to start work, Sir.'
    """
    now = current_time if current_time is not None else time.time()
    dt_now = datetime.datetime.fromtimestamp(now)
    lower = utterance.strip().lower()

    # Relative offset: e.g. "in 30 minutes to check oven"
    rel_match = re.search(r'\bin\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?)\b', lower)
    if rel_match:
        num = int(rel_match.group(1))
        unit = rel_match.group(2)
        secs = num * 60 if 'min' in unit else (num * 3600 if 'hour' in unit or 'hr' in unit else num)
        sched_time = now + secs
        dt_target = datetime.datetime.fromtimestamp(sched_time)
        t_str = dt_target.strftime('%I:%M %p').lstrip('0').lower()
        cleaned = re.sub(r'\bin\s+\d+\s*(?:minutes?|mins?|hours?|hrs?|seconds?|secs?)\b', '', lower)
        for p in ['remind me to', 'remind me about', 'remind me', 'set a reminder to', 'set a reminder for', 'set a reminder', 'set reminder to', 'set reminder']:
            cleaned = cleaned.replace(p, '')
        while cleaned.lower().startswith(('to ', 'about ', 'for ')):
            cleaned = re.sub(r'^(?:to|about|for)\s+', '', cleaned, flags=re.IGNORECASE).strip()
        subj = cleaned.strip(' .,').capitalize() or (default_subject or 'Work session')
        day_str = 'today' if dt_target.date() == dt_now.date() else 'tomorrow'
        return {
            'day': day_str,
            'time_str': t_str,
            'subject': subj,
            'scheduled_time': sched_time,
            'response_message': f'Reminder set for {num} {unit} from now (at {t_str}) to {subj.lower()}, Sir.'
        }

    # Explicit day determination
    explicit_day = None
    if any(w in lower for w in ['today', 'tonight', 'this evening', 'this afternoon', 'later today']):
        explicit_day = 'today'
    elif any(w in lower for w in ['tomorrow morning', 'tomorrow evening', 'tomorrow']):
        explicit_day = 'tomorrow'

    # Time extraction
    time_match = re.search(r'\b(?:at\s+|for\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2}|\d{1,2}\s*(?:am|pm)|noon|midnight)\b', lower)
    if not time_match:
        digit_match = re.search(r'\b(?:at\s+|for\s+)(\d{1,2})\b', lower)
        if digit_match:
            time_match = digit_match

    if not time_match:
        return None

    raw_time = time_match.group(1) if time_match.lastindex else time_match.group(0)
    clean_t = re.sub(r'^(?:at|for)\s+', '', raw_time).strip()

    if clean_t == 'noon':
        h, m_min = 12, 0
    elif clean_t == 'midnight':
        h, m_min = 0, 0
    else:
        m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', clean_t)
        if not m:
            return None
        h = int(m.group(1))
        m_min = int(m.group(2)) if m.group(2) else 0
        merid = m.group(3)
        if merid == 'pm' and h < 12:
            h += 12
        elif merid == 'am' and h == 12:
            h = 0
        elif not merid:
            if h < 7 and 'morning' not in lower:
                h += 12
            elif ('evening' in lower or 'night' in lower) and h < 12:
                h += 12

    disp_m = 'am' if h < 12 else 'pm'
    disp_h = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
    time_str = f'{disp_h}:{m_min:02d} {disp_m}'

    if explicit_day == 'today':
        target_date = dt_now.date()
        day = 'today'
    elif explicit_day == 'tomorrow':
        target_date = dt_now.date() + datetime.timedelta(days=1)
        day = 'tomorrow'
    else:
        cand_dt = datetime.datetime.combine(dt_now.date(), datetime.time(h, m_min, 0))
        if cand_dt.timestamp() > now:
            target_date = dt_now.date()
            day = 'today'
        else:
            target_date = dt_now.date() + datetime.timedelta(days=1)
            day = 'tomorrow'
        if default_day:
            day = default_day
            target_date = dt_now.date() if day == 'today' else dt_now.date() + datetime.timedelta(days=1)

    target_dt = datetime.datetime.combine(target_date, datetime.time(h, m_min, 0))
    scheduled_time = target_dt.timestamp()

    # Subject extraction
    cleaned = lower
    for p in ['remind me to', 'remind me about', 'remind me', 'set a reminder to', 'set a reminder for', 'set a reminder about', 'set a reminder', 'set reminder to', 'set reminder for', 'set reminder', 'schedule a reminder to', 'schedule a reminder', 'schedule reminder to', 'schedule reminder', 'yes', 'yeah', 'please', 'sure', 'ok', 'okay', 'do it']:
        cleaned = re.sub(r'\b' + re.escape(p) + r'\b', '', cleaned)
    for d_w in ['today', 'tonight', 'this evening', 'this afternoon', 'tomorrow morning', 'tomorrow evening', 'tomorrow']:
        cleaned = re.sub(r'\b' + re.escape(d_w) + r'\b', '', cleaned)
    cleaned = re.sub(r'\b(?:at|for)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b', '', cleaned)
    cleaned = re.sub(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b', '', cleaned)
    cleaned = cleaned.strip(' .,')
    while cleaned.lower().startswith(('to ', 'about ', 'for ')):
        cleaned = re.sub(r'^(?:to|about|for)\s+', '', cleaned, flags=re.IGNORECASE).strip()

    subj = cleaned.capitalize() if cleaned else (default_subject or 'Work session')
    action_phrase = f"to {subj.lower()}" if not subj.lower().startswith(('to ', 'about ')) else subj.lower()
    resp = f'Reminder set for {day} at {time_str} {action_phrase}, Sir.'

    return {
        'day': day,
        'time_str': time_str,
        'subject': subj,
        'scheduled_time': scheduled_time,
        'response_message': resp
    }


class AgentDecisionResult(BaseModel):
    """Authoritative result payload of an agent cognitive decision cycle."""
    thought: str
    action_type: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    execution_results: List[Dict[str, Any]] = Field(default_factory=list)
    verified_physical_status: str = "VERIFIED_UNCHANGED"
    goal_updated: Optional[Dict[str, Any]] = None
    response_message: str
    inference_source: str = "LOCAL_OLLAMA"
    latency_seconds: float = 0.0
    expression_payload: Optional[Dict[str, Any]] = None
    relevant_memories: List[Dict[str, Any]] = Field(default_factory=list)


class AgentDecisionEngine:
    """
    Cognitive decision engine orchestrating reasoning, tool actuation,
    and memory persistence for Animus.
    """

    def __init__(
        self,
        ollama_url: str = "http://127.0.0.1:11434",
        ollama_model: str = "qwen3:4b-instruct",
        memory_store: Optional[LongTermMemoryStore] = None,
        prompt_builder: Optional[CognitivePromptBuilder] = None,
        planner_executor: Optional[Any] = None,
        planner_validator: Optional[Any] = None,
        gemini_client: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        task_manager: Optional[Any] = None,
        pc_controller: Optional[Any] = None
    ):
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.memory_store = memory_store or get_long_term_memory()
        self.prompt_builder = prompt_builder or CognitivePromptBuilder(memory_store=self.memory_store)
        self.planner_executor = planner_executor
        self.planner_validator = planner_validator
        self.gemini_client = gemini_client
        self.orchestrator = orchestrator
        self.task_manager = task_manager
        self.pc_controller = pc_controller
        self._wrapup_followup_state: Optional[str] = None
        self._wrapup_context_data: Dict[str, Any] = {}
        self._proactive_followup_state: Optional[Dict[str, Any]] = None
        from agent.personal_reasoner import PersonalReasoningEngine
        self.personal_reasoner = PersonalReasoningEngine(memory_store=self.memory_store)
        from agent.reality_observer import RealityObserver
        self.reality_observer = RealityObserver()

    def set_pending_proactive_followup(
        self,
        category: str,
        followup_context: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Stages an active proactive ambient proposal in the decision engine for conversational resolution."""
        self._proactive_followup_state = {
            "category": category,
            "context": followup_context,
            "message": message,
            "metadata": metadata or {},
            "created_at": time.time(),
            "expires_at": time.time() + 180.0  # 3 minute conversational TTL
        }
        logger.info(f"[DECISION_ENGINE] Staged pending proactive follow-up: {category} ({followup_context})")

    def _handle_proactive_followup_turn(self, raw: str, lower: str) -> Optional[Dict[str, Any]]:
        """Resolves conversational responses to proactive ambient suggestions."""
        if not self._proactive_followup_state:
            return None

        # Check TTL
        if time.time() > self._proactive_followup_state.get("expires_at", float("inf")):
            self._proactive_followup_state = None
            return None

        state = self._proactive_followup_state
        cat = state.get("category", "")
        ctx = state.get("context", "")
        prompt = state.get("message", "")

        # If user explicitly issued a hardware or distinct subsystem command, it's NOT a proactive followup response
        is_hw_subsystem = (
            re.search(r'\b(?:projector|movie|ac|air conditioner|soundbar|volume|workbench|sql|weather|done with work|wrap up|start work)\b', lower) is not None
        )
        # Check if user issued an explicit media/playback command
        is_media_command = (
            lower.startswith("play ") or lower.startswith("listen to ") or lower.startswith("queue ")
        )
        if is_media_command:
            # Only allow morning briefing to handle if specifically requesting focus playlist / morning music
            if (cat == "MORNING_GREETING" or ctx == "PROACTIVE_MORNING_BRIEFING") and any(w in lower for w in ["focus", "morning", "playlist"]):
                pass
            else:
                self._proactive_followup_state = None
                return None

        if is_hw_subsystem:
            self._proactive_followup_state = None
            return None

        # Check for affirmative responses
        is_aff = any(re.search(rf'\b{re.escape(w)}\b', lower) for w in [
            "yes", "yeah", "sure", "please", "yep", "do it", "go ahead", "okay", "ok", 
            "take a break", "break", "dim", "soothing", "relax", "turn on", "turn off", 
            "guitar", "practice", "standby", "print", "music", "song", "playlist", "play it", "play that", "sheet", "checklist", "both"
        ]) or lower.strip() in ["play", "cue"]
        # Check for rejection / snooze responses
        is_neg = any(re.search(rf'\b{re.escape(w)}\b', lower) for w in [
            "no", "nah", "don't", "dont", "not now", "later", "leave it", "leave it off",
            "cancel", "still working", "keep working", "working", "study", "studying", "busy", "snooze"
        ])

        if is_aff and not is_neg:
            self._proactive_followup_state = None
            if cat in ["WORK_SESSION_FATIGUE", "LATE_NIGHT_FATIGUE"] or ctx == "PROACTIVE_WORK_FATIGUE_TRANSITION":
                return {
                    "thought": "Proactive work fatigue accepted: transitioning to RELAX break.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "PC_SET_VOLUME", "params": {"volume": 10}},
                        {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}}
                    ],
                    "light_cue": "REST_AMBER",
                    "ui_state": {"mode": "RELAX", "status": "break"},
                    "sound_cue": "SOOTHING_CHILL",
                    "goal_update": None,
                    "response_message": "Setting things to relax mode for your break, Sir. Take your time."
                }
            elif cat == "WORK_SESSION_WRAPUP" or ctx == "PROACTIVE_WORK_WRAPUP":
                return {
                    "thought": "Proactive wrapup accepted: saving work and setting to RELAX.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "WRAPUP_WORK_SESSION", "params": {"outcome": "NO_PROGRESS"}}
                    ],
                    "light_cue": "RELAX_AMBER",
                    "ui_state": {"mode": "RELAX", "status": "wrapped_up"},
                    "goal_update": None,
                    "response_message": "Progress saved and work applications closed, Sir. Room is set to relax mode."
                }
            elif cat == "THERMAL_CARE" or ctx == "PROACTIVE_THERMAL_CARE":
                temp = 24
                if "19" in prompt or "chilly" in prompt.lower():
                    temp = 25
                return {
                    "thought": f"Proactive thermal care accepted: adjusting AC to {temp}°C.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": temp}},
                        {"tool": "AC_SET_MODE", "params": {"mode": "COOL"}}
                    ],
                    "light_cue": "CLIMATE_PULSE",
                    "goal_update": None,
                    "response_message": f"Setting the AC to {temp}°C COOL, Sir."
                }
            elif cat == "IDLE_OPTICAL_PROTECTION" or ctx == "PROACTIVE_IDLE_OPTICAL":
                return {
                    "thought": "Proactive optical protection accepted: standby projector.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "PROJECTOR_POWER_OFF", "params": {}}
                    ],
                    "goal_update": None,
                    "response_message": "Projector set to standby, Sir."
                }
            elif cat == "ROUTINE_ANTICIPATION" or ctx == "PROACTIVE_ROUTINE_GUITAR":
                return {
                    "thought": "Proactive guitar routine accepted: transitioning to RELAX.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}}
                    ],
                    "light_cue": "RELAX_AMBER",
                    "ui_state": {"mode": "RELAX", "status": "guitar_practice"},
                    "goal_update": None,
                    "response_message": "Setting up for your guitar practice session, Sir. Enjoy your playing."
                }
            elif cat == "MORNING_GREETING" or ctx == "PROACTIVE_MORNING_BRIEFING":
                if any(w in lower for w in ["print", "sheet", "paper", "checklist", "plan", "sql"]):
                    from agent.briefing_service import BriefingService
                    bs = BriefingService(memory_store=self.memory_store, task_manager=self.task_manager)
                    sheet_path = bs.generate_executive_printable_sheet(sheet_type="MORNING_PLAN")
                    if any(m in lower for m in ["both", "and music", "music too", "with music"]):
                        return {
                            "thought": "Proactive morning briefing accepted: printing daily plan and starting focus music.",
                            "action_type": "TOOL_EXECUTION",
                            "tool_calls": [
                                {"tool": "PRINTER_PRINT_FILE", "params": {"file_path": sheet_path}},
                                {"tool": "SOUNDBAR_ROUTE_TO_PC", "params": {}},
                                {"tool": "PC_MEDIA_PLAY", "params": {"query": "morning focus"}}
                            ],
                            "response_message": "Printing your daily executive plan on the HP Ink Tank 310 and starting your morning focus music, Sir."
                        }
                    return {
                        "thought": "Proactive morning briefing accepted: printing daily plan.",
                        "action_type": "TOOL_EXECUTION",
                        "tool_calls": [
                            {"tool": "PRINTER_PRINT_FILE", "params": {"file_path": sheet_path}}
                        ],
                        "response_message": "Printing your daily executive plan on the HP Ink Tank 310, Sir. Let me know when you're ready to begin your work session."
                    }
                elif any(w in lower for w in ["music", "song", "playlist", "focus"]):
                    return {
                        "thought": "Proactive morning briefing accepted: starting morning playlist.",
                        "action_type": "TOOL_EXECUTION",
                        "tool_calls": [
                            {"tool": "SOUNDBAR_ROUTE_TO_PC", "params": {}},
                            {"tool": "PC_MEDIA_PLAY", "params": {"query": "morning focus"}}
                        ],
                        "response_message": "Starting your morning focus playlist on the soundbar, Sir. Have a productive day."
                    }
                else:
                    return {
                        "thought": "Proactive morning greeting accepted.",
                        "action_type": "CONVERSATION",
                        "tool_calls": [],
                        "goal_update": None,
                        "response_message": "Have a wonderful morning, Sir. Let me know whenever you'd like to begin your work session."
                    }
            elif cat == "EVENING_DEBRIEF" or ctx == "PROACTIVE_EVENING_DEBRIEF":
                if any(w in lower for w in ["print", "sheet", "paper", "checklist", "tomorrow"]):
                    from agent.briefing_service import BriefingService
                    bs = BriefingService(memory_store=self.memory_store, task_manager=self.task_manager)
                    sheet_path = bs.generate_executive_printable_sheet(sheet_type="EVENING_DEBRIEF")
                    if any(g in lower for g in ["both", "and guitar", "guitar too", "with guitar", "yes", "sure"]):
                        return {
                            "thought": "Proactive evening debrief accepted: printing checklist and cueing guitar practice.",
                            "action_type": "TOOL_EXECUTION",
                            "tool_calls": [
                                {"tool": "PRINTER_PRINT_FILE", "params": {"file_path": sheet_path}},
                                {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}},
                                {"tool": "SOUNDBAR_ROUTE_TO_PC", "params": {}}
                            ],
                            "response_message": "Printing tomorrow's checklist on the HP Ink Tank 310 and cueing your guitar session on the soundbar, Sir."
                        }
                    return {
                        "thought": "Proactive evening debrief accepted: printing checklist.",
                        "action_type": "TOOL_EXECUTION",
                        "tool_calls": [
                            {"tool": "PRINTER_PRINT_FILE", "params": {"file_path": sheet_path}}
                        ],
                        "response_message": "Printing tomorrow's checklist on the HP Ink Tank 310, Sir. Rest well tonight."
                    }
                elif any(w in lower for w in ["guitar", "practice"]):
                    return {
                        "thought": "Proactive evening debrief accepted: transitioning to guitar session.",
                        "action_type": "TOOL_EXECUTION",
                        "tool_calls": [
                            {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}},
                            {"tool": "SOUNDBAR_ROUTE_TO_PC", "params": {}}
                        ],
                        "response_message": "Setting up for your guitar practice session, Sir. Enjoy your playing."
                    }
                else:
                    from agent.briefing_service import BriefingService
                    bs = BriefingService(memory_store=self.memory_store, task_manager=self.task_manager)
                    sheet_path = bs.generate_executive_printable_sheet(sheet_type="EVENING_DEBRIEF")
                    return {
                        "thought": "Proactive evening debrief accepted: printing checklist and cueing guitar session.",
                        "action_type": "TOOL_EXECUTION",
                        "tool_calls": [
                            {"tool": "PRINTER_PRINT_FILE", "params": {"file_path": sheet_path}},
                            {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}},
                            {"tool": "SOUNDBAR_ROUTE_TO_PC", "params": {}}
                        ],
                        "response_message": "Printing tomorrow's checklist on the HP Ink Tank 310 and cueing your guitar session, Sir."
                    }

        elif is_neg:
            self._proactive_followup_state = None
            if cat in ["WORK_SESSION_FATIGUE", "LATE_NIGHT_FATIGUE"]:
                return {
                    "thought": "Proactive work fatigue declined/snoozed: keeping work active.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "Understood, Sir. Keeping your work focus active."
                }
            elif cat == "ROUTINE_ANTICIPATION":
                return {
                    "thought": "Proactive routine declined: continuing study.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "Understood, Sir. Keeping your study focus active."
                }
            elif cat in ["EVENING_DEBRIEF", "MORNING_GREETING"]:
                return {
                    "thought": "Proactive briefing/debrief declined.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "Understood, Sir. I'm standing by whenever you need me."
                }
            else:
                return {
                    "thought": "Proactive suggestion declined.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "Understood, Sir. Leaving things as they are."
                }

        return None

    # =========================================================================
    # Primary Cognitive Entry Point: decide_and_act()
    # =========================================================================

    # =========================================================================
    # Deterministic Fast-Path Evaluation (< 50ms)
    # =========================================================================

    def _handle_wrapup_followup_turn(self, raw: str, lower: str) -> Optional[Dict[str, Any]]:
        """Handles multi-turn conversational reasoning for session wrap-up and reminder preferences."""
        # 0. Check if user pivoted to an unrelated query, status inquiry, or room device command
        is_pivot_or_query = (
            any(lower.startswith(q) for q in ["what", "how", "when", "where", "who", "why", "which", "is", "are", "can", "could", "will", "do", "does", "tell"]) or
            "?" in lower or
            any(w in lower for w in [
                "mode", "temperature", "temp", "volume", "soundbar", "speaker",
                "projector", "ac", "light", "play", "pause", "resume", "stop",
                "status", "who are you", "weather", "time"
            ])
        )
        if is_pivot_or_query:
            # User is asking a question (e.g. "what mode is the room in?") or issuing a command.
            # Do NOT hijack the conversation or fabricate milestone completions.
            self._wrapup_followup_state = None
            return None

        curr_sg = self.memory_store.get_current_work_subgoal()
        sg_title = curr_sg.get("title", "your milestone") if curr_sg else "your milestone"

        # 1. User was asked for work summary / progress confirmation
        if self._wrapup_followup_state == "AWAITING_WORK_SUMMARY":
            # Check for no work / break
            if any(w in lower for w in ["didn't do anything", "did nothing", "didn't work", "took a break", "taking a break", "nothing", "no progress", "no", "not really", "rest", "rest day", "tired", "didn't study", "nope", "break"]):
                self.memory_store.process_work_session_outcome("NO_PROGRESS")
                self._wrapup_followup_state = "AWAITING_REMINDER_DECISION"
                return {
                    "thought": "Work session wrap-up: user confirmed zero work/break. Marked NO_PROGRESS. Inquiring about reminder.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": f"Understood, Sir. No milestone changes recorded—your current focus '{sg_title}' remains active. Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"
                }
            # Check for partial progress
            elif any(w in lower for w in ["partial", "partially", "halfway", "still working", "in progress", "stuck", "started", "some queries", "not yet", "not finished"]):
                self.memory_store.process_work_session_outcome("PARTIAL", user_summary=raw)
                self._wrapup_followup_state = "AWAITING_REMINDER_DECISION"
                return {
                    "thought": "Work session wrap-up: user logged partial progress. Maintained active milestone. Inquiring about reminder.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": f"Logged your partial progress, Sir. We'll continue '{sg_title}' in your next session. Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"
                }
            # Milestone completed or detailed work summary
            elif any(w in lower for w in ["yes", "yeah", "completed", "finished", "done", "solved", "implemented", "finished the sql", "completed the sql", "completed today's milestone", "finished milestone"]) or any(k in lower for k in ["cte", "lag", "query", "queries", "sql", "formula", "excel", "dataset"]):
                wrap_res = self.memory_store.process_work_session_outcome("COMPLETED", user_summary=raw)
                comp_title = wrap_res.get("completed_subgoal", {}).get("title", sg_title)
                next_title = wrap_res.get("next_subgoal", {}).get("title", "Tomorrow's focus")
                self._wrapup_followup_state = "AWAITING_REMINDER_DECISION"
                return {
                    "thought": "Work session wrap-up: milestone completed and advanced. Inquiring about reminder.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": f"Outstanding progress today, Sir! Milestone '{comp_title}' is marked complete and '{next_title}' is queued on your roadmap. Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"
                }
            else:
                self._wrapup_followup_state = None
                return None

        # 2. User was asked if they want a reminder
        if self._wrapup_followup_state == "AWAITING_REMINDER_DECISION":
            # Explicit negative or decline: NEVER set reminder autonomously
            if any(w in lower for w in ["no", "nah", "don't", "dont", "leave it", "no reminder", "unscheduled", "not needed", "leave it off", "skip", "no thanks", "nope", "negative", "none"]):
                self._wrapup_followup_state = None
                return {
                    "thought": "User explicitly declined reminder.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "Understood, Sir. Leaving your schedule open with no reminders set. Have a restful evening."
                }

            # Check if user provided reminder day, time and/or subject
            parsed = parse_reminder_intention(
                raw,
                current_time=time.time(),
                default_subject=f"Resume Data Analyst session ({sg_title})" if sg_title else "Resume session",
                default_day="tomorrow"
            )
            if parsed:
                self._wrapup_followup_state = None
                action_text = parsed["subject"]
                action_display = action_text.lower() if action_text.lower().startswith(("to ", "about ")) else f"to {action_text.lower()}"
                return {
                    "thought": f"User requested reminder: {parsed['subject']} on {parsed['day']} at {parsed['time_str']}.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [{
                        "tool": "CREATE_TASK",
                        "params": {
                            "title": f"Reminder: {parsed['subject']}",
                            "description": f"Scheduled for {parsed['day']} at {parsed['time_str']}",
                            "priority": "HIGH",
                            "category": "REMINDER",
                            "scheduled_time": parsed["scheduled_time"]
                        }
                    }],
                    "goal_update": None,
                    "response_message": f"Reminder set for {parsed['day']} at {parsed['time_str']} {action_display}, Sir. Have a restful evening."
                }
            # Affirmative WITHOUT a time -> ask when they want to work
            elif any(w in lower for w in ["yes", "yeah", "sure", "please", "yep", "do it", "set a reminder", "set reminder", "okay", "ok"]):
                self._wrapup_followup_state = "AWAITING_REMINDER_TIME"
                return {
                    "thought": "User wants a reminder; prompting for preferred time.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "What time would you like me to set the reminder for, Sir? (e.g. 'today at 5 PM' or 'tomorrow at 10 AM')"
                }

        # 3. User was asked for the reminder time
        if self._wrapup_followup_state == "AWAITING_REMINDER_TIME":
            if any(w in lower for w in ["never mind", "cancel", "no", "nah", "skip"]):
                self._wrapup_followup_state = None
                return {
                    "thought": "User cancelled reminder time entry.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": "Cancelled, Sir. No reminders set. Have a restful evening."
                }
            parsed = parse_reminder_intention(
                raw,
                current_time=time.time(),
                default_subject=f"Resume Data Analyst session ({sg_title})" if sg_title else "Resume session",
                default_day="tomorrow"
            )
            if parsed:
                self._wrapup_followup_state = None
                action_text = parsed["subject"]
                action_display = action_text.lower() if action_text.lower().startswith(("to ", "about ")) else f"to {action_text.lower()}"
                return {
                    "thought": f"User provided reminder time: {parsed['time_str']}.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [{
                        "tool": "CREATE_TASK",
                        "params": {
                            "title": f"Reminder: {parsed['subject']}",
                            "description": f"Scheduled for {parsed['day']} at {parsed['time_str']}",
                            "priority": "HIGH",
                            "category": "REMINDER",
                            "scheduled_time": parsed["scheduled_time"]
                        }
                    }],
                    "goal_update": None,
                    "response_message": f"Reminder set for {parsed['day']} at {parsed['time_str']} {action_display}, Sir. Have a restful evening."
                }

        return None

    def _decompose_compound_utterance(self, raw_utterance: str) -> List[str]:
        """
        Decomposes compound sentences or multi-clause instructions into distinct sequential command clauses.
        Splits on conjunctions ('and then', 'and also', 'then', 'also', 'plus', 'and') and punctuation (';', '\n', ',').
        """
        raw = raw_utterance.strip()
        if not raw:
            return []

        lower = raw.lower()
        # Protect work summaries, ChatGPT milestone logs, and project narratives from splitting
        if any(k in lower for k in [
            "chatgpt", "today i completed", "today i worked", "today i did", "today's work",
            "summary of my work", "here is what i did", "completed the sql", "blinkit",
            "career goal", "milestone", "stakeholder", "sq1", "sq2", "sq3", "sq4", "sq5",
            "replenish", "out-of-stock", "lost revenue"
        ]):
            return [raw]

        # Protect explicit reminder statements if they contain internal conjunctions
        if re.search(r'\b(?:remind me|set a reminder|schedule a reminder)\b', lower) and not any(w in lower for w in [";", "\n", "also", "then", "plus"]):
            return [raw]

        pattern = re.compile(
            r'(?:;\s*|\n+|\s*\band\s+then\b\s*|\s*\band\s+also\b\s*|\s*\band\b\s*|\s*\bthen\b\s*|\s*\balso\b\s*|\s*\bplus\b\s*|,\s*)',
            re.IGNORECASE
        )
        parts = [p.strip() for p in pattern.split(raw) if p.strip()]

        cleaned_parts = []
        for p in parts:
            p_clean = re.sub(r'^(?:animus\s*,?|please\s*|kindly\s*|could you\s*|can you\s*|would you\s*)+', '', p, flags=re.IGNORECASE).strip()
            if p_clean:
                cleaned_parts.append(p_clean)

        return cleaned_parts

    def _try_compound_fastpath_decision(
        self,
        user_utterance: str,
        room_state: Optional[RoomState] = None,
        active_mode: str = "IDLE"
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts and executes multi-command instructions deterministically across subsystems
        (e.g., 'turn off the AC, turn on the projector, and play focus beats').
        """
        parts = self._decompose_compound_utterance(user_utterance)
        if len(parts) <= 1:
            return None

        sub_decisions = []
        for part in parts:
            dec = self._try_single_fastpath_decision(part, room_state, active_mode)
            # Every extracted clause in a compound fast-path MUST resolve to actionable tool calls
            if not dec or not dec.get("tool_calls"):
                return None
            sub_decisions.append((part, dec))

        aggregated_tool_calls = []
        for _, dec in sub_decisions:
            aggregated_tool_calls.extend(dec.get("tool_calls", []))

        if not aggregated_tool_calls:
            return None

        # Synthesize clean, natural unified conversational feedback
        clean_messages = []
        for _, dec in sub_decisions:
            msg = dec.get("response_message", "").strip()
            msg = re.sub(r',?\s*Sir\.?$', '', msg, flags=re.IGNORECASE).strip()
            msg = re.sub(r'[\.!\?]+$', '', msg).strip()
            if msg:
                clean_messages.append(msg)

        if not clean_messages:
            synthesized_msg = "All requested actions executed, Sir."
        elif len(clean_messages) == 1:
            synthesized_msg = f"{clean_messages[0]}, Sir."
        elif len(clean_messages) == 2:
            c2 = clean_messages[1]
            if len(c2) > 1 and c2[0].isupper() and not c2[1].isupper():
                c2 = c2[0].lower() + c2[1:]
            synthesized_msg = f"{clean_messages[0]} and {c2}, Sir."
        else:
            first_parts = clean_messages[:-1]
            last_part = clean_messages[-1]
            if len(last_part) > 1 and last_part[0].isupper() and not last_part[1].isupper():
                last_part = last_part[0].lower() + last_part[1:]
            synthesized_msg = f"{', '.join(first_parts)}, and {last_part}, Sir."

        tool_summary = ", ".join(tc.get("tool", "TOOL") for tc in aggregated_tool_calls)
        return {
            "thought": f"Fast-path multi-command execution across {len(aggregated_tool_calls)} actions: {tool_summary}.",
            "action_type": "TOOL_EXECUTION",
            "tool_calls": aggregated_tool_calls,
            "goal_update": None,
            "response_message": synthesized_msg
        }

    def _try_fastpath_decision(
        self,
        user_utterance: str,
        room_state: Optional[RoomState] = None,
        active_mode: str = "IDLE"
    ) -> Optional[Dict[str, Any]]:
        raw = user_utterance.strip()
        lower = raw.lower()

        # 0. Check active proactive follow-up state first
        if self._proactive_followup_state:
            res_pro = self._handle_proactive_followup_turn(raw, lower)
            if res_pro:
                return res_pro

        # 0b. Check active wrapup follow-up state
        if self._wrapup_followup_state:
            res = self._handle_wrapup_followup_turn(raw, lower)
            if res:
                return res

        # 0c. Multi-command compound extraction
        compound_dec = self._try_compound_fastpath_decision(user_utterance, room_state, active_mode)
        if compound_dec:
            return compound_dec

        # 0d. Single intent fast-path evaluation
        return self._try_single_fastpath_decision(user_utterance, room_state, active_mode)

    def _try_single_fastpath_decision(
        self,
        user_utterance: str,
        room_state: Optional[RoomState] = None,
        active_mode: str = "IDLE"
    ) -> Optional[Dict[str, Any]]:
        """
        Sub-50ms deterministic fast-path for explicit hardware commands, work sessions,
        task/roadmap queries, and pasted ChatGPT daily summaries.
        Bypasses 40s+ CPU LLM latency for known physical room operations.
        """
        raw = user_utterance.strip()
        lower = raw.lower()

        # Mode Introspection Fast-Path: e.g. "what mode is the room in?", "what mode are we in?", "current mode"
        if re.search(r'\b(?:what mode|current mode|which mode|what\'s the mode|active mode)\b', lower) or (
            "mode" in lower and any(w in lower for w in ["what", "which", "current", "room in", "we in"])
        ):
            orch = getattr(self, "orchestrator", None)
            eff_mode = (orch.current_mode if (orch and hasattr(orch, "current_mode")) else active_mode).upper()
            return {
                "thought": f"Fast-path: introspect active mode ({eff_mode}).",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "goal_update": None,
                "response_message": f"The room is currently in {eff_mode} mode, Sir."
            }

        # Standalone Reminder Fast-Path: e.g. "remind me today at 5:00 PM to start work"
        if re.search(r'\b(?:remind me|set a reminder|schedule a reminder|set reminder|schedule reminder)\b', lower):
            parsed = parse_reminder_intention(raw, current_time=time.time())
            if parsed:
                return {
                    "thought": f"Fast-path: standalone reminder scheduled for {parsed['day']} at {parsed['time_str']}.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [{
                        "tool": "CREATE_TASK",
                        "params": {
                            "title": f"Reminder: {parsed['subject']}",
                            "description": f"Scheduled for {parsed['day']} at {parsed['time_str']}",
                            "priority": "HIGH",
                            "category": "REMINDER",
                            "scheduled_time": parsed["scheduled_time"]
                        }
                    }],
                    "goal_update": None,
                    "response_message": parsed["response_message"]
                }

        # 1. AC Temperature & Power & Mode Commands
        has_ac_mention = any(w in lower for w in ["ac", "air conditioner", "air conditioning", "climate", "temp", "temperature", "degree", "cool", "heat"])

        # Check for explicit AC Power Off
        if any(w in lower for w in [
            "turn off ac", "turn off the ac", "ac off", "switch off ac", "switch off the ac",
            "power off ac", "power off the ac", "stop ac", "stop the ac", "shut off ac", "shut off the ac",
            "kill the ac", "kill ac"
        ]) or re.search(r'\b(?:turn off|switch off|power off|shut off|kill|stop)\s+(?:the\s+)?ac\b', lower):
            return {
                "thought": "Fast-path: explicit AC power off command.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "AC_POWER_OFF", "params": {}}],
                "goal_update": None,
                "response_message": "Turning off the AC, Sir."
            }

        # Check for explicit AC Temperature (16 to 30)
        temp_match = re.search(r'\b(?:temp(?:erature)?|ac|degrees?|to|at)?\s*(1[6-9]|2[0-9]|30)\b', lower)
        if temp_match and (has_ac_mention or any(w in lower for w in ["temperature", "set", "degree", "yes", "make it", "put it"])):
            target_temp = int(temp_match.group(1))
            mode = "COOL"
            if "auto" in lower: mode = "AUTO"
            elif "dry" in lower: mode = "DRY"
            elif "fan" in lower: mode = "FAN"

            return {
                "thought": f"Fast-path: direct AC temperature command to {target_temp}°C.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": target_temp}},
                    {"tool": "AC_SET_MODE", "params": {"mode": mode}}
                ],
                "goal_update": None,
                "response_message": f"Setting AC temperature to {target_temp}°C in {mode} mode, Sir."
            }

        # Check for generic AC Power On
        if any(w in lower for w in [
            "turn on ac", "turn on the ac", "ac on", "switch on ac", "switch on the ac",
            "power on ac", "power on the ac", "start ac", "start the ac", "fire up the ac", "fire up ac"
        ]) or re.search(r'\b(?:turn on|switch on|power on|start|fire up)\s+(?:the\s+)?ac\b', lower):
            return {
                "thought": "Fast-path: explicit AC power on command.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": 24}},
                    {"tool": "AC_SET_MODE", "params": {"mode": "COOL"}}
                ],
                "goal_update": None,
                "response_message": "Turning on the AC to 24°C COOL, Sir."
            }

        # Check for AC Mode Change only
        if any(w in lower for w in ["mode on ac", "ac mode", "cool mode", "fan mode", "dry mode", "auto mode"]):
            mode = "COOL"
            if "auto" in lower: mode = "AUTO"
            elif "dry" in lower: mode = "DRY"
            elif "fan" in lower: mode = "FAN"
            return {
                "thought": f"Fast-path: set AC mode to {mode}.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "AC_SET_MODE", "params": {"mode": mode}}],
                "goal_update": None,
                "response_message": f"AC set to {mode} mode, Sir."
            }

        # 2. Work Session Start & Wrap-Up
        is_work_deactivate = any(w in lower for w in [
            "done with work", "i am done with work", "wrap up work", "wrap up",
            "finished work", "finished working", "finish work", "close work apps",
            "end work", "end work mode", "stop work", "stop work mode",
            "exit work", "exit work mode", "quit work", "leave work", "leave work mode",
            "deactivate work", "turn off work", "turn off work mode"
        ])

        if not is_work_deactivate and any(w in lower for w in ["start work", "work mode", "let's work", "start work session", "open work apps", "time to study", "time to code"]):
            return {
                "thought": "Fast-path: work mode activation.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "LAUNCH_WORK_MODE", "params": {}}],
                "goal_update": None,
                "response_message": "Work mode activated, Sir. MySQL Workbench and Word are open, volume set to 15%, and room at 24°C."
            }

        if is_work_deactivate:
            curr_sg = self.memory_store.get_current_work_subgoal()
            sg_title = curr_sg.get("title", "your milestone") if curr_sg else "your milestone"

            # Check if user explicitly stated in this turn that they did zero work or took a break
            if any(w in lower for w in ["didn't do anything", "did nothing", "didn't work", "took a break", "taking a break", "no work", "rest day", "didn't study"]):
                self._wrapup_followup_state = "AWAITING_REMINDER_DECISION"
                return {
                    "thought": "Fast-path: work session wrap-up with zero work. NO_PROGRESS recorded, asking about reminder.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "WRAPUP_WORK_SESSION", "params": {"outcome": "NO_PROGRESS"}}
                    ],
                    "goal_update": None,
                    "response_message": f"All work progress saved and applications closed, Sir. No milestone changes recorded—your current focus '{sg_title}' remains active. Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"
                }
            # Check if user stated they completed the work in this utterance
            elif any(w in lower for w in ["completed the sql", "finished the project", "finished lag", "finished cte", "completed today's milestone"]):
                self._wrapup_followup_state = "AWAITING_REMINDER_DECISION"
                return {
                    "thought": "Fast-path: work session wrap-up with completed milestone. Asking about reminder.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "WRAPUP_WORK_SESSION", "params": {"outcome": "COMPLETED", "summary": raw}}
                    ],
                    "goal_update": None,
                    "response_message": f"All work progress saved and applications closed, Sir. I have recorded milestone '{sg_title}' as complete on your career roadmap. Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"
                }
            # Simple wrapup without summary: ask the user for truth
            else:
                self._wrapup_followup_state = "AWAITING_WORK_SUMMARY"
                return {
                    "thought": "Fast-path: work session wrap-up. Prompting user for truthful session progress.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [
                        {"tool": "WRAPUP_WORK_SESSION", "params": {"outcome": "NO_PROGRESS"}}
                    ],
                    "goal_update": None,
                    "response_message": f"Progress saved and work applications closed, Sir. Did you make progress on '{sg_title}' today, or did you decide to take a break?"
                }

        # Safe Hardware Device Scan & Audit Fast-Path
        if any(w in lower for w in [
            "scan for devices", "scan devices", "scan room devices", "scan all devices",
            "device status", "devices status", "hardware status", "check all devices",
            "check devices", "check room devices", "scan the room", "scan room",
            "what devices are online", "what devices are connected", "scan hardware",
            "status of all devices", "audit devices", "device audit"
        ]):
            try:
                from device_scanner import get_device_scanner
                scanner = get_device_scanner()
                report = scanner.scan_all_devices()
                summary = scanner.format_status_summary(report, preferred_name="Sir")
                return {
                    "thought": "Fast-path: Safe non-disruptive hardware device scan across AC, Fire TV, Projector, Soundbar.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "goal_update": None,
                    "response_message": summary
                }
            except Exception as e:
                logger.error(f"[DEVICE_SCAN_FASTPATH_ERR] {e}")

        # Explicit Mode Transition Fast-Paths
        if re.search(r'\b(?:relax mode|chill mode|set relax mode|switch to relax mode|enter relax mode)\b', lower):
            return {
                "thought": "Fast-path: explicit relax mode activation.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}}
                ],
                "goal_update": None,
                "response_message": "Setting the room to relax mode, Sir."
            }

        if re.search(r'\b(?:idle mode|set idle mode|switch to idle mode|default mode)\b', lower):
            return {
                "thought": "Fast-path: explicit idle mode activation.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "SET_ACTIVE_MODE", "params": {"mode": "IDLE"}}
                ],
                "goal_update": None,
                "response_message": "Room set back to idle baseline, Sir."
            }

        # 3. Master PC Volume Controls
        vol_match = re.search(r'\b(?:volume|sound|vol)\s*(?:to|at|is)?\s*([0-9]{1,3})\b', lower)
        if vol_match or (any(w in lower for w in ["set volume", "change volume", "volume to"]) and re.search(r'\b([0-9]{1,3})\b', lower)):
            v_val = int(vol_match.group(1)) if vol_match else int(re.search(r'\b([0-9]{1,3})\b', lower).group(1))
            v_val = max(0, min(100, v_val))
            return {
                "thought": f"Fast-path: setting PC volume to {v_val}%.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PC_SET_VOLUME", "params": {"volume": v_val}}],
                "goal_update": None,
                "response_message": f"Adjusted PC volume to {v_val}%, Sir."
            }

        # 4. Projector Controls
        if any(w in lower for w in ["turn on projector", "turn on the projector", "projector on", "power on projector", "switch on projector", "start projector"]):
            return {
                "thought": "Fast-path: projector power on.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PROJECTOR_POWER_ON", "params": {}}],
                "goal_update": None,
                "response_message": "Turning on the projector, Sir."
            }
        if any(w in lower for w in ["turn off projector", "turn off the projector", "projector off", "power off projector", "switch off projector", "shut off projector", "shut down projector"]):
            return {
                "thought": "Fast-path: projector power off.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PROJECTOR_POWER_OFF", "params": {}}],
                "goal_update": None,
                "response_message": "Turning off the projector, Sir."
            }

        # 5. Media Playback Controls
        if lower in ["pause", "pause music", "pause song", "stop music", "mute music"]:
            return {
                "thought": "Fast-path: pause media.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "MEDIA_PAUSE", "params": {}}],
                "goal_update": None,
                "response_message": "Playback paused, Sir."
            }
        if lower in ["resume", "resume music", "continue music", "play music", "play song", "unpause"]:
            return {
                "thought": "Fast-path: resume media.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "MEDIA_RESUME", "params": {}}],
                "goal_update": None,
                "response_message": "Playback resumed, Sir."
            }
        # Direct play track / song query (e.g. "play zara zara", "play starboy", "listen to lofi", "put on hans zimmer")
        play_match = re.match(r'^(?:play|listen to|put on)\s+(.+)$', lower.strip())
        if play_match:
            song_query = play_match.group(1).strip().strip('\'"')
            if song_query in ["music", "song", "a song", "some music", "tracks"]:
                return {
                    "thought": "Fast-path: resume media.",
                    "action_type": "TOOL_EXECUTION",
                    "tool_calls": [{"tool": "MEDIA_RESUME", "params": {}}],
                    "goal_update": None,
                    "response_message": "Resuming music playback, Sir."
                }
            raw_match = re.match(r'^(?:play|listen to|put on)\s+(.+)$', user_utterance.strip(), re.IGNORECASE)
            actual_query = raw_match.group(1).strip().strip('\'"') if raw_match else song_query
            return {
                "thought": f"Fast-path: direct music playback request for '{actual_query}'.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PLAY_MUSIC", "params": {"query": actual_query}}],
                "goal_update": None,
                "response_message": f"Playing '{actual_query}' on the soundbar, Sir."
            }

        # 6. Tasks & Career Roadmap Queries
        if any(w in lower for w in ["what are my tasks", "pending tasks", "list tasks", "my roadmap", "career progress", "roadmap status"]):
            roadmap = self.memory_store.get_career_roadmap()
            tasks = roadmap.get("tasks", [])
            pending_titles = [t["title"] for t in tasks if t.get("status") == "PENDING"][:4]
            t_str = "; ".join(pending_titles) if pending_titles else "No pending tasks."
            return {
                "thought": "Fast-path: career roadmap and task query.",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "goal_update": None,
                "response_message": f"Sir, your career target is {roadmap.get('career_target')}. Active project: {roadmap.get('current_project')}. Your top pending tasks are: {t_str}"
            }

        # 7. ChatGPT Daily Work Summary & Project Milestone Ingestion
        is_summary_input = any(k in lower for k in [
            "chatgpt", "today i completed", "today i worked", "today i did", "today's work",
            "summary of my work", "here is what i did", "completed the sql", "completed the project",
            "blinkit stock", "blink kit", "current project", "project 4", "stakeholder 1",
            "stakeholder 2", "learning milestone", "sq1", "sq2", "sq3", "sq4", "sq5",
            "has been completed", "current work:", "current work", "career goal:", "career goal",
            "inventory/replenishment", "replenishment analysis"
        ]) or (
            ("project" in lower or "milestone" in lower or "stakeholder" in lower or "blinkit" in lower)
            and ("completed" in lower or "finished" in lower or "current work" in lower or "sq" in lower)
        )

        if is_summary_input:
            task_title = "Blinkit SQL: Calculate lost revenue per out-of-stock SKU"
            if "lost revenue" in lower or "penalty" in lower or "demand" in lower:
                task_title = "Blinkit SQL: Calculate lost revenue per out-of-stock SKU"
            elif "replenish" in lower or "reorder" in lower or "sq5" in lower:
                task_title = "Blinkit SQL: Event-based replenishment & reorder analysis (SQ5)"
            elif "dashboard" in lower:
                task_title = "Blinkit Analytics: Build Power BI dashboard"
            elif "cte" in lower or "lag" in lower or "duration" in lower:
                task_title = "Blinkit SQL: Join OOS duration events with inventory table"
            elif "interview" in lower:
                task_title = "Practice SQL window function interview drills"

            # Determine whether user finished milestone or made partial progress
            is_completed = any(k in lower for k in ["completed", "has been completed", "finished", "all done", "solved", "finalized"])
            outcome = "COMPLETED" if is_completed else "PARTIAL"

            wrap_res = self.memory_store.process_work_session_outcome(outcome_type=outcome, user_summary=raw)
            tomorrow_task = wrap_res.get("tomorrow_task", {}).get("title", task_title) if wrap_res.get("tomorrow_task") else task_title
            comp_sg = wrap_res.get("completed_subgoal", {})
            comp_title = comp_sg.get("title", "Today's milestone") if comp_sg else "Today's milestone"

            self._wrapup_followup_state = "AWAITING_REMINDER_DECISION"

            if outcome == "COMPLETED":
                next_sg = wrap_res.get("next_subgoal", {})
                next_title = next_sg.get("title", tomorrow_task) if next_sg else tomorrow_task
                msg = (
                    f"Outstanding progress on the Blinkit project, Sir! I have marked milestone '{comp_title}' complete "
                    f"on your Data Analyst roadmap and updated your active focus to '{next_title}'. "
                    f"Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"
                )
            else:
                curr_sg = self.memory_store.get_current_work_subgoal()
                curr_title = curr_sg.get("title", "your milestone") if curr_sg else "your milestone"
                msg = f"Logged your work progress on the Blinkit project, Sir! Current focus '{curr_title}' remains active. Would you like me to set a reminder for when you want to work tomorrow, or should we leave it unscheduled?"

            return {
                "thought": f"Fast-path: Ingested work summary ({outcome}) and updated career roadmap.",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "goal_update": None,
                "response_message": msg
            }

        # 8a. Movie Mode Wrap-Up / Deactivation
        if any(w in lower for w in [
            "done watching movie", "done with movie", "finished movie", "finished watching movie",
            "stop movie", "exit movie mode", "close movie", "turn off movie", "movie is over",
            "end movie mode", "end movie", "stop watching movie", "quit movie mode"
        ]):
            return {
                "thought": "Fast-path: movie mode wrap-up and shutdown.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "PROJECTOR_POWER_OFF", "params": {}},
                    {"tool": "SOUNDBAR_ROUTE_TO_PC", "params": {}},
                    {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": 24}},
                    {"tool": "SET_ACTIVE_MODE", "params": {"mode": "RELAX"}}
                ],
                "goal_update": None,
                "response_message": "Movie mode ended and projector turned off, Sir. Room is set to relax mode."
            }

        # 8b. Movie Mode Activation
        if re.search(r'\b(?:movie mode|start movie|watch a movie|watch movie|cinema mode|prepare movie)\b', lower) or (
            "movie" in lower and not any(w in lower for w in ["done", "stop", "off", "exit", "finish", "over", "end", "close", "quit"])
        ):
            return {
                "thought": "Fast-path: movie mode activation.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "PROJECTOR_POWER_ON", "params": {}},
                    {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": 22}},
                    {"tool": "SOUNDBAR_ROUTE_FIRE_TV", "params": {}},
                    {"tool": "SET_ACTIVE_MODE", "params": {"mode": "MOVIE"}}
                ],
                "goal_update": None,
                "response_message": "Setting up movie mode, Sir."
            }

        # 8b. Cinema / Streaming Disambiguation
        if any(w in lower for w in ["watch something", "stream something", "put on a show", "watch a show"]):
            return {
                "thought": "Fast-path: entertainment disambiguation. Inquiring preference for Netflix, YouTube, or Projector Cinema.",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "goal_update": None,
                "response_message": "Would you like me to fire up the projector for Netflix or YouTube, Sir?"
            }

        # 9. Printer Subsystem Fast-Paths
        if any(w in lower for w in ["printer status", "check printer", "printer ready", "print queue", "is printer on"]):
            return {
                "thought": "Fast-path: query HP Ink Tank 310 printer status.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PRINTER_GET_STATUS", "params": {}}],
                "goal_update": None,
                "response_message": "Checking the HP Ink Tank 310 status for you, Sir."
            }
        if any(w in lower for w in ["cancel print", "clear print queue", "cancel print jobs"]):
            return {
                "thought": "Fast-path: cancel pending print jobs.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PRINTER_CANCEL_JOBS", "params": {}}],
                "goal_update": None,
                "response_message": "Clearing the printer queue, Sir."
            }
        if any(w in lower for w in ["print sql", "sql practice worksheet", "print practice sheet", "print study sheet", "sql worksheet", "print my sql"]):
            return {
                "thought": "Fast-path: generate and spool physical SQL practice worksheet to HP Ink Tank 310.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PRINT_SQL_WORKSHEET", "params": {}}],
                "goal_update": None,
                "response_message": "Generating and spooling your physical SQL practice worksheet to the HP Ink Tank 310, Sir."
            }

        # 9b. Work & Study Weekly Analytics Fast-Path
        if any(w in lower for w in ["work summary", "study summary", "how much did i study", "weekly work analytics", "study analytics", "work analytics", "study report"]):
            analytics = self.memory_store.get_weekly_work_analytics() if self.memory_store and hasattr(self.memory_store, "get_weekly_work_analytics") else {}
            total_hours = analytics.get("total_hours", 0.0)
            sessions = analytics.get("total_sessions", 0)
            avg_min = analytics.get("avg_session_minutes", 0.0)
            resp = f"Sir, over the past 7 days you completed {sessions} deep work sessions totaling {total_hours} hours, averaging {avg_min} minutes per focus sprint."
            return {
                "thought": "Fast-path: synthesized weekly work and study analytics report from SQLite.",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "goal_update": None,
                "response_message": resp
            }

        # 10. PC Workstation Lock
        if any(w in lower for w in ["lock pc", "lock my pc", "lock workstation", "lock computer", "lock screen", "lock the pc"]):
            return {
                "thought": "Fast-path: lock Windows workstation for privacy.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PC_LOCK_WORKSTATION", "params": {}}],
                "goal_update": None,
                "response_message": "Locking your workstation, Sir."
            }

        # 11. Projector Motor Calibration (Autofocus & Keystone)
        if any(w in lower for w in ["focus projector", "autofocus", "auto focus", "projector focus"]):
            return {
                "thought": "Fast-path: trigger projector autofocus calibration.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PROJECTOR_AUTO_FOCUS", "params": {}}],
                "goal_update": None,
                "response_message": "Triggering electric motor autofocus on the projector, Sir."
            }
        if any(w in lower for w in ["keystone projector", "auto keystone", "keystone", "align projector"]):
            return {
                "thought": "Fast-path: trigger projector gyro auto-keystone correction.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "PROJECTOR_AUTO_KEYSTONE", "params": {}}],
                "goal_update": None,
                "response_message": "Calibrating 6D gyro auto-keystone on the projector, Sir."
            }

        # 12. Smart Lighting Presets
        if any(w in lower for w in ["relax lights", "relaxing lights", "lights relax"]):
            return {
                "thought": "Fast-path: set lighting to RELAX scene.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "LIGHTING_SET_SCENE", "params": {"scene": "RELAX"}}],
                "goal_update": None,
                "response_message": "Setting ambient lights to relax mode, Sir."
            }
        if any(w in lower for w in ["focus lights", "work lights", "lights focus"]):
            return {
                "thought": "Fast-path: set lighting to FOCUS scene.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "LIGHTING_SET_SCENE", "params": {"scene": "FOCUS"}}],
                "goal_update": None,
                "response_message": "Setting ambient lights to crisp focus mode, Sir."
            }
        if any(w in lower for w in ["turn off lights", "lights off", "switch off lights"]):
            return {
                "thought": "Fast-path: turn off lights.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "LIGHTING_SET_POWER", "params": {"power": False}}],
                "goal_update": None,
                "response_message": "Switching off ambient lights, Sir."
            }
        if any(w in lower for w in ["turn on lights", "lights on", "switch on lights"]):
            return {
                "thought": "Fast-path: turn on lights.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [{"tool": "LIGHTING_SET_POWER", "params": {"power": True}}],
                "goal_update": None,
                "response_message": "Turning on ambient lighting, Sir."
            }

        return None

    def decide_intent(
        self,
        user_utterance: str,
        room_state: Optional[RoomState] = None,
        active_mode: str = "IDLE"
    ) -> Dict[str, Any]:
        """Convenience evaluation method returning raw decision dictionary."""
        fast = self._try_fastpath_decision(user_utterance, room_state, active_mode)
        if fast:
            return fast
        res = self.decide_and_act(user_utterance, room_state=room_state, active_mode=active_mode)
        return res.model_dump() if hasattr(res, "model_dump") else res.dict()

    def decide_and_act(
        self,
        user_utterance: str,
        room_state: Optional[RoomState] = None,
        active_mode: str = "IDLE",
        recent_turns: Optional[List[Dict[str, str]]] = None
    ) -> AgentDecisionResult:
        """
        Executes complete cognitive loop for a single user turn.
        """
        t0 = time.time()
        logger.info(f"[DECISION_ENGINE] Ingesting turn: '{user_utterance}'")

        # 0. Sub-50ms Deterministic Fast-Path for explicit hardware commands, work sessions, queries
        fast_dec = self._try_fastpath_decision(user_utterance, room_state, active_mode)
        if fast_dec:
            raw_decision = fast_dec
            source = "FASTPATH_DETERMINISTIC"
            latency = round(time.time() - t0, 3)
            logger.info(f"[DECISION_ENGINE] Fast-path actuated in {latency}s: action={raw_decision.get('action_type')}")
        else:
            # 0.5 Phase 2 Personal Situational Reasoning Engine ("What makes sense for Sir in this situation?")
            active_g = self.memory_store.get_active_goal() if hasattr(self.memory_store, "get_active_goal") else None
            sit_dec = None
            if hasattr(self, "personal_reasoner") and self.personal_reasoner:
                sit_dec = self.personal_reasoner.evaluate_situational_turn(
                    user_utterance=user_utterance,
                    room_state=room_state,
                    active_mode=active_mode,
                    current_time=time.time(),
                    active_goal=active_g
                )
            if sit_dec:
                raw_decision = sit_dec
                source = "PERSONAL_SITUATIONAL_REASONING"
                latency = round(time.time() - t0, 3)
                logger.info(f"[DECISION_ENGINE] Personal Situational Reasoning actuated in {latency}s: action={raw_decision.get('action_type')}")
            else:
                # 1. PERCEIVE: Build compact prompt with time + state + RAG memory
                sys_instruction = self.prompt_builder.build_system_instruction()
                prompt_text = self.prompt_builder.build_prompt(
                    user_utterance=user_utterance,
                    room_state=room_state,
                    active_mode=active_mode,
                    recent_turns=recent_turns
                )

                # 2. REASON: Query Local Ollama Qwen 4B (with Gemini Cloud Fallback)
                raw_decision, source = self._infer_with_fallback(sys_instruction, prompt_text, user_utterance, room_state)
                latency = round(time.time() - t0, 2)
                logger.info(f"[DECISION_ENGINE] Reasoned via {source} in {latency}s: action={raw_decision.get('action_type')}")

        # 3. CONFLICT ARBITRATION & TOOL EXECUTION
        tool_calls = raw_decision.get("tool_calls", [])
        agent_msg = raw_decision.get("response_message", f"Certainly, Sir.")
        if hasattr(self, "personal_reasoner") and self.personal_reasoner and tool_calls:
            tool_calls, agent_msg = self.personal_reasoner.arbitrate_conflicts(
                tool_calls=tool_calls,
                response_message=agent_msg,
                current_time=time.time(),
                active_mode=active_mode
            )

        exec_results = []
        verified_status = "NO_ACTION_REQUIRED"

        if tool_calls:
            exec_results, _ = self._execute_tools(tool_calls, room_state)

        # 3.5 OBSERVE & VERIFY (Phase 3: Zero Fake Success)
        if hasattr(self, "reality_observer") and self.reality_observer and tool_calls:
            obs_snapshot = self.reality_observer.observe_physical_state(
                tool_calls=tool_calls,
                execution_results=exec_results,
                pc_controller=self.pc_controller,
                room_state=room_state
            )
            verification_report = self.reality_observer.verify_plan_execution(
                tool_calls=tool_calls,
                execution_results=exec_results,
                snapshot=obs_snapshot
            )
            verified_status = verification_report.status.value
            agent_msg = self.reality_observer.synthesize_truthful_response(
                candidate_message=agent_msg,
                report=verification_report,
                user_utterance=user_utterance
            )

        # 4. TRACK GOALS: Update active goal if present
        goal_data = raw_decision.get("goal_update")
        if goal_data and isinstance(goal_data, dict):
            self._handle_goal_update(goal_data)

        # 5. REMEMBER: Closed-loop structured learning & episodic conversation
        self._extract_and_remember_structured(user_utterance, raw_decision)
        self.memory_store.extract_facts_from_utterance(user_utterance)
        self.memory_store.record_conversation_turn(
            user_utterance=user_utterance,
            agent_response=agent_msg,
            intent_category=raw_decision.get("action_type", "GENERAL")
        )

        # 6. CONTEXTUAL RELEVANT MEMORY & EXPRESSION
        relevant_memories = []
        if hasattr(self.memory_store, "retrieve_relevant_structured_memories"):
            relevant_memories = self.memory_store.retrieve_relevant_structured_memories(
                query=user_utterance,
                active_mode=active_mode,
                limit=6
            )

        expression_payload = self._formulate_expression(
            action_type=raw_decision.get("action_type", "CONVERSATION"),
            tool_calls=tool_calls,
            active_mode=active_mode,
            response_message=agent_msg
        )
        if raw_decision.get("light_cue"):
            expression_payload["light_cue"] = raw_decision["light_cue"]
        if raw_decision.get("ui_state"):
            expression_payload["ui_state"].update(raw_decision["ui_state"])
        if raw_decision.get("sound_cue"):
            expression_payload["sound_cue"] = raw_decision["sound_cue"]

        return AgentDecisionResult(
            thought=raw_decision.get("thought", ""),
            action_type=raw_decision.get("action_type", "CONVERSATION"),
            tool_calls=tool_calls,
            execution_results=exec_results,
            verified_physical_status=verified_status,
            goal_updated=goal_data,
            response_message=agent_msg,
            inference_source=source,
            latency_seconds=latency,
            expression_payload=expression_payload,
            relevant_memories=relevant_memories
        )

    def _formulate_expression(
        self,
        action_type: str,
        tool_calls: List[Dict[str, Any]],
        active_mode: str,
        response_message: str
    ) -> Dict[str, Any]:
        """
        Formulates the unified multi-modal expression channel:
        Voice + Actions + Physical Expression (Light + UI + Sound).
        """
        has_work_launch = any(tc.get("tool") == "LAUNCH_WORK_MODE" for tc in tool_calls)
        has_work_wrapup = any(tc.get("tool") == "WRAPUP_WORK_SESSION" for tc in tool_calls)
        mode_call = next((tc for tc in tool_calls if tc.get("tool") in ["SET_ACTIVE_MODE", "SET_ROOM_MODE", "TRANSITION_MODE"]), None)
        target_mode = mode_call.get("params", {}).get("mode", "").upper() if mode_call else None
        has_projector = any(tc.get("tool") == "SET_PROJECTOR_POWER" for tc in tool_calls)
        has_ac = any(tc.get("tool") == "SET_AC_STATE" for tc in tool_calls)

        if has_work_wrapup or target_mode in ("RELAX", "COMFORT") or (active_mode in ("RELAX", "COMFORT") and not has_work_launch and target_mode != "WORK"):
            return {
                "light_cue": "RELAX_AMBER",
                "ui_state": {"mode": "RELAX", "status": "completed", "badge_color": "#10b981"},
                "sound_cue": "RESTFUL_CHIME"
            }
        elif has_work_launch or target_mode == "WORK" or (active_mode == "WORK" and not has_work_wrapup):
            return {
                "light_cue": "FOCUS_WARM",
                "ui_state": {"mode": "WORK", "status": "active", "badge_color": "#3b82f6"},
                "sound_cue": "FOCUS_START"
            }
        elif target_mode == "MOVIE" or has_projector:
            return {
                "light_cue": "CINEMA_DIM",
                "ui_state": {"mode": "MOVIE", "status": "projector_active", "badge_color": "#f59e0b"},
                "sound_cue": "CINEMA_CHIME"
            }
        elif target_mode == "IDLE":
            return {
                "light_cue": "NEUTRAL",
                "ui_state": {"mode": "IDLE", "status": "idle", "badge_color": "#6b7280"},
                "sound_cue": "SILENT"
            }
        elif has_ac:
            return {
                "light_cue": "CLIMATE_PULSE",
                "ui_state": {"mode": active_mode, "status": "thermal_adjust"},
                "sound_cue": "CHIME_SUBTLE"
            }
        else:
            return {
                "light_cue": "NEUTRAL",
                "ui_state": {"mode": active_mode, "status": "idle"},
                "sound_cue": "SILENT"
            }

    def _extract_and_remember_structured(self, user_utterance: str, raw_decision: Dict[str, Any]) -> None:
        """
        Extracts explicit user preferences, facts, or routines from dialogue
        and stores them into persistent structured memory without hallucination.
        """
        if not hasattr(self.memory_store, "store_structured_memory"):
            return

        lower = user_utterance.strip().lower()

        # 1. AC / Temperature preferences: e.g. "I prefer AC at 23 when watching movies"
        m_ac = re.search(r'\b(?:prefer|like|want)\s+(?:the\s+)?ac\s+(?:at\s+|to\s+)?(\d{1,2})\b', lower)
        if m_ac:
            temp_val = int(m_ac.group(1))
            if 16 <= temp_val <= 30:
                ctx = "movie" if any(w in lower for w in ["movie", "cinema", "watch", "film"]) else "general"
                self.memory_store.store_structured_memory(
                    memory_type="preference",
                    subject="ac",
                    context=ctx,
                    value=f"{temp_val}°C setpoint",
                    confidence=1.0,
                    source="user"
                )

        # 2. Lighting preferences: e.g. "I prefer low brightness for movies"
        if "lighting" in lower or "light" in lower or "brightness" in lower:
            m_light = re.search(r'\b(?:prefer|like)\s+([a-z\s]+)\s+(?:lighting|light|brightness)\b', lower)
            if m_light:
                l_val = m_light.group(1).strip()
                ctx = "movie" if "movie" in lower else "general"
                self.memory_store.store_structured_memory(
                    memory_type="preference",
                    subject="lighting",
                    context=ctx,
                    value=f"{l_val} brightness",
                    confidence=1.0,
                    source="user"
                )

        # 3. Work environment preferences: e.g. "I prefer quiet when working"
        if ("work" in lower or "study" in lower) and any(w in lower for w in ["quiet", "silence", "music", "focus"]):
            if "quiet" in lower or "silence" in lower:
                self.memory_store.store_structured_memory(
                    memory_type="preference",
                    subject="work",
                    context="SQL/data analytics",
                    value="quiet environment",
                    confidence=1.0,
                    source="user"
                )

        # 4. Guitar routines: e.g. "guitar practice at 5 pm"
        if "guitar" in lower:
            m_g = re.search(r'\b(?:at|around)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b', lower)
            if m_g:
                t_val = m_g.group(1)
                self.memory_store.store_structured_memory(
                    memory_type="routine",
                    subject="guitar",
                    context="afternoon/evening",
                    value=f"practice at {t_val}",
                    confidence=0.9,
                    source="user"
                )

    # =========================================================================
    # Inference Strategy: Local Ollama with Gemini Fallback
    # =========================================================================

    def _infer_with_fallback(
        self,
        sys_instruction: str,
        prompt_text: str,
        user_utterance: str,
        room_state: Optional[RoomState]
    ) -> tuple[Dict[str, Any], str]:
        """
        Attempts local inference via Ollama first. If unavailable, falls back to Gemini.
        """
        # 1. Try Local Ollama Qwen 4B
        try:
            payload = {
                "model": self.ollama_model,
                "system": sys_instruction,
                "prompt": prompt_text,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 1024
                }
            }
            resp = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=45.0)
            if resp.status_code == 200:
                raw_text = resp.json().get("response", "").strip()
                parsed = self._clean_and_parse_json(raw_text)
                if parsed:
                    return parsed, f"LOCAL_OLLAMA ({self.ollama_model})"
        except Exception as e:
            logger.warning(f"[DECISION_ENGINE] Local Ollama inference failed/timeout: {e}")

        # 2. Fallback to Google Gemini
        if self.gemini_client and getattr(self.gemini_client, "is_available", False):
            try:
                logger.info("[DECISION_ENGINE] Engaging Gemini cloud fallback...")
                plan_resp = self._infer_with_gemini(sys_instruction, prompt_text)
                if plan_resp:
                    return plan_resp, f"GEMINI_FALLBACK ({getattr(self.gemini_client, 'model_name', 'gemini')})"
            except Exception as e:
                logger.warning(f"[DECISION_ENGINE] Gemini cloud fallback failed: {e}")

        # 3. Emergency Rule-Based Fallback
        logger.warning("[DECISION_ENGINE] LLMs unavailable; using emergency rule fallback.")
        return self._emergency_fallback_decision(user_utterance), "EMERGENCY_FALLBACK"

    def _infer_with_gemini(self, sys_instruction: str, prompt_text: str) -> Optional[Dict[str, Any]]:
        """Invokes Gemini client when local Ollama is offline."""
        try:
            if hasattr(self.gemini_client, "_sdk_client") and self.gemini_client._sdk_client:
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=sys_instruction,
                    response_mime_type="application/json",
                    temperature=0.1
                )
                res = self.gemini_client._sdk_client.models.generate_content(
                    model=self.gemini_client.model_name,
                    contents=prompt_text,
                    config=config
                )
                if res.text:
                    return self._clean_and_parse_json(res.text)
        except Exception as e:
            logger.warning(f"[DECISION_ENGINE] Gemini SDK invocation error: {e}")
        return None

    def _clean_and_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Cleans Markdown formatting and parses JSON safely."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            # Try regex extraction for json block
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
        return None

    def _emergency_fallback_decision(self, utterance: str) -> Dict[str, Any]:
        """Simple baseline fallback when LLMs cannot be reached."""
        fast = self._try_fastpath_decision(utterance)
        if fast:
            return fast
        return {
            "thought": "Direct conversational response.",
            "action_type": "CONVERSATION",
            "tool_calls": [],
            "goal_update": None,
            "response_message": f"I'm here, Sir. How can I assist with the room?"
        }

    # =========================================================================
    # Physical Tool Actuation & Safety Validation
    # =========================================================================

    def _execute_tools(
        self,
        tool_calls: List[Dict[str, Any]],
        room_state: Optional[RoomState] = None
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Translates structured tool calls into validated PlanSteps and executes them.
        """
        results = []
        overall_status = "VERIFIED_SUCCESS"

        for idx, call in enumerate(tool_calls, start=1):
            tool_name = (call.get("tool") or call.get("name") or "").upper()
            params = call.get("params") or call.get("parameters") or call.get("arguments") or {}

            # Map canonical tool name to subsystem capability
            step_result = self._dispatch_single_tool(idx, tool_name, params, room_state)
            results.append(step_result)

            if step_result.get("status") not in ["SUCCESS", "SKIPPED_IDEMPOTENT"]:
                overall_status = "PARTIAL_OR_FAILED"

        return results, overall_status

    def _dispatch_single_tool(
        self,
        step_id: int,
        tool_name: str,
        params: Dict[str, Any],
        room_state: Optional[RoomState]
    ) -> Dict[str, Any]:
        """Dispatches an individual tool call to the PlanExecutor or internal memory store."""
        try:
            # 1. Work Mode Orchestration Tools
            if tool_name == "LAUNCH_WORK_MODE":
                launched_apps = []
                pc_ctrl = self.pc_controller or (getattr(self, "orchestrator", None) and getattr(self.orchestrator, "pc", None))
                if not pc_ctrl:
                    try:
                        from pc_controller import pc_controller as default_pc_ctrl
                        pc_ctrl = default_pc_ctrl
                    except Exception:
                        from pc_controller import PcController
                        pc_ctrl = PcController()

                # Launch SQL Workbench & Word
                ok_sql, _ = pc_ctrl.launch_allowlisted_app("sql")
                if ok_sql:
                    launched_apps.append("MySQL Workbench")
                ok_word, _ = pc_ctrl.launch_allowlisted_app("word")
                if ok_word:
                    launched_apps.append("Microsoft Word")

                # Bring work windows to foreground
                if hasattr(pc_ctrl, "bring_work_windows_to_foreground"):
                    pc_ctrl.bring_work_windows_to_foreground()

                # Set master PC volume to 15
                pc_ctrl.set_volume(15)

                # Route soundbar or start focus music
                orch = getattr(self, "orchestrator", None)
                if orch:
                    if hasattr(orch, "get_room_status"):
                        stat = orch.get_room_status()
                        if stat.get("media_playback_state") != "PLAYING" and hasattr(orch, "play_music"):
                            orch.play_music("soothing lofi focus beats")
                    if hasattr(orch, "set_active_mode"):
                        orch.set_active_mode("WORK")

                # Set AC to 24°C COOL for optimal work comfort
                exec_ctx = self.planner_executor
                ac_ctrl = exec_ctx and (getattr(exec_ctx, "ac_controller", None) or getattr(exec_ctx, "ac", None))
                if ac_ctrl:
                    try:
                        ac_ctrl.set_power(True)
                        ac_ctrl.set_mode("COOL")
                        ac_ctrl.set_temperature(24)
                    except Exception as e:
                        logger.debug(f"[WORK_MODE_AC_ERR] {e}")

                logger.info(f"[DECISION_ENGINE] LAUNCH_WORK_MODE executed: apps={launched_apps}, vol=15, AC=24C")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "launched": launched_apps, "volume": 15, "ac_temp": 24}

            elif tool_name == "WRAPUP_WORK_SESSION":
                pc_ctrl = self.pc_controller or (getattr(self, "orchestrator", None) and getattr(self.orchestrator, "pc", None))
                if not pc_ctrl:
                    try:
                        from pc_controller import pc_controller as default_pc_ctrl
                        pc_ctrl = default_pc_ctrl
                    except Exception:
                        from pc_controller import PcController
                        pc_ctrl = PcController()

                # 1. Safe progress save via Ctrl+S with disk verification
                save_res = pc_ctrl.send_save_keystrokes()
                time.sleep(0.3)

                # 2. Close work applications
                close_res = pc_ctrl.close_apps(["MySQLWorkbench.exe", "WINWORD.EXE"])

                # 3. Transition active mode to RELAX
                orch = getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "set_active_mode"):
                    orch.set_active_mode("RELAX")

                # 4. Reasoned outcome processing in Long-Term Memory (no blind milestone advance)
                outcome = params.get("outcome", "NO_PROGRESS")
                summary = params.get("summary", "")
                wrapup_res = self.memory_store.process_work_session_outcome(outcome_type=outcome, user_summary=summary)

                # Record work session in SQLite
                if self.memory_store and hasattr(self.memory_store, "record_work_session"):
                    dur = 0.0
                    if hasattr(pc_ctrl, "get_work_session_duration"):
                        dur = pc_ctrl.get_work_session_duration()
                    curr_sg = self.memory_store.get_current_work_subgoal() if hasattr(self.memory_store, "get_current_work_subgoal") else None
                    sg_title = curr_sg.get("title") if curr_sg else "Blinkit SQL Work"
                    self.memory_store.record_work_session(
                        session_duration_seconds=dur,
                        subgoal_title=sg_title,
                        exit_reason="MANUAL_WRAPUP"
                    )

                logger.info(f"[DECISION_ENGINE] WRAPUP_WORK_SESSION executed: outcome={outcome}, progress saved, work apps closed, mode=RELAX, wrapup={wrapup_res}")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "action": "WORK_WRAPUP_COMPLETED", "outcome": outcome, "wrapup": wrapup_res, "save_telemetry": save_res}


            # 2. Internal Task & Goal Management Tools
            elif tool_name == "CREATE_TASK":
                title = params.get("title", "New Task")
                priority = params.get("priority", "MEDIUM")
                category = params.get("category", "WORK")
                desc = params.get("description", "")
                sched_time = params.get("scheduled_time")
                tid = self.memory_store.create_task(title=title, description=desc, priority=priority, category=category)
                logger.info(f"[DECISION_ENGINE] Created task in SQLite: {tid} ('{title}')")
                tm = getattr(self, "task_manager", None) or (getattr(self.orchestrator, "task_manager", None) if self.orchestrator else None)
                if tm and category == "REMINDER" and sched_time:
                    try:
                        clean_msg = title.replace("Reminder:", "").strip()
                        tm.schedule_reminder(message=clean_msg, scheduled_time=float(sched_time))
                    except Exception as e:
                        logger.debug(f"[TASK_TM_REMINDER_REGISTER_ERR] {e}")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "task_id": tid, "title": title}

            elif tool_name == "UPDATE_TASK":
                target = params.get("task_name") or params.get("title") or params.get("task_id", "")
                new_status = params.get("new_status")
                new_title = params.get("new_title")
                new_priority = params.get("new_priority")
                ok = self.memory_store.update_task(target, title=new_title, priority=new_priority, status=new_status)
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "NOT_FOUND", "target": target}

            elif tool_name == "DELETE_TASK":
                target = params.get("task_name") or params.get("title") or params.get("task_id", "")
                ok = self.memory_store.delete_task(target)
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "NOT_FOUND", "deleted": ok}

            elif tool_name == "COMPLETE_TASK":
                task_name = params.get("task_name") or params.get("task_name_or_id") or params.get("title", "task")
                completed_title = self.memory_store.complete_task(task_name)
                logger.info(f"[DECISION_ENGINE] Completed task in SQLite: {completed_title or task_name}")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "completed_task": completed_title or task_name}

            elif tool_name in ["SCHEDULE_REMINDER", "SET_ALARM"]:
                rem_text = params.get("reminder") or params.get("label") or params.get("message", "Reminder")
                t_str = params.get("time_or_offset") or params.get("time_str", "due")
                sched_time = params.get("scheduled_time")
                tid = self.memory_store.create_task(title=f"Reminder: {rem_text}", description=f"Scheduled for {t_str}", priority="HIGH", category="REMINDER")
                tm = getattr(self, "task_manager", None) or (getattr(self.orchestrator, "task_manager", None) if self.orchestrator else None)
                if tm and sched_time:
                    try:
                        tm.schedule_reminder(message=rem_text, scheduled_time=float(sched_time))
                    except Exception as e:
                        logger.debug(f"[REMINDER_TM_REGISTER_ERR] {e}")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "reminder": rem_text, "time": t_str, "task_id": tid}

            elif tool_name == "SET_ACTIVE_GOAL":
                title = params.get("title", "Active Goal")
                subgoals = params.get("subgoals", [])
                self._handle_goal_update({"title": title, "subgoals": subgoals, "status": "ACTIVE"})
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "goal": title}

            elif tool_name == "ADVANCE_GOAL_STEP":
                idx = int(params.get("step_index", 0))
                comp = bool(params.get("completed", True))
                active_g = self.memory_store.get_active_goal()
                if active_g:
                    self.memory_store.update_subgoal_status(active_g["id"], idx, completed=comp)
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "step_index": idx}

            exec_ctx = self.planner_executor

            # 2. HP USB & Spooler Printer Subsystem
            if tool_name == "PRINTER_GET_STATUS":
                try:
                    from printer_controller import get_printer_controller
                    p_stat = get_printer_controller().get_status()
                    logger.info(f"[DECISION_ENGINE] PRINTER_GET_STATUS: {p_stat.get('printer_name')} is {p_stat.get('status')}")
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if p_stat.get("success") else "ERROR", "telemetry": p_stat}
                except Exception as e:
                    logger.error(f"[DECISION_ENGINE] PRINTER_GET_STATUS error: {e}")
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            elif tool_name in ["PRINTER_PRINT_FILE", "PRINT_DOCUMENT", "PRINT_FILE"]:
                fpath = params.get("file_path") or params.get("path") or params.get("file")
                if not fpath:
                    return {"step_id": step_id, "tool": tool_name, "status": "INVALID_PARAMETER", "error": "file_path is required"}
                try:
                    from printer_controller import get_printer_controller
                    ok, res = get_printer_controller().print_file(fpath)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "result": res}
                except Exception as e:
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            elif tool_name == "PRINTER_CANCEL_JOBS":
                try:
                    from printer_controller import get_printer_controller
                    ok, res = get_printer_controller().cancel_all_jobs()
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "result": res}
                except Exception as e:
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            elif tool_name in ["PRINT_SQL_WORKSHEET", "PRINTER_PRINT_SQL"]:
                try:
                    from agent.briefing_service import BriefingService
                    from printer_controller import get_printer_controller
                    bs = BriefingService(
                        memory_store=self.memory_store,
                        task_manager=self.task_manager,
                        printer_controller=get_printer_controller()
                    )
                    prob_title = params.get("problem_title")
                    p_res = bs.print_sql_worksheet(problem_title=prob_title)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if p_res.get("success") else "FAILED", "print_result": p_res}
                except Exception as e:
                    logger.error(f"[DECISION_ENGINE] PRINT_SQL_WORKSHEET error: {e}")
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            # 3. AC Commands
            elif tool_name in ["AC_POWER_ON", "TURN_ON_AC", "AC_ON"]:
                ac_ctrl = None
                if exec_ctx:
                    ac_ctrl = getattr(exec_ctx, "ac_controller", None) or getattr(exec_ctx, "ac", None)
                if not ac_ctrl and self.orchestrator:
                    ac_ctrl = getattr(self.orchestrator, "ac_controller", None) or getattr(self.orchestrator, "ac", None)
                if not ac_ctrl:
                    try:
                        from ac_controller import AcController
                        ac_ctrl = AcController()
                    except Exception:
                        pass
                if ac_ctrl:
                    try:
                        ac_ctrl.set_power(True)
                        logger.info("[DECISION_ENGINE] Set AC power to True")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "power": True}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "power": True}

            elif tool_name in ["AC_SET_TEMPERATURE", "SET_AC_TEMPERATURE", "SET_TEMPERATURE", "AC_SET_TEMP"]:
                temp = int(params.get("temperature") or params.get("temp", 24))
                temp = max(16, min(30, temp))
                ac_ctrl = None
                if exec_ctx:
                    ac_ctrl = getattr(exec_ctx, "ac_controller", None) or getattr(exec_ctx, "ac", None)
                if not ac_ctrl and self.orchestrator:
                    ac_ctrl = getattr(self.orchestrator, "ac_controller", None) or getattr(self.orchestrator, "ac", None)
                if not ac_ctrl:
                    try:
                        from ac_controller import AcController
                        ac_ctrl = AcController()
                    except Exception:
                        pass
                if ac_ctrl:
                    try:
                        ac_ctrl.set_power(True)
                        ac_ctrl.set_temperature(temp)
                        logger.info(f"[DECISION_ENGINE] Set AC temperature to {temp}°C (power=True)")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "target_temp": temp}
                    except Exception as e:
                        logger.error(f"[DECISION_ENGINE] Error setting AC temperature: {e}")
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "target_temp": temp}

            elif tool_name in ["AC_SET_MODE", "SET_AC_MODE"]:
                mode = str(params.get("mode", "COOL")).upper()
                ac_ctrl = None
                if exec_ctx:
                    ac_ctrl = getattr(exec_ctx, "ac_controller", None) or getattr(exec_ctx, "ac", None)
                if not ac_ctrl and self.orchestrator:
                    ac_ctrl = getattr(self.orchestrator, "ac_controller", None) or getattr(self.orchestrator, "ac", None)
                if not ac_ctrl:
                    try:
                        from ac_controller import AcController
                        ac_ctrl = AcController()
                    except Exception:
                        pass
                if ac_ctrl:
                    try:
                        ac_ctrl.set_mode(mode)
                        logger.info(f"[DECISION_ENGINE] Set AC mode to {mode}")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "mode": mode}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "mode": mode}

            elif tool_name in ["AC_SET_FAN", "SET_AC_FAN", "SET_FAN_SPEED"]:
                fan = str(params.get("fan_speed") or params.get("fan", "AUTO")).upper()
                ac_ctrl = None
                if exec_ctx:
                    ac_ctrl = getattr(exec_ctx, "ac_controller", None) or getattr(exec_ctx, "ac", None)
                if not ac_ctrl and self.orchestrator:
                    ac_ctrl = getattr(self.orchestrator, "ac_controller", None) or getattr(self.orchestrator, "ac", None)
                if not ac_ctrl:
                    try:
                        from ac_controller import AcController
                        ac_ctrl = AcController()
                    except Exception:
                        pass
                if ac_ctrl and hasattr(ac_ctrl, "set_fan_speed"):
                    try:
                        ok, res = ac_ctrl.set_fan_speed(fan)
                        logger.info(f"[DECISION_ENGINE] Set AC fan speed to {fan} (ok={ok})")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "fan_speed": fan}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "fan_speed": fan}

            elif tool_name in ["AC_POWER_OFF", "TURN_OFF_AC", "AC_OFF"]:
                ac_ctrl = None
                if exec_ctx:
                    ac_ctrl = getattr(exec_ctx, "ac_controller", None) or getattr(exec_ctx, "ac", None)
                if not ac_ctrl and self.orchestrator:
                    ac_ctrl = getattr(self.orchestrator, "ac_controller", None) or getattr(self.orchestrator, "ac", None)
                if not ac_ctrl:
                    try:
                        from ac_controller import AcController
                        ac_ctrl = AcController()
                    except Exception:
                        pass
                if ac_ctrl:
                    try:
                        ac_ctrl.set_power(False)
                        logger.info("[DECISION_ENGINE] Set AC power to False")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            # 4. Projector Commands
            elif tool_name in ["PROJECTOR_POWER_ON", "TURN_ON_PROJECTOR", "PROJECTOR_ON"]:
                proj_ctrl = None
                if exec_ctx:
                    proj_ctrl = getattr(exec_ctx, "projector_controller", None) or getattr(exec_ctx, "projector", None)
                if not proj_ctrl and self.orchestrator:
                    proj_ctrl = getattr(self.orchestrator, "projector_controller", None) or getattr(self.orchestrator, "projector", None)
                if not proj_ctrl:
                    try:
                        from projector_controller import ProjectorController
                        proj_ctrl = ProjectorController()
                    except Exception:
                        pass
                if proj_ctrl:
                    try:
                        if hasattr(proj_ctrl, "wake"):
                            proj_ctrl.wake()
                        elif hasattr(proj_ctrl, "turn_on"):
                            proj_ctrl.turn_on()
                        logger.info("[DECISION_ENGINE] Turned on projector")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}
                    except Exception as e:
                        logger.error(f"[DECISION_ENGINE] Error turning on projector: {e}")
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name in ["PROJECTOR_POWER_OFF", "TURN_OFF_PROJECTOR", "PROJECTOR_OFF"]:
                proj_ctrl = None
                if exec_ctx:
                    proj_ctrl = getattr(exec_ctx, "projector_controller", None) or getattr(exec_ctx, "projector", None)
                if not proj_ctrl and self.orchestrator:
                    proj_ctrl = getattr(self.orchestrator, "projector_controller", None) or getattr(self.orchestrator, "projector", None)
                if not proj_ctrl:
                    try:
                        from projector_controller import ProjectorController
                        proj_ctrl = ProjectorController()
                    except Exception:
                        pass
                if proj_ctrl:
                    try:
                        if hasattr(proj_ctrl, "turn_off"):
                            proj_ctrl.turn_off()
                        elif hasattr(proj_ctrl, "sleep"):
                            proj_ctrl.sleep()
                        elif hasattr(proj_ctrl, "power_off"):
                            proj_ctrl.power_off()
                        logger.info("[DECISION_ENGINE] Turned off projector")
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}
                    except Exception as e:
                        logger.error(f"[DECISION_ENGINE] Error turning off projector: {e}")
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name == "PROJECTOR_SET_SOURCE":
                src = params.get("source", "HDMI_1")
                proj_ctrl = None
                if exec_ctx:
                    proj_ctrl = getattr(exec_ctx, "projector_controller", None) or getattr(exec_ctx, "projector", None)
                if not proj_ctrl and self.orchestrator:
                    proj_ctrl = getattr(self.orchestrator, "projector_controller", None) or getattr(self.orchestrator, "projector", None)
                if not proj_ctrl:
                    try:
                        from projector_controller import ProjectorController
                        proj_ctrl = ProjectorController()
                    except Exception:
                        pass
                if proj_ctrl and hasattr(proj_ctrl, "set_source"):
                    try:
                        ok = proj_ctrl.set_source(src)
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "source": src}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "source": src}

            elif tool_name == "PROJECTOR_AUTO_FOCUS":
                proj_ctrl = None
                if exec_ctx:
                    proj_ctrl = getattr(exec_ctx, "projector_controller", None) or getattr(exec_ctx, "projector", None)
                if not proj_ctrl and self.orchestrator:
                    proj_ctrl = getattr(self.orchestrator, "projector_controller", None) or getattr(self.orchestrator, "projector", None)
                if not proj_ctrl:
                    try:
                        from projector_controller import ProjectorController
                        proj_ctrl = ProjectorController()
                    except Exception:
                        pass
                if proj_ctrl and hasattr(proj_ctrl, "auto_focus"):
                    try:
                        res = proj_ctrl.auto_focus()
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "result": res}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name == "PROJECTOR_AUTO_KEYSTONE":
                proj_ctrl = None
                if exec_ctx:
                    proj_ctrl = getattr(exec_ctx, "projector_controller", None) or getattr(exec_ctx, "projector", None)
                if not proj_ctrl and self.orchestrator:
                    proj_ctrl = getattr(self.orchestrator, "projector_controller", None) or getattr(self.orchestrator, "projector", None)
                if not proj_ctrl:
                    try:
                        from projector_controller import ProjectorController
                        proj_ctrl = ProjectorController()
                    except Exception:
                        pass
                if proj_ctrl and hasattr(proj_ctrl, "auto_keystone"):
                    try:
                        res = proj_ctrl.auto_keystone()
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "result": res}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name == "PROJECTOR_SET_BRIGHTNESS":
                b_val = int(params.get("brightness", 50))
                proj_ctrl = None
                if exec_ctx:
                    proj_ctrl = getattr(exec_ctx, "projector_controller", None) or getattr(exec_ctx, "projector", None)
                if not proj_ctrl and self.orchestrator:
                    proj_ctrl = getattr(self.orchestrator, "projector_controller", None) or getattr(self.orchestrator, "projector", None)
                if not proj_ctrl:
                    try:
                        from projector_controller import ProjectorController
                        proj_ctrl = ProjectorController()
                    except Exception:
                        pass
                if proj_ctrl and hasattr(proj_ctrl, "set_brightness"):
                    try:
                        ok, actual = proj_ctrl.set_brightness(b_val)
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "brightness": actual}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "brightness": b_val}

            # 5. Audio, Routing & Soundbar Commands
            elif tool_name in ["SOUNDBAR_ROUTE_FIRE_TV", "SOUNDBAR_ROUTE_TO_FIRE_TV"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "route_audio_to_fire_tv"):
                    orch.route_audio_to_fire_tv()
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name in ["SOUNDBAR_ROUTE_PC", "SOUNDBAR_ROUTE_TO_PC"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "route_audio_to_pc"):
                    orch.route_audio_to_pc()
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name in ["PC_MEDIA_PLAY", "MEDIA_PLAY", "PLAY_MUSIC"]:
                query = params.get("query") or params.get("title", "morning focus music")
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "play_music"):
                    try:
                        orch.play_music(query)
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "query": query}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                elif orch and hasattr(orch, "safe_play"):
                    try:
                        orch.safe_play(title=query)
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "query": query}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "query": query}

            elif tool_name in ["PC_SET_VOLUME", "SET_VOLUME", "SET_PC_VOLUME"]:
                vol = int(params.get("volume", 30))
                pc_ctrl = self.pc_controller
                if not pc_ctrl and exec_ctx:
                    pc_ctrl = getattr(exec_ctx, "pc_controller", None) or getattr(exec_ctx, "pc", None)
                if not pc_ctrl and self.orchestrator:
                    pc_ctrl = getattr(self.orchestrator, "pc_controller", None) or getattr(self.orchestrator, "pc", None)
                if not pc_ctrl:
                    try:
                        from pc_controller import PcController
                        pc_ctrl = PcController()
                    except Exception:
                        pass
                if pc_ctrl:
                    pc_ctrl.set_volume(vol)
                    logger.info(f"[DECISION_ENGINE] Set PC volume to {vol}%")
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "volume": vol}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "volume": vol}

            elif tool_name == "PC_LOCK_WORKSTATION":
                pc_ctrl = self.pc_controller
                if not pc_ctrl and exec_ctx:
                    pc_ctrl = getattr(exec_ctx, "pc_controller", None) or getattr(exec_ctx, "pc", None)
                if not pc_ctrl and self.orchestrator:
                    pc_ctrl = getattr(self.orchestrator, "pc_controller", None) or getattr(self.orchestrator, "pc", None)
                if not pc_ctrl:
                    try:
                        from pc_controller import PcController
                        pc_ctrl = PcController()
                    except Exception:
                        pass
                if pc_ctrl and hasattr(pc_ctrl, "lock_workstation"):
                    try:
                        ok, res = pc_ctrl.lock_workstation()
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "result": res}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name == "PC_LAUNCH_APP":
                app_n = params.get("app_name") or params.get("app", "chrome")
                pc_ctrl = self.pc_controller
                if not pc_ctrl and exec_ctx:
                    pc_ctrl = getattr(exec_ctx, "pc_controller", None) or getattr(exec_ctx, "pc", None)
                if not pc_ctrl and self.orchestrator:
                    pc_ctrl = getattr(self.orchestrator, "pc_controller", None) or getattr(self.orchestrator, "pc", None)
                if not pc_ctrl:
                    try:
                        from pc_controller import PcController
                        pc_ctrl = PcController()
                    except Exception:
                        pass
                if pc_ctrl and hasattr(pc_ctrl, "launch_allowlisted_app"):
                    try:
                        ok, res = pc_ctrl.launch_allowlisted_app(app_n)
                        return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "app": app_n, "result": res}
                    except Exception as e:
                        return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "app": app_n}

            elif tool_name == "PC_SLEEP":
                pc_ctrl = self.pc_controller or (getattr(exec_ctx, "pc_controller", None) if exec_ctx else None)
                if not pc_ctrl:
                    try:
                        from pc_controller import PcController
                        pc_ctrl = PcController()
                    except Exception:
                        pass
                if pc_ctrl and hasattr(pc_ctrl, "sleep"):
                    ok, res = pc_ctrl.sleep()
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "result": res}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED"}

            elif tool_name in ["SET_ACTIVE_MODE", "SET_ROOM_MODE", "TRANSITION_MODE"]:
                target_mode = str(params.get("mode", "RELAX")).upper()
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "set_active_mode"):
                    orch.set_active_mode(target_mode)
                logger.info(f"[DECISION_ENGINE] Set active mode to {target_mode}")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "mode": target_mode}

            # 6. Ambient Smart Lighting
            elif tool_name == "LIGHTING_SET_SCENE":
                scene_name = str(params.get("scene", "RELAX")).upper()
                try:
                    from light_controller import get_light_controller
                    ok, res = get_light_controller().set_scene(scene_name)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "scene": scene_name, "result": res}
                except Exception as e:
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            elif tool_name == "LIGHTING_SET_BRIGHTNESS":
                b_val = int(params.get("brightness", 80))
                try:
                    from light_controller import get_light_controller
                    ok, res = get_light_controller().set_brightness(b_val)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "brightness": b_val, "result": res}
                except Exception as e:
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            elif tool_name == "LIGHTING_SET_POWER":
                p_val = bool(params.get("power", True))
                try:
                    from light_controller import get_light_controller
                    ok, res = get_light_controller().set_power(p_val)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS" if ok else "FAILED", "power": p_val, "result": res}
                except Exception as e:
                    return {"step_id": step_id, "tool": tool_name, "status": "ERROR", "error": str(e)}

            # 7. Media & Fire TV Controls
            elif tool_name == "FIRE_TV_LAUNCH_APP":
                app = params.get("app_name", "netflix")
                ftv = getattr(exec_ctx, "firetv_service", None) if exec_ctx else None
                if ftv:
                    ftv.launch_app(app)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "app": app}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "app": app}

            elif tool_name == "FIRE_TV_MEDIA_PLAY":
                ftv = getattr(exec_ctx, "firetv_service", None) if exec_ctx else None
                if ftv and hasattr(ftv, "media_play"):
                    ftv.media_play()
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name == "FIRE_TV_MEDIA_PAUSE":
                ftv = getattr(exec_ctx, "firetv_service", None) if exec_ctx else None
                if ftv and hasattr(ftv, "media_pause"):
                    ftv.media_pause()
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name == "FIRE_TV_MEDIA_NEXT":
                ftv = getattr(exec_ctx, "firetv_service", None) if exec_ctx else None
                if ftv and hasattr(ftv, "media_next"):
                    ftv.media_next()
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name == "FIRE_TV_MEDIA_PREVIOUS":
                ftv = getattr(exec_ctx, "firetv_service", None) if exec_ctx else None
                if ftv and hasattr(ftv, "media_previous"):
                    ftv.media_previous()
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name == "FIRE_TV_KEY_NAVIGATE":
                key_name = str(params.get("key", "SELECT")).upper()
                ftv = getattr(exec_ctx, "firetv_service", None) if exec_ctx else None
                if ftv:
                    key_map = {
                        "UP": 19, "DOWN": 20, "LEFT": 21, "RIGHT": 22,
                        "SELECT": 23, "BACK": 4, "HOME": 3, "MENU": 82
                    }
                    keycode = key_map.get(key_name, 23)
                    if hasattr(ftv, "send_key"):
                        ftv.send_key(keycode)
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "key": key_name}

            elif tool_name == "PLAY_MUSIC":
                q = params.get("query", "relaxing music")
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "play_music"):
                    orch.play_music(q)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "query": q}
                elif orch and hasattr(orch, "safe_play"):
                    orch.safe_play(title=q)
                    return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "query": q}
                return {"step_id": step_id, "tool": tool_name, "status": "SIMULATED", "query": q}

            elif tool_name in ["MEDIA_PAUSE", "PAUSE_MEDIA", "PAUSE_MUSIC"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "pause_media"):
                    orch.pause_media()
                elif orch and hasattr(orch, "safe_pause"):
                    orch.safe_pause()
                else:
                    try:
                        from pc_controller import PcController
                        PcController().media_play_pause()
                    except Exception:
                        pass
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name in ["MEDIA_RESUME", "RESUME_MEDIA", "RESUME_MUSIC"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "resume_media"):
                    orch.resume_media()
                elif orch and hasattr(orch, "safe_resume"):
                    orch.safe_resume()
                else:
                    try:
                        from pc_controller import PcController
                        PcController().media_play_pause()
                    except Exception:
                        pass
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name in ["MUSIC_STOP", "STOP_MUSIC", "MEDIA_STOP"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "stop_media"):
                    orch.stop_media()
                else:
                    try:
                        from pc_controller import PcController
                        PcController().media_stop()
                    except Exception:
                        pass
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name in ["MUSIC_NEXT", "NEXT_TRACK", "MEDIA_NEXT"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "next_track"):
                    orch.next_track()
                else:
                    try:
                        from pc_controller import PcController
                        PcController().media_next()
                    except Exception:
                        pass
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            elif tool_name in ["MUSIC_PREVIOUS", "PREVIOUS_TRACK", "MEDIA_PREVIOUS"]:
                orch = getattr(exec_ctx, "orchestrator", None) or getattr(self, "orchestrator", None)
                if orch and hasattr(orch, "previous_track"):
                    orch.previous_track()
                else:
                    try:
                        from pc_controller import PcController
                        PcController().media_previous()
                    except Exception:
                        pass
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS"}

            # 5. Task & Goal Management Tools
            elif tool_name == "COMPLETE_TASK":
                task_name = params.get("task_name", "task")
                completed_title = self.memory_store.complete_task(task_name)
                logger.info(f"[DECISION_ENGINE] Completed task in SQLite: {completed_title or task_name}")
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "completed_task": completed_title or task_name}

            elif tool_name == "SET_ACTIVE_GOAL":
                title = params.get("title", "Active Goal")
                subgoals = params.get("subgoals", [])
                self._handle_goal_update({"title": title, "subgoals": subgoals, "status": "ACTIVE"})
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "goal": title}

            elif tool_name == "ADVANCE_GOAL_STEP":
                idx = int(params.get("step_index", 0))
                comp = bool(params.get("completed", True))
                active_g = self.memory_store.get_active_goal()
                if active_g:
                    self.memory_store.update_subgoal_status(active_g["id"], idx, completed=comp)
                return {"step_id": step_id, "tool": tool_name, "status": "SUCCESS", "step_index": idx}

            # 6. Generic capability fallback via PlanExecutor
            plan_step = PlanStep(
                step_id=step_id,
                device=tool_name.split("_")[0],
                capability=tool_name,
                parameters=params
            )
            res = exec_ctx.execute_step(plan_step, room_state)
            return {"step_id": step_id, "tool": tool_name, "status": str(res.status)}

        except Exception as e:
            logger.error(f"[DECISION_ENGINE] Tool execution error for {tool_name}: {e}")
            return {"step_id": step_id, "tool": tool_name, "status": "FAILED", "error": str(e)}

    # =========================================================================
    # Continuous Goal Management
    # =========================================================================

    def _handle_goal_update(self, goal_dict: Dict[str, Any]) -> None:
        """Saves or updates active continuous goal in persistent memory."""
        title = goal_dict.get("title", "Active Task")
        raw_subgoals = goal_dict.get("subgoals", [])
        status = goal_dict.get("status", "ACTIVE")

        subgoals = []
        for i, sg in enumerate(raw_subgoals, start=1):
            if isinstance(sg, str):
                subgoals.append({"id": i, "title": sg, "completed": False, "is_current": (i == 1)})
            elif isinstance(sg, dict):
                subgoals.append(sg)

        goal_id = f"goal_{int(time.time())}"
        self.memory_store.save_goal(
            goal_id=goal_id,
            title=title,
            subgoals=subgoals,
            status=status
        )
        logger.info(f"[DECISION_ENGINE] Persistent goal updated: '{title}' ({len(subgoals)} subgoals)")
