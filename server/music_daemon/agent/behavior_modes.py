"""
Authoritative Behavioral Mode Management Engine for Animus Smart Room.
Defines strongly typed behavioral modes, deterministic state machine transitions,
physical verification of mode invariants, and bounded mode transition history.

EPISTEMIC INVARIANT:
Behavioral modes represent operational intent and expected room baselines.
Live physical telemetry establishes current physical truth.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.agent.behavior_modes")


class BehaviorMode(str, Enum):
    """Authoritative behavioral modes for Animus Smart Room."""
    IDLE = "IDLE"
    AWAY = "AWAY"
    COMFORT = "COMFORT"
    MOVIE = "MOVIE"
    MUSIC = "MUSIC"
    SLEEP = "SLEEP"
    WAKE_UP = "WAKE_UP"
    WORK = "WORK"
    GAMING = "GAMING"
    CUSTOM = "CUSTOM"


class ModeState(BaseModel):
    """Tracks active behavioral mode state, expectations, and physical telemetry evidence."""
    mode_id: str = Field(default_factory=lambda: f"mode_{uuid.uuid4().hex[:8]}")
    active_mode: BehaviorMode = BehaviorMode.IDLE
    previous_mode: Optional[BehaviorMode] = None
    started_at: float = Field(default_factory=time.time)
    ended_at: Optional[float] = None
    triggering_utterance: Optional[str] = None
    goal_id: Optional[str] = None
    expected_devices: Dict[str, Any] = Field(default_factory=dict)
    expected_environment: Dict[str, Any] = Field(default_factory=dict)
    user_confirmed: bool = True
    confidence: float = 1.0
    last_verified_physical_state: Dict[str, Any] = Field(default_factory=dict)
    termination_reason: Optional[str] = None


class BehaviorModeManager:
    """
    Authoritative state machine governing room behavioral modes.
    Enforces valid transition paths, safe normalization, physical evidence verification,
    and rolling history audit trail.
    """

    VALID_TRANSITIONS: Dict[BehaviorMode, List[BehaviorMode]] = {
        BehaviorMode.IDLE: [
            BehaviorMode.MOVIE,
            BehaviorMode.MUSIC,
            BehaviorMode.SLEEP,
            BehaviorMode.WORK,
            BehaviorMode.GAMING,
            BehaviorMode.COMFORT,
            BehaviorMode.AWAY,
            BehaviorMode.WAKE_UP,
            BehaviorMode.CUSTOM
        ],
        BehaviorMode.MOVIE: [
            BehaviorMode.IDLE,
            BehaviorMode.SLEEP,
            BehaviorMode.MUSIC,
            BehaviorMode.WORK,
            BehaviorMode.GAMING,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.MUSIC: [
            BehaviorMode.MOVIE,
            BehaviorMode.IDLE,
            BehaviorMode.SLEEP,
            BehaviorMode.WORK,
            BehaviorMode.GAMING,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.SLEEP: [
            BehaviorMode.WAKE_UP,
            BehaviorMode.IDLE,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.WAKE_UP: [
            BehaviorMode.IDLE,
            BehaviorMode.WORK,
            BehaviorMode.MUSIC,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.WORK: [
            BehaviorMode.IDLE,
            BehaviorMode.MOVIE,
            BehaviorMode.MUSIC,
            BehaviorMode.SLEEP,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.GAMING: [
            BehaviorMode.IDLE,
            BehaviorMode.MOVIE,
            BehaviorMode.MUSIC,
            BehaviorMode.SLEEP,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.COMFORT: [
            BehaviorMode.IDLE,
            BehaviorMode.MOVIE,
            BehaviorMode.MUSIC,
            BehaviorMode.SLEEP,
            BehaviorMode.WORK,
            BehaviorMode.GAMING
        ],
        BehaviorMode.AWAY: [
            BehaviorMode.IDLE,
            BehaviorMode.WAKE_UP,
            BehaviorMode.COMFORT
        ],
        BehaviorMode.CUSTOM: [
            BehaviorMode.IDLE,
            BehaviorMode.MOVIE,
            BehaviorMode.MUSIC,
            BehaviorMode.SLEEP
        ],
    }

    def __init__(self, initial_mode: BehaviorMode = BehaviorMode.IDLE, max_history: int = 10):
        self.current_state = ModeState(
            active_mode=initial_mode,
            expected_devices=self._default_expected_devices(initial_mode),
            expected_environment=self._default_expected_environment(initial_mode)
        )
        self.history: List[ModeState] = []
        self.max_history = max_history


    @property
    def active_mode(self) -> BehaviorMode:
        return self.current_state.active_mode

    @property
    def previous_mode(self) -> Optional[BehaviorMode]:
        return self.current_state.previous_mode

    def get_mode_state(self) -> ModeState:
        return self.current_state

    def is_in_mode(self, mode: BehaviorMode) -> bool:
        return self.current_state.active_mode == mode

    def can_transition_to(self, target_mode: BehaviorMode) -> bool:
        """Evaluates whether transitioning from active_mode to target_mode is permitted."""
        if target_mode == self.active_mode:
            return True
        allowed = self.VALID_TRANSITIONS.get(self.active_mode, [])
        return target_mode in allowed

    def transition_to(
        self,
        target_mode: BehaviorMode,
        utterance: Optional[str] = None,
        goal_id: Optional[str] = None,
        expected_devices: Optional[Dict[str, Any]] = None,
        expected_environment: Optional[Dict[str, Any]] = None,
        physical_evidence: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Executes a deterministic mode transition if valid, archiving previous mode.
        Returns: (success: bool, message: str)
        """
        # Idempotent no-op
        if target_mode == self.active_mode:
            logger.info(f"[MODE_MANAGER] Already in mode {target_mode}; updating physical evidence.")
            if physical_evidence:
                self.current_state.last_verified_physical_state.update(physical_evidence)
            return True, f"ALREADY_IN_MODE_{target_mode.value}"

        # Validate transition graph
        if not self.can_transition_to(target_mode):
            msg = f"Invalid mode transition requested: {self.active_mode.value} -> {target_mode.value}"
            logger.warning(f"[MODE_MANAGER_REJECT] {msg}")
            return False, msg

        # Archive completed mode state
        self.current_state.ended_at = time.time()
        self.current_state.termination_reason = reason or f"TRANSITION_TO_{target_mode.value}"
        self.history.append(self.current_state)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        prev = self.active_mode
        self.current_state = ModeState(
            active_mode=target_mode,
            previous_mode=prev,
            started_at=time.time(),
            triggering_utterance=utterance,
            goal_id=goal_id,
            expected_devices=expected_devices or self._default_expected_devices(target_mode),
            expected_environment=expected_environment or self._default_expected_environment(target_mode),
            last_verified_physical_state=physical_evidence or {}
        )
        logger.info(f"[MODE_TRANSITION] {prev.value} -> {target_mode.value} (goal_id={goal_id})")
        return True, f"TRANSITIONED_TO_{target_mode.value}"

    def exit_mode(self, reason: str = "USER_EXIT") -> Tuple[bool, str]:
        """Transitions out of active mode back to IDLE."""
        if self.active_mode == BehaviorMode.IDLE:
            return True, "ALREADY_IDLE"
        return self.transition_to(BehaviorMode.IDLE, reason=reason)

    def verify_physical_alignment(self, live_telemetry: Dict[str, Any]) -> bool:
        """
        Validates whether current live physical telemetry aligns with active mode expectations.
        """
        if self.active_mode == BehaviorMode.IDLE:
            return True

        if self.active_mode == BehaviorMode.MOVIE:
            # Expect projector ON and soundbar on Fire TV (if verified)
            proj_pwr = live_telemetry.get("projector_power")
            if proj_pwr is False:
                return False
            sb_owner = live_telemetry.get("soundbar_owner")
            if sb_owner and sb_owner not in ("FIRE_TV", "UNKNOWN"):
                return False
            return True

        if self.active_mode == BehaviorMode.SLEEP:
            # Expect projector OFF
            proj_pwr = live_telemetry.get("projector_power")
            if proj_pwr is True:
                return False
            return True

        if self.active_mode == BehaviorMode.MUSIC:
            # Expect soundbar on PC or active PC playback
            sb_owner = live_telemetry.get("soundbar_owner")
            if sb_owner == "FIRE_TV":
                return False
            return True

        return True

    def get_history(self) -> List[ModeState]:
        return list(self.history)

    def _default_expected_devices(self, mode: BehaviorMode) -> Dict[str, Any]:
        if mode == BehaviorMode.MOVIE:
            return {"projector": "ON", "projector_source": "HDMI_1", "fire_tv": "AWAKE", "soundbar": "FIRE_TV"}
        elif mode == BehaviorMode.SLEEP:
            return {"projector": "OFF", "fire_tv": "SLEEP", "soundbar": "DISCONNECTED"}
        elif mode == BehaviorMode.MUSIC:
            return {"soundbar": "PC", "pc_audio": "PLAYING"}
        return {}

    def _default_expected_environment(self, mode: BehaviorMode) -> Dict[str, Any]:
        if mode == BehaviorMode.MOVIE:
            return {"target_temperature": 23}
        elif mode == BehaviorMode.SLEEP:
            return {"target_temperature": 24}
        elif mode == BehaviorMode.WORK:
            return {"target_temperature": 24}
        return {}
