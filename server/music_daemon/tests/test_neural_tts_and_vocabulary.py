"""
Comprehensive Test Battery for Neural Voice Synthesis, Colloquial & Butler Verb Library,
Long Conversational Utterance Resolution, and Room Status Briefings.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from tts_service import RoomTtsService, TtsState
from agent.intent_resolver import IntentResolver, IntentCategory
from agent.models import UserProfile, UserIdentity
from agent.memory import AgentMemoryStore
from agent.context_buffer import ConversationContextBuffer
from room_state.models import RoomState, StateField, AcState, IrHubState, PcState, ProjectorState
from capability_registry import UnifiedCapabilityRegistry
from agent.core import AnimusPersonalAgent


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


# =========================================================================
# 1. Neural TTS Engine Tests
# =========================================================================

def test_neural_tts_service_configuration(tmp_path):
    cache_dir = str(tmp_path / "tts_cache")
    service = RoomTtsService(
        cache_dir=cache_dir,
        enabled=True,
        voice="en-GB-RyanNeural",
        rate="+5%",
        pitch="+2Hz"
    )
    try:
        cfg = service.get_config()
        assert cfg["enabled"] is True
        assert cfg["voice"] == "en-GB-RyanNeural"
        assert cfg["rate"] == "+5%"
        assert cfg["pitch"] == "+2Hz"
        assert cfg["engine_mode"] == "NEURAL"
        assert cfg["state"] == "IDLE"
        assert cfg["is_speaking"] is False

        # Test dynamic updates
        service.set_voice("en-GB-ThomasNeural")
        service.set_rate("-5%")
        service.set_pitch("-1Hz")
        assert service.voice == "en-GB-ThomasNeural"
        assert service.rate == "-5%"
        assert service.pitch == "-1Hz"
    finally:
        service.shutdown()


def test_neural_tts_synthesis_and_fallback(tmp_path):
    cache_dir = str(tmp_path / "tts_cache")
    service = RoomTtsService(cache_dir=cache_dir, enabled=True)
    out_mp3 = os.path.join(cache_dir, "test_speech.mp3")
    try:
        # 1. Live neural synthesis test
        ok = service.synthesize_to_audio("Good evening, sir. All smart room systems are functioning optimally.", out_mp3)
        assert ok is True
        assert os.path.exists(out_mp3)
        assert os.path.getsize(out_mp3) > 1000

        # 2. Fallback test when neural fails
        with patch.object(service, "_synthesize_neural", return_value=False):
            fallback_file = os.path.join(cache_dir, "fallback_test.wav")
            ok_fb = service.synthesize_to_audio("Testing resilient offline fallback.", fallback_file)
            assert ok_fb is True
            assert os.path.exists(fallback_file)
            assert os.path.getsize(fallback_file) > 1000
    finally:
        service.shutdown()


# =========================================================================
# 2. Colloquial & Butler Verb Library: AC Control
# =========================================================================

@pytest.mark.parametrize("query,expected_intent,expected_temp", [
    ("fire up the ac", "AC_POWER_ON", None),
    ("crank the ac", "AC_POWER_ON", None),
    ("chill the room", "AC_POWER_ON", None),
    ("flick on the ac", "AC_POWER_ON", None),
    ("kindly turn on the ac", "AC_POWER_ON", None),
    ("kill the ac", "AC_POWER_OFF", None),
    ("flick off the ac", "AC_POWER_OFF", None),
    ("shut down the ac", "AC_POWER_OFF", None),
    ("dial the temp to 22", "SET_AC_TEMPERATURE", 22),
    ("drop the temperature to 23", "SET_AC_TEMPERATURE", 23),
    ("chill it to 21", "SET_AC_TEMPERATURE", 21),
    ("crank it down to 20", "SET_AC_TEMPERATURE", 20),
    ("settle it at 24", "SET_AC_TEMPERATURE", 24),
    ("tune the ac to 22", "SET_AC_TEMPERATURE", 22),
    ("kindly set the temp to 23", "SET_AC_TEMPERATURE", 23),
    ("make it chilly at 22", "SET_AC_TEMPERATURE", 22),
])
def test_ac_colloquial_verb_resolution(intent_resolver, query, expected_intent, expected_temp):
    res = intent_resolver.resolve_intent(query)
    assert res.category == IntentCategory.CLEAR_EXECUTABLE
    assert res.primary_intent == expected_intent
    if expected_temp is not None:
        assert res.extracted_parameters.get("temperature") == expected_temp


# =========================================================================
# 3. Colloquial & Butler Verb Library: Cinema & Display Control
# =========================================================================

@pytest.mark.parametrize("query,expected_intent", [
    ("fire up the projector", "PROJECTOR_POWER_WAKE"),
    ("spin up the projector", "PROJECTOR_POWER_WAKE"),
    ("illuminate the screen", "PROJECTOR_POWER_WAKE"),
    ("light up the screen", "PROJECTOR_POWER_WAKE"),
    ("kill the projector", "PROJECTOR_POWER_SLEEP"),
    ("kill the screen", "PROJECTOR_POWER_SLEEP"),
    ("shut down the projector", "PROJECTOR_POWER_SLEEP"),
    ("extinguish the screen", "PROJECTOR_POWER_SLEEP"),
    ("fire up the cinema", "ENTER_MOVIE_MODE"),
    ("ready the cinema", "ENTER_MOVIE_MODE"),
    ("fancy watching a movie", "ENTER_MOVIE_MODE"),
    ("fancy putting on a movie", "ENTER_MOVIE_MODE"),
    ("pop on a movie", "ENTER_MOVIE_MODE"),
    ("roll the film", "ENTER_MOVIE_MODE"),
    ("start cinema setup", "ENTER_MOVIE_MODE"),
])
def test_cinema_and_projector_colloquial_resolution(intent_resolver, query, expected_intent):
    res = intent_resolver.resolve_intent(query)
    assert res.category == IntentCategory.CLEAR_EXECUTABLE
    assert res.primary_intent == expected_intent


# =========================================================================
# 4. Greetings, Salutations & Room Status Briefings
# =========================================================================

@pytest.mark.parametrize("query,expected_intent", [
    ("Good evening Animus", "GREETING"),
    ("Good afternoon Animus", "GREETING"),
    ("Salutations Animus", "GREETING"),
    ("Greetings Animus", "GREETING"),
    ("give me a status rundown", "ROOM_STATUS_BRIEF"),
    ("give me a status brief", "ROOM_STATUS_BRIEF"),
    ("status briefing", "ROOM_STATUS_BRIEF"),
    ("how are we looking today", "ROOM_STATUS_BRIEF"),
    ("how is the room looking", "ROOM_STATUS_BRIEF"),
    ("how's the room holding up", "ROOM_STATUS_BRIEF"),
    ("system status", "ROOM_STATUS_BRIEF"),
    ("all systems check", "ROOM_STATUS_BRIEF"),
    ("give me a quick status briefing", "ROOM_STATUS_BRIEF"),
])
def test_greetings_and_room_status_brief_resolution(intent_resolver, query, expected_intent):
    res = intent_resolver.resolve_intent(query)
    assert res.category == IntentCategory.INFORMATIONAL_ONLY
    assert res.primary_intent == expected_intent


# =========================================================================
# 5. Agent End-to-End Briefing and Interaction Tests
# =========================================================================

def test_room_status_briefing_response():
    agent = AnimusPersonalAgent()
    agent.user_model.profile.identity.preferred_address = "sir"

    # Mock canonical room state
    mock_st = RoomState()
    mock_st.ac = AcState(
        power=StateField.observed(True, "TUYA_LOCAL"),
        target_temperature=StateField.observed(22, "TUYA_LOCAL"),
        mode=StateField.observed("COOL", "TUYA_LOCAL")
    )
    mock_st.projector = ProjectorState(
        power=StateField.observed(False, "PROJECTOR_DRIVER")
    )
    mock_st.ir_hub = IrHubState(
        online=StateField.observed(True, "TUYA_LOCAL")
    )
    mock_st.pc = PcState(
        master_volume=StateField.observed(60, "WASAPI_DIRECT")
    )

    resp = agent.interact("give me a status rundown", room_state=mock_st)
    assert resp.understood_intent == "ROOM_STATUS_BRIEF"
    assert "sir" in resp.agent_message
    assert "the AC is active at 22°C in COOL mode" in resp.agent_message
    assert "the projector is on standby" in resp.agent_message
    assert "the IR hub is online" in resp.agent_message
    assert "audio volume is at 60%" in resp.agent_message
    assert resp.action_taken is False


def test_refined_greeting_response():
    agent = AnimusPersonalAgent()
    agent.user_model.profile.identity.preferred_address = "sir"

    resp = agent.interact("Good evening Animus")
    assert resp.understood_intent == "GREETING"
    assert "sir" in resp.agent_message
    assert "standing by for your command" in resp.agent_message
