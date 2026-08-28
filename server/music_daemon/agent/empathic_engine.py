"""
================================================================================
ANIMUS SMART ROOM — MULTI-DOMAIN EMPATHIC REASONING ENGINE
================================================================================
Authoritative human-state problem solver for Animus Smart Room.
Maps high-level human physical, emotional, and situational statements into
multi-device coordinated room actions (Climate + Cinema + Audio + PC + Timers).
================================================================================
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.agent.empathic_engine")


class EmpathicActionPlan(BaseModel):
    """Structured multi-device plan produced by empathic reasoning."""
    scenario: str
    empathy_speech: str
    ac_action: Optional[Dict[str, Any]] = None
    projector_action: Optional[Dict[str, Any]] = None
    fire_tv_action: Optional[Dict[str, Any]] = None
    audio_action: Optional[Dict[str, Any]] = None
    pc_action: Optional[Dict[str, Any]] = None
    scheduled_followup_minutes: Optional[int] = None
    followup_question: Optional[str] = None


class EmpathicReasoningEngine:
    """
    Evaluates natural human problem statements and generates holistic room configurations.
    """

    def __init__(self):
        pass

    def evaluate_empathic_intent(self, text: str, user_name: str = "buddy") -> Optional[EmpathicActionPlan]:
        """
        Evaluates utterance for high-level human problem states.
        Returns EmpathicActionPlan if matched, else None.
        """
        lower = text.lower().strip()

        # 1. Headache / Migraine / Sick / Unwell
        if re.search(r'\b(?:headache|migraine|head hurts|sick|unwell|fever|not feeling well|dizzy)\b', lower):
            return EmpathicActionPlan(
                scenario="HEADACHE_RELIEF",
                empathy_speech=f"I'm sorry you're not feeling well, {user_name}. I've dimmed the screens, set the AC to a quiet 25 degrees, and started gentle rain sounds. Rest up.",
                ac_action={"power": True, "mode": "COOL", "temp": 25, "fan": "LOW"},
                projector_action={"power": False, "action": "sleep"},
                fire_tv_action={"power": False, "action": "sleep"},
                audio_action={"action": "play_ambient", "query": "gentle rain sounds", "volume": 15},
                pc_action={"action": "dim_display"},
                scheduled_followup_minutes=45,
                followup_question="Checking in, Sayan. Is your headache feeling any better?"
            )

        # 2. Leaving / Going to Work / Heading Out
        if re.search(r'\b(?:leaving|heading out|going to work|going out|bye sonia|goodbye sonia|leaving the room|off to work)\b', lower):
            return EmpathicActionPlan(
                scenario="DEPARTURE_ALL_OFF",
                empathy_speech=f"Have a wonderful day, {user_name}! I have secured the room, powered down the projector, and set the AC to standby.",
                ac_action={"power": False, "mode": "AUTO"},
                projector_action={"power": False, "action": "power_off"},
                fire_tv_action={"power": False, "action": "sleep"},
                audio_action={"action": "stop"},
                pc_action={"action": "lock"}
            )

        # 3. Chill Vibe / Relax Mode / Unwind
        if re.search(r'\b(?:chill vibe|relax mode|set a vibe|unwind|chill out|relaxing vibe|cozy mode)\b', lower):
            return EmpathicActionPlan(
                scenario="CHILL_VIBE",
                empathy_speech=f"Setting a cozy vibe for you, {user_name}. AC set to a comfortable 23 degrees with smooth lofi beats on the soundbar.",
                ac_action={"power": True, "mode": "COOL", "temp": 23, "fan": "AUTO"},
                audio_action={"action": "play_music", "query": "lofi hip hop chill beats", "volume": 25}
            )

        # 4. Focus Mode / Deep Study / Work Time
        if re.search(r'\b(?:focus mode|study time|study mode|deep work|coding mode|time to work|let me study)\b', lower):
            return EmpathicActionPlan(
                scenario="DEEP_FOCUS",
                empathy_speech=f"Focus mode activated, {user_name}. Cooling the room to a crisp 24 degrees and streaming deep focus alpha waves.",
                ac_action={"power": True, "mode": "COOL", "temp": 24, "fan": "AUTO"},
                audio_action={"action": "play_music", "query": "deep focus alpha waves study music", "volume": 20},
                projector_action={"power": False, "action": "sleep"}
            )

        # 5. Party Mode / Hype Vibe
        if re.search(r'\b(?:party mode|hype mode|turn it up|party time|house party)\b', lower):
            return EmpathicActionPlan(
                scenario="PARTY_HYPE",
                empathy_speech=f"Party mode engaged, {user_name}! Turning up the soundbar and boosting AC airflow for the room.",
                ac_action={"power": True, "mode": "COOL", "temp": 21, "fan": "HIGH"},
                audio_action={"action": "play_music", "query": "upbeat party dance hits", "volume": 50}
            )

        return None


# Global singleton instance
_global_empathic_engine: Optional[EmpathicReasoningEngine] = None


def get_empathic_engine() -> EmpathicReasoningEngine:
    """Returns or initializes the global EmpathicReasoningEngine singleton."""
    global _global_empathic_engine
    if _global_empathic_engine is None:
        _global_empathic_engine = EmpathicReasoningEngine()
    return _global_empathic_engine
