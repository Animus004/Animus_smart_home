"""
================================================================================
ANIMUS SMART ROOM — PERSONAL SITUATIONAL REASONING ENGINE (PHASE 2)
================================================================================
Evaluates: "What would make sense for Sir in this specific situation?"
rather than just: "What does the command literally say?"

Core Evaluators:
1. Implicit Thermal & Climate Reasoning (resolves "freezing", "too hot" using live telemetry).
2. Wellbeing & Fatigue Respite (adapts lights, audio, and climate for headache/exhaustion).
3. Temporal & Routine Ambiguity Disambiguation ("play something" -> focus lofi vs acoustic evening).
4. Career & Project Mentorship Reasoning (Blinkit Stock-Out SQL, CTEs, LAG() guidance).
5. Constraint & Quiet-Hours Conflict Arbitration (caps volume late at night).
================================================================================
"""

from __future__ import annotations
import datetime
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("music_daemon.agent.personal_reasoner")


class PersonalReasoningEngine:
    """
    Situational cognitive evaluator translating natural human states and ambiguous
    utterances into proactive, highly context-aware smart room decisions.
    """

    def __init__(self, memory_store: Optional[Any] = None):
        self.memory_store = memory_store

    # =========================================================================
    # Helpers for Room Telemetry Inspection
    # =========================================================================

    @staticmethod
    def _extract_ac_telemetry(room_state: Optional[Any]) -> Tuple[bool, int, Optional[float]]:
        """
        Safely extracts (is_powered_on, target_temp, ambient_temp) from room_state
        regardless of whether room_state is a RoomState model, dict, or None.
        """
        is_on = False
        target_temp = 24
        ambient_temp = None

        if room_state is None:
            return is_on, target_temp, ambient_temp

        # Object inspection
        if hasattr(room_state, "ac") and room_state.ac:
            ac = room_state.ac
            raw_pwr = getattr(ac, "power", None)
            if raw_pwr is not None:
                is_on = bool(getattr(raw_pwr, "value", raw_pwr))
            elif hasattr(ac, "is_powered_on"):
                is_on = bool(ac.is_powered_on)

            raw_target = getattr(ac, "target_temperature", None)
            if raw_target is not None:
                target_temp = int(getattr(raw_target, "value", raw_target) or 24)

            raw_amb = getattr(ac, "current_temperature", None)
            if raw_amb is not None:
                ambient_temp = float(getattr(raw_amb, "value", raw_amb) or 0.0)

        # Dict inspection
        elif isinstance(room_state, dict):
            ac_dict = room_state.get("ac", {})
            if isinstance(ac_dict, dict):
                pwr = ac_dict.get("power", "OFF")
                is_on = pwr in [True, "ON", "true", "True", 1]
                target_temp = int(ac_dict.get("target_temp_c", ac_dict.get("temp", 24)) or 24)
                ambient_temp = ac_dict.get("ambient_temp_c", None)

        return is_on, target_temp, ambient_temp

    # =========================================================================
    # 1. Implicit Thermal & Climate Reasoning
    # =========================================================================

    def evaluate_implicit_climate(
        self,
        lower: str,
        room_state: Optional[Any],
        active_mode: str
    ) -> Optional[Dict[str, Any]]:
        """
        Detects statements of thermal discomfort ('freezing', 'too cold', 'too warm', 'boiling')
        and calculates proportional, preference-aligned temperature adjustments.
        """
        is_cold = any(w in lower for w in [
            "freezing", "freezing cold", "too cold", "so cold", "feeling cold",
            "chilly", "it's cold", "its cold", "shivering", "a bit cold", "quite cold"
        ])
        is_hot = any(w in lower for w in [
            "too warm", "too hot", "so hot", "sweating", "stuffy", "boiling",
            "it's warm", "its warm", "feeling warm", "feeling hot", "a bit warm"
        ])

        if not (is_cold or is_hot):
            return None

        is_on, cur_target, ambient = self._extract_ac_telemetry(room_state)

        if is_cold:
            if not is_on:
                return {
                    "thought": "Implicit climate: user is cold, but AC is already off.",
                    "action_type": "CONVERSATION",
                    "tool_calls": [],
                    "response_message": "The AC is already powered off, Sir. Let me know if you would like me to adjust anything else.",
                    "light_cue": "NEUTRAL"
                }

            # Bump up setpoint towards comfortable baseline (24°C or 25°C)
            new_target = min(26, max(cur_target + 3, 24))
            if new_target <= cur_target:
                new_target = min(28, cur_target + 2)

            return {
                "thought": f"Implicit climate: user reported feeling cold. Current setpoint is {cur_target}°C. Raising setpoint to {new_target}°C.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": new_target}},
                    {"tool": "AC_SET_MODE", "params": {"mode": "COOL"}}
                ],
                "response_message": f"Bumping the AC from {cur_target}°C up to {new_target}°C to make it comfortable for you, Sir.",
                "light_cue": "CLIMATE_PULSE"
            }

        elif is_hot:
            # Lower setpoint towards cool preference (21°C or 22°C)
            new_target = 22 if active_mode == "WORK" else 21
            if is_on and cur_target <= new_target:
                new_target = max(18, cur_target - 2)

            from_str = f"from {cur_target}°C " if is_on else ""
            return {
                "thought": f"Implicit climate: user reported feeling hot/warm. Setting setpoint to {new_target}°C COOL.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": new_target}},
                    {"tool": "AC_SET_MODE", "params": {"mode": "COOL"}}
                ],
                "response_message": f"Lowering the AC {from_str}down to {new_target}°C to cool the room down for you, Sir.",
                "light_cue": "CLIMATE_PULSE"
            }

        return None

    # =========================================================================
    # 2. Wellbeing & Fatigue Respite
    # =========================================================================

    def evaluate_wellbeing_respite(self, lower: str, active_mode: str) -> Optional[Dict[str, Any]]:
        """
        Detects physical fatigue, headaches, or distress and configures a low-sensory
        respite environment (subdued lights, 10% volume/mute, gentle climate).
        """
        is_fatigued = any(w in lower for w in [
            "headache", "migraine", "exhausted", "bad headache", "terrible headache",
            "eye strain", "eyes hurt", "not feeling well", "feeling sick", "need to rest",
            "super tired", "feel dizzy", "too exhausted", "worn out"
        ])

        if not is_fatigued:
            return None

        return {
            "thought": "Wellbeing respite: user reported discomfort/fatigue. Creating low-sensory recovery environment.",
            "action_type": "TOOL_EXECUTION",
            "tool_calls": [
                {"tool": "SET_VOLUME", "params": {"volume": 10}},
                {"tool": "AC_SET_TEMPERATURE", "params": {"temperature": 24}}
            ],
            "response_message": "Turning the volume down and dimming things, Sir. Rest up, and let me know if you need anything else.",
            "light_cue": "REST_AMBER",
            "ui_state": {"mode": "REST", "status": "respite"},
            "sound_cue": "SILENT"
        }

    # =========================================================================
    # 3. Temporal & Routine Contextual Music
    # =========================================================================

    def evaluate_contextual_music(
        self,
        lower: str,
        active_mode: str,
        current_time: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Disambiguates generic music requests ('play something', 'put on music')
        by reasoning over the user's daily study routines and temporal rhythms.
        """
        is_generic_play = bool(re.search(
            r'^(?:please\s+)?(?:play\s+something|put\s+on\s+(?:some\s+)?(?:music|tunes|tracks)|play\s+(?:some\s+)?(?:music|tunes)|start\s+music)(?:\s+please)?$',
            lower.strip()
        ))

        if not is_generic_play:
            return None

        now = current_time if current_time is not None else time.time()
        dt = datetime.datetime.fromtimestamp(now)
        hour = dt.hour

        # 1. Daytime / Active Study Hours (11:00 AM - 5:00 PM) or WORK mode
        if active_mode == "WORK" or (11 <= hour < 17):
            return {
                "thought": "Contextual music: daytime study window. Selecting focus lofi beats at 15% volume.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "PLAY_MUSIC", "params": {"query": "soothing lofi focus beats"}},
                    {"tool": "SET_VOLUME", "params": {"volume": 15}}
                ],
                "response_message": "Putting on some focus lofi beats at low volume for your study session, Sir.",
                "light_cue": "FOCUS_WARM",
                "ui_state": {"mode": "WORK"},
                "sound_cue": "FOCUS_START"
            }

        # 2. Afternoon & Evening Guitar / Relaxation Window (5:00 PM - 9:00 PM)
        elif 17 <= hour < 21:
            return {
                "thought": "Contextual music: evening relaxation window. Selecting relaxed acoustic guitar tracks at 25% volume.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "PLAY_MUSIC", "params": {"query": "relaxing acoustic guitar and instrumental chill"}},
                    {"tool": "SET_VOLUME", "params": {"volume": 25}}
                ],
                "response_message": "Queuing up some relaxed acoustic guitar tracks for the evening, Sir.",
                "light_cue": "RELAX_AMBER",
                "ui_state": {"mode": "RELAX"},
                "sound_cue": "CHIME_SUBTLE"
            }

        # 3. Late Night / Bedtime Window (>= 21:00 or < 07:00)
        else:
            return {
                "thought": "Contextual music: late night quiet window. Selecting soft ambient soundscape at 15% volume.",
                "action_type": "TOOL_EXECUTION",
                "tool_calls": [
                    {"tool": "PLAY_MUSIC", "params": {"query": "ambient sleeping soundscape"}},
                    {"tool": "SET_VOLUME", "params": {"volume": 15}}
                ],
                "response_message": "Playing soft ambient sounds at low volume for the late evening, Sir.",
                "light_cue": "REST_AMBER",
                "ui_state": {"mode": "RELAX"},
                "sound_cue": "SILENT"
            }

    # =========================================================================
    # 4. Career & Project Mentorship Reasoning
    # =========================================================================

    def evaluate_career_mentorship(
        self,
        lower: str,
        active_goal: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Provides actionable Data Analyst mentorship on Sir's active portfolio projects
        (e.g., Blinkit Dark Store stock-out window functions, CTEs, lost revenue metrics).
        """
        # Guard: Ignore if this is a work summary, milestone report, or status report rather than a query help request
        if any(k in lower for k in [
            "current project", "stakeholder", "learning milestone", "has been completed",
            "current work", "career goal", "today's work", "chatgpt"
        ]):
            return None

        has_sql_issue = any(w in lower for w in [
            "stock-out", "stock out", "dark store", "lag()", "cte", "lag function",
            "window function", "out-of-stock", "inventory gap", "query isn't working",
            "query is not working", "query error", "calculation is off", "how to calculate"
        ])

        if not has_sql_issue:
            return None

        # Determine mentorship topic
        if any(w in lower for w in ["lag", "window", "duration", "gap", "time", "between", "how to calculate", "isn't working", "not working"]):
            return {
                "thought": "Career mentorship: advising on Blinkit stock-out duration calculation with CTEs and LAG().",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "response_message": (
                    "For the Blinkit dark store stock-out calculation, Sir, ensure your LAG() window function "
                    "partitions by dark_store_id and sku_id ordered by event_timestamp. "
                    "By subtracting LAG(event_timestamp) from the restock timestamp inside a CTE, "
                    "you isolate the exact out-of-stock duration in minutes for every store."
                ),
                "light_cue": "FOCUS_WARM",
                "ui_state": {"mode": "WORK", "topic": "SQL_MENTORSHIP"}
            }
        elif any(w in lower for w in ["revenue", "lost revenue", "penalty", "demand"]):
            return {
                "thought": "Career mentorship: advising on Blinkit lost revenue estimation formula.",
                "action_type": "CONVERSATION",
                "tool_calls": [],
                "response_message": (
                    "To estimate lost revenue accurately, Sir, multiply the stock-out duration by the average hourly sales rate "
                    "for that specific SKU during that time-of-day bucket, joined against your product price catalog."
                ),
                "light_cue": "FOCUS_WARM",
                "ui_state": {"mode": "WORK", "topic": "SQL_MENTORSHIP"}
            }

        return None

    # =========================================================================
    # 5. Quiet-Hours & Safety Conflict Arbitration
    # =========================================================================

    def arbitrate_conflicts(
        self,
        tool_calls: List[Dict[str, Any]],
        response_message: str,
        current_time: Optional[float] = None,
        active_mode: str = "IDLE"
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Enforces safety bounds and late-night quiet hours without disrupting user experience.
        Between 22:00 (10 PM) and 07:00 (7 AM), caps speaker volume to 25%.
        """
        now = current_time if current_time is not None else time.time()
        dt = datetime.datetime.fromtimestamp(now)
        hour = dt.hour
        is_quiet_hours = (hour >= 22 or hour < 7)

        sanitized_calls = []
        capped_notice = False

        for tc in tool_calls:
            tool_name = tc.get("tool")
            params = dict(tc.get("params", {}))

            if tool_name == "SET_VOLUME":
                vol = params.get("volume", 30)
                if is_quiet_hours and vol > 25:
                    params["volume"] = 25
                    capped_notice = True
                params["volume"] = max(0, min(100, params["volume"]))

            elif tool_name == "AC_SET_TEMPERATURE":
                t = params.get("temperature", 24)
                params["temperature"] = max(16, min(30, t))

            sanitized_calls.append({"tool": tool_name, "params": params})

        final_msg = response_message
        if capped_notice and "quiet hours" not in final_msg.lower():
            final_msg += " (Volume capped at 25% for late-night quiet hours, Sir.)"

        return sanitized_calls, final_msg

    # =========================================================================
    # Master Situational Evaluator
    # =========================================================================

    def evaluate_situational_turn(
        self,
        user_utterance: str,
        room_state: Optional[Any] = None,
        active_mode: str = "IDLE",
        current_time: Optional[float] = None,
        active_goal: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Runs the full suite of Phase 2 personal reasoning evaluators.
        Returns a structured decision plan if a situational match is identified.
        """
        lower = user_utterance.strip().lower()

        # 1. Implicit Thermal & Climate
        res_climate = self.evaluate_implicit_climate(lower, room_state, active_mode)
        if res_climate:
            return res_climate

        # 2. Wellbeing & Fatigue Respite
        res_wellbeing = self.evaluate_wellbeing_respite(lower, active_mode)
        if res_wellbeing:
            return res_wellbeing

        # 3. Contextual Routine Music
        res_music = self.evaluate_contextual_music(lower, active_mode, current_time)
        if res_music:
            return res_music

        # 4. Career & Project Mentorship
        res_career = self.evaluate_career_mentorship(lower, active_goal)
        if res_career:
            return res_career

        return None
