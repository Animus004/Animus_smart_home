"""
Authoritative Routine Engine for Animus Smart Room.
Synthesizes canonical room routines (Movie, Sleep, Wake-Up, Music, Work) into structured,
dependency-linked AgentGoal and TaskStep sequences.

EPISTEMIC INVARIANT:
Routines decompose into deterministic TaskSteps.
Every step evaluates live physical preconditions before dispatch.
Already-satisfied steps are safely skipped without redundant hardware toggling.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from agent.task_models import AgentGoal, TaskStep, GoalType, GoalStatus, StepStatus
from agent.behavior_modes import BehaviorMode

logger = logging.getLogger("music_daemon.agent.routine_engine")


class RoutineEngine:
    """
    Synthesizes and validates canonical multi-device room routines.
    Enforces safe dependency chains, idempotency checks, and mode transitions.
    """

    def create_movie_routine(
        self,
        utterance: str,
        content_title: Optional[str] = None,
        target_temp: int = 23,
        conversation_turn: int = 0
    ) -> AgentGoal:
        """
        Synthesizes the canonical Movie Mode routine:
        1. Projector Power Wake
        2. Projector HDMI 1 Source Switch (dep=[1])
        3. Fire TV Power Wake
        4. Soundbar Route to Fire TV (dep=[3])
        5. AC Set Temperature (target_temp)
        6. (Optional) Fire TV Media Play (only if explicit title provided)
        """
        steps: List[TaskStep] = [
            TaskStep(
                step_id=1,
                target_subsystem="projector",
                capability="PROJECTOR_POWER_WAKE",
                requested_parameters={},
                preconditions=["room_state.projector.power == True"],
                expected_postcondition="projector.power == True",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=2,
                target_subsystem="projector",
                capability="PROJECTOR_SWITCH_HDMI1",
                requested_parameters={"source": "HDMI_1"},
                dependencies=[1],
                preconditions=["room_state.projector.power == True"],
                expected_postcondition="projector.input_source == HDMI_1",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=3,
                target_subsystem="fire_tv",
                capability="FIRE_TV_POWER_WAKE",
                requested_parameters={},
                preconditions=[],
                expected_postcondition="fire_tv.power == True",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=4,
                target_subsystem="soundbar",
                capability="SOUNDBAR_ROUTE_TO_FIRE_TV",
                requested_parameters={},
                dependencies=[3],
                preconditions=["room_state.fire_tv.power == True"],
                expected_postcondition="soundbar.current_owner == FIRE_TV",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=5,
                target_subsystem="ac",
                capability="AC_SET_TEMPERATURE",
                requested_parameters={"temperature": target_temp},
                preconditions=[],
                expected_postcondition=f"ac.target_temperature == {target_temp}",
                retry_safe=True,
                max_retries=1
            )
        ]

        # Only add media playback if user explicitly requested a specific title
        if content_title:
            steps.append(
                TaskStep(
                    step_id=6,
                    target_subsystem="fire_tv",
                    capability="FIRE_TV_MEDIA_PLAY",
                    requested_parameters={"title": content_title},
                    dependencies=[2, 4],
                    preconditions=["room_state.soundbar.current_owner == FIRE_TV"],
                    expected_postcondition="fire_tv.media_state == PLAYING",
                    retry_safe=False,
                    max_retries=0
                )
            )

        goal = AgentGoal(
            user_utterance=utterance,
            normalized_goal=f"Prepare Movie Mode (Target Temp: {target_temp}°C" + (f", Title: '{content_title}'" if content_title else "") + ")",
            goal_type=GoalType.PREPARE_MOVIE,
            steps=steps,
            status=GoalStatus.PLANNING,
            conversation_turn=conversation_turn
        )
        logger.info(f"[ROUTINE_ENGINE] Synthesized Movie routine with {len(steps)} steps.")
        return goal

    def create_sleep_routine(
        self,
        utterance: str,
        sleep_temp: int = 24,
        conversation_turn: int = 0
    ) -> AgentGoal:
        """
        Synthesizes the canonical Sleep Mode routine:
        1. AC Set Sleep Temperature (24°C)
        2. Projector OEM Power Off
        3. Fire TV Power Sleep
        4. Soundbar Route to PC / Disconnect
        """
        steps: List[TaskStep] = [
            TaskStep(
                step_id=1,
                target_subsystem="ac",
                capability="AC_SET_TEMPERATURE",
                requested_parameters={"temperature": sleep_temp},
                preconditions=[],
                expected_postcondition=f"ac.target_temperature == {sleep_temp}",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=2,
                target_subsystem="projector",
                capability="PROJECTOR_POWER_OFF_OEM",
                requested_parameters={},
                preconditions=[],
                expected_postcondition="projector.power == False",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=3,
                target_subsystem="fire_tv",
                capability="FIRE_TV_POWER_SLEEP",
                requested_parameters={},
                preconditions=[],
                expected_postcondition="fire_tv.power == False",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=4,
                target_subsystem="soundbar",
                capability="SOUNDBAR_ROUTE_TO_PC",
                requested_parameters={},
                preconditions=[],
                expected_postcondition="soundbar.current_owner == PC",
                retry_safe=True,
                max_retries=1
            )
        ]

        goal = AgentGoal(
            user_utterance=utterance,
            normalized_goal=f"Prepare Sleep Mode (AC: {sleep_temp}°C, Shutdown Projector & TV)",
            goal_type=GoalType.PREPARE_SLEEP,
            steps=steps,
            status=GoalStatus.PLANNING,
            conversation_turn=conversation_turn
        )
        logger.info(f"[ROUTINE_ENGINE] Synthesized Sleep routine with {len(steps)} steps.")
        return goal

    def create_music_routine(
        self,
        utterance: str,
        query: Optional[str] = None,
        conversation_turn: int = 0
    ) -> AgentGoal:
        """
        Synthesizes the canonical Music routine:
        1. Soundbar Route to PC
        2. PC Audio Play / Stream Resolution (dep=[1])
        """
        steps: List[TaskStep] = [
            TaskStep(
                step_id=1,
                target_subsystem="soundbar",
                capability="SOUNDBAR_ROUTE_TO_PC",
                requested_parameters={},
                preconditions=[],
                expected_postcondition="soundbar.current_owner == PC",
                retry_safe=True,
                max_retries=1
            ),
            TaskStep(
                step_id=2,
                target_subsystem="pc",
                capability="PC_MEDIA_PLAY",
                requested_parameters={"query": query} if query else {},
                dependencies=[1],
                preconditions=["room_state.soundbar.current_owner == PC"],
                expected_postcondition="pc.audio_state == PLAYING",
                retry_safe=False,
                max_retries=0
            )
        ]

        goal = AgentGoal(
            user_utterance=utterance,
            normalized_goal=f"Start Music Playback" + (f" for '{query}'" if query else ""),
            goal_type=GoalType.CUSTOM_GOAL,
            steps=steps,
            status=GoalStatus.PLANNING,
            conversation_turn=conversation_turn
        )
        logger.info(f"[ROUTINE_ENGINE] Synthesized Music routine with {len(steps)} steps.")
        return goal
