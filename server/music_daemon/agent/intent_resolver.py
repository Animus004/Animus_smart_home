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
from agent.context_buffer import ConversationContextBuffer

logger = logging.getLogger("music_daemon.agent.intent_resolver")

WORD_TO_NUM = {
    "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "twenty one": "21", "twenty-one": "21", "twenty two": "22", "twenty-two": "22",
    "twenty three": "23", "twenty-three": "23", "twenty four": "24", "twenty-four": "24",
    "twenty five": "25", "twenty-five": "25", "twenty six": "26", "twenty-six": "26",
    "twenty seven": "27", "twenty-seven": "27", "twenty eight": "28", "twenty-eight": "28",
    "twenty nine": "29", "twenty-nine": "29", "thirty": "30"
}


def extract_ac_mode_and_temp(lower: str) -> tuple[Optional[str], Optional[int]]:
    """
    Deterministically extracts AC operating mode and target temperature from utterance.
    Supports all natural variations and aliases.
    """
    mode_aliases = {
        "auto": "AUTO", "automatic": "AUTO",
        "cool": "COOL", "cold": "COOL", "chilly": "COOL", "chill": "COOL", "cooling": "COOL",
        "dry": "DRY", "dehumidify": "DRY", "dehumidifier": "DRY",
        "fan": "FAN", "blower": "FAN", "fan_only": "FAN",
        "heat": "HEAT", "warm": "HEAT", "heating": "HEAT", "hot": "HEAT"
    }

    extracted_mode: Optional[str] = None

    # Patterns for mode extraction
    patterns = [
        # e.g. "set ac to auto", "change the ac mode to cool", "put the ac on dry mode", "set ac to fan mode at 28"
        r'\b(?:set|change|switch|put|turn)\s+(?:the\s+)?ac\s+(?:mode\s+)?(?:to|on|in)\s+([a-z_]+)',
        # e.g. "set mode to fan", "change mode to auto", "switch ac mode to dry"
        r'\b(?:set|change|switch|put|turn)\s+(?:the\s+)?(?:ac\s+)?mode\s+(?:to|on|in)\s+([a-z_]+)',
        # e.g. "ac on cool mode", "ac auto mode", "ac in fan mode"
        r'\bac\s+(?:on\s+|in\s+)?([a-z_]+)\s+mode\b',
        # e.g. "cool mode on ac", "dry mode on the ac", "fan mode in ac", "auto mode for ac"
        r'\b([a-z_]+)\s+mode\s+(?:on|for|in|of)\s+(?:the\s+)?ac\b',
        # e.g. "put to auto", "switch to dry mode", "put it on cool", "change to fan mode", "put it to auto"
        r'\b(?:set|change|switch|put|turn)\s+(?:it\s+)?(?:mode\s+to|to|on|in)\s+([a-z_]+)',
        # e.g. "cool mode", "dry mode", "fan mode", "auto mode"
        r'\b([a-z_]+)\s+mode\b',
        # Standalone: "auto", "ac auto", "ac cool"
        r'^(?:ac\s+)?(?:mode\s+)?([a-z_]+)\s*(?:mode)?$',
        # e.g. "on auto mode", "in dry mode"
        r'\b(?:on|in)\s+([a-z_]+)\s+mode\b'
    ]

    for pat in patterns:
        m = re.search(pat, lower)
        if m:
            w = m.group(1).lower()
            if w in mode_aliases:
                extracted_mode = mode_aliases[w]
                break

    # Temperature extraction (16 to 30)
    extracted_temp: Optional[int] = None
    for num_match in re.finditer(r'\b(1[6-9]|2[0-9]|30)\b', lower):
        val = int(num_match.group(1))
        # Ignore duration units
        suffix = lower[num_match.end():].strip().split()
        if suffix and suffix[0] in ["min", "mins", "minute", "minutes", "sec", "secs", "second", "seconds", "hour", "hours", "hr", "hrs", "pm", "am"]:
            continue
        extracted_temp = val
        break

    return extracted_mode, extracted_temp


class IntentResolver:
    """
    Synthesizes user utterances, user preferences, memory context, and live room state
    to determine the human's actual intent.
    """

    def __init__(
        self,
        user_profile: UserProfile,
        registry: UnifiedCapabilityRegistry,
        memory: AgentMemoryStore,
        context_buffer: Optional[ConversationContextBuffer] = None
    ):
        self.user_profile = user_profile
        self.registry = registry
        self.memory = memory
        self.context_buffer = context_buffer

    def _normalize_utterance(self, text: str) -> str:
        lower = text.strip().lower()
        for word, num in sorted(WORD_TO_NUM.items(), key=lambda x: len(x[0]), reverse=True):
            lower = re.sub(rf'\b{word}\b', num, lower)
        return lower


    def resolve_intent(
        self,
        utterance: str,
        room_state: Optional[RoomState] = None
    ) -> ResolvedIntent:
        """
        Determines the true human intent from user natural language, context, and capabilities.
        """
        clean_text = utterance.strip()
        lower = self._normalize_utterance(clean_text)

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
        # 1a-1. Stage 5 Proactive Suggestion Responses (Accept / Reject / Defer)
        # =====================================================================
        if self.context_buffer and self.context_buffer.get_pending_suggestion():
            stripped = lower.strip(" .?!,")
            norm = re.sub(r'\s+', ' ', re.sub(r'[,—\-\.:!?]', ' ', lower)).strip()
            if stripped in ["yes", "sure", "yeah", "yep", "please", "please do", "go ahead", "do that", "yes please", "ok", "okay", "yup"] or norm in ["yes please", "yes sure", "sure do that", "please do", "sure"]:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="ACCEPT_SUGGESTION",
                    explanation="User explicitly accepted the active proactive suggestion."
                )
            if stripped in ["no", "leave it", "no leave it", "no thanks", "don't", "dont", "nah", "nope", "leave it as it is", "keep it as is", "don't do that", "dont do that"] or norm in ["no leave it", "no thanks", "leave it as it is", "keep it as is", "dont do it", "no dont", "no", "leave it", "no leave it off"]:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.INFORMATIONAL_ONLY,
                    primary_intent="REJECT_SUGGESTION",
                    explanation="User rejected the active proactive suggestion."
                )
            if stripped in ["later", "not now", "maybe later", "defer"] or norm in ["not now", "maybe later", "later", "defer"]:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.INFORMATIONAL_ONLY,
                    primary_intent="DEFER_SUGGESTION",
                    explanation="User deferred the active proactive suggestion."
                )



        # =====================================================================
        # Stage 6: Scheduled Actions, Timers, and Deferred Intent
        # =====================================================================
        if any(w in lower for w in [
            "cancel scheduled action", "cancel scheduled task", "cancel the scheduled", "don't change the ac later",
            "dont change the ac later", "cancel the timer", "cancel scheduled ac", "forget the scheduled timer",
            "cancel the scheduled task", "cancel the scheduled action"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="CANCEL_SCHEDULED_ACTION",
                explanation="User requested cancellation of scheduled action."
            )

        if any(w in lower for w in [
            "what is scheduled", "show scheduled tasks", "list scheduled actions", "any timers pending",
            "what timers are running", "what's scheduled", "whats scheduled", "show scheduled"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="LIST_SCHEDULED_ACTIONS",
                explanation="User queried active scheduled tasks and timers."
            )

        sched_ac_match = re.search(r'(?:set\s+(?:the\s+)?ac\s+to|turn\s+(?:the\s+)?ac\s+to|make\s+it)\s+(\d+)(?:\s*(?:degrees|c|°c))?\s+in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)', lower)
        if sched_ac_match:
            temp = int(sched_ac_match.group(1))
            val = int(sched_ac_match.group(2))
            unit = sched_ac_match.group(3)
            delay = val * 3600.0 if "hour" in unit or "hr" in unit else val * 60.0
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SCHEDULE_ACTION",
                target_subsystems=["AC"],
                extracted_parameters={"temperature": temp, "delay_seconds": delay, "action_type": "SET_AC_TEMPERATURE", "target_subsystem": "AC", "target_capability": "AC_SET_TEMPERATURE"},
                explanation=f"User requested scheduling AC temperature {temp}°C in {val} {unit}."
            )

        sched_media_match = re.search(r'(?:remind\s+me\s+to\s+)?(?:stop\s+(?:the\s+)?movie|pause\s+(?:the\s+)?movie|turn\s+off\s+(?:the\s+)?movie)\s+in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)', lower)
        if sched_media_match:
            val = int(sched_media_match.group(1))
            unit = sched_media_match.group(2)
            delay = val * 3600.0 if "hour" in unit or "hr" in unit else val * 60.0
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SCHEDULE_ACTION",
                target_subsystems=["MEDIA"],
                extracted_parameters={"delay_seconds": delay, "action_type": "MEDIA_STOP", "target_subsystem": "FIRE_TV", "target_capability": "FIRE_TV_MEDIA_PAUSE"},
                explanation=f"User requested scheduling media stop in {val} {unit}."
            )

        # Multi-Domain Empathic Reasoning Check (Headache, Going to Work, Chill Vibe, Focus Mode, Party Mode)
        try:
            from agent.empathic_engine import get_empathic_engine
            user_addr = getattr(getattr(self.user_profile, 'identity', None), 'preferred_address', 'buddy')
            empathic_plan = get_empathic_engine().evaluate_empathic_intent(clean_text, user_addr)
            if empathic_plan:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent=f"EMPATHIC_{empathic_plan.scenario}",
                    target_subsystems=["AC", "PROJECTOR", "SOUNDBAR", "PC"],
                    extracted_parameters={
                        "scenario": empathic_plan.scenario,
                        "empathy_speech": empathic_plan.empathy_speech,
                        "ac_action": empathic_plan.ac_action,
                        "projector_action": empathic_plan.projector_action,
                        "fire_tv_action": empathic_plan.fire_tv_action,
                        "audio_action": empathic_plan.audio_action,
                        "pc_action": empathic_plan.pc_action,
                        "scheduled_followup_minutes": empathic_plan.scheduled_followup_minutes,
                        "followup_question": empathic_plan.followup_question
                    },
                    explanation=f"Empathic multi-device plan generated for scenario {empathic_plan.scenario}."
                )
        except Exception as e:
            logger.debug(f"[EMPATHIC_RESOLVE_ERR] {e}")

        sched_proj_match = re.search(r'(?:turn\s+off\s+(?:the\s+)?projector|shutdown\s+(?:the\s+)?projector)\s+in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)', lower)
        if sched_proj_match:
            val = int(sched_proj_match.group(1))
            unit = sched_proj_match.group(2)
            delay = val * 3600.0 if "hour" in unit or "hr" in unit else val * 60.0
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SCHEDULE_ACTION",
                target_subsystems=["PROJECTOR"],
                extracted_parameters={"delay_seconds": delay, "action_type": "PROJECTOR_POWER_OFF", "target_subsystem": "PROJECTOR", "target_capability": "PROJECTOR_POWER_OFF"},
                explanation=f"User requested scheduling projector shutdown in {val} {unit}."
            )

        if lower.strip(" .?!") in ("keep the room comfortable", "keep it comfortable", "maintain room comfort", "keep room comfortable"):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="OBSERVE_ROOM_COMFORT",
                target_subsystems=["AC"],
                explanation="User requested long-horizon room comfort observation."
            )

        # Stage 6 Goal Pause / Defer / Resume
        if any(w in lower for w in ["pause the current goal", "pause goal", "pause the setup", "pause the routine", "hold on with the setup", "defer the goal"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PAUSE_GOAL",
                explanation="User requested to pause the active goal."
            )

        if any(w in lower for w in ["resume the goal", "resume goal", "continue the setup", "continue the routine", "resume setup"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="RESUME_GOAL",
                explanation="User requested to resume the paused goal."
            )

        # Stage 6 Situations & Deep Introspection
        if any(w in lower for w in ["what is happening now", "what is happening", "what's happening now", "whats happening now", "what's going on in the room", "what's going on", "whats going on", "what is the room doing"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="WHAT_IS_HAPPENING",
                explanation="User queried current operational situation and room activity."
            )

        # Outdoor Weather Queries
        if any(w in lower for w in [
            "what's the weather", "whats the weather", "what is the weather", "weather outside",
            "weather out side", "is it raining", "how's the weather", "how is the weather",
            "temperature outside", "temp outside", "weather forecast", "outdoor weather"
        ]) or re.search(r'\b(?:weather\s+out\s*side|weather\s+today|weather\s+forecast)\b', lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="WEATHER_QUERY",
                explanation="User queried outdoor weather information."
            )

        # Current Time / Date Queries
        if any(w in lower for w in [
            "what time is it", "what's the time", "whats the time", "what is the time",
            "tell me the time", "current time", "what day is it", "what's today's date", "what is today's date"
        ]) or re.search(r'\b(?:what\s+time\s+is\s+it|what(?:\'s|\s+is)\s+the\s+time)\b', lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="TIME_QUERY",
                explanation="User queried current time or date."
            )

        # Conversational Greetings & Salutations ("hey", "hello", "hi", "good evening", "salutations")
        if re.search(r'^(?:hey|hello|hi|hiya|howdy|hey\s+there|hello\s+there|hey\s+buddy|hello\s+buddy|hey\s+animus|hello\s+animus|good\s+evening(?:\s+animus)?|good\s+afternoon(?:\s+animus)?|salutations(?:\s+animus)?|greetings(?:\s+animus)?)[\s\.\?!]*$', lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="GREETING",
                explanation="Conversational greeting or salutation from user."
            )

        # Conversational Room Status Briefing / Rundown
        if any(w in lower for w in [
            "give me a status rundown", "give me a status brief", "status briefing",
            "give me a rundown", "rundown of the room", "how are we looking today",
            "how is the room looking", "how's the room holding up", "how is the room holding up",
            "system status", "all systems check", "status report", "room status overview",
            "give me a quick status briefing", "brief me on the room"
        ]) or re.search(r'\b(?:status\s+brief(?:ing)?|status\s+rundown|system\s+status|room\s+rundown|all\s+systems\s+check)\b', lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="ROOM_STATUS_BRIEF",
                explanation="User requested a conversational status briefing / rundown of room devices."
            )

        # Agent Identity / Help Queries (exact standalone inquiry)
        if re.search(r'^(?:who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|what\s+do\s+you\s+do|help\s+me|what\s+are\s+your\s+capabilities|tell\s+me\s+about\s+yourself)[\s\.\?!]*$', lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="GET_CAPABILITIES",
                explanation="User queried agent capabilities and identity."
            )



        if any(w in lower for w in ["why did this change", "why did that change", "why did the ac change", "why did the temperature change", "why did the projector turn off"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="WHY_DID_THIS_CHANGE",
                explanation="User asked why a specific state change occurred."
            )


        if any(w in lower for w in ["what changed externally", "what changed in the room", "what changed recently", "what's changed recently", "what changed"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="WHAT_CHANGED",
                explanation="User queried recent room changes and external state diffs."
            )

        # Stage 6 Preferences
        pref_movie_temp = re.search(r'(?:remember\s+that\s+i\s+prefer|prefer|set\s+preferred\s+movie\s+temperature\s+to)\s+(\d+)\s*(?:degrees|c|°c)?\s*(?:for\s+movies|in\s+movie\s+mode)?', lower)
        if pref_movie_temp and any(k in lower for k in ["prefer", "movie", "remember"]):
            t_val = int(pref_movie_temp.group(1))
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_ROOM_PREFERENCE",
                extracted_parameters={"key": "preferred_movie_temperature", "value": t_val},
                explanation=f"User set preferred movie temperature to {t_val}°C."
            )

        if any(w in lower for w in ["forget my movie temperature preference", "forget preferred movie temperature", "forget room preference", "forget my temperature preference"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="FORGET_ROOM_PREFERENCE",
                extracted_parameters={"key": "preferred_movie_temperature"},
                explanation="User requested to forget room temperature preference."
            )


        # =====================================================================
        # 1a-2. Stage 5 Behavioral Introspection
        # =====================================================================
        if any(w in lower for w in [
            "what mode are we in", "what mode is the room in", "what's the active mode",
            "whats the active mode", "are we in movie mode", "are we still in movie mode",
            "what mode are you in", "is movie mode active", "is sleep mode active"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_MODE",
                explanation="User asked for the current behavioral mode of the room."
            )

        if any(w in lower for w in [
            "what's playing", "whats playing", "what are we watching", "is the movie playing",
            "what is playing", "what movie is on", "what track is playing", "is media playing"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_MEDIA",
                explanation="User queried the active media playback session and content."
            )

        if any(w in lower for w in ["what changed recently", "what changed in the room", "what's changed recently"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_RECENT_CHANGE",
                explanation="User queried recent room changes and external state diffs."
            )


        # =====================================================================
        # 1a-3. Stage 5 Autonomous Recovery Queries
        # =====================================================================
        if any(w in lower for w in [
            "recover audio", "fix the sound", "something is wrong with the sound",
            "fix audio", "reconnect audio", "audio is not working", "sound is not working",
            "reconnect soundbar", "fix soundbar"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="RECOVER_AUDIO",
                target_subsystems=["SOUNDBAR"],
                explanation="User requested autonomous audio recovery."
            )

        if any(w in lower for w in ["reconnect fire tv", "fix fire tv", "recover fire tv", "fire tv is disconnected"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="RECOVER_DEVICE",
                target_subsystems=["FIRE_TV"],
                explanation="User requested Fire TV connection recovery."
            )

        # =====================================================================
        # 1a-4. Stage 5 Media Session Controls (Play, Pause, Resume, Stop, Skip, Replay)
        # =====================================================================
        if any(w in lower for w in ["pause it", "pause that for a second", "pause that", "pause the movie", "pause the video", "pause the music", "pause playback", "pause media"]) or lower.strip(" .?!") == "pause":
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PAUSE_MEDIA",
                target_subsystems=["FIRE_TV", "MEDIA"],
                explanation="User requested to pause current media playback."
            )

        if any(w in lower for w in ["resume it", "resume that", "put the movie back on", "resume the movie", "resume the video", "resume playback", "continue the movie", "unpause", "resume media"]) or lower.strip(" .?!") == "resume":
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="RESUME_MEDIA",
                target_subsystems=["FIRE_TV", "MEDIA"],
                explanation="User requested to resume active media playback."
            )

        if any(w in lower for w in ["stop the movie", "stop the music", "stop playback", "stop media"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="MEDIA_STOP",
                target_subsystems=["MEDIA"],
                explanation="User requested to stop media playback."
            )

        if any(w in lower for w in ["skip this", "skip track", "next track", "skip song", "next song"]) or lower.strip(" .?!") == "skip":
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="MEDIA_SKIP",
                target_subsystems=["MEDIA"],
                explanation="User requested to skip to the next track."
            )

        if any(w in lower for w in ["play that again", "replay that", "replay the track", "replay song"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="MEDIA_REPLAY",
                target_subsystems=["MEDIA"],
                explanation="User requested to replay the media item."
            )

        # =====================================================================
        # 1a-5. Stage 5 Behavioral Mode Entries & Exits
        # =====================================================================
        if any(w in lower for w in [
            "let's watch a movie", "lets watch a movie", "get the room ready for a movie",
            "prepare the room for a movie", "prepare room for a movie", "prepare movie mode",
            "enter movie mode", "start movie mode", "movie mode", "put the room in movie mode",
            "fire up the cinema", "ready the cinema", "prepare the cinema", "fancy watching a movie",
            "fancy a film", "fancy putting on a movie", "pop on a movie", "roll the film",
            "start cinema setup", "cinema mode"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="ENTER_MOVIE_MODE",
                target_subsystems=["PROJECTOR", "FIRE_TV", "SOUNDBAR"],
                explanation="User requested to enter Movie Mode."
            )

        if any(w in lower for w in [
            "prepare sleep mode", "put the room to sleep", "ready the room for sleep",
            "enter sleep mode", "start sleep mode", "sleep mode", "bedtime mode",
            "ready the room for bed", "put the quarters to sleep", "retire for the night"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="ENTER_SLEEP_MODE",
                target_subsystems=["AC", "PROJECTOR", "FIRE_TV", "SOUNDBAR"],
                explanation="User requested to enter Sleep Mode."
            )

        if any(w in lower for w in ["wake up mode", "wake the room up", "morning mode"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="ENTER_WAKE_UP_MODE",
                target_subsystems=["AC"],
                explanation="User requested to enter Wake Up Mode."
            )

        if any(w in lower for w in ["work mode", "focus mode", "study mode"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="ENTER_WORK_MODE",
                target_subsystems=["AC"],
                explanation="User requested to enter Work Mode."
            )

        if any(w in lower for w in ["gaming mode", "game mode"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="ENTER_GAMING_MODE",
                target_subsystems=["PROJECTOR", "SOUNDBAR"],
                explanation="User requested to enter Gaming Mode."
            )

        if any(w in lower for w in [
            "stop movie mode", "exit movie mode", "done with the movie",
            "the movie ended", "i'm done here", "im done here", "exit mode", "turn off movie mode"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="EXIT_ACTIVE_MODE",
                explanation="User requested to exit the active behavioral mode."
            )

        # =====================================================================
        # 1a-6. Stage 5 Comfort Expressions ("Too hot", "Freezing", "Make it warmer")
        # =====================================================================
        if any(w in lower for w in ["make it warmer", "a little warmer", "slightly warmer", "raise the ac"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_TEMPERATURE",
                target_subsystems=["AC"],
                extracted_parameters={"relative_delta": 1, "delta": 1, "temperature_relative": 1},
                explanation="User requested relative warming comfort adjustment."
            )

        if any(w in lower for w in ["make it cooler", "a little cooler", "slightly cooler", "lower the ac"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_TEMPERATURE",
                target_subsystems=["AC"],
                extracted_parameters={"relative_delta": -1, "delta": -1, "temperature_relative": -1},
                explanation="User requested relative cooling comfort adjustment."
            )

        if any(w in lower for w in ["i'm comfortable now", "im comfortable now", "temperature is fine", "comfort status"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="COMFORT_STATUS",
                target_subsystems=["AC"],
                explanation="User stated comfort status / checked current comfort."
            )


        # =====================================================================
        # 1b. Replay & Undo Actions ("Do that again", "Put it back")
        # =====================================================================

        if any(u in lower for u in ["put it back", "put the ac back", "change it back", "revert that", "revert it", "set it back", "undo that", "undo the last change", "undo last change", "go back", "undo"]):
            target_sub = ["AC"] if "ac" in lower else []
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="UNDO_RECENT_ACTION",
                target_subsystems=target_sub,
                explanation="User requested to revert the most recent physical action to its prior state."
            )

        if any(r in lower for r in ["do that again", "repeat that", "do it again", "run that again", "replay that", "do the last thing again", "repeat the last thing"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="REPLAY_RECENT_ACTION",
                explanation="User requested to repeat the most recent physical action."
            )

        # =====================================================================
        # =====================================================================
        # 1c-1. Stage 4 Goal Cancellation
        # =====================================================================
        if any(w in lower for w in ["cancel the rest", "cancel the remaining steps", "cancel remaining", "stop the rest", "don't do the rest", "dont do the rest", "wait, don't do the last step", "wait dont do the last step"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="CANCEL_REMAINING_GOAL_STEPS",
                explanation="User cancelled remaining unexecuted goal steps."
            )

        # =====================================================================
        # 1c-2. Cancellation & Conversational Flow Control (Turn Cancellation)
        # =====================================================================
        if any(c in lower for c in [
            "never mind", "nevermind", "forget it", "cancel", "don't do that", "dont do that",
            "actually leave it", "leave it", "stop that", "leave the ac alone", "actually leave the ac alone"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="CANCEL_CURRENT_REQUEST",
                explanation="User explicitly requested cancellation of the pending command or active flow."
            )


        # =====================================================================
        # 1d. Gratitude & Conversational Acknowledgment
        # =====================================================================
        if lower.strip(" .?!") in ["thanks", "thank you", "thanks buddy", "thank you buddy", "thx"]:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="GRATITUDE_ACK",
                explanation="User expressed gratitude / polite conversational closing."
            )

        # =====================================================================
        # 1e. Action Introspection & Historical Queries
        # =====================================================================
        # Historical queries (Depth >= 2 or prior state query)
        if any(w in lower for w in [
            "what did you change before that", "what did you do before that",
            "what was the ac at before", "what was it before", "what was the temperature before",
            "what was it at before"
        ]):
            target_sub = ["AC"] if "ac" in lower or "temperature" in lower else []
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_HISTORICAL_ACTION",
                target_subsystems=target_sub,
                extracted_parameters={"depth": 2 if "before that" in lower else 1, "attribute": "target_temperature" if "temperature" in lower or "ac" in lower else None},
                explanation="User asked for historical action / prior state."
            )

        if any(w in lower for w in ["what did you do to the ac", "what did you change on the ac"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_RECENT_ACTION",
                target_subsystems=["AC"],
                explanation="User asked for the recent action performed on the AC."
            )

        if any(w in lower for w in ["what did you just do", "what did you just change", "what was changed", "what did you change", "what did you do", "what did you switch", "what did you do last"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_RECENT_ACTION",
                explanation="User asked for an explanation of the most recent physical action."
            )

        if any(w in lower for w in ["why did you do that", "why did you turn that off", "why did you change that", "why did you switch that off", "why did you adjust that", "why"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_ACTION_REASON",
                explanation="User asked for the reasoning behind the most recent action."
            )

        # Telemetry / Status query ("Is it still on?", "What is the AC doing now?")
        if any(st in lower for st in ["is it still on", "is the ac still on", "is the projector still on", "what is the ac doing now", "what is the ac at", "what's changed", "whats changed"]):
            dev = "AC" if "ac" in lower else ("PROJECTOR" if "projector" in lower else None)
            if not dev and self.context_buffer:
                dev = self.context_buffer.resolve_reference(clean_text)
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_TELEMETRY_STATUS",
                target_subsystems=[dev] if dev else [],
                explanation="User queried the live physical status of the active device."
            )

        # =====================================================================
        # 1e-2. Goal Introspection Queries (Stage 4)
        # =====================================================================
        if any(w in lower for w in [
            "what are you doing", "what are you working on", "what's happening", "whats happening",
            "did you finish", "are you done", "what did you already do", "what's the room doing now", "whats the room doing now"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_GOAL_STATUS",
                explanation="User queried current deliberative goal / task progress status."
            )

        if any(w in lower for w in ["what's left", "whats left", "what is left", "what's remaining", "whats remaining", "what remains"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_GOAL_REMAINING",
                explanation="User asked for remaining unexecuted steps in the active goal."
            )

        if any(w in lower for w in [
            "what failed", "why haven't you done it", "why havent you done it",
            "why did it fail", "why didn't you continue", "why didnt you continue", "why did it stop"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_GOAL_FAILURES",
                explanation="User asked for explanation of failed/blocked goal steps."
            )

        if any(w in lower for w in ["cancel the rest", "cancel the remaining steps", "stop the rest", "don't do the rest", "dont do the rest", "wait, don't do the last step", "wait dont do the last step"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="CANCEL_REMAINING_GOAL_STEPS",
                explanation="User cancelled remaining unexecuted goal steps."
            )

        if any(wa in lower for wa in ["what about the projector", "how about the projector"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="INTROSPECT_TELEMETRY_STATUS",
                target_subsystems=["PROJECTOR"],
                explanation="User switched conversational focus to the projector."
            )

        # =====================================================================
        # 1e-3. Multi-Step Goals & Conditional Commands (Stage 4)
        # =====================================================================
        # Cinema / Movie Preparation Goal
        if any(kw in lower for kw in [
            "get the room ready for a movie", "prepare the room for a movie",
            "ready for a movie", "movie mode", "prepare for movie", "cinema mode",
            "get ready for movie", "set up for a movie", "set up movie"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="CINEMA_PREPARE",
                target_subsystems=["PROJECTOR", "AC", "FIRE_TV"],
                explanation="User requested multi-step cinema room preparation goal."
            )

        # Sleep / Bedtime Multi-Step Goal (Explicit room commands only)
        if any(kw in lower for kw in [
            "prepare the room for sleep", "get the room ready for sleep", "ready the room for sleep",
            "sleep mode", "bedtime mode", "prepare for sleep", "ready for sleep",
            "turn everything off when i'm done", "turn everything off when im done"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SLEEP_PREPARE",
                target_subsystems=["PROJECTOR", "SOUNDBAR", "AC"],
                explanation="User requested multi-step sleep room preparation goal."
            )


        # Compound Goals: "Cool the room to 23 and turn on the projector" or 3-step movie
        if ("projector" in lower and ("ac" in lower or "cool" in lower or "temperature" in lower)) and ("and" in lower or "then" in lower or "," in lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="MULTI_STEP_GOAL",
                target_subsystems=["PROJECTOR", "AC"],
                explanation="User requested compound multi-device goal."
            )

        # Conditional Commands
        if ("if" in lower or "don't change" in lower or "dont change" in lower or "only" in lower) and ("projector" in lower or "ac" in lower or "soundbar" in lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="CONDITIONAL_GOAL",
                explanation="User requested conditional hardware action."
            )




        # =====================================================================
        # 1f. Semantic Room Thermal & Comfort Reasoning
        # =====================================================================
        if any(c in lower for c in ["i feel chilly", "feeling chilly", "it's chilly in here", "chilly in here", "it's a bit chilly", "a bit chilly", "i'm chilly", "feeling cold"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_MODE",
                target_subsystems=["AC"],
                extracted_parameters={"mode": "FAN"},
                explanation="User reported feeling chilly; transitioning AC to fan mode."
            )

        if any(f in lower for f in ["it's freezing in here", "it's freezing", "i'm freezing", "it's too cold", "it's very cold", "too cold in here"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SEMANTIC_ROOM_FREEZING",
                target_subsystems=["AC"],
                explanation="User reported uncomfortable coldness; requires thermal assessment of live room telemetry."
            )

        if any(h in lower for h in ["it's really hot", "it's too hot", "it's getting warm", "it's boiling in here", "too hot in here", "i'm burning up"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SEMANTIC_ROOM_TOO_HOT",
                target_subsystems=["AC"],
                explanation="User reported uncomfortable warmth; requires thermal cooling adjustment."
            )

        if any(c in lower for c in ["it's comfortable now", "it's already fine", "it's fine now", "feels good now", "comfortable now", "it's perfect now", "make it comfortable"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="SEMANTIC_ROOM_COMFORTABLE",
                target_subsystems=["AC"],
                explanation="User reported thermal satisfaction; no action necessary."
            )

        # Direct Audio Routing Intents
        if any(s in lower for s in ["switch audio to pc", "route audio to pc", "switch to bedroom speaker", "connect soundbar to pc", "audio to pc", "audio to computer"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SOUNDBAR_ROUTE_TO_PC",
                target_subsystems=["SOUNDBAR", "PC"],
                explanation="User explicitly requested routing soundbar audio to PC."
            )

        if any(s in lower for s in ["switch audio to fire tv", "route audio to fire tv", "connect soundbar to fire tv", "audio to fire tv", "audio to tv"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SOUNDBAR_ROUTE_TO_FIRE_TV",
                target_subsystems=["SOUNDBAR", "FIRE_TV"],
                explanation="User explicitly requested routing soundbar audio to Fire TV."
            )

        # =====================================================================
        # 1g. Contextual Corrections (via ConversationContextBuffer)
        # =====================================================================
        if self.context_buffer:
            ac_corr = self.context_buffer.is_ac_correction(clean_text)
            if ac_corr is not None:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SET_AC_TEMPERATURE",
                    target_subsystems=["AC"],
                    extracted_parameters={"temperature": ac_corr},
                    explanation=f"User corrected AC temperature to {ac_corr}°C."
                )

            prov_corr = self.context_buffer.is_provider_correction(clean_text)
            if prov_corr is not None and "actually" in clean_text.lower():
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent=f"LAUNCH_{prov_corr.upper()}",
                    target_subsystems=["PROJECTOR", "FIRE_TV", "SOUNDBAR"],
                    extracted_parameters={"provider": prov_corr},
                    explanation=f"User corrected streaming provider to {prov_corr}."
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
        if any(n in lower for n in ["good night", "goodnight", "going to sleep", "heading to bed", "going to bed", "off to bed", "time for bed"]):
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

        # H2. General Informational Queries (Weather, Time, Identity)
        if any(w_q in lower for w_q in ["what's the weather", "what is the weather", "weather outside", "how's the weather", "how is the weather", "forecast", "weather report"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="WEATHER_QUERY",
                explanation="User requested external weather forecast."
            )

        if any(t_q in lower for t_q in ["what time is it", "what's the time", "what is the time", "current time", "tell me the time"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="TIME_QUERY",
                explanation="User requested current clock time."
            )

        if any(i_q in lower for i_q in ["who are you", "who made you", "what is your name", "what are you"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.INFORMATIONAL_ONLY,
                primary_intent="GET_CAPABILITIES",
                explanation="User queried agent identity / capabilities."
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
            if kw in lower:
                if kw == "fan" and (extract_ac_mode_and_temp(lower)[0] is not None or any(ac_kw in lower for ac_kw in [
                    "ac fan", "fan speed", "fan mode", "mode to fan", "ac to fan", "ac in fan",
                    "ac on fan", "ac mode", "to fan", "on fan", "dry", "cool", "auto", "heat", "ac", "air conditioner"
                ])):
                    continue
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.UNSUPPORTED_CAPABILITY,
                    primary_intent="UNSUPPORTED_DEVICE_CONTROL",
                    extracted_parameters={"unsupported_device": kw},
                    explanation=f"Animus does not currently have hardware integration for '{kw}'."
                )

        # =====================================================================
        # 5. Media Control Commands (Pause / Resume / Stop)
        # =====================================================================
        if any(p_kw in lower for p_kw in [
            "pause that", "pause this", "pause video", "pause media", "pause it",
            "pause for a second", "pause the movie", "pause movie", "pause",
            "stop the video for a second", "stop the video"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PAUSE_MEDIA",
                target_subsystems=["FIRE_TV"],
                explanation="User requested media playback pause."
            )

        if any(r_kw in lower for r_kw in ["resume it", "resume that", "resume this", "resume video", "resume media", "resume playback", "unpause", "continue watching", "resume"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="RESUME_MEDIA",
                target_subsystems=["FIRE_TV"],
                explanation="User requested media playback resume."
            )

        # =====================================================================
        # 6. Direct Projector Power Commands
        # =====================================================================
        if any(p_on in lower for p_on in ["turn on the projector", "turn on projector", "power on projector", "wake projector", "projector on", "switch on the projector", "switch on projector"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PROJECTOR_POWER_WAKE",
                target_subsystems=["PROJECTOR"],
                explanation="User requested direct projector display power wake."
            )

        if any(p_off in lower for p_off in ["turn off the projector", "turn off projector", "power off projector", "sleep projector", "projector off", "switch off the projector", "switch off projector"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PROJECTOR_POWER_SLEEP",
                target_subsystems=["PROJECTOR"],
                explanation="User requested direct projector display standby/sleep."
            )

        # =====================================================================
        # 7. Direct AC Power & Relative Adjustments
        # =====================================================================
        # Direct AC Power On
        if any(ac_on in lower for ac_on in [
            "turn on the ac", "turn the ac on", "switch on the ac", "switch on ac",
            "turn on ac", "it's hot, turn on the ac", "it's hot turn on the ac",
            "can you cool the room", "cool the room", "start the ac", "start ac"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="AC_POWER_ON",
                target_subsystems=["AC"],
                explanation="User requested direct AC power on."
            )

        # Direct AC Power Off
        if not re.search(r'(?:in|after)\s+\d+\s*(?:mins?|minutes?|hours?|hrs?|seconds?|secs?)', lower) and any(ac_off in lower for ac_off in [
            "turn off the ac", "turn the ac off", "switch off the ac", "switch off ac",
            "turn off ac", "stop the ac", "stop ac", "shut off the ac", "shut off ac"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="AC_POWER_OFF",
                target_subsystems=["AC"],
                explanation="User requested direct AC power off."
            )

        # Relative AC: Degree-specific (e.g. "two degrees cooler", "2 degrees warmer", "three degrees cooler")
        rel_deg_match = re.search(r'(?:(?:make\s+(?:it\s+)?)?(?:actually\s+)?)?(\d+)\s*degrees?\s*(cooler|warmer|colder|lower|higher|down|up)', lower)
        if rel_deg_match:
            deg = int(rel_deg_match.group(1))
            direction = rel_deg_match.group(2)
            cur_temp = 24
            if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.target_temperature:
                cur_temp = room_state.ac.target_temperature.value or 24
            elif self.context_buffer and self.context_buffer.last_state_delta and self.context_buffer.last_state_delta.attribute == "target_temperature":
                cur_temp = self.context_buffer.last_state_delta.verified_value or self.context_buffer.last_state_delta.new_value or 24

            delta = -deg if direction in ["cooler", "colder", "lower", "down"] else deg
            target_t = max(16, min(30, cur_temp + delta))
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_TEMPERATURE",
                target_subsystems=["AC"],
                extracted_parameters={"temperature": target_t},
                explanation=f"Relative {direction} adjustment by {deg}°C: {cur_temp}°C -> {target_t}°C."
            )

        # Relative AC: Qualitative Cooler / Warmer (only when no explicit target number is present)
        if not re.search(r'\b\d+\b', lower):
            if any(c_kw in lower for c_kw in ["a little cooler", "make it cooler", "make room cooler", "lower the temperature", "lower the ac", "drop the temp", "cooler"]):
                cur_temp = 24
                if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.target_temperature:
                    cur_temp = room_state.ac.target_temperature.value or 24
                elif self.context_buffer and self.context_buffer.last_state_delta and self.context_buffer.last_state_delta.attribute == "target_temperature":
                    cur_temp = self.context_buffer.last_state_delta.verified_value or self.context_buffer.last_state_delta.new_value or 24
                target_t = max(16, cur_temp - 1)
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SET_AC_TEMPERATURE",
                    target_subsystems=["AC"],
                    extracted_parameters={"temperature": target_t},
                    explanation=f"Relative cooling adjustment: {cur_temp}°C -> {target_t}°C."
                )

            if any(w_kw in lower for w_kw in ["a little warmer", "make it warmer", "make room warmer", "raise the temperature", "raise the ac", "increase the temp", "warmer"]):
                cur_temp = 24
                if room_state and hasattr(room_state, "ac") and room_state.ac and room_state.ac.target_temperature:
                    cur_temp = room_state.ac.target_temperature.value or 24
                elif self.context_buffer and self.context_buffer.last_state_delta and self.context_buffer.last_state_delta.attribute == "target_temperature":
                    cur_temp = self.context_buffer.last_state_delta.verified_value or self.context_buffer.last_state_delta.new_value or 24
                target_t = min(30, cur_temp + 1)
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SET_AC_TEMPERATURE",
                    target_subsystems=["AC"],
                    extracted_parameters={"temperature": target_t},
                    explanation=f"Relative warming adjustment: {cur_temp}°C -> {target_t}°C."
                )

        # Direct Projector Power Wake & Sleep
        if any(w in lower for w in [
            "turn on the projector", "turn on projector", "power on projector", "wake projector",
            "wake the projector", "projector on", "switch on the projector", "switch on projector",
            "fire up the projector", "spin up the projector", "illuminate the screen", "light up the screen",
            "bring up the projector", "power up projector", "kindly turn on the projector"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PROJECTOR_POWER_WAKE",
                target_subsystems=["PROJECTOR"],
                explanation="User requested waking/turning on the projector display."
            )

        if any(w in lower for w in [
            "turn off the projector", "turn off projector", "can you turn off the projector",
            "power off projector", "sleep projector", "projector off", "switch off the projector", "switch off projector",
            "kill the projector", "kill the screen", "shut down the projector", "power down the projector",
            "shut off the projector", "extinguish the screen", "kindly turn off the projector"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PROJECTOR_POWER_SLEEP",
                target_subsystems=["PROJECTOR"],
                explanation="User requested sleeping/turning off the projector display."
            )

        # =====================================================================
        # 11. Thermal & AC Intents (Mode, Temperature, Combined Mode+Temp, Power)
        # =====================================================================
        ac_mode_val, ac_temp_val = extract_ac_mode_and_temp(lower)

        # 1. Combined AC Mode and Temperature (e.g. "set the AC to fan mode at 28", "switch to dry mode at 28", "put the AC on dry at 24")
        if ac_mode_val and ac_temp_val:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_MODE",
                target_subsystems=["AC"],
                extracted_parameters={"mode": ac_mode_val, "temperature": ac_temp_val},
                explanation=f"Set AC operating mode to {ac_mode_val} at {ac_temp_val}°C."
            )

        # 2. AC Mode Only (e.g. "set AC to auto", "put AC on auto", "change AC mode to cool", "cool mode on AC", "put to auto", "dry mode on AC")
        if ac_mode_val:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_MODE",
                target_subsystems=["AC"],
                extracted_parameters={"mode": ac_mode_val},
                explanation=f"Set AC operating mode to {ac_mode_val}."
            )

        # Scheduled Actions ("Turn the AC to 23 in 2 minutes", "turn AC off after 30 sec", "Turn off projector in 15 mins")
        sched_match = re.search(r'(?:in|after)\s+(\d+)\s*(?:mins?|minutes?|hours?|hrs?|seconds?|secs?)', lower)
        if sched_match:
            time_str = sched_match.group(0)
            unit_str = lower[sched_match.start():]
            val = int(sched_match.group(1))
            delay_sec = val * 60.0
            if "hour" in unit_str or "hr" in unit_str:
                delay_sec = val * 3600.0
            elif "sec" in unit_str:
                delay_sec = float(val)

            cmd_part = lower.replace(time_str, '').strip()

            if "ac" in lower or "temperature" in lower or "cool" in lower or "warm" in lower:
                t_match = re.search(r'(?:to\s+)?(\d+)\s*(?:degrees?|°c|celsius)?', cmd_part)
                if t_match:
                    t_val = int(t_match.group(1))
                    if 16 <= t_val <= 30:
                        return ResolvedIntent(
                            raw_query=clean_text,
                            category=IntentCategory.CLEAR_EXECUTABLE,
                            primary_intent="SCHEDULE_ACTION",
                            target_subsystems=["AC"],
                            extracted_parameters={
                                "delay_seconds": delay_sec,
                                "action_type": "SET_AC_TEMPERATURE",
                                "target_subsystem": "AC",
                                "target_capability": "AC_SET_TEMPERATURE",
                                "temperature": t_val
                            },
                            explanation=f"Schedule setting AC temperature to {t_val}°C in {val} minutes."
                        )
                if any(off in cmd_part for off in ["off", "stop", "turn off", "switch off"]):
                    return ResolvedIntent(
                        raw_query=clean_text,
                        category=IntentCategory.CLEAR_EXECUTABLE,
                        primary_intent="SCHEDULE_ACTION",
                        target_subsystems=["AC"],
                        extracted_parameters={
                            "delay_seconds": delay_sec,
                            "action_type": "AC_POWER_OFF",
                            "target_subsystem": "AC",
                            "target_capability": "AC_POWER_OFF"
                        },
                        explanation=f"Schedule turning off AC in {val} minutes."
                    )
            elif "projector" in lower:
                if any(off in cmd_part for off in ["off", "sleep", "turn off", "switch off"]):
                    return ResolvedIntent(
                        raw_query=clean_text,
                        category=IntentCategory.CLEAR_EXECUTABLE,
                        primary_intent="SCHEDULE_ACTION",
                        target_subsystems=["PROJECTOR"],
                        extracted_parameters={
                            "delay_seconds": delay_sec,
                            "action_type": "PROJECTOR_POWER_OFF",
                            "target_subsystem": "PROJECTOR",
                            "target_capability": "PROJECTOR_POWER_SLEEP"
                        },
                        explanation=f"Schedule turning off projector in {val} minutes."
                    )
            elif any(m in lower for m in ["media", "movie", "video", "playback", "song", "music"]):
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SCHEDULE_ACTION",
                    target_subsystems=["MEDIA"],
                    extracted_parameters={
                        "delay_seconds": delay_sec,
                        "action_type": "MEDIA_STOP",
                        "target_subsystem": "FIRE_TV",
                        "target_capability": "FIRE_TV_MEDIA_PAUSE"
                    },
                    explanation=f"Schedule stopping media playback in {val} minutes."
                )

        # Direct AC Power On & Off
        if any(w in lower for w in [
            "turn on the ac", "turn the ac on", "switch on the ac", "switch on ac", "turn on ac", "start the ac",
            "fire up the ac", "flick on the ac", "start up the ac", "crank up the ac", "crank the ac",
            "spin up the ac", "activate the ac", "chill the room", "cool down the room", "cool the room",
            "kindly turn on the ac", "power up the ac", "get the ac going", "switch the ac on", "boot up the ac"
        ]) or lower.strip(" .?!") in ["ac on", "turn on ac", "fire up the ac", "crank the ac", "chill the room"]:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="AC_POWER_ON",
                target_subsystems=["AC"],
                explanation="User requested turning on the AC."
            )

        if any(w in lower for w in [
            "turn off the ac", "turn the ac off", "switch off the ac", "switch off ac", "turn off ac", "stop the ac",
            "kill the ac", "flick off the ac", "shut down the ac", "power down the ac", "cut the ac",
            "shut off the ac", "power off the ac", "kindly turn off the ac"
        ]) or lower.strip(" .?!") in ["ac off", "turn off ac", "kill the ac"]:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="AC_POWER_OFF",
                target_subsystems=["AC"],
                explanation="User requested turning off the AC."
            )

        # 3. Explicit AC Temperature ("Set AC to 24", "change the temperature to 28", "dial the temp to 22", "drop the temperature to 23", "chill it to 22", "crank it down to 21", "make it chilly at 22", "tune the ac to 24", "kindly set the temp to 23")
        if ac_temp_val and re.search(r'\b(?:ac|temp|temperature|degree|degrees|celsius|set\s+to|make\s+it|drop|raise|dial|chill|crank|tune|settle|bring|cool|warm|at)\b', lower):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_TEMPERATURE",
                target_subsystems=["AC"],
                extracted_parameters={"temperature": ac_temp_val},
                explanation=f"Set AC target temperature to {ac_temp_val}°C."
            )

        if lower.strip(" .?!") in ["change mode", "change ac mode", "set ac mode", "switch mode", "set mode"]:
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL,
                primary_intent="SET_AC_MODE",
                target_subsystems=["AC"],
                missing_parameters=["mode"],
                requires_followup=True,
                followup_question="Which mode do you want — Auto, Cool, Dry, or Fan?",
                explanation="AC mode requested with missing mode parameter."
            )

        # 4. AC Fan Speed Commands ("Set AC fan to high", "blower speed medium", "fan speed low", "put ac fan on low", "auto fan speed")
        fan_speed_match = re.search(r'\b(?:(?:ac\s+)?fan\s+speed|(?:ac\s+)?blower\s+speed|ac\s+fan|blower|fan)\s+(?:to\s+|on\s+|at\s+)?(low|medium|high|auto)\b|\b(?:set|put|switch)\s+(?:the\s+)?(?:ac\s+)?(?:fan|blower)(?:\s+speed)?\s+(?:to\s+|on\s+|at\s+)?(low|medium|high|auto)\b|\b(low|medium|high|auto)\s+(?:fan|blower)\s+(?:speed\s+)?(?:on\s+ac)?\b', lower)
        if fan_speed_match and ("ac" in lower or "fan" in lower or "blower" in lower):
            spd = next((g for g in fan_speed_match.groups() if g), "AUTO").upper()
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="SET_AC_FAN_SPEED",
                target_subsystems=["AC"],
                extracted_parameters={"fan_speed": spd},
                explanation=f"Set AC fan speed to {spd}."
            )

        if any(c in lower for c in [
            "cancel scheduled ac", "cancel scheduled action", "cancel schedule", "cancel timer",
            "don't change the ac later", "dont change the ac later", "cancel the ac change"
        ]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="CANCEL_SCHEDULED_ACTION",
                target_subsystems=["AC"] if "ac" in lower else [],
                explanation="User requested cancellation of scheduled room task."
            )




        # =====================================================================
        # 8. Music & Audio Playback (Turn 03: "Put on something to get me moving")
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
        # 9. Focus / SQL Learning Sessions (Turn 11 & Turn 18)
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

        has_specific_provider = any(p in lower for p in ["netflix", "prime video", "prime", "hotstar", "apple tv", "youtube", "zee5", "sonyliv", "disney"])
        if not has_specific_provider and any(e_w in lower for e_w in ["let's watch something", "put something on", "movie mode", "start a movie", "watch a movie", "chill with a movie", "movie", "a movie", "cinema", "feel like watching", "watching something", "watch something", "feel like watching something", "feel like watching a movie", "feel like watching a show"]):
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

        # Direct Streaming Services (Turn 31: "Netflix", "Prime Video", "Hotstar")
        for prov in ["netflix", "prime video", "prime", "hotstar", "apple tv", "disney"]:
            if prov in lower or prov.replace("_", " ") in lower:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent=f"LAUNCH_{prov.upper().replace(' ', '_')}",
                    mood_vibe=MoodVibe.MOVIE,
                    target_subsystems=["PROJECTOR", "FIRE_TV", "SOUNDBAR"],
                    extracted_parameters={"provider": prov},
                    explanation=f"Direct command to launch {prov} on cinema stack."
                )

        # =====================================================================

        # 10b. Negative Constraint Relaxation (Turn 28: "No, not music")
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
        # 10b-1. Media Pause & Video Stop ("pause", "pause that", "pause video", "stop the video")
        # =====================================================================
        if any(p_w in lower for p_w in [
            "pause that", "pause this", "pause video", "pause media", "pause it",
            "pause for a second", "pause the movie", "pause movie", "pause",
            "stop the video for a second", "stop the video"
        ]):
            active_prod = "FIRE_TV"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                prod = getattr(room_state.audio_stream, "active_producer", None)
                if prod:
                    prod_val = getattr(prod, "value", prod)
                    active_prod = prod_val.value if hasattr(prod_val, "value") else str(prod_val or "FIRE_TV")
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="PAUSE_MEDIA",
                target_subsystems=[active_prod] if active_prod in ("FIRE_TV", "PC") else ["FIRE_TV"],
                explanation="User requested pausing active media playback."
            )

        # =====================================================================
        # 10c-0. Media Resume & Bare "Play" Handling ("play", "resume", "unpause", "continue")
        # =====================================================================
        clean_music_cmd = re.sub(
            r'^(?:(?:first|just|please|can\s+you|could\s+you|would\s+you|animus|hey\s+animus|sonia|hey\s+sonia|'
            r'i\s+said|i\s+meant|i\s+wanted\s+you\s+to|i\s+want\s+you\s+to|i\s+asked\s+you\s+to|i\s+told\s+you\s+to|'
            r'i\s+wanted\s+to|i\s+want\s+to|okay|ok)\s+)+', '', lower
        ).strip()
        bare_media_cmd = clean_music_cmd.strip(" .?!,")
        if bare_media_cmd in ["play", "resume", "unpause", "continue", "resume playing", "resume music", "resume playback", "resume it", "continue playing", "continue watching"]:
            is_paused = False
            active_sub = "PC"
            if room_state:
                if hasattr(room_state, "audio_stream") and room_state.audio_stream:
                    pb_f = getattr(room_state.audio_stream, "playback_state", None)
                    pb_st = getattr(pb_f, "value", pb_f)
                    if pb_st == "PAUSED":
                        is_paused = True
                        prod_f = getattr(room_state.audio_stream, "active_producer", None)
                        prod = getattr(prod_f, "value", prod_f)
                        if prod:
                            active_sub = str(prod)
                if hasattr(room_state, "environment") and room_state.environment:
                    mode_f = getattr(room_state.environment, "room_mode", None)
                    mode_st = getattr(mode_f, "value", mode_f)
                    if mode_st == "PAUSED":
                        is_paused = True

            if is_paused or bare_media_cmd in ["resume", "unpause", "continue", "resume playing", "resume playback", "continue playing", "continue watching"]:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="RESUME_MEDIA",
                    mood_vibe=MoodVibe.MUSIC,
                    target_subsystems=[active_sub],
                    explanation="User requested resuming paused media playback."
                )
            else:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_WITH_MISSING_NON_CRITICAL,
                    primary_intent="PLAY_TRACK",
                    mood_vibe=MoodVibe.MUSIC,
                    target_subsystems=["MEDIA", "PC"],
                    missing_parameters=["title"],
                    requires_followup=True,
                    followup_question="What would you like me to play, buddy?",
                    explanation="User requested playback without specifying a song or video title."
                )

        # =====================================================================
        # 10c. Specific Track Playback (e.g. "play Kal Ho Naa Ho", "play alak niranjan on volume 25", "play sunday suspense on volume 30")
        # =====================================================================
        play_track_match = re.search(r'^(?:play|put\s+on|listen\s+to|start\s+playing|stream)\s+(.+)$', clean_music_cmd, re.IGNORECASE)
        if play_track_match:
            candidate = play_track_match.group(1).strip()
            # Check for compound volume modifier e.g. "alak niranjan on volume 25", "kal ho naa ho at volume 30"
            vol_match = re.search(r'^(.*?)\s+(?:on|at|with)\s+volume\s+(\d+)\s*$', candidate, re.IGNORECASE)
            extracted_vol = None
            if vol_match:
                candidate = vol_match.group(1).strip()
                extracted_vol = int(vol_match.group(2))

            non_track_prefixes = [
                "movie", "a movie", "something", "netflix", "youtube", "prime", "hotstar",
                "apple tv", "disney", "music", "something upbeat", "something to get me moving",
                "something relaxing", "video", "the video", "it", "that", "this"
            ]
            if candidate not in non_track_prefixes and not candidate.startswith("the ac") and not candidate.startswith("ac"):
                params = {"title": candidate, "artist": None}
                if extracted_vol is not None:
                    params["volume"] = extracted_vol
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="PLAY_TRACK",
                    mood_vibe=MoodVibe.MUSIC,
                    target_subsystems=["MEDIA", "PC"],
                    extracted_parameters=params,
                    explanation=f"User requested track playback for '{candidate}'."
                )

        # =====================================================================
        # 11. Anaphoric / Contextual Pronoun Reference ("Turn that off", "Turn it off", "Turn that off too")
        # =====================================================================
        if any(off_kw in lower for off_kw in [
            "turn that off too", "turn it off too", "turn that off", "turn this off", "turn it off",
            "switch that off", "switch this off", "switch it off",
            "shut that off", "shut this off", "shut it off", "turn everything off", "done watching"
        ]):
            target_device = None
            if self.context_buffer:
                target_device = self.context_buffer.resolve_reference(clean_text)

            if target_device == "PROJECTOR":
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="PROJECTOR_POWER_SLEEP",
                    target_subsystems=["PROJECTOR"],
                    explanation="Anaphoric pronoun resolved to active Projector."
                )
            elif target_device == "AC":
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="AC_POWER_OFF",
                    target_subsystems=["AC"],
                    explanation="Anaphoric pronoun resolved to active AC."
                )
            elif room_state and hasattr(room_state, "environment") and room_state.environment and room_state.environment.room_mode == "MOVIE":
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SLEEP_ALL",
                    target_subsystems=["PROJECTOR", "FIRE_TV"],
                    explanation="Anaphoric pronoun resolved to active Cinema / Movie stack."
                )
            else:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SLEEP_ALL",
                    target_subsystems=["PROJECTOR", "FIRE_TV"],
                    explanation="Resolved general sleep/turn off intent."
                )


        # =====================================================================
        # 12. Volume & Bare Numeric Disambiguation (Turns 04, 08, 33, 34)
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

        # Explicit Audio Mute & Unmute
        if any(m_kw in lower for m_kw in ["mute", "mute audio", "mute the audio", "mute soundbar", "mute the soundbar", "silence speakers"]):
            if not any(un in lower for un in ["unmute", "un-mute"]):
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="MUTE_AUDIO",
                    target_subsystems=["PC"],
                    explanation="User requested muting audio."
                )
        if any(um_kw in lower for um_kw in ["unmute", "unmute the audio", "unmute audio", "unmute soundbar", "unmute the soundbar"]):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="UNMUTE_AUDIO",
                target_subsystems=["PC"],
                explanation="User requested unmuting audio."
            )

        # Explicit Volume Setpoint ("Set volume to 45", "volume 50%", "change volume to 60")
        vol_set_match = re.search(r'\b(?:set|change|put|make|turn)?\s*(?:the\s+)?volume\s+(?:to\s+|at\s+)?(\d+)\s*%?\b|\bvolume\s+(\d+)\b', lower)
        if vol_set_match and not any(v_dir in lower for v_dir in ["up", "down", "louder", "quieter"]):
            v_val = int(next((g for g in vol_set_match.groups() if g), "50"))
            if 0 <= v_val <= 100:
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent="SET_VOLUME",
                    target_subsystems=["PC"],
                    extracted_parameters={"volume": v_val},
                    explanation=f"Set audio volume to {v_val}%."
                )

        if any(v_w in lower for v_w in [
            "make it quieter", "turn it down", "turn it down a bit", "lower the volume a little",
            "lower the volume", "turn down the volume", "turn down", "softer", "quieter", "that's too loud",
            "decrease volume", "decrease the volume", "reduce volume", "reduce the volume", "lower volume", "volume down",
            "turn it up", "turn it up a bit", "make it louder", "louder", "volume up",
            "increase volume", "increase the volume", "raise volume", "raise the volume", "boost volume"
        ]):
            is_up = any(u in lower for u in ["up", "louder", "increase", "raise", "boost"])
            active_producer = "UNKNOWN"
            if room_state and hasattr(room_state, "audio_stream") and room_state.audio_stream:
                active_producer = getattr(room_state.audio_stream, "active_producer", "UNKNOWN")
                if hasattr(active_producer, "value"):
                    active_producer = active_producer.value

            if active_producer in ("FIRE_TV", "PC"):
                intent_name = "VOLUME_UP" if is_up else "VOLUME_DOWN"
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent=intent_name,
                    target_subsystems=[active_producer],
                    extracted_parameters={"target_producer": active_producer, "direction": "UP" if is_up else "DOWN"},
                    explanation=f"Acoustic adjustment ({intent_name}) resolved to active producer: {active_producer}."
                )
            elif any(w in lower for w in ["increase volume", "increase the volume", "decrease volume", "decrease the volume", "raise volume", "raise the volume", "lower volume", "lower the volume", "volume up", "volume down"]):
                intent_name = "VOLUME_UP" if is_up else "VOLUME_DOWN"
                return ResolvedIntent(
                    raw_query=clean_text,
                    category=IntentCategory.CLEAR_EXECUTABLE,
                    primary_intent=intent_name,
                    target_subsystems=["PC"],
                    extracted_parameters={"target_producer": "PC", "direction": "UP" if is_up else "DOWN"},
                    explanation=f"Explicit volume request ({intent_name}) mapped to PC."
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
        # 13. Default Fallback Classification
        # =====================================================================
        # Check if the query mentions room devices, media, thermal, or power actions
        room_keywords = [
            "ac", "air conditioner", "temperature", "temp", "cool", "fan", "heat",
            "projector", "screen", "hdmi", "display", "brightness",
            "tv", "fire tv", "firetv", "soundbar", "speaker", "bluetooth", "audio", "volume", "mute",
            "movie", "cinema", "netflix", "apple tv", "prime", "youtube", "music", "song", "track", "play", "pause", "stop", "resume",
            "turn on", "turn off", "switch", "power", "set", "mode", "sleep", "wake", "desk", "light", "lights"
        ]
        if any(re.search(rf'\b{re.escape(k)}\b', lower) for k in room_keywords):
            return ResolvedIntent(
                raw_query=clean_text,
                category=IntentCategory.CLEAR_EXECUTABLE,
                primary_intent="GENERAL_ROOM_COMMAND",
                explanation="Standard room orchestration command passed to planner."
            )

        return ResolvedIntent(
            raw_query=clean_text,
            category=IntentCategory.INFORMATIONAL_ONLY,
            primary_intent="NON_ROOM_QUERY",
            explanation="Non-room conversational or informational query."
        )


