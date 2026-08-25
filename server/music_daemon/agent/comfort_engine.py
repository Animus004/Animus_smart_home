"""
Authoritative Environmental Comfort Intelligence Engine for Animus Smart Room.
Translates human natural language comfort expressions into bounded, verifiable AC setpoint adjustments.

EPISTEMIC INVARIANT:
Relative adjustments ALWAYS calculate from CURRENT LIVE TELEMETRY, never from stale memory.
Target temperatures are strictly clamped to physical safety bounds: 18°C <= target <= 28°C.
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("music_daemon.agent.comfort_engine")


class ComfortEngine:
    """
    Evaluates environmental comfort conditions and maps conversational comfort expressions
    to bounded target setpoints.
    """

    MIN_SAFE_TEMP = 18
    MAX_SAFE_TEMP = 28
    DEFAULT_COMFORT_TEMP = 24

    def parse_comfort_adjustment(
        self,
        utterance: str,
        current_live_temp: Optional[int] = None
    ) -> Tuple[Optional[int], str, str]:
        """
        Parses an utterance and returns (target_temperature: Optional[int], adjustment_type: str, explanation: str).
        - If current_live_temp is not provided, defaults to DEFAULT_COMFORT_TEMP (24°C).
        """
        text = utterance.strip().lower()
        base_temp = current_live_temp if current_live_temp is not None else self.DEFAULT_COMFORT_TEMP

        # 1. Explicit numeric setpoints (e.g. "keep the room around 24", "set ac to 22")
        explicit_match = re.search(r'(?:(?:around|to|at|make it)\s+)?(\d{2})\s*(?:degrees?|°c|celsius)?', text)
        if explicit_match:
            val = int(explicit_match.group(1))
            if self.MIN_SAFE_TEMP <= val <= self.MAX_SAFE_TEMP:
                return val, "EXPLICIT_SETPOINT", f"Setting temperature directly to {val}°C."

        # 2. Strong thermal discomfort: "freezing", "too cold", "ice box" -> +2°C
        if any(w in text for w in ("freezing", "too cold", "very cold", "extremely cold", "ice box", "chilly")):
            target = self.clamp_temperature(base_temp + 2)
            delta = target - base_temp
            return target, "WARMER_STRONG", f"Raising temperature by {delta}°C (from live {base_temp}°C to {target}°C) for warming comfort."

        # 3. Strong heat discomfort: "too hot", "boiling", "sweltering", "burning" -> -2°C
        if any(w in text for w in ("too hot", "boiling", "sweltering", "burning up", "very hot", "extremely hot")):
            target = self.clamp_temperature(base_temp - 2)
            delta = base_temp - target
            return target, "COOLER_STRONG", f"Lowering temperature by {delta}°C (from live {base_temp}°C to {target}°C) for cooling comfort."

        # 4. Mild warming: "a little warmer", "slightly warmer", "make it warmer", "bit warmer" -> +1°C
        if any(w in text for w in ("warmer", "warm up", "increase temp", "raise temp", "heat up")):
            target = self.clamp_temperature(base_temp + 1)
            return target, "WARMER_MILD", f"Raising temperature by 1°C (from live {base_temp}°C to {target}°C)."

        # 5. Mild cooling: "a little cooler", "slightly cooler", "make it cooler", "bit cooler", "cool down" -> -1°C
        if any(w in text for w in ("cooler", "cool down", "decrease temp", "lower temp", "more cooling")):
            target = self.clamp_temperature(base_temp - 1)
            return target, "COOLER_MILD", f"Lowering temperature by 1°C (from live {base_temp}°C to {target}°C)."

        # 6. Neutral comfort confirmation: "I'm comfortable now", "temperature is fine"
        if any(w in text for w in ("comfortable now", "perfect now", "temperature is fine", "good now")):
            return base_temp, "COMFORTABLE", f"Maintaining current comfortable temperature at {base_temp}°C."

        return None, "UNRESOLVED", "Could not determine comfort adjustment."

    def clamp_temperature(self, temp: int) -> int:
        """Clamps temperature strictly within [18, 28]."""
        return max(self.MIN_SAFE_TEMP, min(self.MAX_SAFE_TEMP, temp))
