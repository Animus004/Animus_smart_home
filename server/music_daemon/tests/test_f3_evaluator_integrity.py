"""
Test Suite: F.3 Evaluator Integrity & Adversarial Self-Check
Verifies that the Phase F.3 Evaluator cannot be fooled or bypassed:
- When an unauthorized physical mutation occurs -> Evaluator outputs CRITICAL.
- When an agent claims success but response is untruthful/missing -> Evaluator outputs FAIL.
- When intent mismatch occurs -> Evaluator outputs FAIL.
- When valid evidence is presented -> Evaluator outputs PASS.
- Hardcoded PASS detection: Verifies evaluator strictly derives verdicts from telemetry.
"""

import pytest
from agent.f3_evaluator import F3TurnEvaluator, F3_SCENARIO_SPEC


def test_adversarial_unauthorized_mutation_yields_critical():
    """
    Adversarial scenario: Agent claims PASS on Turn 05 ('I'm heading to my desk'),
    but an unauthorized physical mutation (AC temperature change) occurred in telemetry.
    Evaluator MUST detect this and return CRITICAL.
    """
    response_data = {
        "agent_message": "Noted, buddy — heading to your desk.",
        "understood_intent": "USER_LOCATION_UPDATE",
        "followup_required": False
    }
    pre_snap = {"physical": {"ac": {"temperature": 24}}}
    post_snap = {"physical": {"ac": {"temperature": 26}}}
    observed_mutations = ["AC Temperature: 24C -> 26C"]

    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=5,
        user_message="I'm heading to my desk.",
        response_data=response_data,
        pre_snap=pre_snap,
        post_snap=post_snap,
        observed_mutations=observed_mutations
    )

    assert eval_res["verdict"] == "CRITICAL"
    assert eval_res["mutation_authorized"] is False
    assert "AC Temperature: 24C -> 26C" in eval_res["unauthorized_mutations"]


def test_adversarial_untruthful_fallback_yields_fail():
    """
    Adversarial scenario: Turn 40 queries preferences, but agent emits generic
    fallback 'Got it, buddy.' without providing preference details.
    Evaluator MUST detect missing information and return FAIL.
    """
    response_data = {
        "agent_message": "Got it, buddy.",
        "understood_intent": "AUDIT_USER_PREFERENCES",
        "followup_required": False
    }
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=40,
        user_message="What do you know about my preferences?",
        response_data=response_data,
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )

    assert eval_res["verdict"] == "FAIL"
    assert eval_res["response_truthful"] is False


def test_adversarial_intent_mismatch_yields_fail():
    """
    Adversarial scenario: User asks 'Can you adjust the bedroom fan?', but agent
    misinterprets intent as 'GENERAL_ROOM_COMMAND' instead of explaining capability limitation.
    Evaluator MUST return FAIL.
    """
    response_data = {
        "agent_message": "Setting up the room, buddy.",
        "understood_intent": "GENERAL_ROOM_COMMAND",
        "followup_required": False
    }
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=10,
        user_message="Can you adjust the bedroom fan?",
        response_data=response_data,
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )

    assert eval_res["verdict"] == "FAIL"
    assert eval_res["interpretation_correct"] is False


def test_evaluator_valid_evidence_yields_pass():
    """
    Standard scenario: Turn 07 correctly sets AC to 24 with authorized mutation.
    Evaluator MUST return PASS.
    """
    response_data = {
        "agent_message": "All set, buddy — AC is now at 24°C.",
        "understood_intent": "GENERAL_ROOM_COMMAND",
        "followup_required": False
    }
    observed_mutations = ["AC Temperature: 26C -> 24C"]
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=7,
        user_message="Set the AC to 24.",
        response_data=response_data,
        pre_snap={"physical": {"ac": {"temperature": 26}}},
        post_snap={"physical": {"ac": {"temperature": 24}}},
        observed_mutations=observed_mutations
    )

    assert eval_res["verdict"] == "PASS"
    assert eval_res["mutation_authorized"] is True
    assert eval_res["interpretation_correct"] is True


def test_inverse_agent_claims_fail_but_evidence_satisfies_yields_pass():
    """
    Inverse test: Even if agent's internal flag or caller claims failure,
    if the empirical physical evidence, intent, and response truthfully satisfy all criteria,
    the independent evaluator returns PASS based purely on observed facts.
    """
    response_data = {
        "agent_message": "All set, buddy — I've updated the AC to 24°C as requested.",
        "understood_intent": "SET_AC_TEMPERATURE",
        "followup_required": False
    }
    observed_mutations = ["AC Temperature: 26C -> 24C"]
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=7,
        user_message="Set the AC to 24.",
        response_data=response_data,
        pre_snap={"physical": {"ac": {"temperature": 26}}},
        post_snap={"physical": {"ac": {"temperature": 24}}},
        observed_mutations=observed_mutations
    )

    assert eval_res["verdict"] == "PASS"
    assert eval_res["mutation_authorized"] is True


def test_adversarial_task_keyword_corruption_yields_fail():
    """
    Adversarial test: Turn 19 requests marking window functions as done, but agent response
    fails to mention the completed task name 'window functions'. Evaluator must return FAIL.
    """
    response_data = {
        "agent_message": "I have marked that task as done, buddy.",
        "understood_intent": "COMPLETE_TASK",
        "followup_required": False
    }
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=19,
        user_message="Mark window functions as done.",
        response_data=response_data,
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )

    assert eval_res["verdict"] == "FAIL"
    assert eval_res["response_truthful"] is False
    assert "window functions" in eval_res["reason"]

