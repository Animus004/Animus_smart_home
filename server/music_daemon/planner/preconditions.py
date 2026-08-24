"""
Deterministic, Restricted Precondition Evaluator for Animus Smart Room.
Evaluates declarative state predicates against authoritative RoomState.
Strictly ZERO eval(), exec(), or arbitrary code execution.
"""

from __future__ import annotations
import ast
from enum import Enum
from typing import Any, List, Optional, Tuple, Union
from pydantic import BaseModel

from room_state.models import RoomState, StateField
from room_state.provenance import Provenance
from room_state.freshness import (
    PROJECTOR_POWER_TTL,
    PROJECTOR_INPUT_TTL,
    PROJECTOR_BRIGHTNESS_TTL,
    PROJECTOR_SIGNAL_TTL,
    PROJECTOR_HEALTH_TTL,
    AC_POWER_TTL,
    AC_TARGET_TEMP_TTL,
    AC_AMBIENT_TEMP_TTL,
    AC_MODE_TTL,
    AC_FAN_SPEED_TTL,
    FIRE_TV_ONLINE_TTL,
    FIRE_TV_POWER_TTL,
    FIRE_TV_APP_TTL,
    FIRE_TV_BT_TTL,
    PC_ONLINE_TTL,
    PC_VOLUME_TTL,
    PC_MUTE_TTL,
    PC_ENDPOINT_TTL,
    PC_BT_TTL,
    SOUNDBAR_OWNER_TTL,
    SOUNDBAR_CONNECTED_TTL,
    ENVIRONMENT_MODE_TTL
)


class PreconditionStatus(str, Enum):
    """Evaluation outcome for a plan step precondition."""
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN_STATE = "UNKNOWN_STATE"
    STALE_STATE = "STALE_STATE"
    INVALID_PRECONDITION = "INVALID_PRECONDITION"


class PreconditionEvaluationResult(BaseModel):
    """Result of evaluating an individual declarative precondition string."""
    expression: str
    status: PreconditionStatus
    field_path: Optional[str] = None
    observed_value: Optional[Any] = None
    provenance: Optional[str] = None
    is_fresh: Optional[bool] = None
    message: str = ""


# Field TTL lookup table for authoritative freshness verification
FIELD_TTL_MAP: dict[str, float] = {
    "projector.power": PROJECTOR_POWER_TTL,
    "projector.input_source": PROJECTOR_INPUT_TTL,
    "projector.brightness": PROJECTOR_BRIGHTNESS_TTL,
    "projector.signal_active": PROJECTOR_SIGNAL_TTL,
    "projector.health": PROJECTOR_HEALTH_TTL,
    "ac.power": AC_POWER_TTL,
    "ac.target_temperature": AC_TARGET_TEMP_TTL,
    "ac.ambient_temperature": AC_AMBIENT_TEMP_TTL,
    "ac.mode": AC_MODE_TTL,
    "ac.fan_speed": AC_FAN_SPEED_TTL,
    "fire_tv.online": FIRE_TV_ONLINE_TTL,
    "fire_tv.power_state": FIRE_TV_POWER_TTL,
    "fire_tv.foreground_app": FIRE_TV_APP_TTL,
    "fire_tv.soundbar_connected": FIRE_TV_BT_TTL,
    "pc.online": PC_ONLINE_TTL,
    "pc.master_volume": PC_VOLUME_TTL,
    "pc.is_muted": PC_MUTE_TTL,
    "pc.default_audio_endpoint": PC_ENDPOINT_TTL,
    "pc.bluetooth_radio_active": PC_BT_TTL,
    "soundbar.current_owner": SOUNDBAR_OWNER_TTL,
    "soundbar.is_connected": SOUNDBAR_CONNECTED_TTL,
    "environment.room_mode": ENVIRONMENT_MODE_TTL,
}


def _extract_field_path(node: ast.AST) -> Optional[str]:
    """Extracts dot-separated path from an AST Attribute or Name node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parent = _extract_field_path(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _resolve_room_state_field(field_path: str, room_state: RoomState) -> Tuple[Optional[StateField[Any]], Optional[float]]:
    """
    Traverses canonical RoomState to obtain the targeted StateField container and its TTL.
    Supports canonical field paths and semantic reachability aliases.
    """
    clean_path = field_path.strip().lower()

    # Reachability virtual fields
    if clean_path == "projector.reachable":
        p_power = room_state.projector.power
        p_health = room_state.projector.health
        is_reachable = (
            p_power.provenance in (Provenance.OBSERVED, Provenance.DERIVED)
            and p_health.value != "OFFLINE"
        )
        return StateField(
            value=is_reachable if p_power.provenance != Provenance.UNKNOWN else None,
            provenance=p_power.provenance,
            observed_at=p_power.observed_at,
            source="DERIVED_REACHABILITY"
        ), PROJECTOR_POWER_TTL

    if clean_path == "fire_tv.reachable":
        return room_state.fire_tv.online, FIRE_TV_ONLINE_TTL

    if clean_path == "pc.reachable":
        return room_state.pc.online, PC_ONLINE_TTL

    if clean_path == "ac.reachable":
        ac_power = room_state.ac.power
        is_reachable = ac_power.provenance in (Provenance.OBSERVED, Provenance.DERIVED)
        return StateField(
            value=is_reachable if ac_power.provenance != Provenance.UNKNOWN else None,
            provenance=ac_power.provenance,
            observed_at=ac_power.observed_at,
            source="DERIVED_REACHABILITY"
        ), AC_POWER_TTL

    parts = clean_path.split(".")
    if len(parts) != 2:
        return None, None

    subsystem_name, field_name = parts[0], parts[1]
    subsystem = getattr(room_state, subsystem_name, None)
    if subsystem is None:
        return None, None

    field = getattr(subsystem, field_name, None)
    if not isinstance(field, StateField):
        return None, None

    canonical_key = f"{subsystem_name}.{field_name}"
    ttl = FIELD_TTL_MAP.get(canonical_key, 10.0)
    return field, ttl


class RestrictedPreconditionEvaluator:
    """
    Evaluates declarative state preconditions using a strict, restricted AST walker.
    Enforces that:
    1. Zero code execution (eval/exec) occurs.
    2. Function calls, imports, subscripts, and arbitrary expressions are blocked.
    3. UNKNOWN and STALE state values fail safely without guessing.
    """

    ALLOWED_NODES = (
        ast.Expression,
        ast.Compare,
        ast.BoolOp,
        ast.UnaryOp,
        ast.Attribute,
        ast.Name,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Set,
        ast.Load,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.And,
        ast.Or,
        ast.Not
    )

    def __init__(self, current_time: Optional[float] = None):
        self.current_time = current_time

    def evaluate(self, expr_str: str, room_state: RoomState) -> PreconditionEvaluationResult:
        """
        Parses and evaluates a single precondition string against RoomState.
        """
        clean_expr = expr_str.strip()
        if not clean_expr:
            return PreconditionEvaluationResult(
                expression=expr_str,
                status=PreconditionStatus.INVALID_PRECONDITION,
                message="Empty precondition expression."
            )

        # Normalize common casing (e.g. true -> True, false -> False, null -> None)
        normalized = clean_expr
        for word, rep in [("true", "True"), ("false", "False"), ("null", "None"), ("TRUE", "True"), ("FALSE", "False")]:
            normalized = " ".join(rep if tok == word else tok for tok in normalized.split(" "))

        try:
            tree = ast.parse(normalized, mode='eval')
        except SyntaxError as e:
            return PreconditionEvaluationResult(
                expression=expr_str,
                status=PreconditionStatus.INVALID_PRECONDITION,
                message=f"Syntax error in precondition: {e}"
            )

        # 1. Structural Security Validation (AST whitelist)
        for node in ast.walk(tree):
            if not isinstance(node, self.ALLOWED_NODES):
                return PreconditionEvaluationResult(
                    expression=expr_str,
                    status=PreconditionStatus.INVALID_PRECONDITION,
                    message=f"Security violation: AST node '{type(node).__name__}' is forbidden in preconditions."
                )

        # 2. Evaluation Walk
        try:
            return self._eval_node(tree.body, room_state, expr_str)
        except Exception as e:
            return PreconditionEvaluationResult(
                expression=expr_str,
                status=PreconditionStatus.INVALID_PRECONDITION,
                message=f"Evaluation failed: {e}"
            )

    def _eval_node(self, node: ast.AST, room_state: RoomState, original_expr: str) -> PreconditionEvaluationResult:
        """Recursively evaluates whitelisted AST expressions."""
        if isinstance(node, ast.Compare):
            return self._eval_compare(node, room_state, original_expr)
        elif isinstance(node, ast.BoolOp):
            return self._eval_bool_op(node, room_state, original_expr)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            res = self._eval_node(node.operand, room_state, original_expr)
            if res.status in (PreconditionStatus.UNKNOWN_STATE, PreconditionStatus.STALE_STATE, PreconditionStatus.INVALID_PRECONDITION):
                return res
            new_status = PreconditionStatus.NOT_SATISFIED if res.status == PreconditionStatus.SATISFIED else PreconditionStatus.SATISFIED
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=new_status,
                field_path=res.field_path,
                observed_value=res.observed_value,
                provenance=res.provenance,
                is_fresh=res.is_fresh,
                message=f"NOT ({res.message})"
            )
        elif isinstance(node, (ast.Attribute, ast.Name)):
            # Direct boolean field evaluation (e.g. "projector.power")
            field_path = _extract_field_path(node)
            if not field_path:
                return PreconditionEvaluationResult(
                    expression=original_expr,
                    status=PreconditionStatus.INVALID_PRECONDITION,
                    message="Could not resolve field path."
                )
            state_field, ttl = _resolve_room_state_field(field_path, room_state)
            if state_field is None:
                return PreconditionEvaluationResult(
                    expression=original_expr,
                    status=PreconditionStatus.INVALID_PRECONDITION,
                    field_path=field_path,
                    message=f"Field '{field_path}' does not exist in RoomState."
                )
            return self._check_state_field(state_field, ttl, field_path, original_expr, lambda v: bool(v))

        return PreconditionEvaluationResult(
            expression=original_expr,
            status=PreconditionStatus.INVALID_PRECONDITION,
            message=f"Unsupported expression node '{type(node).__name__}'."
        )

    def _eval_compare(self, node: ast.Compare, room_state: RoomState, original_expr: str) -> PreconditionEvaluationResult:
        """Evaluates a binary or membership comparison expression (e.g. field == 'OK')."""
        left_path = _extract_field_path(node.left)
        if not left_path:
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.INVALID_PRECONDITION,
                message="Left side of comparison must be a RoomState field path."
            )

        state_field, ttl = _resolve_room_state_field(left_path, room_state)
        if state_field is None:
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.INVALID_PRECONDITION,
                field_path=left_path,
                message=f"Field '{left_path}' does not exist in RoomState."
            )

        if len(node.ops) != 1 or len(node.comparators) != 1:
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.INVALID_PRECONDITION,
                message="Chained comparisons are not supported."
            )

        op = node.ops[0]
        right_node = node.comparators[0]
        right_val = self._extract_literal(right_node)

        def comparator(val: Any) -> bool:
            # Case-insensitive comparison for strings
            val_comp = str(val).upper() if isinstance(val, str) else val
            r_comp = str(right_val).upper() if isinstance(right_val, str) else right_val

            if isinstance(op, ast.Eq):
                return val_comp == r_comp
            elif isinstance(op, ast.NotEq):
                return val_comp != r_comp
            elif isinstance(op, ast.Lt):
                return val < right_val
            elif isinstance(op, ast.LtE):
                return val <= right_val
            elif isinstance(op, ast.Gt):
                return val > right_val
            elif isinstance(op, ast.GtE):
                return val >= right_val
            elif isinstance(op, ast.In):
                if isinstance(right_val, (list, tuple, set)):
                    return val_comp in [str(x).upper() if isinstance(x, str) else x for x in right_val]
                return False
            elif isinstance(op, ast.NotIn):
                if isinstance(right_val, (list, tuple, set)):
                    return val_comp not in [str(x).upper() if isinstance(x, str) else x for x in right_val]
                return True
            return False

        return self._check_state_field(state_field, ttl, left_path, original_expr, comparator)

    def _eval_bool_op(self, node: ast.BoolOp, room_state: RoomState, original_expr: str) -> PreconditionEvaluationResult:
        """Evaluates logical AND / OR combinations of preconditions."""
        if isinstance(node.op, ast.And):
            for val_node in node.values:
                res = self._eval_node(val_node, room_state, original_expr)
                if res.status != PreconditionStatus.SATISFIED:
                    return res
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.SATISFIED,
                message="All conjuncts satisfied."
            )
        elif isinstance(node.op, ast.Or):
            has_uncertainty: Optional[PreconditionEvaluationResult] = None
            for val_node in node.values:
                res = self._eval_node(val_node, room_state, original_expr)
                if res.status == PreconditionStatus.SATISFIED:
                    return res
                if res.status in (PreconditionStatus.UNKNOWN_STATE, PreconditionStatus.STALE_STATE):
                    has_uncertainty = res
            return has_uncertainty or PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.NOT_SATISFIED,
                message="No disjuncts satisfied."
            )
        return PreconditionEvaluationResult(
            expression=original_expr,
            status=PreconditionStatus.INVALID_PRECONDITION,
            message="Unknown boolean operator."
        )

    def _check_state_field(
        self,
        state_field: StateField[Any],
        ttl: Optional[float],
        field_path: str,
        original_expr: str,
        predicate: Any
    ) -> PreconditionEvaluationResult:
        """Applies provenance and freshness rules to state comparison."""
        effective_prov = state_field.effective_provenance(ttl or 10.0, current_time=self.current_time)

        if effective_prov == Provenance.UNKNOWN or state_field.value is None:
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.UNKNOWN_STATE,
                field_path=field_path,
                observed_value=None,
                provenance=Provenance.UNKNOWN.value,
                is_fresh=False,
                message=f"Precondition cannot be evaluated: '{field_path}' state is UNKNOWN."
            )

        if effective_prov == Provenance.STALE:
            return PreconditionEvaluationResult(
                expression=original_expr,
                status=PreconditionStatus.STALE_STATE,
                field_path=field_path,
                observed_value=state_field.value,
                provenance=Provenance.STALE.value,
                is_fresh=False,
                message=f"Precondition uncertain: '{field_path}' observation is STALE (> {ttl}s)."
            )

        # Value is fresh (OBSERVED or DERIVED)
        is_satisfied = bool(predicate(state_field.value))
        return PreconditionEvaluationResult(
            expression=original_expr,
            status=PreconditionStatus.SATISFIED if is_satisfied else PreconditionStatus.NOT_SATISFIED,
            field_path=field_path,
            observed_value=state_field.value,
            provenance=effective_prov.value,
            is_fresh=True,
            message=f"Field '{field_path}' = {state_field.value} ({'Satisfied' if is_satisfied else 'Not satisfied'})."
        )

    def _extract_literal(self, node: ast.AST) -> Any:
        """Extracts a scalar literal or list from a safe AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return [self._extract_literal(elt) for elt in node.elts]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            return -node.operand.value
        raise ValueError(f"Non-literal node in comparison target: {type(node).__name__}")
