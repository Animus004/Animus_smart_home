"""
Comprehensive Full-Cycle Test Battery for Animus Smart Room:
1. AC Full Cycle of Every Command (Power, Temp, Modes, Fan Speeds, Safety Guards, Scheduling).
2. Movie Time Full Cycle of Every Command (Cinema Prep, Content Launch, Pause/Resume, Volume/Mute, Exit).
"""

import pytest
from unittest.mock import MagicMock, patch

from agent.core import AnimusPersonalAgent
from agent.intent_resolver import IntentResolver, IntentCategory
from agent.models import UserProfile, UserIdentity, MoodVibe
from agent.memory import AgentMemoryStore
from agent.context_buffer import ConversationContextBuffer
from room_state.models import (
    RoomState, StateField, AcState, IrHubState, PcState,
    ProjectorState, FireTvState, SoundbarState, AudioStreamState
)
from capability_registry import UnifiedCapabilityRegistry


@pytest.fixture
def mock_profile():
    p = UserProfile()
    p.identity = UserIdentity(name="Sayan", preferred_address="sir")
    return p


@pytest.fixture
def mock_registry():
    return UnifiedCapabilityRegistry()


@pytest.fixture
def mock_memory():
    return AgentMemoryStore()


@pytest.fixture
def mock_context_buffer():
    return ConversationContextBuffer()


@pytest.fixture
def intent_resolver(mock_profile, mock_registry, mock_memory, mock_context_buffer):
    return IntentResolver(
        user_profile=mock_profile,
        registry=mock_registry,
        memory=mock_memory,
        context_buffer=mock_context_buffer
    )


# =============================================================================
# SCENARIO 1: AC FULL CYCLE OF EVERY COMMAND
# =============================================================================

class TestAcFullCycle:
    """Rigorous verification of all AC command variations and safety limits."""

    def test_1_ac_power_on_variations(self, intent_resolver):
        queries = [
            "turn on the ac", "turn on ac", "fire up the ac",
            "crank the ac", "flick on the ac", "chill the room", "kindly turn on the ac"
        ]
        for q in queries:
            res = intent_resolver.resolve_intent(q)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {q}"
            assert res.primary_intent == "AC_POWER_ON", f"Failed on {q}"
            assert res.target_subsystems == ["AC"]

    def test_2_ac_temperature_setpoints(self, intent_resolver):
        temp_cases = [
            ("dial the temp to 22", 22),
            ("set the AC to 24", 24),
            ("drop the temperature to 21", 21),
            ("make it chilly at 20", 20),
            ("settle the temp at 25", 25),
            ("tune the ac to 23", 23),
            ("kindly set the temp to 26", 26),
        ]
        for query, expected_t in temp_cases:
            res = intent_resolver.resolve_intent(query)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {query}"
            assert res.primary_intent == "SET_AC_TEMPERATURE", f"Failed on {query}"
            assert res.extracted_parameters.get("temperature") == expected_t

    def test_3_ac_modes_full_cycle(self, intent_resolver):
        mode_cases = [
            ("set AC to cool mode", "COOL"),
            ("switch to auto mode", "AUTO"),
            ("put the AC in dry mode", "DRY"),
            ("set AC to fan mode", "FAN"),
            ("put AC on auto", "AUTO"),
            ("cool mode on AC", "COOL"),
        ]
        for query, expected_m in mode_cases:
            res = intent_resolver.resolve_intent(query)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {query}"
            assert res.primary_intent == "SET_AC_MODE", f"Failed on {query}"
            assert res.extracted_parameters.get("mode") == expected_m

    def test_4_ac_fan_speeds_full_cycle(self, intent_resolver):
        fan_cases = [
            ("set AC fan to high", "HIGH"),
            ("set ac fan speed to medium", "MEDIUM"),
            ("put ac fan on low", "LOW"),
            ("switch ac fan to auto", "AUTO"),
            ("blower speed high", "HIGH"),
        ]
        for query, expected_spd in fan_cases:
            res = intent_resolver.resolve_intent(query)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {query}"
            assert res.primary_intent == "SET_AC_FAN_SPEED", f"Failed on {query}"
            assert res.extracted_parameters.get("fan_speed") == expected_spd

    def test_5_ac_safety_out_of_bounds(self, intent_resolver):
        unsafe_queries = [
            "set AC temperature to 45",
            "set AC to 50 degrees",
            "drop temperature to 10 degrees",
            "make it 12 degrees"
        ]
        for q in unsafe_queries:
            res = intent_resolver.resolve_intent(q)
            assert res.category == IntentCategory.UNSAFE_NOT_AUTHORIZED, f"Safety guard failed on {q}"

    def test_6_ac_scheduled_actions(self, intent_resolver):
        res1 = intent_resolver.resolve_intent("turn off the AC in 10 minutes")
        assert res1.category == IntentCategory.CLEAR_EXECUTABLE
        assert res1.primary_intent == "SCHEDULE_ACTION"
        assert res1.extracted_parameters.get("action_type") == "AC_POWER_OFF"
        assert res1.extracted_parameters.get("delay_seconds") == 600.0

        res2 = intent_resolver.resolve_intent("set AC to 25 in 5 minutes")
        assert res2.category == IntentCategory.CLEAR_EXECUTABLE
        assert res2.primary_intent == "SCHEDULE_ACTION"
        assert res2.extracted_parameters.get("action_type") == "SET_AC_TEMPERATURE"
        assert res2.extracted_parameters.get("temperature") == 25
        assert res2.extracted_parameters.get("delay_seconds") == 300.0

    def test_7_ac_power_off_variations(self, intent_resolver):
        queries = [
            "turn off the ac", "turn the ac off", "switch off the ac",
            "kill the ac", "flick off the ac", "shut down the ac", "power down the ac"
        ]
        for q in queries:
            res = intent_resolver.resolve_intent(q)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {q}"
            assert res.primary_intent == "AC_POWER_OFF", f"Failed on {q}"


# =============================================================================
# SCENARIO 2: MOVIE TIME FULL CYCLE OF EVERY COMMAND
# =============================================================================

class TestMovieTimeFullCycle:
    """Rigorous verification of full Cinema and Movie Mode lifecycle."""

    def test_1_movie_mode_entry_variations(self, intent_resolver):
        queries = [
            "let's watch a movie", "lets watch a movie", "movie mode",
            "prepare the room for a movie", "fire up the cinema", "ready the cinema",
            "fancy watching a movie", "pop on a movie", "start cinema setup"
        ]
        for q in queries:
            res = intent_resolver.resolve_intent(q)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {q}"
            assert res.primary_intent == "ENTER_MOVIE_MODE", f"Failed on {q}"
            assert "PROJECTOR" in res.target_subsystems
            assert "SOUNDBAR" in res.target_subsystems

    def test_2_projector_wake_and_illumination(self, intent_resolver):
        queries = [
            "turn on the projector", "wake projector", "fire up the projector",
            "spin up the projector", "illuminate the screen", "light up the screen"
        ]
        for q in queries:
            res = intent_resolver.resolve_intent(q)
            assert res.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed on {q}"
            assert res.primary_intent == "PROJECTOR_POWER_WAKE", f"Failed on {q}"

    def test_3_streaming_app_launches(self, intent_resolver):
        res_netflix = intent_resolver.resolve_intent("Netflix")
        assert res_netflix.primary_intent == "LAUNCH_NETFLIX"
        assert res_netflix.category == IntentCategory.CLEAR_EXECUTABLE

        res_prime = intent_resolver.resolve_intent("Prime Video")
        assert res_prime.primary_intent == "LAUNCH_PRIME_VIDEO"

        res_yt = intent_resolver.resolve_intent("YouTube")
        assert res_yt.primary_intent == "PLAY_YOUTUBE"

    def test_4_in_flight_media_playback_control(self, intent_resolver):
        res_pause = intent_resolver.resolve_intent("pause the movie")
        assert res_pause.primary_intent == "PAUSE_MEDIA"

        res_resume = intent_resolver.resolve_intent("resume the movie")
        assert res_resume.primary_intent in ("RESUME_MEDIA", "MEDIA_RESUME")

    def test_5_audio_and_volume_controls(self, intent_resolver):
        res_vol = intent_resolver.resolve_intent("set volume to 45")
        assert res_vol.primary_intent == "SET_VOLUME"
        assert res_vol.extracted_parameters.get("volume") == 45

        res_mute = intent_resolver.resolve_intent("mute the audio")
        assert res_mute.primary_intent == "MUTE_AUDIO"

        res_unmute = intent_resolver.resolve_intent("unmute the soundbar")
        assert res_unmute.primary_intent == "UNMUTE_AUDIO"

    def test_6_projector_sleep_and_movie_exit(self, intent_resolver):
        sleep_queries = [
            "kill the projector", "kill the screen", "extinguish the screen",
            "shut down the projector", "turn off the projector"
        ]
        for q in sleep_queries:
            res = intent_resolver.resolve_intent(q)
            assert res.primary_intent == "PROJECTOR_POWER_SLEEP", f"Failed on {q}"


# =============================================================================
# SCENARIO 3: END-TO-END AGENT INTERACTION & PERCEPTION BRIEFINGS
# =============================================================================

def test_ac_and_movie_agent_interaction_flow():
    agent = AnimusPersonalAgent()
    agent.user_model.profile.identity.preferred_address = "sir"

    # Step 1: AC power on & setpoint confirmation
    mock_st = RoomState()
    mock_st.ac = AcState(
        power=StateField.observed(True, "TUYA_LOCAL"),
        target_temperature=StateField.observed(23, "TUYA_LOCAL"),
        mode=StateField.observed("COOL", "TUYA_LOCAL")
    )
    mock_st.projector = ProjectorState(
        power=StateField.observed(False, "PROJECTOR_DRIVER")
    )
    mock_st.ir_hub = IrHubState(
        online=StateField.observed(True, "TUYA_LOCAL")
    )
    mock_st.pc = PcState(
        master_volume=StateField.observed(50, "WASAPI_DIRECT")
    )

    resp_ac = agent.interact("Give me a status rundown", room_state=mock_st)
    assert resp_ac.understood_intent == "ROOM_STATUS_BRIEF"
    assert "the AC is active at 23°C in COOL mode" in resp_ac.agent_message

    # Step 2: Cinema Mode Entry
    resp_cinema = agent.interact("Fire up the cinema", room_state=mock_st)
    assert resp_cinema.understood_intent == "ENTER_MOVIE_MODE"
    assert "sir" in resp_cinema.agent_message.lower()
