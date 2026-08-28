"""
Comprehensive Live Input Scenario Tests for Animus Personal Agent.
Validates all real-world voice command patterns across:
1. Multi-Turn Conversational Progression (Greeting -> Weather -> Tasks -> Reminder -> Music)
2. Streaming / Cinema Mode Invocations ("want to watch prime", "watch netflix", etc.)
3. Scheduled / Timed Hardware Actions ("turn AC off after 30 sec", "turn off projector in 10 mins")
4. Thermal Comfort Reasoning ("I feel chilly" -> Fan mode, "it's freezing in here" -> AC off)
5. AC Multi-Turn Conversational Cycles (Power -> Mode -> Temperature -> Delta -> Fan)
6. PC Music Playback & Audio Ownership Invariant ("play <song>" -> routes to PC Soundbar)
7. Bare "Play" / "Resume" State-Aware Handling (Paused -> Resume, Idle -> Ask Preference)
"""

import pytest
from unittest.mock import MagicMock, patch
from agent.intent_resolver import IntentResolver, IntentCategory
from agent.core import AnimusPersonalAgent, AgentInteractionResponse
from room_state.models import RoomState, AcState, AudioStreamState, MediaPlaybackState, ActiveAudioProducer, StateField
from room_state.provenance import Provenance
import time


@pytest.fixture
def agent_system():
    agent = AnimusPersonalAgent()
    return agent, agent.intent_resolver


# =============================================================================
# SCENARIO 1: Conversational Multi-Turn Briefing & Music Progression
# =============================================================================

def test_scenario1_multi_turn_briefing_progression(agent_system):
    agent, resolver = agent_system

    # Turn 1: Greeting
    r1 = resolver.resolve_intent("hey")
    assert r1.primary_intent in ["GREETING", "GENERAL_GREETING", "INFORMATIONAL_QUERY"]

    # Turn 2: Weather Query
    r2 = resolver.resolve_intent("what's the weather today")
    assert r2.primary_intent in ["WEATHER_QUERY", "INFORMATIONAL_QUERY"]
    assert r2.category == IntentCategory.INFORMATIONAL_ONLY

    # Turn 3: Tasks Query
    r3 = resolver.resolve_intent("what are my tasks today")
    assert r3.primary_intent in ["TASK_SCHEDULE_QUERY", "SCHEDULE_QUERY", "CALENDAR_TASKS_QUERY", "INFORMATIONAL_QUERY"]

    # Turn 4: Add Reminder / Task
    r4 = resolver.resolve_intent("remind me to call John after lunch")
    assert r4.primary_intent in ["SCHEDULE_REMINDER", "TASK_CREATION", "BOOKKEEPING_REQUEST", "SCHEDULE_ACTION", "INFORMATIONAL_QUERY"]

    # Turn 5: Music Playback Request
    r5 = resolver.resolve_intent("play some upbeat music")
    assert r5.primary_intent in ["PLAY_MUSIC", "PLAY_TRACK"]
    assert r5.category == IntentCategory.CLEAR_EXECUTABLE


def test_scenario1_variations(agent_system):
    _, resolver = agent_system
    # Variations on greeting and briefing
    assert resolver.resolve_intent("good morning animus").category == IntentCategory.INFORMATIONAL_ONLY
    assert resolver.resolve_intent("how is the weather outside").category == IntentCategory.INFORMATIONAL_ONLY
    assert resolver.resolve_intent("what did I have scheduled for this morning").category == IntentCategory.INFORMATIONAL_ONLY
    assert resolver.resolve_intent("put on something to get me moving").primary_intent == "PLAY_MUSIC"


# =============================================================================
# SCENARIO 2: Streaming / Cinema Mode Invocations ("want to watch prime")
# =============================================================================

def test_scenario2_want_to_watch_prime_and_streaming(agent_system):
    agent, resolver = agent_system

    # User explicitly: "want to watch prime"
    r_prime = resolver.resolve_intent("want to watch prime")
    assert r_prime.primary_intent in ["LAUNCH_PRIME", "START_CINEMA_ENTERTAINMENT"]
    assert r_prime.category == IntentCategory.CLEAR_EXECUTABLE
    assert "PROJECTOR" in r_prime.target_subsystems
    assert "FIRE_TV" in r_prime.target_subsystems

    # Variations: "watch netflix", "watch hotstar", "feel like watching something on youtube"
    r_netflix = resolver.resolve_intent("watch netflix")
    assert r_netflix.primary_intent in ["LAUNCH_NETFLIX", "START_CINEMA_ENTERTAINMENT"]

    r_hotstar = resolver.resolve_intent("watch hotstar")
    assert r_hotstar.primary_intent in ["LAUNCH_HOTSTAR", "START_CINEMA_ENTERTAINMENT"]

    r_yt = resolver.resolve_intent("feel like watching something on youtube")
    assert r_yt.primary_intent in ["PLAY_YOUTUBE", "LAUNCH_YOUTUBE", "START_CINEMA_ENTERTAINMENT"]


def test_scenario2_cinema_plan_synthesis(agent_system):
    agent, _ = agent_system
    plan = agent._synthesize_canonical_plan("want to watch prime", None)
    assert plan is not None
    capabilities = [s.capability for s in plan.steps]
    # Invariant: Projector wake (120s tolerance), HDMI1, Fire TV wake, Direct Provider, Soundbar to Fire TV
    assert "PROJECTOR_POWER_WAKE" in capabilities
    assert "PROJECTOR_SWITCH_HDMI1" in capabilities
    assert "FIRE_TV_POWER_WAKE" in capabilities
    assert "SOUNDBAR_ROUTE_TO_FIRE_TV" in capabilities


# =============================================================================
# SCENARIO 3: Scheduled / Timed Hardware Actions ("turn AC off after 30 sec")
# =============================================================================

def test_scenario3_scheduled_actions(agent_system):
    _, resolver = agent_system

    # Explicit user test: "turn AC off after 30 sec"
    r_ac_30s = resolver.resolve_intent("turn AC off after 30 sec")
    assert r_ac_30s.primary_intent == "SCHEDULE_ACTION"
    assert r_ac_30s.extracted_parameters.get("delay_seconds") == 30.0
    assert r_ac_30s.extracted_parameters.get("action_type") == "AC_POWER_OFF"

    # Variation: "turn off ac in 15 seconds"
    r_ac_15s = resolver.resolve_intent("turn off ac in 15 seconds")
    assert r_ac_15s.primary_intent == "SCHEDULE_ACTION"
    assert r_ac_15s.extracted_parameters.get("delay_seconds") == 15.0

    # Variation: "set ac to 22 in 5 minutes"
    r_ac_5m = resolver.resolve_intent("set ac to 22 in 5 minutes")
    assert r_ac_5m.primary_intent == "SCHEDULE_ACTION"
    assert r_ac_5m.extracted_parameters.get("delay_seconds") == 300.0
    assert r_ac_5m.extracted_parameters.get("temperature") == 22

    # Variation: "turn off projector in 10 minutes"
    r_proj_10m = resolver.resolve_intent("turn off projector in 10 minutes")
    assert r_proj_10m.primary_intent == "SCHEDULE_ACTION"
    assert r_proj_10m.extracted_parameters.get("delay_seconds") == 600.0


# =============================================================================
# SCENARIO 4: Thermal Comfort & "I feel chilly" Mode Transition
# =============================================================================

def test_scenario4_feel_chilly_transitions_to_fan(agent_system):
    _, resolver = agent_system

    # User test: "I feel chilly" -> Fan mode
    r1 = resolver.resolve_intent("I feel chilly")
    assert r1.primary_intent == "SET_AC_MODE"
    assert r1.extracted_parameters.get("mode") == "FAN"

    # Variations: "feeling chilly", "it's chilly in here", "a bit chilly"
    assert resolver.resolve_intent("feeling chilly").extracted_parameters.get("mode") == "FAN"
    assert resolver.resolve_intent("it's chilly in here").extracted_parameters.get("mode") == "FAN"
    assert resolver.resolve_intent("it's a bit chilly").extracted_parameters.get("mode") == "FAN"

    # Freezing case: powers off AC
    r_freeze = resolver.resolve_intent("it's freezing in here")
    assert r_freeze.primary_intent == "SEMANTIC_ROOM_FREEZING"


# =============================================================================
# SCENARIO 5: Multi-Turn AC Conversational Cycles
# =============================================================================

def test_scenario5_ac_follow_up_cycle(agent_system):
    agent, _ = agent_system

    # Turn 1: Power on
    resp1 = agent.interact("turn on the ac")
    assert resp1.understood_intent == "AC_POWER_ON"

    # Turn 2: Mode change to COOL
    resp2 = agent.interact("put it on cool mode")
    assert resp2.understood_intent == "SET_AC_MODE"

    # Turn 3: Set absolute temperature ("set it to 22" in AC conversation context)
    resp3 = agent.interact("set it to 22")
    assert resp3.understood_intent == "SET_AC_TEMPERATURE"

    # Turn 4: Relative delta warming
    resp4 = agent.interact("make it a little warmer")
    assert resp4.understood_intent in ["SET_AC_WARMER", "SET_AC_TEMPERATURE"]

    # Turn 5: Switch to fan mode
    resp5 = agent.interact("switch to fan mode")
    assert resp5.understood_intent == "SET_AC_MODE"


# =============================================================================
# SCENARIO 6: PC Music Playback & Soundbar Audio Ownership Invariant
# =============================================================================

def test_scenario6_play_song_routes_to_pc(agent_system):
    _, resolver = agent_system

    # Direct song requests
    r1 = resolver.resolve_intent("play Zara Zara")
    assert r1.primary_intent == "PLAY_TRACK"
    assert "PC" in r1.target_subsystems or "MEDIA" in r1.target_subsystems

    r2 = resolver.resolve_intent("play Sunday Suspense on volume 30")
    assert r2.primary_intent == "PLAY_TRACK"
    assert r2.extracted_parameters.get("volume") == 30

    r3 = resolver.resolve_intent("play Kesariya")
    assert r3.primary_intent == "PLAY_TRACK"

    # Explicit audio routing commands
    r_route = resolver.resolve_intent("switch to bedroom speaker")
    assert r_route.primary_intent == "SOUNDBAR_ROUTE_TO_PC"

    r_route_pc = resolver.resolve_intent("switch audio to pc")
    assert r_route_pc.primary_intent == "SOUNDBAR_ROUTE_TO_PC"


# =============================================================================
# SCENARIO 7: Bare "Play" / "Resume" State Awareness
# =============================================================================

def test_scenario7_bare_play_paused_vs_idle(agent_system):
    _, resolver = agent_system

    # Case A: Media is paused -> "play" should resume playback
    now = time.time()
    mock_paused_state = RoomState(
        timestamp=now,
        audio_stream=AudioStreamState(
            playback_state=StateField(value=MediaPlaybackState.PAUSED.value, provenance=Provenance.OBSERVED, updated_at=now),
            active_producer=StateField(value=ActiveAudioProducer.PC.value, provenance=Provenance.OBSERVED, updated_at=now)
        )
    )
    r_paused = resolver.resolve_intent("play", room_state=mock_paused_state)
    assert r_paused.primary_intent == "RESUME_MEDIA"
    assert r_paused.category == IntentCategory.CLEAR_EXECUTABLE

    # Case B: Media is idle / not paused -> "play" should ask for song preference
    mock_idle_state = RoomState(
        timestamp=now,
        audio_stream=AudioStreamState(
            playback_state=StateField(value=MediaPlaybackState.IDLE.value, provenance=Provenance.OBSERVED, updated_at=now),
            active_producer=StateField(value=ActiveAudioProducer.NONE.value, provenance=Provenance.OBSERVED, updated_at=now)
        )
    )
    r_idle = resolver.resolve_intent("play", room_state=mock_idle_state)
    assert r_idle.primary_intent == "PLAY_TRACK"
    assert r_idle.requires_followup is True
    assert "What would you like me to play" in r_idle.followup_question

    # Case C: Explicit "resume" always resumes
    r_resume = resolver.resolve_intent("resume")
    assert r_resume.primary_intent == "RESUME_MEDIA"


# =============================================================================
# SCENARIO 8: Netflix Streaming Priority & Media Output Pause Logic
# =============================================================================

def test_scenario8_want_to_watch_something_on_netflix_synthesis(agent_system):
    agent, resolver = agent_system

    # Test Intent Resolution
    r_net = resolver.resolve_intent("I want to watch something on Netflix")
    assert r_net.primary_intent in ["LAUNCH_NETFLIX", "START_CINEMA_ENTERTAINMENT"]

    # Test Plan Synthesis: Must include 5 full steps (including FIRE_TV_MEDIA_DIRECT_PROVIDER for netflix)
    plan = agent._synthesize_canonical_plan("I want to watch something on Netflix", None)
    assert plan is not None
    assert plan.intent == "LAUNCH_NETFLIX"
    assert len(plan.steps) == 5
    caps = [s.capability for s in plan.steps]
    assert caps == [
        "PROJECTOR_POWER_WAKE",
        "PROJECTOR_SWITCH_HDMI1",
        "FIRE_TV_POWER_WAKE",
        "FIRE_TV_MEDIA_DIRECT_PROVIDER",
        "SOUNDBAR_ROUTE_TO_FIRE_TV"
    ]
    assert plan.steps[3].parameters.get("provider") == "netflix"


def test_scenario8_pause_media_output_logic(agent_system):
    agent, resolver = agent_system

    # Intent Resolution
    r_pause = resolver.resolve_intent("pause")
    assert r_pause.primary_intent == "PAUSE_MEDIA"
    assert r_pause.category == IntentCategory.CLEAR_EXECUTABLE

    # Plan Synthesis with Active Fire TV
    now = time.time()
    mock_ftv_state = RoomState(
        timestamp=now,
        audio_stream=AudioStreamState(
            playback_state=StateField(value=MediaPlaybackState.PLAYING.value, provenance=Provenance.OBSERVED, updated_at=now),
            active_producer=StateField(value=ActiveAudioProducer.FIRE_TV.value, provenance=Provenance.OBSERVED, updated_at=now)
        )
    )
    plan_ftv = agent._synthesize_canonical_plan("pause", mock_ftv_state)
    assert plan_ftv is not None
    assert len(plan_ftv.steps) == 1
    assert plan_ftv.steps[0].capability == "FIRE_TV_MEDIA_PAUSE"

    # Plan Synthesis with Active PC Music
    mock_pc_state = RoomState(
        timestamp=now,
        audio_stream=AudioStreamState(
            playback_state=StateField(value=MediaPlaybackState.PLAYING.value, provenance=Provenance.OBSERVED, updated_at=now),
            active_producer=StateField(value=ActiveAudioProducer.PC.value, provenance=Provenance.OBSERVED, updated_at=now)
        )
    )
    plan_pc = agent._synthesize_canonical_plan("pause", mock_pc_state)
    assert plan_pc is not None
    assert len(plan_pc.steps) == 1
    assert plan_pc.steps[0].capability == "PC_MEDIA_PLAY_PAUSE"


# =============================================================================
# SCENARIO 9: YouTube Song Playback & Output-Aware Pause Execution
# =============================================================================

def test_scenario9_youtube_song_play_and_pause_execution(agent_system):
    agent, resolver = agent_system

    # Mock orchestrator and player on agent
    mock_orch = MagicMock()
    mock_player = MagicMock()
    mock_player.get_status.return_value = {
        "status": "PLAYING",
        "playback_status": "PLAYING",
        "title": "Kesariya",
        "artist": "Arijit Singh",
        "paused": False
    }
    mock_orch.player = mock_player
    mock_orch.safe_pause.return_value = True
    mock_orch.safe_resume.return_value = True
    agent.orchestrator = mock_orch

    # 1. When YouTube song is actively playing on PC, agent.interact("pause") calls orchestrator.safe_pause()
    res_pause = agent.interact("pause")
    assert res_pause.understood_intent == "PAUSE_MEDIA"
    assert res_pause.action_taken is True
    assert "Paused the media" in res_pause.agent_message or "paused" in res_pause.agent_message.lower()
    assert mock_orch.safe_pause.call_count == 1
    assert res_pause.physical_audits[0].target == "PC"
    assert res_pause.physical_audits[0].capability == "PC_MEDIA_PLAY_PAUSE"

    # 2. When YouTube song is paused, agent.interact("resume") calls orchestrator.safe_resume()
    mock_player.get_status.return_value = {
        "status": "PAUSED",
        "playback_status": "PAUSED",
        "title": "Kesariya",
        "artist": "Arijit Singh",
        "paused": True
    }
    res_resume = agent.interact("resume")
    assert res_resume.understood_intent == "RESUME_MEDIA"
    assert res_resume.action_taken is True
    assert "Resumed playback" in res_resume.agent_message or "resuming" in res_resume.agent_message.lower()
    assert mock_orch.safe_resume.call_count == 1
    assert res_resume.physical_audits[0].target == "PC"
    assert res_resume.physical_audits[0].capability == "PC_MEDIA_PLAY_PAUSE"


