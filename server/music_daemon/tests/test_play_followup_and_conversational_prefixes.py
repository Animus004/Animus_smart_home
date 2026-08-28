"""
Unit Test Suite for Conversational Play Follow-up and Prefixes:
Verifies:
1. Bare 'play' -> prompts 'What would you like me to play?'
2. Replying with just '<song_title>' resolves the pending follow-up directly to 'play <song_title>'
3. 'I wanted you to play <song_title>' resolves to PLAY_TRACK
4. 'I said play <song_title>' resolves to PLAY_TRACK
5. 'Can you please play <song_title>' resolves to PLAY_TRACK
"""

from unittest.mock import MagicMock
import pytest

from agent.core import AnimusPersonalAgent
from agent.intent_resolver import IntentResolver
from agent.models import UserProfile, IntentCategory
from agent.context_buffer import ConversationContextBuffer
from agent.followup_engine import FollowUpEngine


@pytest.fixture
def agent():
    mock_planner_exec = MagicMock()
    mock_orchestrator = MagicMock()
    mock_orchestrator.safe_play.return_value = (True, {"title": "Starboy"}, None)
    return AnimusPersonalAgent(
        planner_executor=mock_planner_exec,
        orchestrator=mock_orchestrator
    )


def test_bare_play_followed_by_song_title(agent):
    # Turn 1: User says "play"
    r1 = agent.interact("play")
    assert r1.followup_required is True
    assert "what would you like me to play" in r1.agent_message.lower()

    # Turn 2: User responds with just song title "Starboy"
    r2 = agent.interact("Starboy")
    assert r2.action_taken is True
    assert "Starboy" in r2.understood_intent or "PLAY_TRACK" in r2.understood_intent
    # Verify orchestrator played Starboy via safe_play
    assert agent.orchestrator.safe_play.called


def test_conversational_music_prefixes(agent):
    test_phrases = [
        ("I wanted you to play Heat Waves", "Heat Waves"),
        ("I want you to play Starboy", "Starboy"),
        ("I said play Tum Hi Ho", "Tum Hi Ho"),
        ("I meant play Kesariya", "Kesariya"),
        ("Can you please play Believer", "Believer"),
        ("Please play Alak Niranjan", "Alak Niranjan"),
    ]

    resolver = agent.intent_resolver
    for phrase, expected_title in test_phrases:
        intent = resolver.resolve_intent(phrase)
        assert intent.category == IntentCategory.CLEAR_EXECUTABLE, f"Failed for '{phrase}'"
        assert intent.primary_intent == "PLAY_TRACK", f"Failed for '{phrase}'"
        assert intent.extracted_parameters.get("title").lower() == expected_title.lower(), f"Failed for '{phrase}'"
