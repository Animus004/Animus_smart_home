"""
Authoritative Independent Forensic Evaluator Engine for Phase F.3.
Strict Invariant: ZERO hardcoded verdicts.
Derives verdicts (PASS, FAIL, CRITICAL) exclusively from observed physical evidence,
verified intent taxonomy, memory/task state, and response truthfulness.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("music_daemon.agent.f3_evaluator")


# =============================================================================
# 45-Turn Authoritative Scenario Specification
# =============================================================================

F3_SCENARIO_SPEC: Dict[int, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # SESSION A — MORNING (Turns 1–5)
    # -------------------------------------------------------------------------
    1: {
        "session_id": "session_a",
        "session_name": "Morning",
        "user_message": "Buddy, I'm up.",
        "expected_intents": ["MORNING_ROUTINE_BRIEF"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Priorities", "SQL", "buddy"],
        "disallowed_response_keywords": ["Sayan"],
        "description": "Morning wake-up greeting triggers daily priorities briefing."
    },
    2: {
        "session_id": "session_a",
        "session_name": "Morning",
        "user_message": "What's on my plate today?",
        "expected_intents": ["TASK_SCHEDULE_QUERY"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["agenda", "SQL"],
        "disallowed_response_keywords": [],
        "description": "Query agenda / pending tasks for today."
    },
    3: {
        "session_id": "session_a",
        "session_name": "Morning",
        "user_message": "Put on something to get me moving.",
        "expected_intents": ["PLAY_MUSIC"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["music", "motivation"],
        "disallowed_response_keywords": [],
        "description": "Request morning motivational music playback."
    },
    4: {
        "session_id": "session_a",
        "session_name": "Morning",
        "user_message": "Make it a little louder.",
        "expected_intents": ["ADJUST_VOLUME_AMBIGUOUS", "ADJUST_ACTIVE_VOLUME"],
        "followup_required": True,
        "physical_action_expected": False,
        "allowed_mutation_patterns": ["Projector Power:", "Projector Source:"],
        "required_response_keywords": ["Fire TV", "PC"],
        "disallowed_response_keywords": [],
        "description": "Volume increase on ambiguous target asks for audio producer clarification."
    },
    5: {
        "session_id": "session_a",
        "session_name": "Morning",
        "user_message": "I'm heading to my desk.",
        "expected_intents": ["USER_LOCATION_UPDATE"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["desk"],
        "disallowed_response_keywords": ["prepared Fire TV volume"],
        "description": "User location statement must not execute deferred physical actions."
    },

    # -------------------------------------------------------------------------
    # SESSION B — WORK SESSION (Turns 6–10)
    # -------------------------------------------------------------------------
    6: {
        "session_id": "session_b",
        "session_name": "Work Session",
        "user_message": "I need to start working.",
        "expected_intents": ["ENTER_WORK_FOCUS_MODE"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Focus mode", "SQL"],
        "disallowed_response_keywords": [],
        "description": "Activate work focus mode."
    },
    7: {
        "session_id": "session_b",
        "session_name": "Work Session",
        "user_message": "Set the AC to 24.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "SET_AC_TEMPERATURE"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["AC Temperature:", "AC Power:"],
        "required_response_keywords": ["AC", "24"],
        "disallowed_response_keywords": [],
        "description": "Set AC target temperature to 24C."
    },
    8: {
        "session_id": "session_b",
        "session_name": "Work Session",
        "user_message": "Make it quieter.",
        "expected_intents": ["ADJUST_VOLUME_AMBIGUOUS", "ADJUST_ACTIVE_VOLUME", "VOLUME_DOWN"],
        "followup_required": True,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Fire TV", "PC"],
        "disallowed_response_keywords": [],
        "description": "Volume decrease on ambiguous target asks for clarification."
    },
    9: {
        "session_id": "session_b",
        "session_name": "Work Session",
        "user_message": "Quiet mode please.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "VOLUME_DOWN", "QUIET_ROOM_COMFORT"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": ["PC Volume:", "Soundbar Owner:"],
        "required_response_keywords": [],
        "disallowed_response_keywords": [],
        "description": "Set room to quiet audio profile."
    },
    10: {
        "session_id": "session_b",
        "session_name": "Work Session",
        "user_message": "Can you adjust the bedroom fan?",
        "expected_intents": ["UNSUPPORTED_DEVICE_CONTROL"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["can't control the fan", "Projector", "Fire TV", "AC"],
        "disallowed_response_keywords": [],
        "description": "Truthfully explain limitation on unsupported bedroom fan."
    },

    # -------------------------------------------------------------------------
    # SESSION C — SQL LEARNING & TASKS (Turns 11–15)
    # -------------------------------------------------------------------------
    11: {
        "session_id": "session_c",
        "session_name": "SQL Learning",
        "user_message": "Time to focus on SQL.",
        "expected_intents": ["ENTER_WORK_FOCUS_MODE"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Focus", "SQL"],
        "disallowed_response_keywords": [],
        "description": "Transition to SQL focus mode."
    },
    12: {
        "session_id": "session_c",
        "session_name": "SQL Learning",
        "user_message": "Remind me to review window functions.",
        "expected_intents": ["BOOKKEEPING_REQUEST"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Review window functions"],
        "disallowed_response_keywords": [],
        "description": "Create reminder for review window functions."
    },
    13: {
        "session_id": "session_c",
        "session_name": "SQL Learning",
        "user_message": "Actually remind me after lunch.",
        "expected_intents": ["BOOKKEEPING_REQUEST"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["after lunch"],
        "disallowed_response_keywords": ["to 'Reminder'"],
        "description": "Modify previous reminder time to after lunch."
    },
    14: {
        "session_id": "session_c",
        "session_name": "SQL Learning",
        "user_message": "What did I just add?",
        "expected_intents": ["TASK_SCHEDULE_QUERY"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["window functions"],
        "disallowed_response_keywords": ["Got it, buddy."],
        "description": "Query most recently added reminder from task state."
    },
    15: {
        "session_id": "session_c",
        "session_name": "SQL Learning",
        "user_message": "Okay, focusing now.",
        "expected_intents": ["CONVERSATIONAL_ACK"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["focus"],
        "disallowed_response_keywords": [],
        "description": "Conversational acknowledgment of active focus."
    },

    # -------------------------------------------------------------------------
    # SESSION D — LUNCH TRANSITION (Turns 16–20)
    # -------------------------------------------------------------------------
    16: {
        "session_id": "session_d",
        "session_name": "Lunch Transition",
        "user_message": "I had lunch.",
        "expected_intents": ["LUNCH_COMPLETED_TRIGGER"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Lunch done", "guitar", "SQL"],
        "disallowed_response_keywords": [],
        "description": "Signal lunch completion and offer routine suggestions."
    },
    17: {
        "session_id": "session_d",
        "session_name": "Lunch Transition",
        "user_message": "What was I supposed to do after lunch?",
        "expected_intents": ["TASK_SCHEDULE_QUERY"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["window functions"],
        "disallowed_response_keywords": [],
        "description": "Query specific task scheduled for after lunch."
    },
    18: {
        "session_id": "session_d",
        "session_name": "Lunch Transition",
        "user_message": "Let's do SQL for 30 minutes.",
        "expected_intents": ["START_FOCUS_SESSION"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["30", "SQL"],
        "disallowed_response_keywords": ["prepared PC volume"],
        "description": "Start 30-minute study session without volume mutation."
    },
    19: {
        "session_id": "session_d",
        "session_name": "Lunch Transition",
        "user_message": "Mark window functions as done.",
        "expected_intents": ["COMPLETE_TASK"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["completed", "window functions"],
        "disallowed_response_keywords": [],
        "description": "Complete task in task manager."
    },
    20: {
        "session_id": "session_d",
        "session_name": "Lunch Transition",
        "user_message": "Great, that's done.",
        "expected_intents": ["CONVERSATIONAL_ACK"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["job", "buddy"],
        "disallowed_response_keywords": [],
        "description": "Conversational acknowledgment."
    },

    # -------------------------------------------------------------------------
    # SESSION E — AFTERNOON & GUITAR (Turns 21–25)
    # -------------------------------------------------------------------------
    21: {
        "session_id": "session_e",
        "session_name": "Afternoon Guitar",
        "user_message": "Remind me to practice guitar at 5.",
        "expected_intents": ["BOOKKEEPING_REQUEST"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["guitar"],
        "disallowed_response_keywords": [],
        "description": "Schedule guitar reminder for 17:00."
    },
    22: {
        "session_id": "session_e",
        "session_name": "Afternoon Guitar",
        "user_message": "Remind me about guitar.",
        "expected_intents": ["BOOKKEEPING_REQUEST"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["already have a reminder", "guitar"],
        "disallowed_response_keywords": [],
        "description": "Deduplicate guitar reminder against existing reminder."
    },
    23: {
        "session_id": "session_e",
        "session_name": "Afternoon Guitar",
        "user_message": "I'm practicing guitar now.",
        "expected_intents": ["USER_STATE_UPDATE"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["guitar"],
        "disallowed_response_keywords": [],
        "description": "User state update for guitar practice."
    },
    24: {
        "session_id": "session_e",
        "session_name": "Afternoon Guitar",
        "user_message": "Did I finish my guitar practice on the list?",
        "expected_intents": ["TASK_SCHEDULE_QUERY"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["guitar", "pending", "list"],
        "disallowed_response_keywords": ["Got it, buddy."],
        "description": "Query completion status of guitar practice task."
    },
    25: {
        "session_id": "session_e",
        "session_name": "Afternoon Guitar",
        "user_message": "Set AC to 25.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "SET_AC_TEMPERATURE"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["AC Temperature:", "AC Power:"],
        "required_response_keywords": ["AC", "25"],
        "disallowed_response_keywords": [],
        "description": "Set AC target temperature to 25C."
    },

    # -------------------------------------------------------------------------
    # SESSION F — EVENING MOOD & DISAMBIGUATION (Turns 26–30)
    # -------------------------------------------------------------------------
    26: {
        "session_id": "session_f",
        "session_name": "Evening Mood",
        "user_message": "I'm exhausted buddy.",
        "expected_intents": ["USER_MOOD_STATEMENT"],
        "followup_required": True,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["music", "movie", "quiet"],
        "disallowed_response_keywords": ["Got it, buddy."],
        "description": "Empathetic acknowledgment of fatigue offering relaxation options."
    },
    27: {
        "session_id": "session_f",
        "session_name": "Evening Mood",
        "user_message": "I want something relaxing.",
        "expected_intents": ["RELAXATION_INTENT"],
        "followup_required": True,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["music", "movie", "quiet room"],
        "disallowed_response_keywords": [],
        "description": "Relaxation intent disambiguation."
    },
    28: {
        "session_id": "session_f",
        "session_name": "Evening Mood",
        "user_message": "No, not music.",
        "expected_intents": ["RELAXATION_NARROW_OPTIONS", "GENERAL_ROOM_COMMAND"],
        "followup_required": True,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["movie", "quiet room"],
        "disallowed_response_keywords": ["Got it, buddy."],
        "description": "Negative constraint narrows relaxation choices."
    },
    29: {
        "session_id": "session_f",
        "session_name": "Evening Mood",
        "user_message": "Let's chill with a movie then.",
        "expected_intents": ["START_CINEMA_ENTERTAINMENT"],
        "followup_required": True,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Projector Source:", "Fire TV Power:", "Soundbar Owner:", "Fire TV App:"],
        "required_response_keywords": ["Netflix", "YouTube"],
        "disallowed_response_keywords": [],
        "description": "Resolve to movie option; prepare cinema hardware."
    },
    30: {
        "session_id": "session_f",
        "session_name": "Evening Mood",
        "user_message": "Let's watch something.",
        "expected_intents": ["START_CINEMA_ENTERTAINMENT"],
        "followup_required": True,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Projector Source:", "Fire TV Power:", "Soundbar Owner:", "Fire TV App:"],
        "required_response_keywords": ["Netflix", "YouTube"],
        "disallowed_response_keywords": [],
        "description": "Prepare cinema hardware and ask for streaming provider."
    },

    # -------------------------------------------------------------------------
    # SESSION G — ENTERTAINMENT, MIND CHANGES & AUDIO (Turns 31–37)
    # -------------------------------------------------------------------------
    31: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "Netflix.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "LAUNCH_NETFLIX"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Fire TV App:"],
        "required_response_keywords": ["Netflix", "fire tv"],
        "disallowed_response_keywords": [],
        "description": "Launch Netflix on Fire TV."
    },
    32: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "Actually no, put on YouTube instead.",
        "expected_intents": ["PLAY_YOUTUBE"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Fire TV App:"],
        "required_response_keywords": ["youtube"],
        "disallowed_response_keywords": [],
        "description": "Change mind from Netflix to YouTube."
    },
    33: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "Make it a little quieter.",
        "expected_intents": ["ADJUST_ACTIVE_VOLUME", "VOLUME_DOWN"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Fire TV volume", "volume"],
        "disallowed_response_keywords": ["PC volume"],
        "description": "Attenuate volume on active Fire TV media stack."
    },
    34: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "Actually 25 is fine.",
        "expected_intents": ["BARE_NUMERIC_AMBIGUOUS", "ADJUST_ACTIVE_VOLUME"],
        "followup_required": True,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["25 what", "volume", "AC"],
        "disallowed_response_keywords": ["prepared PC volume"],
        "description": "Bare numeric statement prompts clarification without arbitrary hardware mutation."
    },
    35: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "Pause that for a second.",
        "expected_intents": ["PAUSE_MEDIA", "GENERAL_ROOM_COMMAND"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Pause", "media"],
        "disallowed_response_keywords": [],
        "description": "Pause active media on Fire TV."
    },
    36: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "Resume it.",
        "expected_intents": ["RESUME_MEDIA", "GENERAL_ROOM_COMMAND"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Fire TV App:"],
        "required_response_keywords": ["Resume", "media"],
        "disallowed_response_keywords": [],
        "description": "Resume active media on Fire TV."
    },
    37: {
        "session_id": "session_g",
        "session_name": "Entertainment",
        "user_message": "I'm done watching.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "SLEEP_ALL"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Fire TV Power:", "Projector Power:"],
        "required_response_keywords": ["sleep", "ready"],
        "disallowed_response_keywords": [],
        "description": "Put cinema displays to sleep."
    },

    # -------------------------------------------------------------------------
    # SESSION H — TOPIC INTERRUPTION & SELF-KNOWLEDGE (Turns 38–41)
    # -------------------------------------------------------------------------
    38: {
        "session_id": "session_h",
        "session_name": "Interruption & Audit",
        "user_message": "Let's watch something.",
        "expected_intents": ["START_CINEMA_ENTERTAINMENT"],
        "followup_required": True,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Projector Source:", "Fire TV Power:", "Soundbar Owner:", "Fire TV App:"],
        "required_response_keywords": ["Netflix", "YouTube"],
        "disallowed_response_keywords": [],
        "description": "Cinema preparation with streaming follow-up."
    },
    39: {
        "session_id": "session_h",
        "session_name": "Interruption & Audit",
        "user_message": "Actually remind me to check server logs tomorrow at 10.",
        "expected_intents": ["BOOKKEEPING_REQUEST"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["Check server logs"],
        "disallowed_response_keywords": [],
        "description": "Topic interruption supersedes pending cinema follow-up."
    },
    40: {
        "session_id": "session_h",
        "session_name": "Interruption & Audit",
        "user_message": "What do you know about my preferences?",
        "expected_intents": ["AUDIT_USER_PREFERENCES"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["preferences", "buddy"],
        "disallowed_response_keywords": ["Got it, buddy."],
        "description": "Audit stored preferences from user model."
    },
    41: {
        "session_id": "session_h",
        "session_name": "Interruption & Audit",
        "user_message": "What are you unsure about?",
        "expected_intents": ["AUDIT_UNCERTAINTY"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["assumptions"],
        "disallowed_response_keywords": ["Got it, buddy."],
        "description": "Audit system uncertainties and unconfirmed assumptions."
    },

    # -------------------------------------------------------------------------
    # SESSION I — NIGHT WRAP-UP & RESTORATION (Turns 42–45)
    # -------------------------------------------------------------------------
    42: {
        "session_id": "session_i",
        "session_name": "Night Wrap-Up",
        "user_message": "What did I accomplish today?",
        "expected_intents": ["TASK_SCHEDULE_QUERY"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": [],
        "required_response_keywords": ["completed", "window functions"],
        "disallowed_response_keywords": ["No completed tasks recorded"],
        "description": "Query completed tasks summary."
    },
    43: {
        "session_id": "session_i",
        "session_name": "Night Wrap-Up",
        "user_message": "Set AC to 24 for the night.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "SET_AC_TEMPERATURE"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["AC Temperature:", "AC Power:"],
        "required_response_keywords": ["AC", "24"],
        "disallowed_response_keywords": [],
        "description": "Set night AC temperature to 24C."
    },
    44: {
        "session_id": "session_i",
        "session_name": "Night Wrap-Up",
        "user_message": "Turn everything off.",
        "expected_intents": ["GENERAL_ROOM_COMMAND", "SLEEP_ALL"],
        "followup_required": False,
        "physical_action_expected": True,
        "allowed_mutation_patterns": ["Fire TV Power:", "Projector Power:"],
        "required_response_keywords": ["sleep", "ready"],
        "disallowed_response_keywords": [],
        "description": "Sleep all room hardware."
    },
    45: {
        "session_id": "session_i",
        "session_name": "Night Wrap-Up",
        "user_message": "Good night buddy.",
        "expected_intents": ["NIGHT_ROUTINE_TRANSITION"],
        "followup_required": False,
        "physical_action_expected": False,
        "allowed_mutation_patterns": ["Projector Source:", "Projector Power:"],
        "required_response_keywords": ["Good night", "Sleep well"],
        "disallowed_response_keywords": [],
        "description": "Evening sign-off with zero hardware mutations."
    }
}


# =============================================================================
# Forensic Turn Evaluator Engine
# =============================================================================

class F3TurnEvaluator:
    """
    Independent forensic evaluator for Phase F.3 conversational turns.
    Evaluates empirical hardware before/after snapshots, intent taxonomy,
    task state, and response truthfulness against authoritative specifications.
    """

    @classmethod
    def evaluate_turn(
        cls,
        turn_number: int,
        user_message: str,
        response_data: Dict[str, Any],
        pre_snap: Dict[str, Any],
        post_snap: Dict[str, Any],
        observed_mutations: List[str]
    ) -> Dict[str, Any]:
        """
        Calculates an independent evidence-derived verdict for a single conversational turn.
        """
        spec = F3_SCENARIO_SPEC.get(turn_number)
        if not spec:
            return {
                "verdict": "FAIL",
                "reason": f"No scenario specification found for Turn {turn_number}",
                "unauthorized_mutations": observed_mutations,
                "interpretation_correct": False,
                "followup_appropriate": False,
                "response_truthful": False
            }

        agent_message = response_data.get("agent_message", "")
        understood_intent = response_data.get("understood_intent", "")
        followup_required = response_data.get("followup_required", False)

        # 1. Intent Taxonomy Verification
        expected_intents = spec["expected_intents"]
        interpretation_correct = understood_intent in expected_intents

        # 2. Follow-Up Appropriateness
        expected_followup = spec["followup_required"]
        followup_appropriate = (followup_required == expected_followup)

        # 3. Physical Mutation Authorization Check
        allowed_patterns = spec["allowed_mutation_patterns"]
        unauthorized_mutations: List[str] = []

        for mut in observed_mutations:
            if not any(pat in mut for pat in allowed_patterns):
                unauthorized_mutations.append(mut)

        mutation_authorized = (len(unauthorized_mutations) == 0)

        # 4. Response Truthfulness & Key Content Verification
        response_truthful = True
        missing_keywords: List[str] = []
        forbidden_hits: List[str] = []

        for req_kw in spec.get("required_response_keywords", []):
            if req_kw.lower() not in agent_message.lower():
                response_truthful = False
                missing_keywords.append(req_kw)

        for dis_kw in spec.get("disallowed_response_keywords", []):
            if dis_kw.lower() in agent_message.lower():
                response_truthful = False
                forbidden_hits.append(dis_kw)

        # 5. Readback Verification
        readback_verified = True
        if spec["physical_action_expected"] and observed_mutations and not any(p in agent_message.lower() for p in ["all set", "prepared", "switched", "ac", "volume", "sleep"]):
            readback_verified = False

        # 6. Final Independent Verdict Calculation
        # CRITICAL: Any unauthorized physical mutation
        if not mutation_authorized or len(unauthorized_mutations) > 0:
            verdict = "CRITICAL"
            reason = f"Unauthorized physical mutations observed: {', '.join(unauthorized_mutations)}"
        elif not interpretation_correct:
            verdict = "FAIL"
            reason = f"Intent mismatch: understood '{understood_intent}', expected one of {expected_intents}"
        elif not followup_appropriate:
            verdict = "FAIL"
            reason = f"Follow-up requirement mismatch: actual {followup_required}, expected {expected_followup}"
        elif not response_truthful:
            verdict = "FAIL"
            reason = f"Response untruthful: missing {missing_keywords}, forbidden hits {forbidden_hits}"
        elif not readback_verified:
            verdict = "FAIL"
            reason = "Readback failed: physical action occurred without truthful agent confirmation"
        else:
            verdict = "PASS"
            reason = "Empirical physical evidence, intent, follow-up, and response verified"

        return {
            "turn_number": turn_number,
            "session_id": spec["session_id"],
            "session_name": spec["session_name"],
            "user_message": user_message,
            "agent_response": agent_message,
            "expected_intents": expected_intents,
            "understood_intent": understood_intent,
            "interpretation_correct": interpretation_correct,
            "followup_required": followup_required,
            "followup_appropriate": followup_appropriate,
            "physical_action_expected": spec["physical_action_expected"],
            "observed_mutations": observed_mutations,
            "unauthorized_mutations": unauthorized_mutations,
            "mutation_authorized": mutation_authorized,
            "readback_verified": readback_verified,
            "response_truthful": response_truthful,
            "verdict": verdict,
            "reason": reason
        }
