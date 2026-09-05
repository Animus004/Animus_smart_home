"""
Follow-Up Question Engine for Animus Personal Agent.
Manages conversational follow-up turns to systematically reduce intent uncertainty.
Strict Invariant: Asks only one concise question at a time and never asks for information
that can be determined from RoomState.
"""

from __future__ import annotations
import time
import logging
from typing import Any, Dict, Optional
from agent.models import ResolvedIntent, UserProfile, IntentCategory
from agent.context_buffer import ConversationContextBuffer

logger = logging.getLogger("music_daemon.agent.followup_engine")


class FollowUpEngine:
    """
    Manages interactive uncertainty-reduction follow-up sessions.
    """

    def __init__(
        self,
        user_profile: UserProfile,
        context_buffer: Optional[ConversationContextBuffer] = None
    ):
        self.user_profile = user_profile
        self.context_buffer = context_buffer
        self._pending_context: Optional[Dict[str, Any]] = None
        self._last_followup_time: float = 0.0
        self._last_followup_intent: Optional[str] = None
        self._last_followup_question: Optional[str] = None

    @property
    def has_pending_followup(self) -> bool:
        return self._pending_context is not None

    def set_pending_followup(self, context_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Explicitly sets a pending proactive or contextual follow-up expectation."""
        self._pending_context = {
            "type": context_type,
            "created_at": time.time(),
            "metadata": metadata or {}
        }
        logger.info(f"[FOLLOWUP_ENGINE] Pending follow-up context set: {context_type}")

    def create_followup_for_intent(self, intent: ResolvedIntent) -> str:
        """
        Constructs a tailored follow-up question for an ambiguous or partially resolved intent.
        Includes single-flight deduplication: prevents duplicate questions within 3.0s.
        """
        now = time.time()
        if (self._last_followup_intent == intent.primary_intent and 
            (now - self._last_followup_time) < 3.0 and 
            self._last_followup_question):
            logger.info(f"[FOLLOWUP_ENGINE_DEDUP] Suppressing duplicate follow-up for {intent.primary_intent} within debounce window.")
            return self._last_followup_question

        addr = self.user_profile.identity.preferred_address

        question = f"Could you clarify what you'd like me to do, {addr}?"

        if intent.primary_intent in ("RELAXATION_INTENT", "USER_MOOD_STATEMENT"):
            question = f"Want some music, a movie, or just a quiet room, {addr}?"
            self._pending_context = {
                "type": "RELAXATION_DISAMBIGUATION",
                "original_intent": intent.model_dump()
            }
            if self.context_buffer:
                self.context_buffer.start_thread("RELAXATION_FLOW", original_intent=intent)
            self._last_followup_time = now
            self._last_followup_intent = intent.primary_intent
            self._last_followup_question = question
            return question


        elif intent.primary_intent == "START_CINEMA_ENTERTAINMENT":
            # Preferred streaming providers from user profile
            services = ", ".join([s.replace("_", " ").title() for s in self.user_profile.entertainment.preferred_streaming_services[:3]])
            question = f"Sure {addr} — {services}, or YouTube?"
            self._pending_context = {
                "type": "STREAMING_PROVIDER_SELECTION",
                "original_intent": intent.model_dump()
            }
            if self.context_buffer:
                self.context_buffer.start_thread("CINEMA_SETUP", original_intent=intent, missing_parameters=["streaming_provider"])

        elif intent.primary_intent == "ADJUST_VOLUME_AMBIGUOUS":
            question = f"Sure {addr} — are you listening on the Fire TV or the PC?"
            self._pending_context = {
                "type": "AUDIO_PRODUCER_DISAMBIGUATION",
                "original_intent": intent.model_dump()
            }

        elif intent.followup_question:
            question = intent.followup_question
            self._pending_context = {
                "type": "CUSTOM_FOLLOWUP",
                "original_intent": intent.model_dump()
            }

        else:
            # Fallback clarification
            question = f"Could you clarify what you'd like me to do, {addr}?"

        self._last_followup_time = now
        self._last_followup_intent = intent.primary_intent
        self._last_followup_question = question
        return question

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

        # 0. Proactive Work Fatigue & Wrap-Up Follow-up ("Dim lights and play soothing track")
        if context_type in ("PROACTIVE_WORK_FATIGUE_TRANSITION", "PROACTIVE_WORK_WRAPUP", "PROACTIVE_FATIGUE"):
            self._pending_context = None

            # 0a. Check for partial modifier requests first
            if any(lo in lower for lo in ["just light", "just the light", "lights only", "only lights", "no music", "not music", "without music", "just dim"]):
                return {
                    "resolved": True,
                    "request": "Dim the lights to relax mode",
                    "intent": "DIM_LIGHTS_ONLY"
                }
            if any(mo in lower for mo in ["just music", "just song", "music only", "only music", "leave lights", "keep lights", "no lights", "without dimming"]):
                return {
                    "resolved": True,
                    "request": "Play soothing music on soundbar",
                    "intent": "PLAY_RELAXING_MUSIC"
                }

            # 0b. Check for snooze / postponement
            if any(sn in lower for sn in ["not yet", "later", "give me", "more minutes", "still working", "10 min", "15 min", "20 min", "wait", "working"]):
                return {
                    "resolved": True,
                    "request": "Snooze work fatigue prompt",
                    "intent": "SNOOZE_WORK_FATIGUE"
                }

            # 0c. Check for standalone negative / rejection
            if any(neg in lower for neg in ["nah", "don't", "dont", "never mind", "cancel", "leave it", "leave it off", "stop"]) or lower in ["no", "no thanks", "no don't", "no dont"]:
                return {
                    "resolved": True,
                    "request": "Cancel fatigue relaxation prompt",
                    "intent": "REJECT_PROACTIVE_SUGGESTION"
                }

            # 0d. Check for affirmative responses
            if any(aff in lower for aff in ["yes", "yeah", "sure", "please", "yep", "do it", "go ahead", "dim", "soothing", "relax", "music", "play", "okay", "ok"]):
                return {
                    "resolved": True,
                    "request": "Dim lights to relax mode and play soothing track",
                    "intent": "DIM_LIGHTS_AND_PLAY_SOOTHING_MEDIA"
                }

            # Unrecognized response -> fall through to regular processing
            return {"resolved": False, "request": user_response}

        # 0b. Proactive Morning Briefing Follow-up ("Music" vs "Print" vs "Both" vs "No")
        if context_type == "PROACTIVE_MORNING_BRIEFING":
            self._pending_context = None
            if any(neg in lower for neg in ["no", "nah", "don't", "dont", "not now", "later", "never mind", "cancel"]):
                return {
                    "resolved": True,
                    "request": "Decline morning briefing action",
                    "intent": "DECLINE_MORNING_ACTION"
                }
            if any(p in lower for p in ["print", "paper", "sheet", "checklist", "plan", "sql"]):
                if any(m in lower for m in ["both", "and music", "music too", "with music"]):
                    return {
                        "resolved": True,
                        "request": "Print daily study plan on HP Ink Tank 310 and start morning focus playlist",
                        "intent": "MORNING_PRINT_AND_MUSIC"
                    }
                return {
                    "resolved": True,
                    "request": "Print daily study plan on HP Ink Tank 310",
                    "intent": "PRINT_MORNING_PLAN"
                }
            if any(m in lower for m in ["music", "song", "playlist", "focus"]):
                return {
                    "resolved": True,
                    "request": "Start morning focus playlist",
                    "intent": "START_MORNING_MUSIC"
                }
            if any(aff in lower for aff in ["yes", "yeah", "sure", "please", "yep", "do it", "go ahead", "okay", "ok"]):
                return {
                    "resolved": True,
                    "request": "Start morning focus playlist",
                    "intent": "START_MORNING_MUSIC"
                }
            return {"resolved": False, "request": user_response}

        # 0c. Proactive Evening Debrief Follow-up ("Print" vs "Guitar" vs "Both" vs "No")
        if context_type == "PROACTIVE_EVENING_DEBRIEF":
            self._pending_context = None
            if any(neg in lower for neg in ["no", "nah", "don't", "dont", "not now", "later", "never mind", "cancel"]):
                return {
                    "resolved": True,
                    "request": "Decline evening debrief action",
                    "intent": "DECLINE_EVENING_ACTION"
                }
            if any(p in lower for p in ["print", "paper", "sheet", "checklist", "tomorrow"]):
                if any(g in lower for g in ["both", "and guitar", "guitar too", "with guitar"]):
                    return {
                        "resolved": True,
                        "request": "Print tomorrow's checklist on HP Ink Tank 310 and cue guitar practice",
                        "intent": "EVENING_PRINT_AND_GUITAR"
                    }
                return {
                    "resolved": True,
                    "request": "Print tomorrow's checklist on HP Ink Tank 310",
                    "intent": "PRINT_EVENING_CHECKLIST"
                }
            if any(g in lower for g in ["guitar", "practice", "play"]):
                return {
                    "resolved": True,
                    "request": "Set room to guitar practice mode",
                    "intent": "START_GUITAR_PRACTICE"
                }
            if any(aff in lower for aff in ["yes", "yeah", "sure", "please", "yep", "do it", "go ahead", "okay", "ok"]):
                return {
                    "resolved": True,
                    "request": "Set room to guitar practice mode and print tomorrow's checklist",
                    "intent": "EVENING_PRINT_AND_GUITAR"
                }
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
            elif any(w in lower for w in ["music", "song", "tune", "first", "1st", "option 1", "number 1", "first one", "lofi", "lo-fi", "chill"]):
                if "quiet" not in lower:
                    return {
                        "resolved": True,
                        "request": "Play relaxing music on soundbar",
                        "intent": "PLAY_RELAXING_MUSIC"
                    }
            if any(m in lower for m in ["movie", "watch", "cinema", "film", "second", "2nd", "option 2", "number 2", "second one"]):
                return {
                    "resolved": True,
                    "request": "Let's watch something.",
                    "intent": "START_CINEMA_ENTERTAINMENT"
                }
            elif any(q in lower for q in ["quiet", "silence", "just quiet", "quiet room", "third", "3rd", "option 3", "number 3", "third one"]):
                return {
                    "resolved": True,
                    "request": "Set room to quiet comfortable mode",
                    "intent": "QUIET_ROOM_COMFORT"
                }
            else:
                # Unrelated statement -> supersede follow-up safely
                return {"resolved": False, "request": user_response}

        # 2. Streaming Provider Selection ("Netflix", "Prime", "Apple TV", "YouTube", or ordinals)
        if context_type == "STREAMING_PROVIDER_SELECTION":
            self._pending_context = None
            prefs = self.user_profile.entertainment.preferred_streaming_services
            # Ordinals
            if any(o in lower for o in ["first", "1st", "number 1", "option 1", "the first one"]) and len(prefs) >= 1:
                prov = prefs[0]
                return {
                    "resolved": True,
                    "request": f"Put on {prov.title()}",
                    "intent": f"LAUNCH_{prov.upper().replace(' ', '_')}"
                }
            elif any(o in lower for o in ["second", "2nd", "number 2", "option 2", "the second one"]) and len(prefs) >= 2:
                prov = prefs[1]
                return {
                    "resolved": True,
                    "request": f"Put on {prov.title()}",
                    "intent": f"LAUNCH_{prov.upper().replace(' ', '_')}"
                }
            elif any(o in lower for o in ["third", "3rd", "number 3", "option 3", "the third one"]) and len(prefs) >= 3:
                prov = prefs[2]
                return {
                    "resolved": True,
                    "request": f"Put on {prov.title()}",
                    "intent": f"LAUNCH_{prov.upper().replace(' ', '_')}"
                }

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
            if any(tv_kw in lower for tv_kw in ["fire", "tv", "television", "firetv", "fire stick", "fire tv", "first", "1st", "option 1", "the first one"]):
                return {
                    "resolved": True,
                    "request": "Turn down Fire TV volume",
                    "intent": "FIRE_TV_VOLUME_DOWN"
                }
            elif any(pc_kw in lower for pc_kw in ["pc", "computer", "laptop", "pc audio", "desktop audio", "windows", "second", "2nd", "option 2", "the second one"]):
                return {
                    "resolved": True,
                    "request": "Turn down PC volume",
                    "intent": "PC_SET_VOLUME"
                }
            else:
                # Safety Invariant: Do NOT assume a default device if utterance is unrelated (e.g. location update)
                logger.info(f"[AUDIO_FOLLOWUP_SUPERSEDED] Input '{user_response}' does not specify an audio producer; clearing follow-up.")
                return {"resolved": False, "request": user_response}

        # 4. Music Track Selection Follow-up ("What would you like me to play?")
        orig_intent = self._pending_context.get("original_intent") or {}
        if (
            orig_intent.get("primary_intent") == "PLAY_TRACK"
            or "play" in self._pending_context.get("type", "").lower()
            or "play" in str(orig_intent.get("followup_question", "")).lower()
            or "title" in orig_intent.get("missing_parameters", [])
        ):
            self._pending_context = None
            clean_title = user_response.strip(" .?!\"'")
            if clean_title:
                logger.info(f"[PLAY_TRACK_FOLLOWUP_RESOLVED] Bound user response '{clean_title}' to 'play {clean_title}'")
                return {
                    "resolved": True,
                    "request": f"play {clean_title}",
                    "intent": "PLAY_TRACK",
                    "extracted_parameters": {"title": clean_title}
                }

        # Default clearing
        self._pending_context = None
        return {"resolved": False, "request": user_response}

    def clear_pending_followup(self) -> None:
        """Clears any active follow-up state."""
        self._pending_context = None

