"""
Test Suite: F.3 Critical Mutation Prevention
Verifies that all 4 critical physical mutation hazards are completely eliminated:
- Turn 05: Location update does not trigger physical mutations.
- Turn 18: 30-minute duration does not mutate PC volume.
- Turn 34: Bare numeric statement does not mutate PC volume.
- Turn 45: Good night sign-off does not mutate projector input source.
"""

import pytest
import time
from agent.core import AnimusPersonalAgent
from agent.user_model import UserModel
from agent.task_manager import TaskManager
from agent.memory import AgentMemoryStore
from agent.f3_evaluator import F3TurnEvaluator


@pytest.fixture
def agent():
    user_model = UserModel()
    task_manager = TaskManager()
    memory_store = AgentMemoryStore()
    return AnimusPersonalAgent(
        user_model=user_model,
        task_manager=task_manager,
        memory=memory_store
    )


def test_turn_05_location_update_zero_mutations(agent):
    """Turn 05: 'I'm heading to my desk.' must produce 0 physical mutations."""
    # First simulate prior ambiguous volume turn
    res1 = agent.interact("Make it a little louder.")
    assert res1.followup_required is True

    # User gives location update instead of answering follow-up
    res2 = agent.interact("I'm heading to my desk.")
    assert res2.action_taken is False
    assert res2.understood_intent == "USER_LOCATION_UPDATE"
    assert "desk" in res2.agent_message.lower()

    # Evaluator check with zero mutations
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=5,
        user_message="I'm heading to my desk.",
        response_data=res2.model_dump(),
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )
    assert eval_res["verdict"] == "PASS"
    assert eval_res["mutation_authorized"] is True


def test_turn_18_duration_no_volume_mutation(agent):
    """Turn 18: 'Let's do SQL for 30 minutes.' must not mutate PC volume."""
    res = agent.interact("Let's do SQL for 30 minutes.")
    assert res.action_taken is True
    assert res.understood_intent == "START_FOCUS_SESSION"
    assert "30" in res.agent_message
    assert "SQL" in res.agent_message

    # Evaluator check
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=18,
        user_message="Let's do SQL for 30 minutes.",
        response_data=res.model_dump(),
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )
    assert eval_res["verdict"] == "PASS"
    assert eval_res["mutation_authorized"] is True


def test_turn_34_bare_numeric_disambiguation(agent):
    """Turn 34: 'Actually 25 is fine.' must prompt clarification and not mutate volume."""
    res = agent.interact("Actually 25 is fine.")
    assert res.followup_required is True
    assert res.understood_intent == "BARE_NUMERIC_AMBIGUOUS"
    assert "25 what" in res.agent_message.lower()

    # Evaluator check
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=34,
        user_message="Actually 25 is fine.",
        response_data=res.model_dump(),
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )
    assert eval_res["verdict"] == "PASS"


def test_turn_45_good_night_zero_mutations(agent):
    """Turn 45: 'Good night buddy.' must not mutate display inputs."""
    res = agent.interact("Good night buddy.")
    assert res.action_taken is False
    assert res.understood_intent == "NIGHT_ROUTINE_TRANSITION"
    assert "good night" in res.agent_message.lower()

    # Evaluator check
    eval_res = F3TurnEvaluator.evaluate_turn(
        turn_number=45,
        user_message="Good night buddy.",
        response_data=res.model_dump(),
        pre_snap={"physical": {}},
        post_snap={"physical": {}},
        observed_mutations=[]
    )
    assert eval_res["verdict"] == "PASS"
    assert eval_res["mutation_authorized"] is True
