"""
Follow-Up Question Engine for Animus Personal Agent.
Manages conversational follow-up turns to systematically reduce intent uncertainty.
Strict Invariant: Asks only one concise question at a time and never asks for information
that can be determined from RoomState.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from agent.models import ResolvedIntent, UserProfile, IntentCategory

logger = logging.getLogger("music_daemon.agent.followup_engine")


class FollowUpEngine:
    """
    Manages interactive uncertainty-reduction follow-up sessions.
    """

    def __init__(self, user_profile: UserProfile):
        self.user_profile = user_profile
        self._pending_context: Optional[Dict[str, Any]] = None

    @property
    def has_pending_followup(self) -> bool:
        return self._pending_context is not None

    def create_followup_for_intent(self, intent: ResolvedIntent) -> str:
        """
        Constructs a tailored follow-up question for an ambiguous or partially resolved intent.
        """
        addr = self.user_profile.identity.preferred_address

        if intent.primary_intent == "RELAXATION_INTENT":
            question = f"Want some music, a movie, or just a quiet room, {addr}?"
            self._pending_context = {
                "type": "RELAXATION_DISAMBIGUATION",
                "original_intent": intent.model_dump()
            }
            return question

        if intent.primary_intent == "START_CINEMA_ENTERTAINMENT":
            # Preferred streaming providers from user profile
            services = ", ".join([s.replace("_", " ").title() for s in self.user_profile.entertainment.preferred_streaming_services[:3]])
            question = f"Sure {addr} — {services}, or YouTube?"
            self._pending_context = {
                "type": "STREAMING_PROVIDER_SELECTION",
                "original_intent": intent.model_dump()
            }
            return question

        if intent.primary_intent == "ADJUST_VOLUME_AMBIGUOUS":
            question = f"Sure {addr} — are you listening on the Fire TV or the PC?"
            self._pending_context = {
                "type": "AUDIO_PRODUCER_DISAMBIGUATION",
                "original_intent": intent.model_dump()
            }
            return question

        if intent.followup_question:
            self._pending_context = {
                "type": "CUSTOM_FOLLOWUP",
                "original_intent": intent.model_dump()
            }
            return intent.followup_question

        # Fallback clarification
        return f"Could you clarify what you'd like me to do, {addr}?"

    def resolve_followup_response(self, user_response: str) -> Dict[str, Any]:
        """
        Interprets the user's answer to a pending follow-up question and converts it into
        an executable resolved plan request.
        Strict Invariant: An unresolved clarification must NEVER cause an unrelated subsequent
        conversational/location statement to execute a physical action.
        """
        if not self._pending_context:
            return {"resolved": False, "request": user_response}

        context_type = self._pending_context.get("type")
        lower = user_response.strip().lower()

        # Check if the user is switching topics, giving a location update, or issuing a new command
        interrupt_triggers = [
            "remind me", "add task", "create task", "what do i", "what are my", "what's on", "what did i",
            "set ac", "turn on", "turn off", "wake", "good morning", "good night", "i had lunch", "i've had lunch",
            "just had lunch", "can you", "what can you", "sit for sql", "focus mode", "time to focus",
            "heading to", "going to", "at my desk", "practicing guitar", "mark ", "completed ", "done "
        ]
        if any(trigger in lower for trigger in interrupt_triggers):
            logger.info(f"[FOLLOWUP_INTERRUPTED] Pending follow-up superseded by new utterance: '{user_response}'")
            self._pending_context = None
            return {"resolved": False, "request": user_response}

        # 1. Relaxation follow-up answer ("Music" vs "Movie" vs "Quiet" vs Negative Constraint)
        if context_type in ("RELAXATION_DISAMBIGUATION", "RELAXATION_DISAMBIGUATION_NO_MUSIC"):
            # Handle negative constraints (e.g. "No, not music")
            if any(nc in lower for nc in ["not music", "no music", "no, not music", "anything but music", "no songs"]):
                self._pending_context = {
                    "type": "RELAXATION_DISAMBIGUATION_NO_MUSIC",
                    "original_intent": self._pending_context.get("original_intent")
                }
                return {
                    "resolved": True,
                    "request": "Narrow relaxation to movie or quiet room",
                    "intent": "RELAXATION_NARROW_OPTIONS",
                    "followup_question": "Understood, no music. Would you like a movie, or just a quiet room, buddy?"
                }

            self._pending_context = None
            if any(neg in lower for neg in ["no", "not", "neither", "don't", "dont", "never"]) and ("music" in lower or "song" in lower):
                return {
                    "resolved": True,
                    "request": "No, not music",
                    "intent": "RELAXATION_NARROW_OPTIONS"
                }
            elif "music" in lower or "song" in lower or "tune" in lower:
                return {
                    "resolved": True,
                    "request": "Play relaxing music on soundbar",
                    "intent": "PLAY_RELAXING_MUSIC"
                }
            elif any(m in lower for m in ["movie", "watch", "cinema", "film"]):
                return {
                    "resolved": True,
                    "request": "Let's watch something.",
                    "intent": "START_CINEMA_ENTERTAINMENT"
                }
            elif any(q in lower for q in ["quiet", "silence", "just quiet", "quiet room", "chill"]):
                return {
                    "resolved": True,
                    "request": "Set room to quiet comfortable mode",
                    "intent": "QUIET_ROOM_COMFORT"
                }
            else:
                # Unrelated statement -> supersede follow-up safely
                return {"resolved": False, "request": user_response}

        # 2. Streaming Provider Selection ("Netflix", "Prime", "Apple TV", "YouTube")
        if context_type == "STREAMING_PROVIDER_SELECTION":
            self._pending_context = None
            for prov in ["netflix", "apple tv", "prime video", "prime", "youtube", "hotstar", "smarttube", "vlc", "hulu", "disney"]:
                if prov in lower:
                    return {
                        "resolved": True,
                        "request": f"Put on {prov.title()}",
                        "intent": f"LAUNCH_{prov.upper().replace(' ', '_')}"
                    }
            # Not a recognized streaming provider -> treat as new request
            logger.info(f"[STREAMING_FOLLOWUP_SUPERSEDED] Input '{user_response}' not a provider; treating as new intent.")
            return {"resolved": False, "request": user_response}

        # 3. Audio producer volume selection ("Fire TV" vs "PC")
        if context_type == "AUDIO_PRODUCER_DISAMBIGUATION":
            self._pending_context = None
            if any(tv_kw in lower for tv_kw in ["fire", "tv", "television", "firetv", "fire stick", "fire tv"]):
                return {
                    "resolved": True,
                    "request": "Turn down Fire TV volume",
                    "intent": "FIRE_TV_VOLUME_DOWN"
                }
            elif any(pc_kw in lower for pc_kw in ["pc", "computer", "laptop", "pc audio", "desktop audio", "windows"]):
                return {
                    "resolved": True,
                    "request": "Turn down PC volume",
                    "intent": "PC_SET_VOLUME"
                }
            else:
                # Safety Invariant: Do NOT assume a default device if utterance is unrelated (e.g. location update)
                logger.info(f"[AUDIO_FOLLOWUP_SUPERSEDED] Input '{user_response}' does not specify an audio producer; clearing follow-up.")
                return {"resolved": False, "request": user_response}

        # Default clearing
        self._pending_context = None
        return {"resolved": False, "request": user_response}

    def clear_pending_followup(self) -> None:
        """Clears any active follow-up state."""
        self._pending_context = None

