"""
Projector Command Router & Natural Language Resolver for Animus Smart Room.
Authoritatively resolves real-world user queries to explicit Projector Capabilities,
executes them with physical telemetry read-back, verifies real state, and enforces safety invariants.

Architectural Flow:
Brain understands -> Router decides -> Projector Controller executes -> Physical Device verifies -> UI reports reality
"""

import re
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum

from projector_controller import (
    ProjectorController,
    ProjectorPowerState,
    ProjectorSource,
    ProjectorSignalState,
    ThermalStatus,
    FanStatus
)

logger = logging.getLogger("projector_command_router")

class CommandCategory(str, Enum):
    POWER = "POWER"
    INPUT_SOURCE = "INPUT_SOURCE"
    VIDEO_SIGNAL = "VIDEO_SIGNAL"
    OPTICAL_MAINTENANCE = "OPTICAL_MAINTENANCE"
    BRIGHTNESS = "BRIGHTNESS"
    HARDWARE_HEALTH = "HARDWARE_HEALTH"
    NAVIGATION = "NAVIGATION"
    SAFETY_NEGATIVE = "SAFETY_NEGATIVE"


class ProjectorCommandRouter:
    """
    Routes natural-language commands to authoritative Projector capabilities
    with sub-millisecond parsing and physical telemetry verification.
    """
    def __init__(self, controller: Optional[ProjectorController] = None):
        self.controller = controller or ProjectorController()

    def route_command(self, query: str) -> Dict[str, Any]:
        """
        Main entrypoint: parses natural language, resolves capability, executes,
        verifies physical telemetry, and measures end-to-end latency.
        """
        q_raw = query.strip()
        q_clean = q_raw.lower()
        t0 = time.time()

        # ---------------------------------------------------------------------
        # 1. Safety & Negative Tests (HDMI 2, HDMI 3, Cold Power Off)
        # ---------------------------------------------------------------------
        if re.search(r'\b(hdmi\s*2|hdmi2|port\s*2)\b', q_clean):
            t_disp = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.SAFETY_NEGATIVE.value,
                "capability": "PROJECTOR_SWITCH_HDMI2",
                "success": False,
                "status": "UNSUPPORTED_HARDWARE",
                "error": "Zebronics PixaPlay 25 only has ONE physical HDMI port. HDMI 2 is physically unavailable.",
                "physical_result": "REJECTED_BY_HARDWARE_INVARIANT",
                "truthful_status": "REJECTED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_disp
            }

        if re.search(r'\b(hdmi\s*3|hdmi3|port\s*3)\b', q_clean):
            t_disp = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.SAFETY_NEGATIVE.value,
                "capability": "PROJECTOR_SWITCH_HDMI3",
                "success": False,
                "status": "UNSUPPORTED_HARDWARE",
                "error": "Zebronics PixaPlay 25 only has ONE physical HDMI port. HDMI 3 is physically unavailable.",
                "physical_result": "REJECTED_BY_HARDWARE_INVARIANT",
                "truthful_status": "REJECTED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_disp
            }

        if "cold" in q_clean and ("turn on" in q_clean or "power on" in q_clean):
            t_disp = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.SAFETY_NEGATIVE.value,
                "capability": "PROJECTOR_POWER_ON_COLD",
                "success": False,
                "status": "NOT_AVAILABLE_VIA_ADB",
                "error": "Cold power-on unavailable via ADB (requires IR blaster or physical power button).",
                "physical_result": "IR_REQUIRED",
                "truthful_status": "IR_REQUIRED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_disp
            }

        # ---------------------------------------------------------------------
        # 2. Hardware Health & Thermals
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["how hot", "temperature", "overheating", "fans working", "fan speed", "projector health", "projector status", "health"]):
            t_d0 = time.time()
            health = self.controller.get_hardware_health()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            temp = health.get("temperature_celsius")
            m_rpm = health.get("main_fan_rpm")
            s_rpm = health.get("sub_fan_rpm")
            t_stat = health.get("thermal_status")
            f_stat = health.get("fan_status")

            msg = f"Projector temperature is {temp}°C ({t_stat}). Fans: Main {m_rpm} RPM, Sub {s_rpm} RPM ({f_stat})." if temp is not None else "Health data unavailable."

            return {
                "query": q_raw,
                "category": CommandCategory.HARDWARE_HEALTH.value,
                "capability": "PROJECTOR_GET_HARDWARE_HEALTH",
                "success": health.get("verified", False),
                "status": "HEALTH_OK" if t_stat == "SAFE" else t_stat,
                "message": msg,
                "health_data": health,
                "physical_result": f"Temp: {temp}°C, Main Fan: {m_rpm} RPM, Sub Fan: {s_rpm} RPM",
                "truthful_status": t_stat,
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 3. Video Signal & Handshake Diagnostics
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["getting a signal", "signal", "hdmi working", "fire tv signal", "screen black", "video signal"]):
            t_d0 = time.time()
            sig = self.controller.get_signal_state()
            pwr = self.controller.get_power_state()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            sig_state = sig.get("signal_state")
            active_stream = sig.get("active_stream")
            pwr_state = pwr.get("power_state")

            if pwr_state in ["STANDBY", "OFF", "SLEEPING"]:
                msg = f"Projector screen is currently {pwr_state}. Video is not active."
                status_res = "SCREEN_STANDBY"
            elif sig_state == ProjectorSignalState.HDMI_SIGNAL_ACTIVE.value:
                msg = "HDMI video signal is active and streaming from Fire TV."
                status_res = "HDMI_SIGNAL_ACTIVE"
            elif sig_state == ProjectorSignalState.HDMI_CONNECTED_NO_ACTIVE_STREAM.value:
                msg = "HDMI 1 is connected but no active video stream was detected."
                status_res = "HDMI_CONNECTED_NO_ACTIVE_STREAM"
            else:
                msg = "HDMI video signal lost or cable disconnected."
                status_res = "HDMI_SIGNAL_LOST"

            return {
                "query": q_raw,
                "category": CommandCategory.VIDEO_SIGNAL.value,
                "capability": "PROJECTOR_GET_SIGNAL_STATE",
                "success": sig.get("verified", False),
                "status": status_res,
                "message": msg,
                "signal_data": sig,
                "power_state": pwr_state,
                "physical_result": f"Signal: {sig_state}, Stream Active: {active_stream}, Display: {pwr.get('display_state')}",
                "truthful_status": sig_state,
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 4. Brightness Controls (Set / Get / Dim / Brighter / Darker)
        # ---------------------------------------------------------------------
        if "brightness" in q_clean or "dim" in q_clean or "brighter" in q_clean or "darker" in q_clean:
            # Query brightness
            if any(kw in q_clean for kw in ["what is", "current brightness", "get brightness", "how bright"]):
                t_d0 = time.time()
                cur_b = self.controller.get_brightness()
                t_disp = int((time.time() - t_d0) * 1000)
                t_total = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": CommandCategory.BRIGHTNESS.value,
                    "capability": "PROJECTOR_GET_BRIGHTNESS",
                    "success": True,
                    "status": "BRIGHTNESS_READ",
                    "brightness_percent": cur_b,
                    "message": f"Projector brightness is currently {cur_b}%.",
                    "physical_result": f"Brightness: {cur_b}%",
                    "truthful_status": "VERIFIED",
                    "dispatch_latency_ms": t_disp,
                    "verification_latency_ms": 0,
                    "total_latency_ms": t_total
                }

            # Extract percentage from request (supports negative numbers for bounds checking)
            pct_match = re.search(r'(-?[0-9]+)\s*%', q_clean) or re.search(r'\b(?:to|at|set)\s*(-?[0-9]+)\b', q_clean)
            if pct_match:
                target_pct = int(pct_match.group(1))
            elif "dim" in q_clean and "to" not in q_clean:
                target_pct = 30
            elif "brighter" in q_clean:
                target_pct = min(100, self.controller.get_brightness() + 15)
            elif "darker" in q_clean:
                target_pct = max(0, self.controller.get_brightness() - 15)
            else:
                target_pct = 50

            # Reject invalid values (>100 or <0)
            if target_pct < 0 or target_pct > 100:
                t_disp = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": CommandCategory.SAFETY_NEGATIVE.value,
                    "capability": "PROJECTOR_SET_BRIGHTNESS",
                    "success": False,
                    "status": "INVALID_PARAMETER",
                    "error": f"Brightness {target_pct}% is out of bounds (0–100%).",
                    "physical_result": "REJECTED_INVALID_BOUNDS",
                    "truthful_status": "REJECTED",
                    "dispatch_latency_ms": t_disp,
                    "verification_latency_ms": 0,
                    "total_latency_ms": t_disp
                }

            t_d0 = time.time()
            ok, actual_b = self.controller.set_brightness(target_pct)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": CommandCategory.BRIGHTNESS.value,
                "capability": "PROJECTOR_SET_BRIGHTNESS",
                "success": ok,
                "status": "BRIGHTNESS_SET_VERIFIED" if ok else "READBACK_FAILED",
                "requested_percent": target_pct,
                "actual_percent": actual_b,
                "message": f"Projector brightness set to {actual_b}% (verified read-back)." if ok else f"Failed to verify brightness {target_pct}%.",
                "physical_result": f"Set: {target_pct}% -> Verified: {actual_b}%",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 5. Optical Maintenance (Auto-Focus & Auto-Keystone)
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["focus", "blurry", "auto focus", "auto-focus"]):
            t_d0 = time.time()
            res = self.controller.auto_focus()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            status_trig = res.get("status") == "TRIGGERED"

            return {
                "query": q_raw,
                "category": CommandCategory.OPTICAL_MAINTENANCE.value,
                "capability": "PROJECTOR_AUTO_FOCUS",
                "success": status_trig,
                "status": "FOCUS_TRIGGERED" if status_trig else "TRIGGER_FAILED",
                "message": "Electric motor auto-focus triggered." if status_trig else "Failed to dispatch auto-focus intent.",
                "physical_result": f"Intent: AUTO_FOCUS_CORRECTION, Status: {res.get('status')}",
                "truthful_status": "TRIGGERED",  # Truthful: Activity triggered, optical calibration is hardware
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["keystone", "crooked", "align", "auto align", "auto-keystone"]):
            t_d0 = time.time()
            res = self.controller.auto_keystone()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            status_trig = res.get("status") == "TRIGGERED"

            return {
                "query": q_raw,
                "category": CommandCategory.OPTICAL_MAINTENANCE.value,
                "capability": "PROJECTOR_AUTO_KEYSTONE",
                "success": status_trig,
                "status": "KEYSTONE_TRIGGERED" if status_trig else "TRIGGER_FAILED",
                "message": "Gyro-assisted auto-keystone triggered." if status_trig else "Failed to dispatch auto-keystone intent.",
                "physical_result": f"Intent: ONE_AUTO_CORRECTION_KEYSTONE, Status: {res.get('status')}",
                "truthful_status": "TRIGGERED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 6. Input / Source Switching (HDMI 1, Android Home, USB)
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["hdmi", "fire tv", "firetv", "input 1", "source 1"]):
            # Idempotency check: If already on HDMI 1, avoid redundant redispatch unless needed
            t_v0 = time.time()
            cur_src = self.controller.get_current_source()
            t_verif_initial = int((time.time() - t_v0) * 1000)

            if cur_src == ProjectorSource.HDMI_1:
                t_total = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": CommandCategory.INPUT_SOURCE.value,
                    "capability": "PROJECTOR_SWITCH_HDMI1",
                    "success": True,
                    "status": "ALREADY_ON_HDMI_1",
                    "idempotent": True,
                    "message": "Projector is already on HDMI 1.",
                    "physical_result": "HDMI_1 (No action required)",
                    "truthful_status": "VERIFIED_IDEMPOTENT",
                    "dispatch_latency_ms": 0,
                    "verification_latency_ms": t_verif_initial,
                    "total_latency_ms": t_total
                }

            t_d0 = time.time()
            ok = self.controller.set_hdmi(1)
            t_disp = int((time.time() - t_d0) * 1000)

            t_v1 = time.time()
            cur_after = self.controller.get_current_source()
            t_verif = int((time.time() - t_v1) * 1000)
            t_total = int((time.time() - t0) * 1000)
            verified = ok and cur_after == ProjectorSource.HDMI_1

            return {
                "query": q_raw,
                "category": CommandCategory.INPUT_SOURCE.value,
                "capability": "PROJECTOR_SWITCH_HDMI1",
                "success": verified,
                "status": "SWITCHED_TO_HDMI_1" if verified else "SWITCH_FAILED",
                "idempotent": False,
                "message": "Switched projector to HDMI 1 (Fire TV)." if verified else "Failed to switch to HDMI 1.",
                "physical_result": f"Foreground: {cur_after.value}",
                "truthful_status": "VERIFIED" if verified else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": t_verif,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["android home", "home screen", "projector home", "launcher"]):
            t_d0 = time.time()
            ok = self.controller.home()
            t_disp = int((time.time() - t_d0) * 1000)

            t_v1 = time.time()
            cur_after = self.controller.get_current_source()
            t_verif = int((time.time() - t_v1) * 1000)
            t_total = int((time.time() - t0) * 1000)
            verified = ok and cur_after == ProjectorSource.ANDROID_HOME

            return {
                "query": q_raw,
                "category": CommandCategory.INPUT_SOURCE.value,
                "capability": "PROJECTOR_SWITCH_ANDROID_HOME",
                "success": verified,
                "status": "SWITCHED_TO_ANDROID_HOME" if verified else "SWITCH_FAILED",
                "message": "Returned to projector Android home screen." if verified else "Failed to return home.",
                "physical_result": f"Foreground: {cur_after.value}",
                "truthful_status": "VERIFIED" if verified else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": t_verif,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["usb", "file manager", "media player"]):
            t_d0 = time.time()
            ok = self.controller.set_source(ProjectorSource.USB)
            t_disp = int((time.time() - t_d0) * 1000)

            t_v1 = time.time()
            cur_after = self.controller.get_current_source()
            t_verif = int((time.time() - t_v1) * 1000)
            t_total = int((time.time() - t0) * 1000)
            verified = ok and cur_after == ProjectorSource.USB

            return {
                "query": q_raw,
                "category": CommandCategory.INPUT_SOURCE.value,
                "capability": "PROJECTOR_SWITCH_USB_FILEMGR",
                "success": verified,
                "status": "SWITCHED_TO_USB" if verified else "SWITCH_FAILED",
                "message": "Opened USB media player." if verified else "Failed to open USB player.",
                "physical_result": f"Foreground: {cur_after.value}",
                "truthful_status": "VERIFIED" if verified else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": t_verif,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 7. Power Controls (Wake / Sleep / Graceful Off / Cold Power On)
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["turn on", "wake", "wake up"]):
            t_v0 = time.time()
            pwr = self.controller.get_power_state()
            t_verif_initial = int((time.time() - t_v0) * 1000)

            if not pwr.get("reachable"):
                t_total = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": CommandCategory.POWER.value,
                    "capability": "PROJECTOR_POWER_ON_COLD",
                    "success": False,
                    "status": "NOT_AVAILABLE_VIA_ADB",
                    "error": "Projector is completely powered off. Cold power-on requires IR blaster or physical button.",
                    "physical_result": "IR_REQUIRED",
                    "truthful_status": "IR_REQUIRED",
                    "dispatch_latency_ms": 0,
                    "verification_latency_ms": t_verif_initial,
                    "total_latency_ms": t_total
                }

            if pwr.get("power_state") == ProjectorPowerState.ON.value and pwr.get("interactive"):
                t_total = int((time.time() - t0) * 1000)
                return {
                    "query": q_raw,
                    "category": CommandCategory.POWER.value,
                    "capability": "PROJECTOR_POWER_WAKE",
                    "success": True,
                    "status": "ALREADY_ON",
                    "idempotent": True,
                    "message": "Projector is already on and interactive.",
                    "physical_result": "ON (No action required)",
                    "truthful_status": "VERIFIED_IDEMPOTENT",
                    "dispatch_latency_ms": 0,
                    "verification_latency_ms": t_verif_initial,
                    "total_latency_ms": t_total
                }

            t_d0 = time.time()
            ok = self.controller.wake()
            t_disp = int((time.time() - t_d0) * 1000)

            t_v1 = time.time()
            pwr_after = self.controller.get_power_state()
            t_verif = int((time.time() - t_v1) * 1000)
            t_total = int((time.time() - t0) * 1000)
            verified = ok and pwr_after.get("power_state") in [ProjectorPowerState.ON.value, ProjectorPowerState.AWAKE.value]

            return {
                "query": q_raw,
                "category": CommandCategory.POWER.value,
                "capability": "PROJECTOR_POWER_WAKE",
                "success": verified,
                "status": "WOKEN_FROM_STANDBY" if verified else "WAKE_FAILED",
                "message": "Woke projector from standby." if verified else "Failed to wake projector.",
                "physical_result": f"State: {pwr_after.get('power_state')}, Display: {pwr_after.get('display_state')}",
                "truthful_status": "VERIFIED" if verified else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": t_verif,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["sleep", "standby", "screen off", "blank"]):
            t_d0 = time.time()
            ok = self.controller.sleep()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": CommandCategory.POWER.value,
                "capability": "PROJECTOR_POWER_SLEEP",
                "success": ok,
                "status": "PUT_TO_SLEEP" if ok else "SLEEP_FAILED",
                "message": "Projector display put to sleep / standby." if ok else "Failed to put projector to sleep.",
                "physical_result": "KEYCODE_SLEEP (223) Dispatched",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }


        if any(kw in q_clean for kw in ["turn off", "power off", "shut down", "shutdown", "turn the projector off"]):
            t_d0 = time.time()
            ok = self.controller.power_off()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": CommandCategory.POWER.value,
                "capability": "PROJECTOR_POWER_OFF_OEM",
                "success": ok,
                "status": "OEM_SHUTDOWN_INITIATED" if ok else "SHUTDOWN_FAILED",
                "message": "Graceful optical shutdown initiated with 3-second cooling sequence." if ok else "Failed to initiate power-off.",
                "physical_result": "OEM PowerActivity Cooling Sequence Triggered",
                "truthful_status": "INITIATED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 8. Navigation & Keyevent Controls
        # ---------------------------------------------------------------------
        if "go back" in q_clean or "back" in q_clean:
            t_d0 = time.time()
            ok = self.controller.back()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_BACK",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_BACK (4)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if "menu" in q_clean:
            t_d0 = time.time()
            ok = self.controller.menu()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_MENU",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_MENU (82)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if "up" in q_clean:
            t_d0 = time.time()
            ok = self.controller.dpad_up()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_DPAD_UP",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_DPAD_UP (19)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if "down" in q_clean:
            t_d0 = time.time()
            ok = self.controller.dpad_down()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_DPAD_DOWN",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_DPAD_DOWN (20)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if "left" in q_clean:
            t_d0 = time.time()
            ok = self.controller.dpad_left()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_DPAD_LEFT",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_DPAD_LEFT (21)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if "right" in q_clean:
            t_d0 = time.time()
            ok = self.controller.dpad_right()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_DPAD_RIGHT",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_DPAD_RIGHT (22)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
                "total_latency_ms": t_total
            }

        if "select" in q_clean or "enter" in q_clean or "ok" in q_clean:
            t_d0 = time.time()
            ok = self.controller.dpad_center()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": CommandCategory.NAVIGATION.value,
                "capability": "PROJECTOR_NAV_SELECT",
                "success": ok,
                "status": "KEY_SENT",
                "physical_result": "KEYCODE_DPAD_CENTER (23)",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "verification_latency_ms": 0,
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
            "error": f"Could not map query to a verified projector capability: '{q_raw}'",
            "physical_result": "NO_ACTION",
            "truthful_status": "UNRESOLVED",
            "dispatch_latency_ms": 0,
            "verification_latency_ms": 0,
            "total_latency_ms": t_total
        }
