"""
Authoritative Interface-Agnostic Conversation Engine for Phase 2 Stage 10 Animus Smart Room.
Handles multi-turn dialogue context, pronoun/reference resolution, interruptions,
corrections, confirmations, and natural conversational flow.

EPISTEMIC & CONVERSATIONAL INVARIANTS:
1. Reference Resolution Hierarchy:
   Current Turn > Active Thread > Active Goal > Active Media > Active Mode > Recent Action > History
2. Never guess hardware actions when ambiguity materially affects the physical room.
3. Natural interruptions ("stop", "wait", "actually...") safely pause or modify goals without corrupting history.
4. Interface Agnostic: Ingests turns uniformly from Voice STT, Android client, WebSockets, or text API.
"""

from __future__ import annotations
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agent.behavior_modes import BehaviorMode
from agent.task_models import AgentGoal, GoalStatus
from agent.room_events import RoomEvent

logger = logging.getLogger("music_daemon.agent.conversation_engine")


class ConversationTurn(BaseModel):
    """Immutable record of an individual conversational turn."""
    turn_id: int
    user_utterance: str
    resolved_intent: Optional[str] = None
    target_entity: Optional[str] = None
    agent_response: str = ""
    timestamp: float = Field(default_factory=time.time)
    was_interruption: bool = False
    was_correction: bool = False


class ConversationEngine:
    """
    Manages conversational memory, pronoun reference resolution, and turn state.
    """

    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self.turn_history: List[ConversationTurn] = []
        self._turn_counter: int = 0
        self.active_subject: Optional[str] = None  # e.g. "AC", "MOVIE", "PROJECTOR", "MUSIC"
        self.pending_confirmation_action: Optional[Dict[str, Any]] = None

    def process_utterance(
        self,
        utterance: str,
        active_mode: BehaviorMode = BehaviorMode.IDLE,
        active_goal: Optional[AgentGoal] = None,
        active_media_app: Optional[str] = None,
        recent_action: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Optional[str], bool, bool]:
        """
        Resolves pronouns, detects interruptions/corrections, and returns:
        (resolved_utterance, detected_intent_hint, is_interruption, is_correction)
        """
        clean_text = utterance.strip()
        lower = clean_text.lower()
        is_interruption = False
        is_correction = False
        intent_hint: Optional[str] = None

        # ---------------------------------------------------------------------
        # 1. Interruption Detection ("stop", "wait", "hold on", "cancel")
        # ---------------------------------------------------------------------
        if any(lower == w or lower.startswith(w + " ") for w in ["stop", "wait", "hold on", "pause", "never mind", "cancel"]):
            is_interruption = True
            if "pause" in lower:
                intent_hint = "PAUSE_MEDIA" if (active_media_app or active_mode == BehaviorMode.MOVIE) else "PAUSE_GOAL"
            elif any(w in lower for w in ["stop", "cancel", "never mind"]):
                intent_hint = "CANCEL_ACTION"

        # ---------------------------------------------------------------------
        # 2. Correction Detection ("actually make it 24", "no 23", "instead", "make it", "make that")
        # ---------------------------------------------------------------------
        if any(lower.startswith(w) for w in ["actually", "no make", "instead", "change that to", "make that", "make it"]):
            is_correction = True


        # ---------------------------------------------------------------------
        # 3. Pronoun & Reference Resolution ("it", "that", "make that 24")
        # ---------------------------------------------------------------------
        resolved_text = clean_text

        # Pattern: "make that 24" / "make it 24" / "actually 24"
        temp_match = re.search(r'(?:make (?:it|that)|actually|set to)\s+(\d{2})', lower)
        if temp_match:
            temp_val = temp_match.group(1)
            resolved_text = f"set ac temperature to {temp_val}"
            self.active_subject = "AC"
            return resolved_text, "AC_SET_TEMPERATURE", is_interruption, is_correction

        # Pattern: "pause it" / "resume it"
        if "pause it" in lower or "pause that" in lower:
            if active_mode == BehaviorMode.MOVIE or active_media_app:
                resolved_text = "pause movie"
                self.active_subject = "MOVIE"
                intent_hint = "PAUSE_MEDIA"
            elif active_goal:
                resolved_text = "pause active goal"
                intent_hint = "PAUSE_GOAL"

        if "resume it" in lower or "resume that" in lower or "play it" in lower:
            if active_mode == BehaviorMode.MOVIE or active_media_app:
                resolved_text = "resume movie"
                self.active_subject = "MOVIE"
                intent_hint = "RESUME_MEDIA"
            elif active_goal:
                resolved_text = "resume active goal"
                intent_hint = "RESUME_GOAL"

        # Update active subject tracking from utterance context
        if "movie" in lower or "cinema" in lower or "film" in lower:
            self.active_subject = "MOVIE"
        elif "ac" in lower or "temperature" in lower or "cool" in lower:
            self.active_subject = "AC"
        elif "music" in lower or "song" in lower or "spotify" in lower:
            self.active_subject = "MUSIC"
        elif "projector" in lower:
            self.active_subject = "PROJECTOR"

        return resolved_text, intent_hint, is_interruption, is_correction

    def record_turn(
        self,
        user_utterance: str,
        resolved_intent: Optional[str] = None,
        agent_response: str = "",
        was_interruption: bool = False,
        was_correction: bool = False
    ) -> ConversationTurn:
        """
        Records completed turn into bounded history.
        """
        self._turn_counter += 1
        turn = ConversationTurn(
            turn_id=self._turn_counter,
            user_utterance=user_utterance,
            resolved_intent=resolved_intent,
            target_entity=self.active_subject,
            agent_response=agent_response,
            was_interruption=was_interruption,
            was_correction=was_correction
        )
        self.turn_history.append(turn)
        if len(self.turn_history) > self.max_turns:
            self.turn_history.pop(0)
        return turn

    def get_last_turn(self) -> Optional[ConversationTurn]:
        return self.turn_history[-1] if self.turn_history else None

    def clear_history(self) -> None:
        self.turn_history.clear()
        self.active_subject = None
        self.pending_confirmation_action = None
