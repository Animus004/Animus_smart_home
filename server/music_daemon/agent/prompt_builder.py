"""
================================================================================
ANIMUS SMART ROOM — 3-LAYER COGNITIVE PROMPT BUILDER
================================================================================
Constructs compact, highly structured context prompts (< 800 tokens) with:
1. Core Identity (Autonomous, proactive, truthful, concise, 'buddy' address)
2. Temporal Awareness & Current Physical State (Date, time, mode, hardware telemetry, active goal)
3. Epistemic Long-Term Memory (Top RAG facts, habits, past conversational episodes)
4. Canonical Tool / Capability Schema
================================================================================
"""

from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent.long_term_memory import LongTermMemoryStore, get_long_term_memory
from room_state.models import RoomState

logger = logging.getLogger("music_daemon.agent.prompt_builder")


class CognitivePromptBuilder:
    """
    Synthesizes compact 3-layer prompt contexts optimized for local Qwen 4B Instruct
    (and Gemini fallback) without token bloating or memory saturation.
    """

    def __init__(self, memory_store: Optional[LongTermMemoryStore] = None):
        self.memory_store = memory_store or get_long_term_memory()

    # =========================================================================
    # Temporal State Synthesis
    # =========================================================================

    @staticmethod
    def get_temporal_context() -> Dict[str, Any]:
        """
        Produces rich temporal context for scheduling, habits, and user tracking.
        Uses local system time (Windows system clock) with full offset/tz awareness.
        """
        now = datetime.now().astimezone()
        hour = now.hour

        if 5 <= hour < 12:
            time_of_day = "MORNING"
            daylight = "DAYLIGHT"
        elif 12 <= hour < 17:
            time_of_day = "AFTERNOON"
            daylight = "DAYLIGHT"
        elif 17 <= hour < 21:
            time_of_day = "EVENING"
            daylight = "DUSK / TWILIGHT"
        else:
            time_of_day = "NIGHT"
            daylight = "DARK"

        formatted_time = now.strftime("%A, %d %B %Y, %I:%M %p")
        tz_name = now.tzname() or "Local"

        return {
            "iso_timestamp": now.isoformat(),
            "formatted_time": f"{formatted_time} ({tz_name})",
            "day_of_week": now.strftime("%A"),
            "time_of_day": time_of_day,
            "hour_24": hour,
            "minute": now.minute,
            "daylight_state": daylight,
            "timezone": tz_name
        }

    # =========================================================================
    # Physical Room State Sanitization
    # =========================================================================

    @staticmethod
    def sanitize_room_telemetry(room_state: Optional[RoomState]) -> Dict[str, Any]:
        """
        Extracts concise hardware state snapshot for the prompt.
        """
        if not room_state:
            printer_status = {"online": True, "model": "HP Ink Tank 310 series", "jobs": 0}
            try:
                from printer_controller import get_printer_controller
                p = get_printer_controller().get_status()
                printer_status = {"online": p.get("is_online", True), "model": p.get("printer_name", "HP Ink Tank 310 series"), "jobs": p.get("job_count", 0)}
            except Exception:
                pass

            return {
                "projector": "OFF",
                "ac": {"power": "UNKNOWN", "temp": 24, "mode": "COOL"},
                "soundbar": {"owner": "PC"},
                "lighting": {"power": "OFF", "scene": "DAY", "brightness": 80},
                "printer": printer_status,
                "active_mode": "IDLE"
            }
        # Extract values unwrapping StateField if present
        def _unwrap(v: Any, fallback: Any = None) -> Any:
            if v is None:
                return fallback
            if hasattr(v, "value"):
                return v.value if v.value is not None else fallback
            return v

        # AC State
        ac_power = "OFF"
        ac_temp = 24
        ac_mode = "COOL"
        ambient_temp = None
        if hasattr(room_state, "ac") and room_state.ac:
            raw_pwr = getattr(room_state.ac, "power", None)
            if raw_pwr is not None:
                ac_power = "ON" if _unwrap(raw_pwr, False) else "OFF"
            elif hasattr(room_state.ac, "is_powered_on"):
                ac_power = "ON" if room_state.ac.is_powered_on else "OFF"
            ac_temp = _unwrap(getattr(room_state.ac, "target_temperature", None), 24)
            ac_mode = str(_unwrap(getattr(room_state.ac, "mode", None), "COOL"))
            ambient_temp = _unwrap(getattr(room_state.ac, "current_temperature", None), None)

        # Projector State
        proj_power = "OFF"
        if hasattr(room_state, "projector") and room_state.projector:
            raw_proj = getattr(room_state.projector, "power", None)
            if raw_proj is not None:
                proj_power = "ON" if _unwrap(raw_proj, False) else "OFF"
            elif hasattr(room_state.projector, "is_powered_on"):
                proj_power = "ON" if room_state.projector.is_powered_on else "OFF"

        # Soundbar State
        soundbar_owner = "PC"
        if hasattr(room_state, "soundbar") and room_state.soundbar:
            raw_owner = getattr(room_state.soundbar, "current_owner", None) or getattr(room_state.soundbar, "active_owner", None)
            soundbar_owner = str(_unwrap(raw_owner, "PC"))

        # Lighting State
        lighting_state = {"power": "OFF", "scene": "DAY", "brightness": 80}
        try:
            from light_controller import get_light_controller
            l_stat = get_light_controller().get_status()
            lighting_state = {
                "power": "ON" if l_stat.get("power") else "OFF",
                "scene": l_stat.get("active_scene", "DAY"),
                "brightness": l_stat.get("brightness", 80)
            }
        except Exception:
            pass

        # Printer State
        printer_state = {"online": True, "model": "HP Ink Tank 310 series", "jobs": 0}
        try:
            from printer_controller import get_printer_controller
            p_stat = get_printer_controller().get_status()
            printer_state = {
                "online": p_stat.get("is_online", True),
                "model": p_stat.get("printer_name", "HP Ink Tank 310 series"),
                "jobs": p_stat.get("job_count", 0),
                "status": p_stat.get("status", "Normal")
            }
        except Exception:
            pass

        return {
            "projector": proj_power,
            "ac": {
                "power": ac_power,
                "target_temp_c": ac_temp,
                "ambient_temp_c": ambient_temp,
                "mode": ac_mode
            },
            "soundbar": {
                "audio_routed_to": soundbar_owner
            },
            "lighting": lighting_state,
            "printer": printer_state
        }

    # =========================================================================
    # System Instruction & Prompt Compilation
    # =========================================================================

    def build_system_instruction(self) -> str:
        """
        Returns Layer 1 (Core Identity, Personality & Behavioral Invariants).
        """
        return (
            "You are Animus, an intelligent, poised, and proactive personal smart room companion "
            "for Sayan (address him respectfully and naturally as 'Sir').\n\n"
            "PERSONALITY & CONVERSATIONAL STYLE:\n"
            "- Speak with natural warmth, executive composure, and quiet confidence (like J.A.R.V.I.S.). You are a capable executive companion, not a sterile robotic terminal.\n"
            "- NEVER use repetitive, stiff robotic templates like 'All set, buddy', 'I have adjusted...', 'Done, buddy', or 'Room is now cool'.\n"
            "- Vary your phrasing naturally. Express what you did casually and fluidly with dignified polish:\n"
            "  • e.g. 'Chilled the room to 22°C and fired up the projector for you, Sir. Throw on whatever you like!'\n"
            "  • e.g. 'Turned down the volume, Sir — let me know if you need it even quieter.'\n"
            "  • e.g. 'Projector is already running, Sir — we're good to go.'\n"
            "  • e.g. 'Haha, 40°C would turn your room into a sauna, Sir! Keeping it in the safe 16–30°C range.'\n"
            "- Keep conversational turns concise, smooth, and engaging (1-2 sentences).\n\n"
            "CORE OPERATIONAL RULES:\n"
            "1. You are an AGENT: perceive the room state, decide on actions, execute tools, maintain active goals, and remember user facts.\n"
            "2. Always stay aware of the current time, schedules, and active objectives.\n"
            "3. Ground all statements in verified physical reality. NEVER pretend a hardware action succeeded if it didn't.\n"
            "4. Hardware bounds: AC is 16°C to 30°C (modes: COOL, AUTO, DRY, FAN). PC Volume is 0 to 100%.\n"
            "5. STATUS & TASK QUERIES: When Sir asks 'what are we working on?', 'what are my tasks?', 'what's on my agenda?', or asks what to do next, do NOT execute hardware tools. Set action_type to CONVERSATION and naturally summarize the active objective and pending tasks (e.g. SmartRoom development, SQL practice, guitar session).\n"
            "6. WORK MODE INITIATION: When Sir says 'start work', 'work mode', 'let's work', or asks to begin studying/coding, call LAUNCH_WORK_MODE. This launches MySQL Workbench and Word, sets PC volume to 15%, checks focus music, and sets AC to 24°C.\n"
            "7. WORK WRAP-UP: When Sir says 'I am done with work', 'wrap up work', 'finished working', or 'wrap up for today', call WRAPUP_WORK_SESSION. This automatically saves progress (Ctrl+S), closes work apps, and sets active mode to RELAX. You MUST summarize today's accomplishments in 'response_message' and formulate 1-2 new tasks for tomorrow using CREATE_TASK tool calls!\n"
            "8. TASK & REMINDER AUTONOMY: You have full authority to add, update, delete, or complete tasks (CREATE_TASK, UPDATE_TASK, DELETE_TASK, COMPLETE_TASK), and schedule reminders or alarms (SCHEDULE_REMINDER, SET_ALARM) when requested or appropriate.\n"
            "9. SITUATIONAL PERSONAL REASONING: Always answer: 'What would make sense for Sir in this specific situation?' rather than merely executing literal text. If Sir reports discomfort (freezing, too cold, too hot, fatigue, headache), adapt room environment proactively and gently. When discussing SQL or career projects, reason with his Blinkit Dark Store project context.\n"
            "10. PHYSICAL ROOM AGENT (MINI-ASTRA): You have physical control over the connected hardware:\n"
            "    • HP USB Printer: Check spooler/status (PRINTER_GET_STATUS), print files (PRINTER_PRINT_FILE), or clear print queue (PRINTER_CANCEL_JOBS).\n"
            "    • Projector: Switch sources (PROJECTOR_SET_SOURCE), trigger autofocus (PROJECTOR_AUTO_FOCUS), auto-keystone (PROJECTOR_AUTO_KEYSTONE), or adjust screen brightness (PROJECTOR_SET_BRIGHTNESS).\n"
            "    • Fire TV: Control playback (FIRE_TV_MEDIA_PLAY, FIRE_TV_MEDIA_PAUSE, FIRE_TV_MEDIA_NEXT, FIRE_TV_MEDIA_PREVIOUS) and navigate remote D-Pad (FIRE_TV_KEY_NAVIGATE).\n"
            "    • PC Workstation: Lock screen (PC_LOCK_WORKSTATION), launch allowlisted apps (PC_LAUNCH_APP: chrome, edge, notepad, calc, word, sql), or sleep (PC_SLEEP).\n"
            "    • AC: Power on (AC_POWER_ON), temperature, mode, and blower fan speed (AC_SET_FAN: LOW, MEDIUM, HIGH, AUTO).\n"
            "    • Lighting: Ambient scenes (LIGHTING_SET_SCENE: RELAX, FOCUS, CINEMA, DAY, NIGHT), brightness, or power.\n"
            "11. Output MUST ALWAYS be valid JSON strictly matching the requested schema."
        )

    def build_prompt(
        self,
        user_utterance: str,
        room_state: Optional[RoomState] = None,
        active_mode: str = "IDLE",
        recent_turns: Optional[List[Dict[str, str]]] = None,
        tool_catalog: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Synthesizes the complete prompt payload (< 800 tokens) ready for LLM inference.
        """
        temporal = self.get_temporal_context()
        telemetry = self.sanitize_room_telemetry(room_state)
        
        # Epistemic facts, active goal & tasks from SQLite
        facts = self.memory_store.get_all_facts()
        active_goal = self.memory_store.get_active_goal()
        tasks = self.memory_store.get_active_tasks(limit=5)
        past_turns = self.memory_store.search_past_conversations(user_utterance, limit=2)

        # Astra Contextual Associative Memory Retrieval (Relevance-filtered, zero context flooding)
        relevant_memories = []
        user_facts_compact = {}
        if hasattr(self.memory_store, "retrieve_relevant_structured_memories"):
            structured_hits = self.memory_store.retrieve_relevant_structured_memories(
                query=user_utterance,
                active_mode=active_mode,
                limit=6
            )
            for m in structured_hits:
                m_type = m.get("type", "fact").upper()
                m_subj = m.get("subject", "")
                m_ctx = f" ({m.get('context')})" if m.get("context") else ""
                m_val = m.get("value", "")
                relevant_memories.append(f"[{m_type}] {m_subj}{m_ctx}: {m_val}")
                user_facts_compact[f"{m_subj}{m_ctx}"] = m_val

        # Merge explicit user facts from SQLite
        for k, v in list(facts.items()):
            if k not in user_facts_compact and len(user_facts_compact) < 10:
                user_facts_compact[k] = v

        # Build ultra-compact representations for rapid CPU inference
        raw_tools = tool_catalog or self.get_default_tool_catalog()
        compact_tools = []
        for t in raw_tools:
            name = t.get("name")
            p_keys = list(t.get("parameters", {}).keys())
            compact_tools.append(f"{name}({', '.join(p_keys)})" if p_keys else name)

        current_subgoal = None
        if active_goal:
            for sg in active_goal.get("subgoals", []):
                if sg.get("is_current") and not sg.get("completed"):
                    current_subgoal = sg.get("title")
                    break

        context_payload = {
            "current_time": temporal["formatted_time"],
            "time_of_day": temporal["time_of_day"],
            "active_mode": active_mode,
            "room_state": telemetry,
            "active_objective": active_goal["title"] if active_goal else None,
            "current_milestone": current_subgoal,
            "pending_tasks": [f"{t['title']} [{t.get('priority', 'MED')}]" for t in tasks],
            "relevant_personal_memories": relevant_memories,
            "user_facts": user_facts_compact,
            "recent_conversation": recent_turns or [],
            "user_utterance": user_utterance,
            "tools": compact_tools
        }

        format_instructions = (
            "You are Animus, executive smart room assistant and Senior Data Analyst mentor to Sir (Sayan Halder).\n"
            "PARAGRAPH & MULTI-ACTION DECOMPOSITION:\n"
            "- When Sir submits a paragraph, multi-command, or compound instruction (e.g., 'Turn off the AC, turn on the projector, and play focus beats'), extract ALL executable actions into the `tool_calls` array in sequential execution order.\n"
            "- Never stop after the first command. Every actionable clause must have its corresponding tool in `tool_calls`.\n"
            "If Sir shares a work summary from ChatGPT or project progress, acknowledge his technical accomplishments (SQL, CTEs, Excel), advance the milestone, schedule tomorrow's task via CREATE_TASK, and provide motivating feedback.\n"
            "RESPOND STRICTLY IN VALID JSON WITH THIS EXACT STRUCTURE:\n"
            "{\n"
            '  "thought": "1-sentence internal reasoning based on time, state, and user desire",\n'
            '  "action_type": "TOOL_EXECUTION" | "CONVERSATION" | "CLARIFICATION" | "GOAL_UPDATE",\n'
            '  "tool_calls": [\n'
            '    {"tool": "TOOL_NAME", "params": {"param_key": "param_val"}}\n'
            '  ],\n'
            '  "goal_update": null | {"title": "Goal Name", "subgoals": ["Step 1", "Step 2"], "status": "ACTIVE"},\n'
            '  "response_message": "Concise natural response to Sir"\n'
            "}"
        )

        return (
            f"### CONTEXT & CURRENT STATE\n"
            f"{json.dumps(context_payload, indent=2, default=str)}\n\n"
            f"### INSTRUCTIONS\n"
            f"{format_instructions}"
        )

    # =========================================================================
    # Default Tool Catalog (Semantic Capability Schema for Qwen)
    # =========================================================================

    def get_default_tool_catalog(self) -> List[Dict[str, Any]]:
        """Returns authoritative tool schemas with typed signatures."""
        return [
            # Work & Orchestration
            {
                "name": "LAUNCH_WORK_MODE",
                "description": "Activates Work Mode: launches SQL and Word, sets PC volume to 15%, checks focus music, adjusts AC to 24°C.",
                "parameters": {}
            },
            {
                "name": "WRAPUP_WORK_SESSION",
                "description": "Saves unsaved work progress (Ctrl+S), closes work apps, switches room to relax mode, and queues next-day tasks.",
                "parameters": {}
            },
            # HP USB Printer Subsystem
            {
                "name": "PRINTER_GET_STATUS",
                "description": "Checks HP Ink Tank 310 status, USB connection, driver health, and active print spooler queue count.",
                "parameters": {}
            },
            {
                "name": "PRINTER_PRINT_FILE",
                "description": "Dispatches a local document, report, or cheat sheet to HP Ink Tank 310 series printer.",
                "parameters": {"file_path": "string (absolute or relative file path)"}
            },
            {
                "name": "PRINTER_CANCEL_JOBS",
                "description": "Cancels all pending or stuck jobs in the HP Ink Tank print queue.",
                "parameters": {}
            },
            # Air Conditioner (Tuya Local 3.3)
            {
                "name": "AC_POWER_ON",
                "description": "Powers on the AC.",
                "parameters": {}
            },
            {
                "name": "AC_POWER_OFF",
                "description": "Turns off the AC.",
                "parameters": {}
            },
            {
                "name": "AC_SET_TEMPERATURE",
                "description": "Sets the air conditioner target temperature (16 to 30°C).",
                "parameters": {"temperature": "integer (16 to 30)"}
            },
            {
                "name": "AC_SET_MODE",
                "description": "Sets Tuya AC mode.",
                "parameters": {"mode": "string (COOL | AUTO | DRY | FAN)"}
            },
            {
                "name": "AC_SET_FAN",
                "description": "Sets AC blower fan speed.",
                "parameters": {"fan_speed": "string (LOW | MEDIUM | HIGH | AUTO)"}
            },
            # Zebronics Projector (ADB Wi-Fi & Tuya IR)
            {
                "name": "PROJECTOR_POWER_ON",
                "description": "Powers on Zebronics projector via Tuya Local IR or ADB wake.",
                "parameters": {}
            },
            {
                "name": "PROJECTOR_POWER_OFF",
                "description": "Powers off projector gracefully.",
                "parameters": {}
            },
            {
                "name": "PROJECTOR_SET_SOURCE",
                "description": "Switches projector video input source.",
                "parameters": {"source": "string (HDMI_1 | ANDROID_HOME | USB)"}
            },
            {
                "name": "PROJECTOR_AUTO_FOCUS",
                "description": "Triggers electric motor camera autofocus calibration.",
                "parameters": {}
            },
            {
                "name": "PROJECTOR_AUTO_KEYSTONE",
                "description": "Triggers 6D gyro automatic keystone geometry correction.",
                "parameters": {}
            },
            {
                "name": "PROJECTOR_SET_BRIGHTNESS",
                "description": "Sets projector optical brightness on 0-100% scale.",
                "parameters": {"brightness": "integer (0 to 100)"}
            },
            # Fire TV Stick (ADB Wi-Fi)
            {
                "name": "FIRE_TV_LAUNCH_APP",
                "description": "Launches streaming app on Fire TV (netflix, youtube, prime_video, hotstar, apple_tv).",
                "parameters": {"app_name": "string"}
            },
            {
                "name": "FIRE_TV_MEDIA_PLAY",
                "description": "Sends Play key to Fire TV streaming playback.",
                "parameters": {}
            },
            {
                "name": "FIRE_TV_MEDIA_PAUSE",
                "description": "Sends Pause key to Fire TV streaming playback.",
                "parameters": {}
            },
            {
                "name": "FIRE_TV_MEDIA_NEXT",
                "description": "Skips to next episode or track on Fire TV.",
                "parameters": {}
            },
            {
                "name": "FIRE_TV_MEDIA_PREVIOUS",
                "description": "Rewinds or skips to previous episode/track on Fire TV.",
                "parameters": {}
            },
            {
                "name": "FIRE_TV_KEY_NAVIGATE",
                "description": "Sends remote navigation key event to Fire TV.",
                "parameters": {"key": "string (UP | DOWN | LEFT | RIGHT | SELECT | BACK | HOME)"}
            },
            # PC Workstation Controls
            {
                "name": "PC_SET_VOLUME",
                "description": "Adjusts master PC volume level.",
                "parameters": {"volume": "integer (0 to 100)"}
            },
            {
                "name": "PC_LOCK_WORKSTATION",
                "description": "Locks the Windows workstation instantly for privacy when stepping away.",
                "parameters": {}
            },
            {
                "name": "PC_LAUNCH_APP",
                "description": "Launches an allowlisted desktop application onto user's screen.",
                "parameters": {"app_name": "string (chrome | edge | notepad | calc | explorer | sql | word)"}
            },
            {
                "name": "PC_SLEEP",
                "description": "Puts PC into system sleep/suspend.",
                "parameters": {}
            },
            # Ambient Smart Lighting
            {
                "name": "LIGHTING_SET_SCENE",
                "description": "Sets ambient room lighting scene preset.",
                "parameters": {"scene": "string (FOCUS | RELAX | CINEMA | DAY | NIGHT | OFF)"}
            },
            {
                "name": "LIGHTING_SET_BRIGHTNESS",
                "description": "Sets smart lighting brightness level.",
                "parameters": {"brightness": "integer (1 to 100)"}
            },
            {
                "name": "LIGHTING_SET_POWER",
                "description": "Turns room lighting ON or OFF.",
                "parameters": {"power": "boolean"}
            },
            # Soundbar & Music Subsystem
            {
                "name": "SOUNDBAR_ROUTE_FIRE_TV",
                "description": "Connects LG Soundbar audio to Fire TV.",
                "parameters": {}
            },
            {
                "name": "SOUNDBAR_ROUTE_PC",
                "description": "Connects LG Soundbar audio to PC.",
                "parameters": {}
            },
            {
                "name": "PLAY_MUSIC",
                "description": "Resolves and plays track/playlist via YouTube Music / MPV.",
                "parameters": {"query": "string (song title, artist, or vibe)"}
            },
            {
                "name": "MEDIA_PAUSE",
                "description": "Pauses currently active media playback.",
                "parameters": {}
            },
            {
                "name": "MEDIA_RESUME",
                "description": "Resumes paused media playback.",
                "parameters": {}
            },
            {
                "name": "MUSIC_STOP",
                "description": "Stops music playback.",
                "parameters": {}
            },
            {
                "name": "MUSIC_NEXT",
                "description": "Skips to next track in music queue.",
                "parameters": {}
            },
            {
                "name": "MUSIC_PREVIOUS",
                "description": "Returns to previous music track.",
                "parameters": {}
            },
            # Agenda, Tasks & Goals
            {
                "name": "CREATE_TASK",
                "description": "Adds a new task to schedule or tomorrow's agenda.",
                "parameters": {"title": "string", "priority": "HIGH | MEDIUM | LOW", "category": "WORK | PERSONAL | LEARNING"}
            },
            {
                "name": "UPDATE_TASK",
                "description": "Updates status or title of an existing task.",
                "parameters": {"task_name": "string", "new_status": "COMPLETED | PENDING | IN_PROGRESS"}
            },
            {
                "name": "DELETE_TASK",
                "description": "Removes a task from agenda.",
                "parameters": {"task_name": "string"}
            },
            {
                "name": "COMPLETE_TASK",
                "description": "Marks a pending task as completed (e.g. SQL practice, project).",
                "parameters": {"task_name": "string"}
            },
            {
                "name": "SCHEDULE_REMINDER",
                "description": "Schedules a time-based task or reminder.",
                "parameters": {"reminder": "string", "time_or_offset": "string (e.g. '17:00' or 'in 20 mins')"}
            },
            {
                "name": "SET_ALARM",
                "description": "Sets a wakeup or focus alarm.",
                "parameters": {"time_str": "string (e.g. 07:00)", "label": "string"}
            },
            {
                "name": "SET_ACTIVE_GOAL",
                "description": "Sets or changes the current active roadmap goal and subgoals.",
                "parameters": {"title": "string", "subgoals": "list of strings"}
            },
            {
                "name": "ADVANCE_GOAL_STEP",
                "description": "Advances or completes a specific step in the active goal.",
                "parameters": {"step_index": "integer (0-based)", "completed": "boolean"}
            }
        ]
