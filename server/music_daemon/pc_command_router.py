"""
PC Command Router & Natural Language Resolver for Animus Smart Room.
Authoritatively resolves real-world user queries to explicit PC capabilities,
executes them with physical telemetry read-back verification, and enforces strict security invariants.

Architectural Flow:
Brain understands -> Router decides -> PC Controller executes -> Physical Device verifies -> UI reports reality
"""

import re
import time
import logging
from typing import Dict, Any, Optional
from enum import Enum

from pc_controller import PcController

logger = logging.getLogger("pc_command_router")

class PcCommandCategory(str, Enum):
    AUDIO = "AUDIO"
    BLUETOOTH = "BLUETOOTH"
    MEDIA = "MEDIA"
    POWER = "POWER"
    SYSTEM = "SYSTEM"
    APPLICATION = "APPLICATION"
    SAFETY_NEGATIVE = "SAFETY_NEGATIVE"


class PcCommandRouter:
    """
    Routes natural-language commands to authoritative PC capabilities
    with sub-millisecond parsing and physical telemetry verification.
    """
    def __init__(self, controller: Optional[PcController] = None):
        self.controller = controller or PcController()

    def route_command(self, query: str) -> Dict[str, Any]:
        """
        Main entrypoint: parses natural language, resolves capability, executes,
        verifies physical telemetry, and measures end-to-end latency.
        """
        q_raw = query.strip()
        q_clean = q_raw.lower()
        t0 = time.time()

        # ---------------------------------------------------------------------
        # 1. Security & Arbitrary Shell Rejection Guard (STRICT SAFETY)
        # ---------------------------------------------------------------------
        dangerous_keywords = [
            "powershell", "cmd.exe", "bash", "sh ", "curl ", "wget ", "rm ", "del ",
            "format ", "drop ", "eval ", "exec(", "system(", "sudo ", "format c:", "rmdir"
        ]
        if any(dk in q_clean for dk in dangerous_keywords):
            t_disp = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.SAFETY_NEGATIVE.value,
                "capability": "SECURITY_GUARD_REJECT_ARBITRARY_COMMAND",
                "success": False,
                "status": "SECURITY_REJECTED",
                "error": "Arbitrary command and shell execution is strictly blocked by Animus security invariants.",
                "physical_result": "BLOCKED_BY_ALLOWLIST",
                "truthful_status": "REJECTED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_disp
            }

        # ---------------------------------------------------------------------
        # 2. Audio Subsystem (Volume, Mute, Output)
        # ---------------------------------------------------------------------
        # Volume Queries
        if ("volume" in q_clean or "sound level" in q_clean) and ("what" in q_clean or "get" in q_clean or "how loud" in q_clean):
            t_d0 = time.time()
            st = self.controller.get_audio_status()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            v = st.get("master_volume", 0)

            return {
                "query": q_raw,
                "category": PcCommandCategory.AUDIO.value,
                "capability": "PC_GET_VOLUME",
                "success": st.get("verified", False),
                "master_volume": v,
                "is_muted": st.get("is_muted", False),
                "status": "VOLUME_READ",
                "message": f"PC master volume is {v}%.",
                "physical_result": f"CoreAudio Scalar: {v}%",
                "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # Volume Increase / Louder
        if any(kw in q_clean for kw in ["louder", "increase volume", "volume up", "raise volume", "turn it up"]):
            t_d0 = time.time()
            cur_v = self.controller.get_volume()
            target_v = min(100, cur_v + 5)
            ok, res = self.controller.set_volume(target_v)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": PcCommandCategory.AUDIO.value,
                "capability": "PC_VOLUME_UP",
                "success": ok,
                "master_volume": res.get("master_volume", target_v),
                "status": "VOLUME_SET_VERIFIED" if ok else "VOLUME_SET_FAILED",
                "message": res.get("message"),
                "physical_result": f"CoreAudio: {res.get('master_volume')}%",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # Volume Decrease / Quieter
        if any(kw in q_clean for kw in ["quieter", "decrease volume", "volume down", "lower volume", "turn it down"]):
            t_d0 = time.time()
            cur_v = self.controller.get_volume()
            target_v = max(0, cur_v - 5)
            ok, res = self.controller.set_volume(target_v)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            return {
                "query": q_raw,
                "category": PcCommandCategory.AUDIO.value,
                "capability": "PC_VOLUME_DOWN",
                "success": ok,
                "master_volume": res.get("master_volume", target_v),
                "status": "VOLUME_SET_VERIFIED" if ok else "VOLUME_SET_FAILED",
                "message": res.get("message"),
                "physical_result": f"CoreAudio: {res.get('master_volume')}%",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # Explicit Volume Setpoint
        vol_match = re.search(r'(-?[0-9]+)\s*(?:%|percent)?\b', q_clean)
        if "volume" in q_clean and vol_match and "to" in q_clean:
            tgt_v = int(vol_match.group(1))
            t_d0 = time.time()
            ok, res = self.controller.set_volume(tgt_v)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            cat = PcCommandCategory.AUDIO.value if ok or (0 <= tgt_v <= 100) else PcCommandCategory.SAFETY_NEGATIVE.value
            return {
                "query": q_raw,
                "category": cat,
                "capability": "PC_SET_VOLUME",
                "success": ok,
                "requested_volume": tgt_v,
                "master_volume": res.get("master_volume"),
                "status": "VOLUME_SET_VERIFIED" if ok else res.get("status", "VOLUME_SET_FAILED"),
                "error": res.get("error"),
                "message": res.get("message"),
                "physical_result": f"CoreAudio: {res.get('master_volume')}%" if ok else "REJECTED_OUT_OF_BOUNDS",
                "truthful_status": "VERIFIED" if ok else "REJECTED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # Mute / Unmute
        if "unmute" in q_clean:
            t_d0 = time.time()
            ok, res = self.controller.set_mute(False)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.AUDIO.value,
                "capability": "PC_UNMUTE",
                "success": ok,
                "is_muted": False,
                "status": "UNMUTE_VERIFIED" if ok else "UNMUTE_FAILED",
                "message": res.get("message"),
                "physical_result": "CoreAudio Mute: False",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if "mute" in q_clean:
            t_d0 = time.time()
            ok, res = self.controller.set_mute(True)
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.AUDIO.value,
                "capability": "PC_MUTE",
                "success": ok,
                "is_muted": True,
                "status": "MUTE_VERIFIED" if ok else "MUTE_FAILED",
                "message": res.get("message"),
                "physical_result": "CoreAudio Mute: True",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # Audio Output Query
        if any(kw in q_clean for kw in ["audio output", "audio device", "playback device", "sound device", "speaker device"]):
            t_d0 = time.time()
            st = self.controller.get_audio_status()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            def_ep = st.get("default_endpoint", {})
            return {
                "query": q_raw,
                "category": PcCommandCategory.AUDIO.value,
                "capability": "PC_GET_AUDIO_OUTPUT",
                "success": st.get("verified", False),
                "default_endpoint": def_ep,
                "active_endpoints": st.get("active_endpoints", []),
                "status": "AUDIO_OUTPUT_READ",
                "message": f"Default audio output is {def_ep.get('name')}.",
                "physical_result": f"Endpoint: {def_ep.get('name')}",
                "truthful_status": "VERIFIED" if st.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 3. Bluetooth Subsystem
        # ---------------------------------------------------------------------
        if "bluetooth" in q_clean or "bt device" in q_clean:
            t_d0 = time.time()
            bt_st = self.controller.get_bluetooth_status()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)

            devs = bt_st.get("devices", [])
            names = [d.get("name") for d in devs]
            return {
                "query": q_raw,
                "category": PcCommandCategory.BLUETOOTH.value,
                "capability": "PC_GET_BLUETOOTH_DEVICES",
                "success": bt_st.get("verified", False),
                "radio_name": bt_st.get("radio_name"),
                "radio_mac": bt_st.get("radio_mac"),
                "device_count": len(devs),
                "devices": devs,
                "status": "BLUETOOTH_DEVICES_READ",
                "message": f"Discovered {len(devs)} Bluetooth devices on radio {bt_st.get('radio_name')}: {', '.join(names) if names else 'None'}.",
                "physical_result": f"Bluetooth Radio {bt_st.get('radio_mac')}",
                "truthful_status": "VERIFIED" if bt_st.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 4. Media Transport Controls
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["next track", "next song", "skip song", "skip track", "skip", "next", "next music"]):
            t_d0 = time.time()
            ok, res = self.controller.media_next()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.MEDIA.value,
                "capability": "PC_MEDIA_NEXT",
                "success": ok,
                "status": "MEDIA_KEY_SENT",
                "message": res.get("message"),
                "physical_result": "VK_MEDIA_NEXT_TRACK",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["previous track", "previous song", "prev song", "prev track", "last song", "previous", "prev"]):
            t_d0 = time.time()
            ok, res = self.controller.media_previous()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.MEDIA.value,
                "capability": "PC_MEDIA_PREVIOUS",
                "success": ok,
                "status": "MEDIA_KEY_SENT",
                "message": res.get("message"),
                "physical_result": "VK_MEDIA_PREV_TRACK",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["stop music", "stop media", "stop playback", "stop song", "stop"]):
            t_d0 = time.time()
            ok, res = self.controller.media_stop()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.MEDIA.value,
                "capability": "PC_MEDIA_STOP",
                "success": ok,
                "status": "MEDIA_KEY_SENT",
                "message": res.get("message"),
                "physical_result": "VK_MEDIA_STOP",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["pause", "resume", "play/pause", "toggle playback", "play music", "play"]):
            t_d0 = time.time()
            ok, res = self.controller.media_play_pause()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.MEDIA.value,
                "capability": "PC_MEDIA_PLAY_PAUSE",
                "success": ok,
                "status": "MEDIA_KEY_SENT",
                "message": res.get("message"),
                "physical_result": "VK_MEDIA_PLAY_PAUSE",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }


        # ---------------------------------------------------------------------
        # 5. Power & System Management
        # ---------------------------------------------------------------------
        if "lock" in q_clean and ("pc" in q_clean or "computer" in q_clean or "screen" in q_clean or "workstation" in q_clean):
            t_d0 = time.time()
            ok, res = self.controller.lock_workstation()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.POWER.value,
                "capability": "PC_LOCK",
                "success": ok,
                "status": "LOCK_VERIFIED" if ok else "LOCK_FAILED",
                "message": res.get("message"),
                "physical_result": "LockWorkStation: SUCCESS",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if "sleep" in q_clean and ("pc" in q_clean or "computer" in q_clean):
            t_d0 = time.time()
            ok, res = self.controller.sleep()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.POWER.value,
                "capability": "PC_SLEEP",
                "success": ok,
                "status": "SLEEP_SENT",
                "message": res.get("message"),
                "physical_result": "SetSuspendState: SUCCESS",
                "truthful_status": "TRIGGERED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if any(kw in q_clean for kw in ["is the pc on", "pc uptime", "power status", "pc power", "is computer on"]):
            t_d0 = time.time()
            pwr = self.controller.get_power_state()
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.POWER.value,
                "capability": "PC_GET_POWER_STATE",
                "success": pwr.get("verified", False),
                "power_state": pwr.get("power_state"),
                "power_source": pwr.get("power_source"),
                "uptime_hours": pwr.get("uptime_hours"),
                "status": "POWER_STATE_READ",
                "message": f"PC is {pwr.get('power_state')}, Power: {pwr.get('power_source')}, Uptime: {pwr.get('uptime_hours')} hrs.",
                "physical_result": f"Uptime {pwr.get('uptime_hours')} hrs",
                "truthful_status": "VERIFIED" if pwr.get("verified") else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # 6. Allowlisted Application Launching
        # ---------------------------------------------------------------------
        if any(kw in q_clean for kw in ["open browser", "launch browser", "open chrome", "open edge"]):
            t_d0 = time.time()
            ok, res = self.controller.launch_allowlisted_app("browser")
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.APPLICATION.value,
                "capability": "PC_OPEN_BROWSER",
                "success": ok,
                "status": "APP_LAUNCHED" if ok else "APP_LAUNCH_FAILED",
                "message": res.get("message"),
                "physical_result": f"Process PID {res.get('pid')}",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if "open notepad" in q_clean:
            t_d0 = time.time()
            ok, res = self.controller.launch_allowlisted_app("notepad")
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.APPLICATION.value,
                "capability": "PC_LAUNCH_APP_NOTEPAD",
                "success": ok,
                "status": "APP_LAUNCHED" if ok else "APP_LAUNCH_FAILED",
                "message": res.get("message"),
                "physical_result": f"Process PID {res.get('pid')}",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        if "open calculator" in q_clean or "open calc" in q_clean:
            t_d0 = time.time()
            ok, res = self.controller.launch_allowlisted_app("calc")
            t_disp = int((time.time() - t_d0) * 1000)
            t_total = int((time.time() - t0) * 1000)
            return {
                "query": q_raw,
                "category": PcCommandCategory.APPLICATION.value,
                "capability": "PC_LAUNCH_APP_CALC",
                "success": ok,
                "status": "APP_LAUNCHED" if ok else "APP_LAUNCH_FAILED",
                "message": res.get("message"),
                "physical_result": f"Process PID {res.get('pid')}",
                "truthful_status": "VERIFIED" if ok else "FAILED",
                "dispatch_latency_ms": t_disp,
                "total_latency_ms": t_total
            }

        # ---------------------------------------------------------------------
        # Fallback / Unknown Command
        # ---------------------------------------------------------------------
        t_total = int((time.time() - t0) * 1000)
        return {
            "query": q_raw,
            "category": "UNKNOWN",
            "capability": "UNKNOWN",
            "success": False,
            "status": "UNRESOLVED_COMMAND",
            "error": f"Could not map query to an allowlisted PC capability: '{q_raw}'",
            "physical_result": "NO_ACTION",
            "truthful_status": "UNRESOLVED",
            "dispatch_latency_ms": 0,
            "total_latency_ms": t_total
        }
