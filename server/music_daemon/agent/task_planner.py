"""
Deliberative Task Planner for Animus Smart Room.
Transforms compound user intents and multi-step goals into structured, dependency-linked,
condition-aware execution graphs executed strictly sequentially with physical readback verification.

Strict Physical-Truth Invariants:
1. Planned state != physical state.
2. Memory != current physical truth.
3. Every consequential hardware step performs fresh telemetry readback before mutation and verification.
4. Failed prerequisites strictly block dependent steps.
5. No uncontrolled parallel hardware execution.
6. Bounded deterministic retries only for explicitly safe operations.
"""

from __future__ import annotations
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from agent.task_models import AgentGoal, TaskStep, GoalStatus, StepStatus, GoalType
from agent.models import ResolvedIntent, IntentCategory
from agent.state_memory import FactProvenance, RecentActionMemory
from agent.interaction_result import StateDelta
from room_state.models import RoomState
from planner.models import GeminiStructuredPlan, PlanStep, FailurePolicy, ExecutionMode, OverallExecutionStatus

logger = logging.getLogger("music_daemon.agent.task_planner")


class DeliberativeTaskPlanner:
    """
    Decomposes natural language requests into structured, dependency-aware AgentGoals,
    evaluates preconditions against fresh physical telemetry, and sequentially orchestrates
    plan validation, hardware execution, and physical readback.
    """

    def __init__(self):
        pass

    # =========================================================================
    # 1. GOAL DECOMPOSITION
    # =========================================================================

    def decompose_intent_to_goal(
        self,
        intent: ResolvedIntent,
        utterance: str,
        room_state: Optional[RoomState] = None
    ) -> Optional[AgentGoal]:
        """
        Decomposes compound or multi-step requests into an AgentGoal with ordered TaskSteps.
        Returns None if the utterance is a single direct primitive command rather than a goal.
        """
        lower = utterance.strip().lower()

        # Clean punctuation
        clean_text = re.sub(r'[,—\-\.:!?]', ' ', lower)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        # ---------------------------------------------------------------------
        # A. Cinema / Movie Preparation Goal
        # ---------------------------------------------------------------------
        if any(kw in clean_text for kw in [
            "get the room ready for a movie", "prepare the room for a movie",
            "ready for a movie", "movie mode", "prepare for movie", "cinema mode",
            "get ready for movie", "set up for a movie", "set up movie"
        ]) or intent.primary_intent == "CINEMA_PREPARE":
            goal = AgentGoal(
                user_utterance=utterance,
                normalized_goal="Prepare room for cinema/movie playback",
                goal_type=GoalType.PREPARE_MOVIE,
                steps=[
                    TaskStep(
                        step_id=1,
                        target_subsystem="PROJECTOR",
                        capability="PROJECTOR_POWER_WAKE",
                        requested_parameters={},
                        expected_postcondition="projector.power == True",
                        retry_safe=True,
                        max_retries=1,
                        is_required=True
                    ),
                    TaskStep(
                        step_id=2,
                        target_subsystem="AC",
                        capability="AC_SET_TEMPERATURE",
                        requested_parameters={"temperature": 23},
                        expected_postcondition="ac.target_temperature == 23",
                        retry_safe=True,
                        max_retries=1,
                        is_required=False
                    ),
                    TaskStep(
                        step_id=3,
                        target_subsystem="FIRE_TV",
                        capability="FIRE_TV_MEDIA_PLAY",
                        requested_parameters={},
                        dependencies=[1],
                        preconditions=["PROJECTOR.power == True"],
                        expected_postcondition="environment.room_mode == 'MOVIE'",
                        retry_safe=False,
                        max_retries=0,
                        is_required=False
                    )
                ]
            )
            return goal

        # ---------------------------------------------------------------------
        # B. Sleep / Goodnight Goal
        # ---------------------------------------------------------------------
        if any(kw in clean_text for kw in [
            "prepare the room for sleep", "ready for sleep", "sleep mode",
            "good night", "goodnight", "turn everything off when i'm done",
            "turn everything off when im done", "bedtime mode", "prepare for sleep"
        ]) or intent.primary_intent == "SLEEP_PREPARE":
            goal = AgentGoal(
                user_utterance=utterance,
                normalized_goal="Prepare room for sleep and power down displays",
                goal_type=GoalType.PREPARE_SLEEP,
                steps=[
                    TaskStep(
                        step_id=1,
                        target_subsystem="PROJECTOR",
                        capability="PROJECTOR_POWER_SLEEP",
                        requested_parameters={},
                        expected_postcondition="projector.power == False",
                        retry_safe=True,
                        max_retries=1,
                        is_required=True
                    ),
                    TaskStep(
                        step_id=2,
                        target_subsystem="PC",
                        capability="PC_MEDIA_STOP",
                        requested_parameters={},
                        retry_safe=False,
                        max_retries=0,
                        is_required=False
                    ),
                    TaskStep(
                        step_id=3,
                        target_subsystem="AC",
                        capability="AC_SET_TEMPERATURE",
                        requested_parameters={"temperature": 25},
                        expected_postcondition="ac.target_temperature == 25",
                        retry_safe=True,
                        max_retries=1,
                        is_required=False
                    )
                ]
            )
            return goal

        # ---------------------------------------------------------------------
        # E. Compound 3-Step: "Turn on the projector, set the AC to 23, and start the movie"
        # ---------------------------------------------------------------------
        if "projector" in clean_text and ("movie" in clean_text or "start the movie" in clean_text or "start movie" in clean_text) and ("ac" in clean_text or "cool" in clean_text):
            temp_match = re.search(r'(\d+)', clean_text)
            target_t = int(temp_match.group(1)) if temp_match else 23
            target_t = max(16, min(30, target_t))

            return AgentGoal(
                user_utterance=utterance,
                normalized_goal=f"Turn on projector, set AC to {target_t}°C, and start movie",
                goal_type=GoalType.PREPARE_MOVIE,
                steps=[
                    TaskStep(
                        step_id=1,
                        target_subsystem="PROJECTOR",
                        capability="PROJECTOR_POWER_WAKE",
                        requested_parameters={},
                        expected_postcondition="projector.power == True",
                        retry_safe=True,
                        max_retries=1,
                        is_required=True
                    ),
                    TaskStep(
                        step_id=2,
                        target_subsystem="AC",
                        capability="AC_SET_TEMPERATURE",
                        requested_parameters={"temperature": target_t},
                        expected_postcondition=f"ac.target_temperature == {target_t}",
                        retry_safe=True,
                        max_retries=1,
                        is_required=True
                    ),
                    TaskStep(
                        step_id=3,
                        target_subsystem="FIRE_TV",
                        capability="FIRE_TV_MEDIA_PLAY",
                        requested_parameters={},
                        dependencies=[1],
                        preconditions=["PROJECTOR.power == True"],
                        expected_postcondition="media_playback == 'PLAYING'",
                        retry_safe=False,
                        max_retries=0,
                        is_required=True
                    )
                ]
            )

        # ---------------------------------------------------------------------
        # C. Compound AC + Projector / Projector + AC Goals (2-step)
        # ---------------------------------------------------------------------
        # e.g. "Cool the room to 23 and turn on the projector", "Turn on the projector and set the AC to 25"
        has_proj = any(p in clean_text for p in ["projector", "display", "screen"]) and any(on in clean_text for on in ["turn on", "turn the projector on", "wake", "start the projector"])
        has_ac_temp = re.search(r'(?:(?:ac|temperature|room|cool|temp)\s+(?:to\s+|at\s+)?(\d+)|(?:set\s+(?:the\s+)?ac\s+to\s+)(\d+)|(?:cool\s+(?:the\s+room\s+)?to\s+)(\d+))', clean_text)
        has_ac_rel = any(r in clean_text for r in ["cooler", "warmer", "make the room cooler", "make the room warmer", "cool the room"]) and ("and" in clean_text or "then" in clean_text)

        if has_proj and (has_ac_temp or has_ac_rel):
            target_t = 24
            if has_ac_temp:
                target_t = int(has_ac_temp.group(1) or has_ac_temp.group(2) or has_ac_temp.group(3))
            elif has_ac_rel and room_state and room_state.ac and room_state.ac.target_temperature:
                cur = room_state.ac.target_temperature.value or 24
                target_t = cur - 1 if "cooler" in clean_text or "cool" in clean_text else cur + 1

            target_t = max(16, min(30, target_t))

            # Determine order from utterance
            proj_idx = clean_text.find("projector")
            ac_idx = min([i for i in [clean_text.find("ac"), clean_text.find("cool"), clean_text.find("temperature")] if i != -1] or [999])

            step_proj = TaskStep(
                step_id=1 if proj_idx < ac_idx else 2,
                target_subsystem="PROJECTOR",
                capability="PROJECTOR_POWER_WAKE",
                requested_parameters={},
                expected_postcondition="projector.power == True",
                retry_safe=True,
                max_retries=1
            )
            step_ac = TaskStep(
                step_id=2 if proj_idx < ac_idx else 1,
                target_subsystem="AC",
                capability="AC_SET_TEMPERATURE",
                requested_parameters={"temperature": target_t},
                expected_postcondition=f"ac.target_temperature == {target_t}",
                retry_safe=True,
                max_retries=1
            )

            steps = [step_proj, step_ac] if proj_idx < ac_idx else [step_ac, step_proj]
            return AgentGoal(
                user_utterance=utterance,
                normalized_goal=f"Turn on projector and set AC to {target_t}°C",
                goal_type=GoalType.COOL_AND_PROJECTOR,
                steps=steps
            )

        # ---------------------------------------------------------------------
        # D. Conditional Goal Execution
        # ---------------------------------------------------------------------
        # "If the projector is off, turn it on" / "Turn on the projector if it's off"
        if ("projector" in clean_text or "it" in clean_text) and ("if" in clean_text or "don't change" in clean_text or "dont change" in clean_text or "only" in clean_text):
            if "if it is off" in clean_text or "if its off" in clean_text or "if off" in clean_text or "if it's off" in lower or "if the projector is off" in clean_text or "don't change the projector if it's already on" in lower or "dont change the projector if its already on" in clean_text:
                return AgentGoal(
                    user_utterance=utterance,
                    normalized_goal="Conditional Projector Wake (if powered off)",
                    goal_type=GoalType.CONDITIONAL_CONTROL,
                    steps=[
                        TaskStep(
                            step_id=1,
                            target_subsystem="PROJECTOR",
                            capability="PROJECTOR_POWER_WAKE",
                            requested_parameters={},
                            condition_expr="PROJECTOR.power != True",
                            expected_postcondition="projector.power == True",
                            retry_safe=True,
                            max_retries=1
                        )
                    ]
                )

            # "If the AC is above 24, set it to 24"
            ac_cond_match = re.search(r'if\s+(?:the\s+)?ac\s+is\s+above\s+(\d+)\s*(?:,\s*|\s+then\s+|\s+)?set\s+(?:it\s+to\s+)?(\d+)', clean_text)
            if ac_cond_match:
                thresh = int(ac_cond_match.group(1))
                target = int(ac_cond_match.group(2))
                return AgentGoal(
                    user_utterance=utterance,
                    normalized_goal=f"Conditional AC Temperature (set to {target}°C if above {thresh}°C)",
                    goal_type=GoalType.CONDITIONAL_CONTROL,
                    steps=[
                        TaskStep(
                            step_id=1,
                            target_subsystem="AC",
                            capability="AC_SET_TEMPERATURE",
                            requested_parameters={"temperature": target},
                            condition_expr=f"AC.target_temperature > {thresh}",
                            expected_postcondition=f"ac.target_temperature == {target}",
                            retry_safe=True,
                            max_retries=1
                        )
                    ]
                )

        return None

    # =========================================================================
    # 2. GOAL EXECUTION ORCHESTRATION ENGINE
    # =========================================================================

    def execute_goal(
        self,
        goal: AgentGoal,
        room_state_aggregator: Optional[RoomStateAggregator],
        planner_executor: Any,
        context_buffer: Optional[ConversationContextBuffer] = None,
        on_step_callback: Optional[Callable[[TaskStep], None]] = None
    ) -> AgentGoal:
        """
        Executes an AgentGoal deterministically and strictly sequentially.
        """
        goal.status = GoalStatus.EXECUTING
        status_map: Dict[int, StepStatus] = {}

        logger.info(f"[TASK_PLANNER] Executing Goal '{goal.goal_id}' ({goal.normalized_goal}) with {len(goal.steps)} step(s).")

        for step in goal.steps:
            step.status = StepStatus.READY

            # 1. Dependency Check
            if not step.is_dependency_satisfied(status_map):
                failed_deps = [d for d in step.dependencies if status_map.get(d) in (StepStatus.FAILED, StepStatus.BLOCKED, StepStatus.CANCELLED)]
                step.status = StepStatus.BLOCKED
                step.failure_reason = f"Blocked by failed or cancelled dependency steps: {failed_deps}"
                status_map[step.step_id] = StepStatus.BLOCKED
                logger.warning(f"[TASK_PLANNER] Step {step.step_id} ({step.capability}) BLOCKED due to failed dependencies {failed_deps}.")
                if on_step_callback:
                    on_step_callback(step)
                continue

            # 2. Fetch Fresh Live Physical Telemetry (Non-negotiable)
            current_state = None
            if room_state_aggregator:
                current_state = room_state_aggregator.get_room_state(force_refresh=True)

            # 3. Precondition Evaluation & Conditional Branching
            if step.condition_expr and not self._evaluate_condition(step.condition_expr, current_state):
                step.status = StepStatus.SKIPPED_ALREADY_SATISFIED
                step.physical_readback = {"skipped_reason": f"Condition '{step.condition_expr}' evaluated to False."}
                status_map[step.step_id] = StepStatus.SKIPPED_ALREADY_SATISFIED
                logger.info(f"[TASK_PLANNER] Step {step.step_id} ({step.capability}) skipped because condition '{step.condition_expr}' is False.")
                if on_step_callback:
                    on_step_callback(step)
                continue

            # 4. Idempotency Check (Safe Skipping of already satisfied physical states)
            if self._is_step_already_satisfied(step, current_state):
                step.status = StepStatus.SKIPPED_ALREADY_SATISFIED
                step.physical_readback = {"already_satisfied": True}
                status_map[step.step_id] = StepStatus.SKIPPED_ALREADY_SATISFIED
                logger.info(f"[TASK_PLANNER] Step {step.step_id} ({step.capability}) already physically satisfied in live telemetry. Skipping safely.")
                if on_step_callback:
                    on_step_callback(step)
                continue

            # 5. Execute Step Hardware Action
            step.status = StepStatus.EXECUTING
            step.started_at = time.time()

            exec_success, readback_data, err_reason = self._execute_atomic_step(
                step=step,
                current_state=current_state,
                planner_executor=planner_executor
            )

            # 6. Bounded Safe Retry Handling
            if not exec_success and step.retry_safe and step.retries_attempted < step.max_retries:
                step.retries_attempted += 1
                logger.warning(f"[TASK_PLANNER] Step {step.step_id} failed. Attempting bounded retry {step.retries_attempted}/{step.max_retries}...")
                if room_state_aggregator:
                    current_state = room_state_aggregator.get_room_state(force_refresh=True)

                exec_success, readback_data, err_reason = self._execute_atomic_step(
                    step=step,
                    current_state=current_state,
                    planner_executor=planner_executor
                )

            # 7. Record Step Outcome
            step.completed_at = time.time()
            if exec_success:
                step.status = StepStatus.VERIFIED
                step.execution_result = {"success": True}
                step.physical_readback = readback_data
                status_map[step.step_id] = StepStatus.VERIFIED
                logger.info(f"[TASK_PLANNER] Step {step.step_id} ({step.capability}) physically VERIFIED.")

                # Record verified action in session memory
                if context_buffer:
                    context_buffer.last_target_device = step.target_subsystem
                    if hasattr(context_buffer, "session_memory"):
                        delta = None
                        if step.target_subsystem == "AC" and "temperature" in step.requested_parameters:
                            t_req = step.requested_parameters["temperature"]
                            prev_t = current_state.ac.target_temperature.value if current_state and current_state.ac else None
                            delta = StateDelta(
                                subsystem="AC",
                                attribute="target_temperature",
                                previous_value=prev_t,
                                new_value=t_req,
                                verified_value=t_req,
                                delta=(t_req - prev_t) if prev_t is not None else 0
                            )
                        elif step.target_subsystem == "PROJECTOR":
                            pow_req = (step.capability == "PROJECTOR_POWER_WAKE")
                            prev_p = current_state.projector.power.value if current_state and current_state.projector else None
                            delta = StateDelta(
                                subsystem="PROJECTOR",
                                attribute="power",
                                previous_value=prev_p,
                                new_value=pow_req,
                                verified_value=pow_req
                            )

                        action_mem = RecentActionMemory(
                            turn_index=goal.conversation_turn,
                            user_utterance=goal.user_utterance,
                            intent=step.capability,
                            target_subsystem=step.target_subsystem,
                            state_delta=delta,
                            execution_success=True,
                            readback_status="VERIFIED"
                        )
                        context_buffer.session_memory.record_action(action_mem)
            else:
                step.status = StepStatus.FAILED
                step.failure_reason = err_reason or "Hardware execution or readback verification failed."
                status_map[step.step_id] = StepStatus.FAILED
                logger.error(f"[TASK_PLANNER] Step {step.step_id} ({step.capability}) FAILED: {step.failure_reason}")

            if on_step_callback:
                on_step_callback(step)

        # 8. Reconcile Overall Goal Status
        goal.update_overall_status()
        logger.info(f"[TASK_PLANNER] Goal '{goal.goal_id}' completed with status {goal.status}.")

        # 9. Record Goal in Session Memory
        if context_buffer and hasattr(context_buffer, "session_memory"):
            context_buffer.session_memory.record_goal(goal)

        return goal

    # =========================================================================
    # 3. HELPER METHODS: IDEMPOTENCY, CONDITIONS & ATOMIC EXECUTION
    # =========================================================================

    def _is_step_already_satisfied(self, step: TaskStep, room_state: Optional[RoomState]) -> bool:
        """
        Determines whether the target physical state is already satisfied in live telemetry.
        """
        if not room_state:
            return False

        # Projector Power & Source
        if step.target_subsystem.upper() == "PROJECTOR":
            if step.capability in ("PROJECTOR_POWER_WAKE", "PROJECTOR_WAKE", "PROJECTOR_POWER_ON"):
                return room_state.projector.power.value is True
            if step.capability in ("PROJECTOR_POWER_SLEEP", "PROJECTOR_SLEEP", "PROJECTOR_POWER_OFF", "PROJECTOR_POWER_OFF_OEM"):
                return room_state.projector.power.value is False
            if step.capability == "PROJECTOR_SWITCH_HDMI1":
                return getattr(room_state.projector.input_source, "value", None) == "HDMI_1"

        # AC Temperature & Power
        if step.target_subsystem.upper() == "AC":
            if step.capability == "AC_SET_TEMPERATURE":
                target_t = step.requested_parameters.get("temperature")
                return target_t is not None and room_state.ac.target_temperature.value == target_t
            if step.capability == "AC_POWER_ON":
                return room_state.ac.power.value is True
            if step.capability == "AC_POWER_OFF":
                return room_state.ac.power.value is False

        # Fire TV / Media
        if step.target_subsystem.upper() == "FIRE_TV":
            if step.capability in ("FIRE_TV_MEDIA_PLAY", "MEDIA_PLAY"):
                return getattr(room_state.environment.room_mode, "value", None) == "MOVIE"
            if step.capability == "FIRE_TV_POWER_WAKE":
                ftv_pow = getattr(room_state.fire_tv, "power_state", None) or getattr(room_state.fire_tv, "power", None)
                return getattr(ftv_pow, "value", None) in ("AWAKE", "ON", True)
            if step.capability == "FIRE_TV_POWER_SLEEP":
                ftv_pow = getattr(room_state.fire_tv, "power_state", None) or getattr(room_state.fire_tv, "power", None)
                return getattr(ftv_pow, "value", None) in ("ASLEEP", "STANDBY", "OFF", False)


        # Soundbar Ownership
        if step.target_subsystem.upper() == "SOUNDBAR":
            if step.capability == "SOUNDBAR_ROUTE_TO_FIRE_TV":
                return getattr(room_state.soundbar.current_owner, "value", None) == "FIRE_TV"
            if step.capability == "SOUNDBAR_ROUTE_TO_PC":
                return getattr(room_state.soundbar.current_owner, "value", None) == "PC"

        # Media Playback
        if step.target_subsystem.upper() in ("FIRE_TV", "PC", "MEDIA"):
            if step.capability == "PAUSE_MEDIA":
                return getattr(room_state.environment, "room_mode", None) == "PAUSED"

        return False


    def _evaluate_condition(self, condition_expr: str, room_state: Optional[RoomState]) -> bool:
        """
        Safely evaluates condition expression against authoritative RoomState.
        """
        if not room_state:
            return False

        try:
            # PROJECTOR.power != True or PROJECTOR.power == False
            if "PROJECTOR.power" in condition_expr:
                pow_val = room_state.projector.power.value
                if "!=" in condition_expr:
                    return pow_val is not True
                if "==" in condition_expr:
                    return pow_val is True

            # AC.target_temperature > X
            if "AC.target_temperature" in condition_expr:
                cur_t = room_state.ac.target_temperature.value
                if cur_t is None:
                    return False
                match = re.search(r'AC\.target_temperature\s*([><!=]+)\s*(\d+)', condition_expr)
                if match:
                    op, val_str = match.group(1), match.group(2)
                    thresh = int(val_str)
                    if op == ">": return cur_t > thresh
                    if op == ">=": return cur_t >= thresh
                    if op == "<": return cur_t < thresh
                    if op == "<=": return cur_t <= thresh
                    if op == "==": return cur_t == thresh
                    if op == "!=": return cur_t != thresh

            # SOUNDBAR.is_connected != True
            if "SOUNDBAR.is_connected" in condition_expr:
                conn = room_state.soundbar.is_connected.value
                if "!=" in condition_expr:
                    return conn is not True
                if "==" in condition_expr:
                    return conn is True

        except Exception as e:
            logger.warning(f"[TASK_PLANNER] Condition evaluation failed for '{condition_expr}': {e}")
            return False

        return False

    def _execute_atomic_step(
        self,
        step: TaskStep,
        current_state: Optional[RoomState],
        planner_executor: Any
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Builds a GeminiStructuredPlan for the atomic step, validates with PlanValidator,
        and executes with PlanExecutor.
        """
        if not planner_executor:
            return False, None, "PlannerExecutor not configured."

        # Construct single-step declarative plan
        plan = GeminiStructuredPlan(
            intent=step.capability,
            objective_summary=f"Execute {step.capability} on {step.target_subsystem}",
            user_request=f"Goal step {step.step_id}",
            steps=[
                PlanStep(
                    step_id=1,
                    device=step.target_subsystem,
                    capability=step.capability,
                    parameters=step.requested_parameters,
                    execution_mode=ExecutionMode.SEQUENTIAL,
                    on_failure=FailurePolicy.ABORT_PLAN
                )
            ]
        )

        # Validate with PlanValidator
        val_res = planner_executor.validator.validate_plan(plan_input=plan, room_state=current_state)
        if not val_res.valid:
            err_msg = "; ".join([e.message for e in val_res.errors]) if val_res.errors else "Plan validation rejected step."
            return False, None, err_msg

        # Execute through PlanExecutor
        exec_res = planner_executor.execute_plan(val_res)
        is_success = getattr(exec_res, "success", False) or (getattr(exec_res, "overall_status", None) == OverallExecutionStatus.SUCCESS)
        if not is_success:
            return False, None, getattr(exec_res, "failure_reason", "Hardware command failed.")

        # Extract readback info from step results
        readback_info = {"success": True}
        step_list = getattr(exec_res, "step_results", None) or getattr(exec_res, "steps", [])
        if step_list:
            last_step = step_list[0]
            if hasattr(last_step, "readback_result") and last_step.readback_result:
                readback_info = last_step.readback_result
            elif hasattr(last_step, "physical_readback") and last_step.physical_readback:
                readback_info = last_step.physical_readback

        return True, readback_info, None
