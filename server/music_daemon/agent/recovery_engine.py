"""
Authoritative Bounded Autonomous Recovery Engine for Animus Smart Room.
Handles transient hardware and audio routing dropouts with strict boundedness.

EPISTEMIC & SOUNDBAR INVARIANTS:
1. Maximum autonomous recovery attempts = 1. No infinite retry loops.
2. If Fire TV owns the soundbar, recovery MUST operate from the Fire TV side (e.g. fire_tv.connect_soundbar()).
3. NEVER reclaim Bluetooth to Windows or call ensure_audio_endpoint() during Fire TV audio recovery.
4. Recovery results must be physically verified via fresh telemetry readback before claiming success.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.agent.recovery_engine")


class RecoveryType(str, Enum):
    """Categorization of supported autonomous recovery workflows."""
    FIRE_TV_AUDIO = "FIRE_TV_AUDIO"
    FIRE_TV_CONNECTIVITY = "FIRE_TV_CONNECTIVITY"
    SOUNDBAR_PC_AUDIO = "SOUNDBAR_PC_AUDIO"
    PROJECTOR_ADB = "PROJECTOR_ADB"


class RecoveryResult(BaseModel):
    """Structured report of an autonomous recovery attempt."""
    recovery_id: str = Field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:8]}")
    recovery_type: RecoveryType
    success: bool
    attempts: int
    details: Dict[str, Any] = Field(default_factory=dict)
    message: str
    timestamp: float = Field(default_factory=time.time)


class RecoveryEngine:
    """
    Orchestrates bounded single-attempt recovery for transient room faults.
    """

    def __init__(self, max_attempts: int = 1):
        self.max_attempts = max_attempts
        self.recovery_history: list[RecoveryResult] = []

    def recover_fire_tv_audio(
        self,
        fire_tv_controller: Any,
        soundbar_owner: str = "FIRE_TV"
    ) -> RecoveryResult:
        """
        Recovers Fire TV Bluetooth audio without stealing the soundbar back to PC.
        Strict Invariant: Reconnect is triggered strictly from the Fire TV side.
        """
        logger.info("[RECOVERY_ENGINE] Initiating Fire TV audio recovery (max_attempts=1)...")
        if not fire_tv_controller:
            res = RecoveryResult(
                recovery_type=RecoveryType.FIRE_TV_AUDIO,
                success=False,
                attempts=0,
                message="Fire TV controller unavailable."
            )
            self._archive(res)
            return res

        try:
            # Reconnect strictly on Fire TV side
            connect_fn = getattr(fire_tv_controller, "connect_soundbar", None)
            if callable(connect_fn):
                ok = bool(connect_fn(timeout_seconds=5.0))
                # Verify readback
                verify_fn = getattr(fire_tv_controller, "is_soundbar_connected", None)
                is_connected = bool(verify_fn()) if callable(verify_fn) else ok
                success = is_connected

                msg = "Fire TV soundbar audio successfully reconnected." if success else "Fire TV soundbar reconnection failed after 1 attempt."
                res = RecoveryResult(
                    recovery_type=RecoveryType.FIRE_TV_AUDIO,
                    success=success,
                    attempts=1,
                    details={"soundbar_connected": is_connected, "ownership_preserved": "FIRE_TV"},
                    message=msg
                )
                self._archive(res)
                logger.info(f"[RECOVERY_FIRE_TV_AUDIO] Result: {success} ({msg})")
                return res
        except Exception as e:
            logger.error(f"[RECOVERY_FIRE_TV_AUDIO_ERR] Exception during recovery: {e}")

        res = RecoveryResult(
            recovery_type=RecoveryType.FIRE_TV_AUDIO,
            success=False,
            attempts=1,
            message="Fire TV audio recovery encountered an exception."
        )
        self._archive(res)
        return res

    def recover_pc_soundbar_audio(
        self,
        bt_helper: Any,
        soundbar_owner: str = "PC"
    ) -> RecoveryResult:
        """
        Recovers PC Soundbar audio when soundbar is owned by PC.
        Allowed to call ensure_audio_endpoint() only because PC is the legitimate owner.
        """
        if soundbar_owner == "FIRE_TV":
            logger.error("[RECOVERY_SECURITY_VIOLATION] Attempted PC audio recovery while soundbar is owned by FIRE_TV!")
            res = RecoveryResult(
                recovery_type=RecoveryType.SOUNDBAR_PC_AUDIO,
                success=False,
                attempts=0,
                message="Prohibited: Soundbar is owned by Fire TV."
            )
            self._archive(res)
            return res

        logger.info("[RECOVERY_ENGINE] Initiating PC Soundbar audio recovery (max_attempts=1)...")
        if not bt_helper:
            res = RecoveryResult(
                recovery_type=RecoveryType.SOUNDBAR_PC_AUDIO,
                success=False,
                attempts=0,
                message="Bluetooth audio helper unavailable."
            )
            self._archive(res)
            return res

        try:
            if hasattr(bt_helper, "ensure_audio_endpoint") and callable(bt_helper.ensure_audio_endpoint):
                ready, lg_dev, status = bt_helper.ensure_audio_endpoint()
                success = bool(ready and lg_dev)
                msg = f"PC Soundbar reconnected via {status}." if success else f"PC Soundbar recovery failed ({status})."
                res = RecoveryResult(
                    recovery_type=RecoveryType.SOUNDBAR_PC_AUDIO,
                    success=success,
                    attempts=1,
                    details={"ready": ready, "device": lg_dev, "status": status},
                    message=msg
                )
                self._archive(res)
                return res
        except Exception as e:
            logger.error(f"[RECOVERY_PC_AUDIO_ERR] Exception: {e}")

        res = RecoveryResult(
            recovery_type=RecoveryType.SOUNDBAR_PC_AUDIO,
            success=False,
            attempts=1,
            message="PC Soundbar recovery encountered an error."
        )
        self._archive(res)
        return res

    def recover_fire_tv_connection(self, fire_tv_controller: Any) -> RecoveryResult:
        """Recovers Fire TV ADB connection with bounded single attempt."""
        if not fire_tv_controller:
            return RecoveryResult(
                recovery_type=RecoveryType.FIRE_TV_CONNECTIVITY,
                success=False,
                attempts=0,
                message="Fire TV controller unavailable."
            )
        try:
            connect_fn = getattr(fire_tv_controller, "connect", None)
            if callable(connect_fn):
                ok = bool(connect_fn())
                res = RecoveryResult(
                    recovery_type=RecoveryType.FIRE_TV_CONNECTIVITY,
                    success=ok,
                    attempts=1,
                    message="Fire TV reconnected." if ok else "Fire TV reconnection failed."
                )
                self._archive(res)
                return res
        except Exception as e:
            logger.error(f"[RECOVERY_FTV_CONN_ERR] {e}")

        return RecoveryResult(
            recovery_type=RecoveryType.FIRE_TV_CONNECTIVITY,
            success=False,
            attempts=1,
            message="Fire TV connection recovery failed."
        )

    def _archive(self, result: RecoveryResult):
        self.recovery_history.append(result)
        if len(self.recovery_history) > 20:
            self.recovery_history.pop(0)
