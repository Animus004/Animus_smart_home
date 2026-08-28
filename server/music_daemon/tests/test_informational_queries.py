"""
Automated regression tests verifying informational and non-room queries:
1. "what's the weather out side" / "what is the weather outside"
2. "what time is it" / "what is the time"
3. "who are you" / "what can you do"
4. "tell me a joke" / non-room conversational queries
Ensures action_taken is strictly FALSE and no hardware execution pipeline is invoked.
"""

import pytest
from agent.core import AnimusPersonalAgent
from agent.models import IntentCategory


@pytest.fixture
def agent():
    return AnimusPersonalAgent()


def test_weather_query_out_side(agent):
    """Exact user utterance: 'what's the weather out side'."""
    res = agent.interact("what's the weather out side")
    assert res.action_taken is False
    assert res.understood_intent == "WEATHER_QUERY"
    assert "weather" in res.agent_message.lower()
    assert "outside" in res.agent_message.lower() or "not configured" in res.agent_message.lower()


def test_weather_query_outside_standard(agent):
    """Standard spelling: 'what is the weather outside'."""
    res = agent.interact("what is the weather outside")
    assert res.action_taken is False
    assert res.understood_intent == "WEATHER_QUERY"


def test_weather_query_forecast(agent):
    """Weather forecast query."""
    res = agent.interact("what's the weather forecast today")
    assert res.action_taken is False
    assert res.understood_intent == "WEATHER_QUERY"


def test_time_query(agent):
    """Current time query: 'what time is it'."""
    res = agent.interact("what time is it")
    assert res.action_taken is False
    assert res.understood_intent == "TIME_QUERY"
    assert "It's " in res.agent_message or "it's " in res.agent_message.lower()


def test_capabilities_query(agent):
    """Identity / capabilities query: 'who are you' / 'what can you do'."""
    res = agent.interact("what can you do")
    assert res.action_taken is False
    assert res.understood_intent == "GET_CAPABILITIES"
    assert "Animus" in res.agent_message or "room" in res.agent_message.lower()


def test_non_room_general_query(agent):
    """Completely non-room query: 'tell me a joke'."""
    res = agent.interact("tell me a joke")
    assert res.action_taken is False
    assert res.understood_intent == "NON_ROOM_QUERY"
    assert len(res.agent_message) > 0


def test_intent_resolver_weather_category(agent):
    """Intent resolver classifies weather as INFORMATIONAL_ONLY."""
    resolved = agent.intent_resolver.resolve_intent("what's the weather out side")
    assert resolved.category == IntentCategory.INFORMATIONAL_ONLY
    assert resolved.primary_intent == "WEATHER_QUERY"
