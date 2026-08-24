"""
Deterministic Plan Validator Guard for Animus Smart Room.
Validates untrusted Gemini Structured Plans against authoritative capability definitions,
parameter safety bounds, physical precondition realities, and safety rules before execution.
STRICTLY ZERO eval(), exec(), or hardware execution.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional, Union

from capability_registry import (
    UnifiedCapabilityRegistry,
    CapabilityDefinition,
    CapabilityStatus,
    ParameterType
)
from room_state.models import RoomState, StateField
from room_state.provenance import Provenance
from planner.models import (
    GeminiStructuredPlan,
    PlanStep,
    ValidatedStep,
    ValidationResult
)
from planner.errors import (
    ErrorCode,
    WarningCode,
    PlanValidationErrorDetail,
    PlanValidationWarningDetail
)
from planner.preconditions import (
    RestrictedPreconditionEvaluator,
    PreconditionStatus,
    PreconditionEvaluationResult
)

logger = logging.getLogger("music_daemon.planner.validator")


class PlanValidator:
    """
    Deterministic Safety & Validation Guard.
    Enforces that untrusted generative plans conform strictly to physical constraints,
    verified capability contracts, and authoritative room state before any downstream handling.
    """

    def __init__(self, registry: Optional[UnifiedCapabilityRegistry] = None):
        self.registry = registry or UnifiedCapabilityRegistry()
        self.precondition_evaluator = RestrictedPreconditionEvaluator()

    def validate_plan(
        self,
        plan_input: Union[GeminiStructuredPlan, Dict[str, Any]],
        room_state: Optional[RoomState] = None,
        current_time: Optional[float] = None
    ) -> ValidationResult:
        """
        Main validation pipeline.
        Fails closed on any schema violation, unknown capability, out-of-bounds parameter,
        or unsatisfied precondition.
        """
        errors: List[PlanValidationErrorDetail] = []
        warnings: List[PlanValidationWarningDetail] = []
        validated_steps: List[ValidatedStep] = []
        rejected_steps: List[Dict[str, Any]] = []
        idempotent_step_ids: List[int] = []

        # 1. Parse & Ingest Plan Model
        plan: Optional[GeminiStructuredPlan] = None
        if isinstance(plan_input, GeminiStructuredPlan):
            plan = plan_input
        elif isinstance(plan_input, dict):
            try:
                plan = GeminiStructuredPlan.model_validate(plan_input)
            except Exception as e:
                errors.append(
                    PlanValidationErrorDetail(
                        error_code=ErrorCode.INVALID_PLAN_STRUCTURE,
                        message=f"Plan schema validation failed: {e}"
                    )
                )
                return ValidationResult(
                    valid=False,
                    errors=errors,
                    rejected_steps=[plan_input] if isinstance(plan_input, dict) else []
                )
        else:
            errors.append(
                PlanValidationErrorDetail(
                    error_code=ErrorCode.INVALID_PLAN_STRUCTURE,
                    message=f"Unsupported plan input type: {type(plan_input).__name__}"
                )
            )
            return ValidationResult(valid=False, errors=errors)

        # 2. Check for Duplicate Step IDs
        seen_step_ids = set()
        for step in plan.steps:
            if step.step_id in seen_step_ids:
                errors.append(
                    PlanValidationErrorDetail(
                        error_code=ErrorCode.DUPLICATE_STEP,
                        step_id=step.step_id,
                        capability=step.capability,
                        message=f"Duplicate step_id {step.step_id} detected in plan."
                    )
                )
            seen_step_ids.add(step.step_id)

        # 3. Validate Each Step in Graph
        evaluator = RestrictedPreconditionEvaluator(current_time=current_time)
        simulated_state = room_state.model_copy(deep=True) if room_state is not None else None

        for step in plan.steps:
            step_dict = step.model_dump()
            step_errors: List[PlanValidationErrorDetail] = []
            step_warnings: List[PlanValidationWarningDetail] = []
            is_idempotent_no_op = False

            # A. Capability Existence & Status Check
            cap_def = self.registry.get_capability(step.capability)
            if cap_def is None:
                step_errors.append(
                    PlanValidationErrorDetail(
                        error_code=ErrorCode.UNKNOWN_CAPABILITY,
                        step_id=step.step_id,
                        capability=step.capability,
                        message=f"Capability '{step.capability}' is not registered in the authoritative catalog."
                    )
                )
            elif cap_def.status == CapabilityStatus.UNSUPPORTED_HARDWARE:
                step_errors.append(
                    PlanValidationErrorDetail(
                        error_code=ErrorCode.UNSUPPORTED_CAPABILITY,
                        step_id=step.step_id,
                        capability=step.capability,
                        message=f"Capability '{step.capability}' is unsupported by physical room hardware."
                    )
                )
            elif cap_def.status == CapabilityStatus.DEFERRED_PENDING_IMPLEMENTATION:
                step_errors.append(
                    PlanValidationErrorDetail(
                        error_code=ErrorCode.DEFERRED_CAPABILITY,
                        step_id=step.step_id,
                        capability=step.capability,
                        message=f"Capability '{step.capability}' is deferred pending driver implementation."
                    )
                )

            # B. Parameter Validation
            if cap_def is not None and cap_def.is_executable:
                # Check for unexpected/unknown parameters
                for param_name, param_val in step.parameters.items():
                    if param_name not in cap_def.parameters:
                        step_errors.append(
                            PlanValidationErrorDetail(
                                error_code=ErrorCode.UNKNOWN_PARAMETER,
                                step_id=step.step_id,
                                capability=step.capability,
                                field=param_name,
                                message=f"Parameter '{param_name}' is not accepted by capability '{step.capability}'."
                            )
                        )
                    else:
                        constraint = cap_def.parameters[param_name]
                        # Type & bounds validation
                        if not constraint.validate_value(param_val):
                            if constraint.param_type in (ParameterType.INTEGER, ParameterType.FLOAT):
                                step_errors.append(
                                    PlanValidationErrorDetail(
                                        error_code=ErrorCode.OUT_OF_RANGE,
                                        step_id=step.step_id,
                                        capability=step.capability,
                                        field=param_name,
                                        message=(
                                            f"Parameter '{param_name}' value {param_val} is invalid or out of bounds "
                                            f"[{constraint.min_value}, {constraint.max_value}]."
                                        )
                                    )
                                )
                            elif constraint.param_type in (ParameterType.ENUM, ParameterType.STRING):
                                step_errors.append(
                                    PlanValidationErrorDetail(
                                        error_code=ErrorCode.INVALID_ENUM,
                                        step_id=step.step_id,
                                        capability=step.capability,
                                        field=param_name,
                                        message=(
                                            f"Parameter '{param_name}' value '{param_val}' is not in allowed list "
                                            f"{constraint.allowed_values}."
                                        )
                                    )
                                )
                            else:
                                step_errors.append(
                                    PlanValidationErrorDetail(
                                        error_code=ErrorCode.INVALID_PARAMETER,
                                        step_id=step.step_id,
                                        capability=step.capability,
                                        field=param_name,
                                        message=f"Parameter '{param_name}' value {param_val} failed validation."
                                    )
                                )

                # Check for missing required parameters
                for req_param_name, req_constraint in cap_def.parameters.items():
                    if req_constraint.required and req_param_name not in step.parameters:
                        step_errors.append(
                            PlanValidationErrorDetail(
                                error_code=ErrorCode.MISSING_PARAMETER,
                                step_id=step.step_id,
                                capability=step.capability,
                                field=req_param_name,
                                message=f"Missing required parameter '{req_param_name}' for capability '{step.capability}'."
                            )
                        )

            # C. Preconditions Evaluation (if RoomState provided)
            if simulated_state is not None:
                # Merge explicit step preconditions and capability definition preconditions
                all_preconditions = list(set(step.preconditions + (cap_def.preconditions if cap_def else [])))
                for pre in all_preconditions:
                    res: PreconditionEvaluationResult = evaluator.evaluate(pre, simulated_state)
                    if res.status == PreconditionStatus.INVALID_PRECONDITION:
                        step_errors.append(
                            PlanValidationErrorDetail(
                                error_code=ErrorCode.INVALID_PRECONDITION,
                                step_id=step.step_id,
                                capability=step.capability,
                                message=f"Precondition '{pre}' is malformed: {res.message}"
                            )
                        )
                    elif res.status == PreconditionStatus.UNKNOWN_STATE:
                        step_errors.append(
                            PlanValidationErrorDetail(
                                error_code=ErrorCode.UNKNOWN_STATE,
                                step_id=step.step_id,
                                capability=step.capability,
                                message=f"Precondition '{pre}' cannot be evaluated: target state is UNKNOWN."
                            )
                        )
                    elif res.status == PreconditionStatus.NOT_SATISFIED:
                        step_errors.append(
                            PlanValidationErrorDetail(
                                error_code=ErrorCode.PRECONDITION_FAILED,
                                step_id=step.step_id,
                                capability=step.capability,
                                message=f"Precondition '{pre}' not satisfied in physical RoomState: {res.message}"
                            )
                        )
                    elif res.status == PreconditionStatus.STALE_STATE:
                        step_warnings.append(
                            PlanValidationWarningDetail(
                                warning_code=WarningCode.PRECONDITION_UNCERTAIN_STALE,
                                step_id=step.step_id,
                                capability=step.capability,
                                message=f"Precondition '{pre}' evaluated on STALE telemetry: {res.message}"
                            )
                        )

            # D. Idempotency Check (if RoomState provided and capability is idempotent)
            if simulated_state is not None and cap_def is not None and cap_def.idempotent and len(step_errors) == 0:
                is_idempotent_no_op = self._check_step_idempotency(step, cap_def, simulated_state, current_time)
                if is_idempotent_no_op:
                    idempotent_step_ids.append(step.step_id)
                    step_warnings.append(
                        PlanValidationWarningDetail(
                            warning_code=WarningCode.IDEMPOTENT_SKIPPED,
                            step_id=step.step_id,
                            capability=step.capability,
                            message=f"Step {step.step_id} ({step.capability}) is already satisfied in verified RoomState."
                        )
                    )

            # E. Step Decision & Simulated State Transition
            if len(step_errors) > 0:
                errors.extend(step_errors)
                rejected_steps.append({
                    "step": step_dict,
                    "errors": [e.model_dump() for e in step_errors]
                })
            else:
                warnings.extend(step_warnings)
                validated_steps.append(
                    ValidatedStep(
                        step_id=step.step_id,
                        device=step.device,
                        canonical_capability_id=cap_def.canonical_id if cap_def else step.capability,
                        underlying_capability_name=cap_def.underlying_capability_name if cap_def else "",
                        underlying_controller=cap_def.underlying_controller if cap_def else "",
                        operation_type=cap_def.operation_type if cap_def else cap_def,
                        safety_level=cap_def.safety_level if cap_def else cap_def,
                        parameters=step.parameters,
                        priority=step.priority,
                        execution_mode=step.execution_mode,
                        preconditions=step.preconditions,
                        expected_state_transition=step.expected_state_transition,
                        on_failure=step.on_failure,
                        fallback_step=step.fallback_step,
                        is_idempotent_no_op=is_idempotent_no_op
                    )
                )
                if simulated_state is not None:
                    self._apply_simulated_transition(simulated_state, cap_def, step)

        is_plan_valid = len(errors) == 0

        return ValidationResult(
            valid=is_plan_valid,
            plan_id=plan.plan_id,
            schema_version=plan.schema_version,
            user_request=plan.user_request,
            intent=plan.intent,
            objective_summary=plan.objective_summary,
            requires_user_confirmation=plan.requires_user_confirmation,
            validated_steps=validated_steps if is_plan_valid else [],
            rejected_steps=rejected_steps,
            errors=errors,
            warnings=warnings,
            idempotent_step_ids=idempotent_step_ids
        )

    def _check_step_idempotency(
        self,
        step: PlanStep,
        cap_def: CapabilityDefinition,
        room_state: RoomState,
        current_time: Optional[float]
    ) -> bool:
        """
        Determines whether a plan step is a complete no-op given the observed RoomState.
        Strict invariant: UNKNOWN or STALE state NEVER qualifies as idempotent.
        """
        cid = cap_def.canonical_id

        # 1. Projector Power Wake
        if cid == "PROJECTOR_POWER_WAKE":
            field = room_state.projector.power
            if field.effective_provenance(5.0, current_time) == Provenance.OBSERVED and field.value is True:
                return True

        # 2. Projector Power Sleep
        elif cid == "PROJECTOR_POWER_SLEEP":
            field = room_state.projector.power
            if field.effective_provenance(5.0, current_time) == Provenance.OBSERVED and field.value is False:
                return True

        # 3. Projector Switch HDMI 1
        elif cid == "PROJECTOR_SWITCH_HDMI1":
            field = room_state.projector.input_source
            if field.effective_provenance(10.0, current_time) in (Provenance.OBSERVED, Provenance.DERIVED):
                if str(field.value).upper() == "HDMI_1":
                    return True

        # 4. AC Power On
        elif cid == "AC_POWER_ON":
            field = room_state.ac.power
            if field.effective_provenance(15.0, current_time) == Provenance.OBSERVED and field.value is True:
                return True

        # 5. AC Power Off
        elif cid == "AC_POWER_OFF":
            field = room_state.ac.power
            if field.effective_provenance(15.0, current_time) == Provenance.OBSERVED and field.value is False:
                return True

        # 6. AC Set Temperature
        elif cid == "AC_SET_TEMPERATURE":
            target_t = step.parameters.get("temperature")
            field = room_state.ac.target_temperature
            if target_t is not None and field.effective_provenance(15.0, current_time) == Provenance.OBSERVED:
                if field.value == target_t:
                    return True

        # 7. Soundbar Route to Fire TV
        elif cid in ("SOUNDBAR_ROUTE_TO_FIRE_TV", "FIRE_TV_AUDIO_SWITCH_TO_FIRE_TV"):
            field = room_state.soundbar.current_owner
            if field.effective_provenance(3.0, current_time) in (Provenance.OBSERVED, Provenance.DERIVED):
                if str(field.value).upper() == "FIRE_TV":
                    return True

        # 8. Soundbar Route to PC
        elif cid in ("SOUNDBAR_ROUTE_TO_PC", "FIRE_TV_AUDIO_SWITCH_TO_PC"):
            field = room_state.soundbar.current_owner
            if field.effective_provenance(3.0, current_time) in (Provenance.OBSERVED, Provenance.DERIVED):
                if str(field.value).upper() == "PC":
                    return True

        return False

    def _apply_simulated_transition(
        self,
        simulated_state: RoomState,
        cap_def: Optional[CapabilityDefinition],
        step: PlanStep
    ) -> None:
        """
        Applies expected state transitions to the simulated RoomState graph during sequential validation.
        Allows subsequent steps in a valid multi-step plan to satisfy their preconditions.
        """
        if not cap_def or not cap_def.expected_state_transition:
            return

        now = time.time()
        for field_path, target_val in cap_def.expected_state_transition.items():
            parts = field_path.strip().lower().split(".")
            if len(parts) != 2:
                continue
            subsys_name, field_name = parts[0], parts[1]
            subsys = getattr(simulated_state, subsys_name, None)
            if subsys is None:
                continue
            f = getattr(subsys, field_name, None)
            if not isinstance(f, StateField):
                continue

            actual_val = target_val
            if isinstance(target_val, str) and target_val in step.parameters:
                actual_val = step.parameters[target_val]

            f.value = actual_val
            f.provenance = Provenance.DERIVED
            f.observed_at = now
