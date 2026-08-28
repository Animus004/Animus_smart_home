"""
Unit Test Suite for EmpathicReasoningEngine:
Verifies classification and compound action generation for:
- Headache / Migraine relief
- Departure / Going to work
- Chill vibe / Relax mode
- Deep focus / Study mode
- Party mode
"""

import pytest
from agent.empathic_engine import EmpathicReasoningEngine


def test_headache_relief_plan():
    engine = EmpathicReasoningEngine()
    plan = engine.evaluate_empathic_intent("Sonia, I have a terrible migraine right now", user_name="Sayan")
    assert plan is not None
    assert plan.scenario == "HEADACHE_RELIEF"
    assert plan.ac_action["temp"] == 25
    assert plan.ac_action["fan"] == "LOW"
    assert plan.projector_action["power"] is False
    assert plan.scheduled_followup_minutes == 45
    assert "rest" in plan.empathy_speech.lower()


def test_departure_going_to_work_plan():
    engine = EmpathicReasoningEngine()
    plan = engine.evaluate_empathic_intent("I'm going to work, bye Sonia", user_name="Sayan")
    assert plan is not None
    assert plan.scenario == "DEPARTURE_ALL_OFF"
    assert plan.ac_action["power"] is False
    assert plan.projector_action["action"] == "power_off"
    assert plan.pc_action["action"] == "lock"


def test_chill_vibe_plan():
    engine = EmpathicReasoningEngine()
    plan = engine.evaluate_empathic_intent("Can you set a chill vibe for me?", user_name="Sayan")
    assert plan is not None
    assert plan.scenario == "CHILL_VIBE"
    assert plan.ac_action["temp"] == 23
    assert "lofi" in plan.audio_action["query"].lower()


def test_deep_focus_study_plan():
    engine = EmpathicReasoningEngine()
    plan = engine.evaluate_empathic_intent("It's study time, let me focus", user_name="Sayan")
    assert plan is not None
    assert plan.scenario == "DEEP_FOCUS"
    assert plan.ac_action["temp"] == 24
    assert "alpha waves" in plan.audio_action["query"].lower()


def test_party_hype_plan():
    engine = EmpathicReasoningEngine()
    plan = engine.evaluate_empathic_intent("Let's activate party mode!", user_name="Sayan")
    assert plan is not None
    assert plan.scenario == "PARTY_HYPE"
    assert plan.ac_action["temp"] == 21
    assert plan.ac_action["fan"] == "HIGH"
    assert plan.audio_action["volume"] == 50


def test_unmatched_regular_utterance():
    engine = EmpathicReasoningEngine()
    plan = engine.evaluate_empathic_intent("What is the capital of France?")
    assert plan is None
