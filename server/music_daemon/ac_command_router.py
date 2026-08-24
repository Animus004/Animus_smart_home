"""
Air Conditioner Command Router & Natural Language Resolver for Animus Smart Room.
Authoritatively resolves real-world user queries to explicit AC capabilities,
executes them with physical telemetry read-back verification, and enforces safety invariants.

Architectural Flow:
Brain understands -> Router decides -> AC Controller executes -> Physical Device verifies -> UI reports reality
"""

import re
import time
import logging
from typing import Dict, Any, Optional
from enum import Enum

from ac_controller import AcController, AcMode, AcFanSpeed

logger = logging.getLogger("ac_command_router")

class AcCommandCategory(str, Enum):
    POWER = "POWER"
    TEMPERATURE = "TEMPERATURE"
    MODE = "MODE"
    FAN = "FAN"
    SAFETY_NEGATIVE = "SAFETY_NEGATIVE"
    DIAGNOSTICS = "DIAGNOSTICS"


class AcCommandRouter:
    """
    Routes natural-language commands to authoritative AC capabilities
    with sub-millisecond parsing and physical telemetry verification.
    """
    def __init__(self, controller: Optional[AcController] = None):
        self.controller = controller or AcController()

    def route_command(self, query: str) -> Dict[str, Any]:
        """
        Main entrypoint: parses natural language, resolves capability, executes,
        verifies physical telemetry, and measures end-to-end latency.
        """
        q_raw = query.strip()
        q_clean = q_raw.lower()
        t0 = time.time()

        # ---------------------------------------------------------------------
        # 1. Safety & Unsupported Hardware Rejections (Heat, Swing)
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["heat", "heating", "warm mode"]):
            t_disp = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": AcCommandCategory.SAFETY_NEGATIVE.value,
                "capability": "AC_SET_MODE_HEAT",
                "success": False,
                "status": "UNSUPPORTED_HARDWARE",
                "error": "This AC is a cooling-only inverter model. Heat mode is physically unsupported.",
                "physical_result": "REJECTED_UNSUPPORTED_HEAT",
                "truthful_status": "REJECTED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_disp
            }

        if "swing" in q_clean or "vane" in q_clean or "louvre" in q_clean or "louver" in q_clean:
            t_disp = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": AcCommandCategory.SAFETY_NEGATIVE.value,
                "capability": "AC_SET_SWING",
                "success": False,
                "status": "UNSUPPORTED_HARDWARE",
                "error": "Louver swing control is not available on this AC's Wi-Fi interface.",
                "physical_result": "REJECTED_UNSUPPORTED_SWING",
                "truthful_status": "REJECTED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_disp
            }

        # ---------------------------------------------------------------------
        # 2. Ambient / Room Temperature Diagnostics
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["room temp", "room temperature", "ambient", "how hot is the room", "current temperature in the room"]):
            t_d0 = time.time()
            st = self.controller.get_status()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            amb = st.get("ambient_temperature")
            return {
                "query": q_raw,
                "category": AcCommandCategory.DIAGNOSTICS.value,
                "capability": "AC_GET_AMBIENT_TEMPERATURE",
                "success": st.get("verified", False),
                "ambient_temperature": amb,
                "target_temperature": st.get("target_temperature"),
                "status": "AMBIENT_TEMP_READ",
                "message": f"Room ambient temperature is {amb}°C (indoor thermistor sensor)." if amb is not None else "Ambient temperature unavailable.",
                "physical_result": f"Sensor temp_current: {amb}°C",
                "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 3. Target Temperature Queries & Setpoints
        # ---------------------------------------------------------------------
        if "what" in q_clean and ("set to" in q_clean or "target" in q_clean or "ac temp" in q_clean):
            t_d0 = time.time()
            st = self.controller.get_status()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            tgt = st.get("target_temperature")
            return {
                "query": q_raw,
                "category": AcCommandCategory.TEMPERATURE.value,
                "capability": "AC_GET_TARGET_TEMPERATURE",
                "success": st.get("verified", False),
                "target_temperature": tgt,
                "status": "TARGET_TEMP_READ",
                "message": f"AC target temperature is set to {tgt}°C.",
                "physical_result": f"Setpoint temp_set: {tgt}°C",
                "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["cooler", "colder", "drop the ac", "decrease ac", "lower ac"]):
            t_d0 = time.time()
            st = self.controller.get_status()
            cur_t = st.get("target_temperature", 24)
            new_t = max(16, cur_t - 1)
            ok, res = self.controller.set_temperature(new_t)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": AcCommandCategory.TEMPERATURE.value,
                "capability": "AC_SET_TEMPERATURE",
                "success": ok,
                "requested_temperature": new_t,
                "target_temperature": res.get("target_temperature", new_t),
                "status": "TEMP_SET_VERIFIED" if ok else "TEMP_SET_FAILED",
                "message": res.get("message"),
                "physical_result": f"temp_set: {res.get('target_temperature')}°C",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["warmer", "increase ac", "raise ac"]):
            t_d0 = time.time()
            st = self.controller.get_status()
            cur_t = st.get("target_temperature", 24)
            new_t = min(30, cur_t + 1)
            ok, res = self.controller.set_temperature(new_t)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": AcCommandCategory.TEMPERATURE.value,
                "capability": "AC_SET_TEMPERATURE",
                "success": ok,
                "requested_temperature": new_t,
                "target_temperature": res.get("target_temperature", new_t),
                "status": "TEMP_SET_VERIFIED" if ok else "TEMP_SET_FAILED",
                "message": res.get("message"),
                "physical_result": f"temp_set: {res.get('target_temperature')}°C",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        temp_match = re.search(r'(-?[0-9]+)\s*(?:degrees|degree|°c|c\b)', q_clean) or re.search(r'\b(?:to|at|set)\s*(-?[0-9]+)\b', q_clean)
        if temp_match and "fan" not in q_clean and "mode" not in q_clean:
            tgt_t = int(temp_match.group(1))
            t_d0 = time.time()
            ok, res = self.controller.set_temperature(tgt_t)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            cat = AcCommandCategory.TEMPERATURE.value if ok or (16 <= tgt_t <= 30) else AcCommandCategory.SAFETY_NEGATIVE.value
            return {
                "query": q_raw,
                "category": cat,
                "capability": "AC_SET_TEMPERATURE",
                "success": ok,
                "requested_temperature": tgt_t,
                "target_temperature": res.get("target_temperature"),
                "status": res.get("status", "TEMP_SET_VERIFIED" if ok else "TEMP_SET_FAILED"),
                "error": res.get("error"),
                "message": res.get("message"),
                "physical_result": f"temp_set: {res.get('target_temperature')}°C" if ok else "REJECTED_OUT_OF_BOUNDS",
                "truthful_status": "VERIFIED" if ok else "REJECTED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 4. Mode Controls (Cool, Dry, Fan, Auto)
        # ---------------------------------------------------------------------
        if "mode" in q_clean or any(kw in q_clean for kw in ["cool", "dry", "dehumidify", "fan only", "auto mode"]):
            if "what mode" in q_clean:
                t_d0 = time.time()
                st = self.controller.get_status()
                t_disp = int((time.time() - t_d0) * 1000)
                t_total = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": AcCommandCategory.MODE.value,
                    "capability": "AC_GET_MODE",
                    "success": st.get("verified", False),
                    "mode": st.get("mode"),
                    "status": "MODE_READ",
                    "message": f"AC is in {st.get('mode')} mode.",
                    "physical_result": f"mode: {st.get('raw_mode')}",
                    "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                    "dispatch_latency_ms": t_disp,
                    "total_latency_ms": t_total
                }

            target_m = "COOL"
            if "dry" in q_clean or "dehumidify" in q_clean or "wet" in q_clean:
                target_m = "DRY"
            elif "fan" in q_clean or "wind" in q_clean:
                target_m = "FAN"
            elif "auto" in q_clean:
                target_m = "AUTO"

            t_d0 = time.time()
            ok, res = self.controller.set_mode(target_m)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": AcCommandCategory.MODE.value,
                "capability": f"AC_SET_MODE_{target_m}",
                "success": ok,
                "requested_mode": target_m,
                "mode": res.get("mode", target_m),
                "status": "MODE_SET_VERIFIED" if ok else "MODE_SET_FAILED",
                "message": res.get("message"),
                "physical_result": f"mode: {res.get('mode')}",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 5. Fan Speed Controls (Low, Medium, High, Auto)
        # ---------------------------------------------------------------------
        if "fan" in q_clean:
            if "what" in q_clean or "get" in q_clean:
                t_d0 = time.time()
                st = self.controller.get_status()
                t_disp = int((time.time() - t_d0) * 1000)
                t_total = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": AcCommandCategory.FAN.value,
                    "capability": "AC_GET_FAN_SPEED",
                    "success": st.get("verified", False),
                    "fan_speed": st.get("fan_speed"),
                    "status": "FAN_READ",
                    "message": f"AC fan speed is {st.get('fan_speed')}.",
                    "physical_result": f"fan_speed_enum: {st.get('raw_fan')}",
                    "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                    "dispatch_latency_ms": t_disp,
                    "total_latency_ms": t_total
                }

            target_fan = "AUTO"
            if "high" in q_clean or "max" in q_clean:
                target_fan = "HIGH"
            elif "medium" in q_clean or "mid" in q_clean:
                target_fan = "MEDIUM"
            elif "low" in q_clean or "min" in q_clean or "quiet" in q_clean:
                target_fan = "LOW"

            t_d0 = time.time()
            ok, res = self.controller.set_fan_speed(target_fan)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": AcCommandCategory.FAN.value,
                "capability": f"AC_SET_FAN_SPEED_{target_fan}",
                "success": ok,
                "requested_fan_speed": target_fan,
                "fan_speed": res.get("fan_speed", target_fan),
                "status": "FAN_SET_VERIFIED" if ok else "FAN_SET_FAILED",
                "message": res.get("message"),
                "physical_result": f"fan_speed_enum: {res.get('fan_speed')}",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 6. Power Controls (On / Off / Status)
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["is the ac on", "ac running", "ac power status", "is ac on"]):
            t_d0 = time.time()
            st = self.controller.get_status()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            pwr = st.get("power", False)
            return {
                "query": q_raw,
                "category": AcCommandCategory.POWER.value,
                "capability": "AC_GET_POWER_STATE",
                "success": st.get("verified", False),
                "power": pwr,
                "status": "POWER_STATE_READ",
                "message": f"AC is currently {'ON' if pwr else 'OFF'}.",
                "physical_result": f"switch: {pwr}",
                "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["turn on", "power on", "start the ac", "turn the ac on"]):
            t_d0 = time.time()
            ok, res = self.controller.set_power(True)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": AcCommandCategory.POWER.value,
                "capability": "AC_POWER_ON",
                "success": ok,
                "power": True,
                "idempotent": res.get("idempotent", False),
                "status": "POWER_ON_VERIFIED" if ok else "POWER_ON_FAILED",
                "message": res.get("message"),
                "physical_result": "switch: True",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["turn off", "power off", "shut down", "stop the ac", "turn the ac off"]):
            t_d0 = time.time()
            ok, res = self.controller.set_power(False)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": AcCommandCategory.POWER.value,
                "capability": "AC_POWER_OFF",
                "success": ok,
                "power": False,
                "idempotent": res.get("idempotent", False),
                "status": "POWER_OFF_VERIFIED" if ok else "POWER_OFF_FAILED",
                "message": res.get("message"),
                "physical_result": "switch: False",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # Fallback / Unknown
        # ---------------------------------------------------------------------
        t_total = int((time.time() - t0) * 1000)
        return {
            "query": q_raw,
            "category": "UNKNOWN",
            "capability": "UNKNOWN",
            "success": False,
            "status": "UNRESOLVED_COMMAND",
            "error": f"Could not map query to a verified AC capability: '{q_raw}'",
            "physical_result": "NO_ACTION",
            "truthful_status": "UNRESOLVED",
            "dispatch_latency_ms": 0,
            "total_latency_ms": t_total
        }
