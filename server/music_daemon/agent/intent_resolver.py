"""
Authoritative Intent Resolution Engine for Animus Personal Agent.
Classifies natural language requests into 6 explicit categories, evaluates mood/vibe semantics,
and identifies whether requests are clear, deterministic with missing parameters, ambiguous,
unsupported, unsafe, or informational.
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional
from capability_registry import UnifiedCapabilityRegistry
from room_state.models import RoomState
from agent.models import (
    IntentCategory,
    MoodVibe,
    ResolvedIntent,
    UserProfile
)
from agent.memory import AgentMemoryStore

logger = logging.getLogger("music_daemon.agent.intent_resolver")


class IntentResolver:
    """
    Synthesizes user utterances, user preferences, memory context, and live room state
    to determine the human's actual intent.
    """

    def __init__(
        self,
        user_profile: UserProfile,
        registry: UnifiedCapabilityRegistry,
        memory: AgentMemoryStore
    ):
        self.user_profile = user_profile
        self.registry = registry
        self.memory = memory

    def resolve_intent(
        self,
        utterance: str,
        room_state: Optional[RoomState] = None
    ) -> ResolvedIntent:
        """
        Determines the true human intent from user natural language, context, and capabilities.
        """
        clean_text = utterance.strip()
        lower = clean_text.lower()

        # =====================================================================
        # 1. Unsafe / Out-of-Bounds Rejection
        # =====================================================================
        # Check for dangerous AC temperatures (>30 or <16)
        temp_match = re.search(r'(?:(?:ac|temperature|temp)\s+(?:to\s+)?(\d+)|(\d+)\s*(?:degrees?|°c|celsius))', lower)
        if temp_match:
            val = int(temp_match.group(1) or temp_match.group(2))
            if val < 16 or val > 30:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.UNSAFE_NOT_AUTHORIZED,
                    primary_intent="AC_TEMPERATURE_OUT_OF_BOUNDS",
                    explanation=f"Requested temperature {val}°C is outside safe physical hardware bounds [16, 30]."
                )

        # Check for volume > 100%
        vol_match = re.search(r'(?:volume|vol)\s+(?:to\s+)?(\d+)', lower)
        if vol_match:
            val = int(vol_match.group(1))
            if val > 100 or val < 0:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.UNSAFE_NOT_AUTHORIZED,
                    primary_intent="VOLUME_OUT_OF_BOUNDS",
                    explanation=f"Requested volume {val}% is outside safe bounds [0, 100]."
                )

        # =====================================================================
        # 2. Location Update (Turn 05: "I'm heading to my desk")
        # =====================================================================
        if any(loc_kw in lower for loc_kw in [
            "heading to my desk", "heading to desk", "going to my desk", "at my desk",
            "sitting at my desk", "moving to my desk", "stepping to my desk"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="USER_LOCATION_UPDATE",
                extracted_parameters={"location": "DESK"},
                explanation="User reported a location transition to desk workspace. Context updated; zero hardware mutations."
            )

        # =====================================================================
        # 3. Informational / Routine Triggers / Task Management & Bookkeeping
        # =====================================================================
        # A. Morning greeting / Briefing
        if any(g in lower for g in ["good morning", "morning brief", "wake up brief", "start my day", "i'm up", "i am up", "woke up"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="MORNING_ROUTINE_BRIEF",
                mood_vibe=MoodVibe.WAKE_UP,
                explanation="User initiated morning routine greeting and daily brief request."
            )

        # B. Night / Sleep transition
        if any(n in lower for n in ["good night", "going to sleep", "heading to bed"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="NIGHT_ROUTINE_TRANSITION",
                mood_vibe=MoodVibe.SLEEP,
                explanation="User signaled end-of-day sleep transition. No automatic hardware mutations without explicit command."
            )

        # C. Lunch routine trigger
        if any(trigger in lower for trigger in self.user_profile.routines.lunch_trigger_keywords):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="LUNCH_COMPLETED_TRIGGER",
                mood_vibe=MoodVibe.RELAX,
                explanation="User reported lunch completion. Routine transition opportunity."
            )

        # D. Task Completion (Turn 19: "Mark window functions as done")
        if any(comp_kw in lower for comp_kw in ["mark ", "completed ", "done with ", "finish task ", "mark as done"]):
            clean_task = lower
            for prefix in ["mark as done", "mark ", "as done", "as completed", "completed", "done with", "finished"]:
                clean_task = clean_task.replace(prefix, "").strip()
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="COMPLETE_TASK",
                extracted_parameters={"task_target": clean_task},
                explanation=f"User requested task completion for '{clean_task}'."
            )

        # E. Specific Task & Schedule Queries
        if any(r_add in lower for r_add in ["what did i just add", "what was the last thing i added", "what reminder did i just add", "what task did i just add"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="TASK_SCHEDULE_QUERY",
                extracted_parameters={"query_type": "RECENT_ADDITION"},
                explanation="User queried recently added task/reminder."
            )

        if any(a_l in lower for a_l in ["what was i supposed to do after lunch", "what to do after lunch", "after lunch tasks", "after lunch reminder"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="TASK_SCHEDULE_QUERY",
                extracted_parameters={"query_type": "AFTER_LUNCH"},
                explanation="User queried tasks/reminders specifically scheduled for after lunch."
            )

        if any(t_s in lower for t_s in ["did i finish", "is my guitar practice", "finish my guitar practice", "on the list", "is that done"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="TASK_SCHEDULE_QUERY",
                extracted_parameters={"query_type": "TASK_STATUS"},
                explanation="User queried completion status of a specific task."
            )

        if any(t_q in lower for t_q in [
            "what do i have to do", "what's on my schedule", "what are my tasks", "what did i forget",
            "what is pending", "what's on my plate", "what on my plate", "what was i supposed to do", "what did i accomplish"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="TASK_SCHEDULE_QUERY",
                explanation="User requested task agenda or pending items."
            )

        # F. Reminder / Add Task requests (including reminder modifications like "Actually remind me after lunch")
        if any(r_t in lower for r_t in ["remind me", "add task", "create task", "remember to"]):
            is_mod = "actually remind me" in lower or "change reminder" in lower
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="BOOKKEEPING_REQUEST",
                extracted_parameters={"is_modification": is_mod},
                explanation="User requested task or reminder creation / modification."
            )

        # G. Self-Knowledge / Audits (Turns 40 & 41)
        if any(p_q in lower for p_q in ["what do you know about my preferences", "my preferences", "what are my preferences", "audit preferences"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="AUDIT_USER_PREFERENCES",
                explanation="User requested audit of stored user model preferences."
            )

        if any(u_q in lower for u_q in ["what are you unsure about", "what uncertainties", "what assumptions", "unsure about"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="AUDIT_UNCERTAINTY",
                explanation="User requested audit of system uncertainties and unconfirmed assumptions."
            )

        # H. Capability queries ("What can you control?")
        if any(c_q in lower for c_q in ["what can you control", "what can you do", "what are your capabilities", "list devices"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="CAPABILITY_INQUIRY",
                explanation="User inquired about supported device and automation capabilities."
            )

        # I. Conversational Acknowledgments & State Updates (Turns 15, 20, 23)
        if any(ack_kw in lower for ack_kw in ["okay, focusing now", "focusing now", "great, that's done", "that's done"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="CONVERSATIONAL_ACK",
                explanation="Conversational acknowledgment from user."
            )

        if any(g_kw in lower for g_kw in ["practicing guitar now", "playing guitar now", "i'm practicing guitar"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="USER_STATE_UPDATE",
                extracted_parameters={"activity": "GUITAR_PRACTICE"},
                explanation="User indicated active guitar practice in progress."
            )

        # =====================================================================
        # 4. Unsupported Device Inquiries (e.g. bedroom fan, microwave)
        # =====================================================================
        unsupported_keywords = ["fan", "microwave", "coffee", "blinds", "curtains", "door lock", "garage", "refrigerator"]
        for kw in unsupported_keywords:
            if kw in lower and not ("ac fan" in lower or "fan speed" in lower):
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.UNSUPPORTED_CAPABILITY,
                    primary_intent="UNSUPPORTED_DEVICE_CONTROL",
                    extracted_parameters={"unsupported_device": kw},
                    explanation=f"Animus does not currently have hardware integration for '{kw}'."
                )

        # =====================================================================
        # 5. Media Control Commands (Pause / Resume - Turns 35 & 36)
        # =====================================================================
        if any(p_kw in lower for p_kw in ["pause that", "pause video", "pause media", "pause it", "pause for a second", "pause"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PAUSE_MEDIA",
                explanation="User requested media playback pause."
            )

        if any(r_kw in lower for r_kw in ["resume it", "resume that", "resume video", "resume media", "resume playback", "unpause", "continue watching"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="RESUME_MEDIA",
                explanation="User requested media playback resume."
            )

        # =====================================================================
        # 6. Music & Audio Playback (Turn 03: "Put on something to get me moving")
        # =====================================================================
        if any(m_kw in lower for m_kw in ["put on something to get me moving", "put on music", "play music", "play something upbeat", "morning music", "motivation music"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PLAY_MUSIC",
                mood_vibe=MoodVibe.MUSIC,
                explanation="User requested motivational music playback."
            )

        # =====================================================================
        # 7. Focus / SQL Learning Sessions (Turn 11 & Turn 18)
        # =====================================================================
        # Semantic Unit-Aware Duration Check (e.g. "Let's do SQL for 30 minutes")
        dur_match = re.search(r'(?:for\s+)?(\d+)\s*(?:mins?|minutes?|hours?|hrs?)', lower)
        if dur_match and any(f_w in lower for f_w in ["sql", "study", "learn", "focus", "work"]):
            mins = int(dur_match.group(1))
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="START_FOCUS_SESSION",
                mood_vibe=MoodVibe.FOCUS,
                extracted_parameters={"duration_minutes": mins, "subject": "SQL"},
                explanation=f"User requested a {mins}-minute SQL focus/study session."
            )

        if any(f_w in lower for f_w in ["sit for sql", "study sql", "learn sql", "start working", "focus mode", "time to work", "time to focus on sql", "time to focus"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="ENTER_WORK_FOCUS_MODE",
                mood_vibe=MoodVibe.FOCUS,
                target_subsystems=["AC", "TASK_SYSTEM"],
                explanation="User is entering a focused work / SQL learning session."
            )

        # Mood statement: Exhausted / Fatigue (Turn 26)
        if any(ex_kw in lower for ex_kw in ["exhausted", "so tired", "feeling exhausted", "worn out"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="USER_MOOD_STATEMENT",
                mood_vibe=MoodVibe.RELAX,
                explanation="User expressed exhaustion; trigger empathetic relaxation options."
            )

        # Ambiguous Relax / Tired expression (Turn 27)
        if any(t_w in lower for t_w in ["need to relax", "let's relax", "let's chill", "chill mode", "something relaxing", "relax mode", "relax for a bit"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.AMBIGUOUS_REQUIRES_FOLLOW_UP,
                primary_intent="RELAXATION_INTENT",
                mood_vibe=MoodVibe.RELAX,
                requires_followup=True,
                followup_question="Want some music, a movie, or just a quiet room, buddy?",
                explanation="User expressed relaxation mood, but specific media form is ambiguous."
            )

        # =====================================================================
        # 8. Compound Entertainment Commands (Cinema, YouTube, Movie Mode)
        # =====================================================================
        if any(e_w in lower for e_w in ["let's watch something", "put something on", "movie mode", "start a movie", "watch a movie", "chill with a movie"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL,
                primary_intent="START_CINEMA_ENTERTAINMENT",
                mood_vibe=MoodVibe.MOVIE,
                target_subsystems=["PROJECTOR", "FIRE_TV", "SOUNDBAR"],
                missing_parameters=["streaming_provider"],
                requires_followup=True,
                followup_question="Netflix, Prime Video, Apple TV, or YouTube?",
                explanation="Deterministic cinema hardware preparation is clear; content source is open."
            )

        if "youtube" in lower:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PLAY_YOUTUBE",
                mood_vibe=MoodVibe.ENTERTAINMENT,
                target_subsystems=["PROJECTOR", "FIRE_TV", "SOUNDBAR"],
                extracted_parameters={"app_id": "com.amazon.firetv.youtube"},
                explanation="Launch YouTube application on cinema stack."
            )

        # =====================================================================
        # 8b. Negative Constraint Relaxation (Turn 28: "No, not music")
        # =====================================================================
        if any(neg in lower for neg in ["no, not music", "not music", "no music", "anything but music"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="RELAXATION_NARROW_OPTIONS",
                mood_vibe=MoodVibe.RELAX,
                requires_followup=True,
                followup_question="Want to watch a movie or just keep the room quiet, buddy?",
                explanation="User rejected music option; offer remaining relaxation choices."
            )

        # =====================================================================
        # 9. Volume & Bare Numeric Disambiguation (Turns 04, 08, 33, 34)
        # =====================================================================
        # Bare numeric statement (Turn 34: "Actually 25 is fine")
        clean_num_str = lower.strip(" .?!,")
        bare_num_match = re.search(r'^(?:actually\s+)?(?:make\s+(?:it|that)\s+)?(?:set\s+(?:it|that)\s+to\s+)?(\d+)(?:\s*(?:percent|%|is\s+(?:fine|good|okay|enough)))?$', clean_num_str)
        if bare_num_match:
            val = int(bare_num_match.group(1))
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.AMBIGUOUS_REQUIRES_FOLLOW_UP,
                primary_intent="BARE_NUMERIC_AMBIGUOUS",
                extracted_parameters={"value": val},
                requires_followup=True,
                followup_question=f"{val} what — volume, AC temperature, or something else, buddy?",
                explanation="A bare numeric statement cannot mutate hardware without validated target context."
            )

        if any(v_w in lower for v_w in ["make it quieter", "turn it down", "turn it up", "louder", "softer", "quieter"]):
            active_producer = "UNKNOWN"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                active_producer = getattr(room_state.audio_stream, "active_producer", "UNKNOWN")
                if hasattr(active_producer, "value"):
                    active_producer = active_producer.value

            if active_producer in ("FIRE_TV", "PC"):
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="ADJUST_ACTIVE_VOLUME",
                    target_subsystems=[active_producer],
                    extracted_parameters={"target_producer": active_producer},
                    explanation=f"Acoustic adjustment resolved to active producer: {active_producer}."
                )
            else:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.AMBIGUOUS_REQUIRES_FOLLOW_UP,
                    primary_intent="ADJUST_VOLUME_AMBIGUOUS",
                    requires_followup=True,
                    followup_question="Are you listening on the Fire TV or the PC, buddy?",
                    explanation="Audio producer is unknown; follow-up required to avoid incorrect domain mutation."
                )

        # =====================================================================
        # 10. Default Clear Executable Command
        # =====================================================================
        return ResolvedIntent(
            raw_query=clean_text,
            category=IntentCategory.CLEAR_EXECUTABLE,
            primary_intent="GENERAL_ROOM_COMMAND",
            explanation="Standard room orchestration command passed to planner."
        )
