"""
Physical Acceptance Suite for Phase E.3.2: Zebronics PixaPlay 25 Projector Capabilities.
Runs against real hardware at 192.168.1.10:5555.
Measures latency, validates physical invariants, tests read-back verification,
and outputs a structured results artifact.
"""

import sys
import time
import json
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("projector_physical_acceptance")

from projector_controller import (
    ProjectorController,
    ProjectorPowerState,
    ProjectorSource,
    ProjectorSignalState,
    ThermalStatus,
    FanStatus
)

def run_acceptance_suite() -> Dict[str, Any]:
    print("=" * 80)
    print("   ANIMUS SMART ROOM — PHASE E.3.2 PROJECTOR PHYSICAL ACCEPTANCE SUITE")
    print("   Target: Zebronics PixaPlay 25 (192.168.1.10:5555)")
    print("=" * 80)

    proj = ProjectorController(target="192.168.1.10:5555")

    # Step 1: Connect to physical hardware
    t0 = time.time()
    connected = proj.connect()
    lat_conn = int((time.time() - t0) * 1000)
    is_ready, state = proj.is_connected(auto_connect=False)
    print(f"\n[1] Physical ADB Connection: connected={connected}, state={state} ({lat_conn}ms)")
    if not is_ready:
        print(f"FATAL: Projector is not reachable over ADB (state: {state}). Aborting physical suite.")
        sys.exit(1)

    results: List[Dict[str, Any]] = []

    def record(name: str, passed: bool, lat_ms: int, verif_method: str, detail: Any, notes: str = ""):
        res = {
            "capability": name,
            "passed": passed,
            "latency_ms": lat_ms,
            "verification_method": verif_method,
            "detail": detail,
            "notes": notes
        }
        results.append(res)
        status_sym = "PASS [OK]" if passed else "FAIL [X]"
        print(f"  -> {name:<36} : {status_sym} ({lat_ms:>4}ms) | {notes or str(detail)[:60]}")

    # Step 2: Test PROJECTOR_GET_POWER_STATE
    t0 = time.time()
    pwr = proj.get_power_state()
    lat_pwr = int((time.time() - t0) * 1000)
    pwr_ok = pwr.get("reachable") is True and pwr.get("power_state") in [ProjectorPowerState.ON.value, ProjectorPowerState.AWAKE.value]
    record(
        "PROJECTOR_GET_POWER_STATE",
        pwr_ok,
        lat_pwr,
        "dumpsys power + dumpsys display",
        pwr,
        f"State: {pwr.get('power_state')}, Wakefulness: {pwr.get('wakefulness')}, Display: {pwr.get('display_state')}"
    )

    # Step 3: Test PROJECTOR_GET_HARDWARE_HEALTH
    t0 = time.time()
    health = proj.get_hardware_health()
    lat_health = int((time.time() - t0) * 1000)
    health_ok = health.get("verified") is True and health.get("temperature_celsius") is not None
    record(
        "PROJECTOR_GET_HARDWARE_HEALTH",
        health_ok,
        lat_health,
        "getprop zysys.light_temp + main_speed + sub_speed",
        health,
        f"Temp: {health.get('temperature_celsius')}°C ({health.get('thermal_status')}), Main Fan: {health.get('main_fan_rpm')} RPM, Sub Fan: {health.get('sub_fan_rpm')} RPM"
    )

    # Step 4: Test PROJECTOR_GET_SIGNAL_STATE
    t0 = time.time()
    signal = proj.get_signal_state()
    lat_sig = int((time.time() - t0) * 1000)
    sig_ok = signal.get("verified") is True
    record(
        "PROJECTOR_GET_SIGNAL_STATE",
        sig_ok,
        lat_sig,
        "dumpsys tv_input (HDMI0000C2 / TvStreamConfig)",
        signal,
        f"Signal State: {signal.get('signal_state')}, Active Stream: {signal.get('active_stream')}"
    )

    # Step 5: Test PROJECTOR_GET_CURRENT_INPUT
    t0 = time.time()
    cur_src = proj.get_current_source()
    lat_src = int((time.time() - t0) * 1000)
    src_ok = cur_src in [ProjectorSource.HDMI_1, ProjectorSource.ANDROID_HOME, ProjectorSource.USB]
    record(
        "PROJECTOR_GET_CURRENT_INPUT",
        src_ok,
        lat_src,
        "dumpsys activity activities foreground inspection",
        cur_src.value,
        f"Current Source: {cur_src.value}"
    )

    # Step 6: Test PROJECTOR_GET_BRIGHTNESS & PROJECTOR_SET_BRIGHTNESS
    t0 = time.time()
    initial_b = proj.get_brightness()
    lat_b_get = int((time.time() - t0) * 1000)
    record(
        "PROJECTOR_GET_BRIGHTNESS",
        initial_b > 0,
        lat_b_get,
        "settings get system screen_brightness",
        {"initial_brightness_percent": initial_b},
        f"Initial Brightness: {initial_b}%"
    )

    # Set brightness to 70% with read-back verification
    target_test_b = 70 if initial_b != 70 else 60
    t0 = time.time()
    set_ok, actual_b = proj.set_brightness(target_test_b)
    lat_b_set = int((time.time() - t0) * 1000)
    record(
        "PROJECTOR_SET_BRIGHTNESS (Set 70%)",
        set_ok and abs(actual_b - target_test_b) <= 2,
        lat_b_set,
        "settings put + read-back verification",
        {"requested": target_test_b, "actual": actual_b},
        f"Set to {target_test_b}% -> Verified actual: {actual_b}%"
    )

    # Restore initial brightness with read-back verification
    t0 = time.time()
    rest_ok, actual_rest_b = proj.set_brightness(initial_b)
    lat_b_rest = int((time.time() - t0) * 1000)
    record(
        "PROJECTOR_SET_BRIGHTNESS (Restore)",
        rest_ok and abs(actual_rest_b - initial_b) <= 2,
        lat_b_rest,
        "settings put + read-back verification",
        {"restored": initial_b, "actual": actual_rest_b},
        f"Restored to {initial_b}% -> Verified actual: {actual_rest_b}%"
    )

    # Step 7: Test PROJECTOR_AUTO_FOCUS
    t0 = time.time()
    focus_res = proj.auto_focus()
    lat_focus = int((time.time() - t0) * 1000)
    focus_ok = focus_res.get("status") == "TRIGGERED" and focus_res.get("verified") is False
    record(
        "PROJECTOR_AUTO_FOCUS",
        focus_ok,
        lat_focus,
        "am start -a com.zhiying.AUTO_FOCUS_CORRECTION",
        focus_res,
        f"Status: {focus_res.get('status')}, Truthful verified flag: {focus_res.get('verified')}"
    )

    # Allow optical motor routine 2 seconds
    time.sleep(2.0)

    # Step 8: Test PROJECTOR_AUTO_KEYSTONE
    t0 = time.time()
    keystone_res = proj.auto_keystone()
    lat_keystone = int((time.time() - t0) * 1000)
    keystone_ok = keystone_res.get("status") == "TRIGGERED" and keystone_res.get("verified") is False
    record(
        "PROJECTOR_AUTO_KEYSTONE",
        keystone_ok,
        lat_keystone,
        "am start -a com.zhiying.ONE_AUTO_CORRECTION_KEYSTONE",
        keystone_res,
        f"Status: {keystone_res.get('status')}, Truthful verified flag: {keystone_res.get('verified')}"
    )

    # Allow gyro routine 2 seconds
    time.sleep(2.0)

    # Step 9: Test PROJECTOR_SINGLE_HDMI_PORT_INVARIANT
    t0 = time.time()
    hdmi2_res = proj.set_hdmi(2)
    lat_hdmi2 = int((time.time() - t0) * 1000)
    hdmi2_ok = hdmi2_res is False  # Must be rejected because hardware only has 1 port
    record(
        "PROJECTOR_SINGLE_HDMI_PORT_INVARIANT",
        hdmi2_ok,
        lat_hdmi2,
        "set_hdmi(2) hardware constraint guard",
        {"set_hdmi_2_result": hdmi2_res},
        "Correctly rejected HDMI_2 (Physical hardware has only 1 HDMI port)"
    )

    # Step 10: Test PROJECTOR_SWITCH_HDMI1
    t0 = time.time()
    hdmi1_ok = proj.set_hdmi(1)
    lat_hdmi1 = int((time.time() - t0) * 1000)
    time.sleep(1.0)
    cur_src_after = proj.get_current_source()
    record(
        "PROJECTOR_SWITCH_HDMI1",
        hdmi1_ok and cur_src_after == ProjectorSource.HDMI_1,
        lat_hdmi1,
        "am start com.newlink.nlsource + foreground verification",
        {"current_source": cur_src_after.value},
        f"Switched to HDMI 1 -> Verified foreground: {cur_src_after.value}"
    )

    # Step 11: Test PROJECTOR_COLD_POWER_ON_INVARIANT
    dev_info = proj.get_device_info()
    cold_supported = dev_info.get("cold_power_on_supported_via_adb")
    record(
        "PROJECTOR_COLD_POWER_ON_INVARIANT",
        cold_supported is False,
        0,
        "Hardware architectural invariant",
        {"cold_power_on_supported_via_adb": cold_supported},
        "Cold power-on explicitly classified as NOT_AVAILABLE_VIA_ADB (requires IR blaster)"
    )

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target": "192.168.1.10:5555",
        "model": "Zebronics PixaPlay 25 (NL5H00X)",
        "total_capabilities_tested": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "results": results
    }

    with open("phase_e32_projector_physical_acceptance_results.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 80)
    print(f"   PHYSICAL ACCEPTANCE SUMMARY: {summary['passed']} / {summary['total_capabilities_tested']} PASSED")
    print("=" * 80)
    return summary

if __name__ == "__main__":
    run_acceptance_suite()
