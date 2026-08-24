"""
Phase E.5 Live Physical PC Acceptance Test Runner.
Executes real hardware and OS verification against the PC controller, CoreAudio,
Bluetooth subsystem, Media transports, and Natural Language Router.
"""

import sys
import time
import json
import logging
from typing import Dict, Any, List

from pc_controller import PcController
from pc_command_router import PcCommandRouter, PcCommandCategory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pc_physical_acceptance")

class PcPhysicalAcceptanceRunner:
    def __init__(self):
        self.controller = PcController()
        self.router = PcCommandRouter(controller=self.controller)
        self.results: List[Dict[str, Any]] = []

    def log_result(self, test_num: int, name: str, passed: bool, details: Dict[str, Any], latency_ms: float):
        status_str = "PASS" if passed else "FAIL"
        entry = {
            "test_num": test_num,
            "test_name": name,
            "passed": passed,
            "status": status_str,
            "latency_ms": round(latency_ms, 2),
            "details": details
        }
        self.results.append(entry)
        print(f"[{status_str}] Test {test_num:02d}: {name} ({latency_ms:.2f}ms)")
        if not passed:
            print(f"       Details: {details}")

    def run_all(self):
        print("\n================================================================================")
        print("  ANIMUS SMART ROOM — PHASE E.5 LIVE PC PHYSICAL ACCEPTANCE TEST SUITE")
        print("================================================================================\n")

        test_idx = 1

        # ---------------------------------------------------------------------
        # 1. LIVE PC Identity & Power State
        # ---------------------------------------------------------------------
        t0 = time.time()
        pwr = self.controller.get_power_state()
        t_el = (time.time() - t0) * 1000
        p_ok = pwr.get("verified") and pwr.get("power_state") == "AWAKE_AND_RUNNING"
        self.log_result(test_idx, "LIVE_PC_POWER_AND_UPTIME_TELEMETRY", p_ok, pwr, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 2. LIVE Audio Endpoints & Default Device
        # ---------------------------------------------------------------------
        t0 = time.time()
        ast = self.controller.get_audio_status()
        t_el = (time.time() - t0) * 1000
        a_ok = ast.get("verified") and bool(ast.get("default_endpoint", {}).get("id"))
        self.log_result(test_idx, "LIVE_COREAUDIO_ENDPOINT_QUERY", a_ok, {
            "default_endpoint": ast.get("default_endpoint"),
            "active_count": len(ast.get("active_endpoints", []))
        }, t_el)
        test_idx += 1

        # Save initial state for safe non-destructive restoration
        orig_vol = ast.get("master_volume", 80)
        orig_mute = ast.get("is_muted", False)

        # ---------------------------------------------------------------------
        # 3. LIVE CoreAudio Volume Set 82% & Readback
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok82, res82 = self.controller.set_volume(82)
        t_el = (time.time() - t0) * 1000
        v82_ok = ok82 and abs(res82.get("master_volume", 0) - 82) <= 1
        self.log_result(test_idx, "LIVE_COREAUDIO_VOLUME_SET_82_READBACK", v82_ok, res82, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 4. LIVE CoreAudio Volume Set 68% & Readback
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok68, res68 = self.controller.set_volume(68)
        t_el = (time.time() - t0) * 1000
        v68_ok = ok68 and abs(res68.get("master_volume", 0) - 68) <= 1
        self.log_result(test_idx, "LIVE_COREAUDIO_VOLUME_SET_68_READBACK", v68_ok, res68, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 5. LIVE CoreAudio Volume Idempotency
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok_idemp, res_idemp = self.controller.set_volume(68)
        t_el = (time.time() - t0) * 1000
        idemp_ok = ok_idemp and res_idemp.get("idempotent") is True
        self.log_result(test_idx, "LIVE_COREAUDIO_VOLUME_IDEMPOTENCY", idemp_ok, res_idemp, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 6. LIVE CoreAudio Volume Lower/Upper Bounds Rejections
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok_neg, res_neg = self.controller.set_volume(-10)
        ok_high, res_high = self.controller.set_volume(150)
        t_el = (time.time() - t0) * 1000
        bounds_ok = (not ok_neg and res_neg.get("status") == "INVALID_PARAMETER") and \
                    (not ok_high and res_high.get("status") == "INVALID_PARAMETER")
        self.log_result(test_idx, "LIVE_COREAUDIO_VOLUME_BOUNDS_REJECTION", bounds_ok, {
            "neg_res": res_neg, "high_res": res_high
        }, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 7. LIVE CoreAudio Mute True & Readback
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok_m, res_m = self.controller.set_mute(True)
        t_el = (time.time() - t0) * 1000
        m_ok = ok_m and res_m.get("is_muted") is True
        self.log_result(test_idx, "LIVE_COREAUDIO_MUTE_TRUE_READBACK", m_ok, res_m, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 8. LIVE CoreAudio Mute False (Unmute) & Readback
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok_um, res_um = self.controller.set_mute(False)
        t_el = (time.time() - t0) * 1000
        um_ok = ok_um and res_um.get("is_muted") is False
        self.log_result(test_idx, "LIVE_COREAUDIO_MUTE_FALSE_READBACK", um_ok, res_um, t_el)
        test_idx += 1

        # Restore original audio state
        self.controller.set_volume(orig_vol)
        self.controller.set_mute(orig_mute)

        # ---------------------------------------------------------------------
        # 9. LIVE Bluetooth Radio & Paired Peripherals Discovery
        # ---------------------------------------------------------------------
        t0 = time.time()
        bt_st = self.controller.get_bluetooth_status()
        t_el = (time.time() - t0) * 1000
        bt_ok = bt_st.get("verified") and bt_st.get("radio_present") is True
        self.log_result(test_idx, "LIVE_BLUETOOTH_RADIO_AND_DEVICE_DISCOVERY", bt_ok, {
            "radio_name": bt_st.get("radio_name"),
            "radio_mac": bt_st.get("radio_mac"),
            "device_count": bt_st.get("device_count")
        }, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 10. LIVE Global Media Transport Virtual Keys
        # ---------------------------------------------------------------------
        t0 = time.time()
        ok_pp, _ = self.controller.media_play_pause()
        ok_n, _ = self.controller.media_next()
        ok_pr, _ = self.controller.media_previous()
        ok_s, _ = self.controller.media_stop()
        t_el = (time.time() - t0) * 1000
        media_ok = ok_pp and ok_n and ok_pr and ok_s
        self.log_result(test_idx, "LIVE_MEDIA_TRANSPORT_DISPATCH", media_ok, {
            "play_pause": ok_pp, "next": ok_n, "prev": ok_pr, "stop": ok_s
        }, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 11. LIVE Router NL: Volume Query
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_vq = self.router.route_command("What is the PC volume?")
        t_el = (time.time() - t0) * 1000
        vq_ok = r_vq.get("success") and r_vq.get("capability") == "PC_GET_VOLUME"
        self.log_result(test_idx, "ROUTER_NL_GET_VOLUME", vq_ok, r_vq, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 12. LIVE Router NL: Volume Set 75%
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_vs = self.router.route_command("Set the PC volume to 75%.")
        t_el = (time.time() - t0) * 1000
        vs_ok = r_vs.get("success") and r_vs.get("capability") == "PC_SET_VOLUME" and abs(r_vs.get("master_volume", 0) - 75) <= 1
        self.log_result(test_idx, "ROUTER_NL_SET_VOLUME_75", vs_ok, r_vs, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 13. LIVE Router NL: Volume Louder / Quieter
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_up = self.router.route_command("Make the PC louder.")
        r_down = self.router.route_command("Make the PC quieter.")
        t_el = (time.time() - t0) * 1000
        rel_ok = r_up.get("success") and r_down.get("success")
        self.log_result(test_idx, "ROUTER_NL_VOLUME_RELATIVE_UP_DOWN", rel_ok, {
            "up_res": r_up.get("master_volume"), "down_res": r_down.get("master_volume")
        }, t_el)
        test_idx += 1

        # Restore initial volume
        self.controller.set_volume(orig_vol)

        # ---------------------------------------------------------------------
        # 14. LIVE Router NL: Mute / Unmute
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_m = self.router.route_command("Mute the computer.")
        r_um = self.router.route_command("Unmute the computer.")
        t_el = (time.time() - t0) * 1000
        mum_ok = r_m.get("success") and r_um.get("success") and r_m.get("capability") == "PC_MUTE" and r_um.get("capability") == "PC_UNMUTE"
        self.log_result(test_idx, "ROUTER_NL_MUTE_AND_UNMUTE", mum_ok, {
            "mute": r_m.get("status"), "unmute": r_um.get("status")
        }, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 15. LIVE Router NL: Bluetooth Query
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_btq = self.router.route_command("Show me connected Bluetooth devices.")
        t_el = (time.time() - t0) * 1000
        btq_ok = r_btq.get("success") and r_btq.get("capability") == "PC_GET_BLUETOOTH_DEVICES"
        self.log_result(test_idx, "ROUTER_NL_BLUETOOTH_QUERY", btq_ok, r_btq, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 16. LIVE Router NL: Media Transport Keys
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_pp = self.router.route_command("Pause the music.")
        r_nx = self.router.route_command("Skip this song.")
        r_pr = self.router.route_command("Previous song on PC.")
        r_st = self.router.route_command("Stop music on PC.")
        t_el = (time.time() - t0) * 1000
        m_nl_ok = r_pp.get("success") and r_nx.get("success") and r_pr.get("success") and r_st.get("success")
        self.log_result(test_idx, "ROUTER_NL_MEDIA_TRANSPORT_COMMANDS", m_nl_ok, {
            "pause": r_pp.get("capability"), "skip": r_nx.get("capability"), "prev": r_pr.get("capability"), "stop": r_st.get("capability")
        }, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 17. LIVE Router NL: Power State Query
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_pw = self.router.route_command("Is the PC on?")
        t_el = (time.time() - t0) * 1000
        pw_ok = r_pw.get("success") and r_pw.get("capability") == "PC_GET_POWER_STATE"
        self.log_result(test_idx, "ROUTER_NL_POWER_STATUS_QUERY", pw_ok, r_pw, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # 18. LIVE Security Guard Rejection: Arbitrary Shell & Out-of-Bounds
        # ---------------------------------------------------------------------
        t0 = time.time()
        r_sec1 = self.router.route_command("powershell -Command Remove-Item -Recurse C:\\")
        r_sec2 = self.router.route_command("rm -rf /")
        r_sec3 = self.router.route_command("Set the PC volume to 250%.")
        t_el = (time.time() - t0) * 1000
        sec_ok = (r_sec1.get("status") == "SECURITY_REJECTED") and \
                 (r_sec2.get("status") == "SECURITY_REJECTED") and \
                 (r_sec3.get("status") == "INVALID_PARAMETER" or not r_sec3.get("success"))
        self.log_result(test_idx, "SECURITY_GUARD_REJECTION_INVARIANTS", sec_ok, {
            "sec1": r_sec1.get("status"), "sec2": r_sec2.get("status"), "sec3": r_sec3.get("status")
        }, t_el)
        test_idx += 1

        # ---------------------------------------------------------------------
        # Summary & JSON Report Output
        # ---------------------------------------------------------------------
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print("\n================================================================================")
        print(f"  ACCEPTANCE RESULTS: {passed} / {total} PASSED ({(passed/total)*100:.1f}%)")
        print("================================================================================\n")

        with open("d:/AnimusSmartRoom/scratch/pc_physical_acceptance_results.json", "w") as f:
            json.dump(self.results, f, indent=2)

        return passed == total

if __name__ == "__main__":
    runner = PcPhysicalAcceptanceRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
