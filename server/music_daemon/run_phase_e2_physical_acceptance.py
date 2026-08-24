"""
ANIMUS SMART ROOM — PHASE E.2 PHYSICAL ACCEPTANCE BATTERY
Executes comprehensive physical device acceptance across:
1. Fire TV Connectivity & Direct Bluetooth Broadcast (5-cycle latency audit).
2. Four Key Streaming Providers (YouTube, Netflix, Prime Video, Apple TV).
3. End-to-End Cinema Start & Stop Orchestration.
4. Natural Language Content Resolution & State Synchronization.
"""

import sys
import time
import json
import logging
from typing import Dict, Any, List

from fire_tv_controller import FireTvController
from projector_controller import ProjectorController
from bluetooth_helper import BluetoothAudioHelper
from player import MpvPlayer
from media_provider_registry import MediaProviderRegistry, ProviderCapabilityStatus
from content_resolver import SmartRoomContentResolver
from fire_tv_capabilities import FireTVCapabilityRegistry, FireTVState
from firetv_service import FireTvService, ServiceResult
from automation_registry import AutomationRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PhaseE2PhysicalAcceptance")


def run_phase_e2_acceptance():
    print("=" * 80)
    print("ANIMUS SMART ROOM — PHASE E.2 PHYSICAL ACCEPTANCE TEST SUITE")
    print("=" * 80)

    # 1. Initialize physical subsystem controllers
    print("\n[1/5] Initializing Physical Controllers...")
    ftv = FireTvController(target="192.168.1.5:5555", required_bt_mac="54:15:89:DC:A5:79")
    proj = ProjectorController()
    player = MpvPlayer(preferred_device_keyword="LG SNC4R")
    bt_helper = player.bt_helper
    prov_reg = MediaProviderRegistry()
    content_res = SmartRoomContentResolver(provider_registry=prov_reg)
    capabilities = FireTVCapabilityRegistry(
        fire_tv=ftv,
        projector=proj,
        bt_helper=bt_helper,
        player=player,
        provider_registry=prov_reg
    )
    auto_reg = AutomationRegistry()
    service = FireTvService(
        capabilities=capabilities,
        fire_tv=ftv,
        projector=proj,
        bt_helper=bt_helper,
        player=player,
        provider_registry=prov_reg,
        content_resolver=content_res,
        automation_registry=auto_reg
    )

    # Pre-test connectivity check
    is_conn, status_str = ftv.is_connected(auto_connect=True)
    print(f"  -> Fire TV ADB Connectivity: {is_conn} ({status_str})")
    if not is_conn:
        print("[FAIL] Fire TV is unreachable at 192.168.1.5:5555. Aborting physical suite.")
        sys.exit(1)

    results: Dict[str, Any] = {
        "timestamp": time.time(),
        "fire_tv_target": "192.168.1.5:5555",
        "soundbar_mac": "54:15:89:DC:A5:79",
        "bt_cycles": [],
        "provider_matrix": {},
        "cinema_cycles": [],
        "natural_language_tests": []
    }

    # --------------------------------------------------------------------------
    # TEST SUITE 1: 5-CYCLE DIRECT BLUETOOTH AUDIT
    # --------------------------------------------------------------------------
    print("\n[2/5] Running 5-Cycle Direct Bluetooth Helper Audit...")
    for cycle in range(1, 6):
        print(f"\n  --- Bluetooth Cycle {cycle}/5 ---")
        # Step A: Disconnect
        t_disc_start = time.time()
        disc_ok, disc_method = ftv.disconnect_soundbar(timeout_seconds=4.0)
        disc_lat_ms = int((time.time() - t_disc_start) * 1000)
        time.sleep(0.5)
        bt_st_after_disc = ftv.is_required_bluetooth_connected()
        print(f"    Disconnect: success={disc_ok}, method={disc_method}, lat={disc_lat_ms}ms, connected_now={bt_st_after_disc}")

        # Step B: Connect Direct
        t_conn_start = time.time()
        conn_ok, conn_method = ftv.connect_soundbar_with_method(timeout_seconds=6.0, force_fallback=False)
        conn_lat_ms = int((time.time() - t_conn_start) * 1000)
        time.sleep(0.5)
        bt_st_after_conn = ftv.is_required_bluetooth_connected()
        print(f"    Connect: success={conn_ok}, method={conn_method}, lat={conn_lat_ms}ms, connected_now={bt_st_after_conn}")

        results["bt_cycles"].append({
            "cycle": cycle,
            "disconnect_success": disc_ok,
            "disconnect_method": disc_method,
            "disconnect_latency_ms": disc_lat_ms,
            "connect_success": conn_ok,
            "connect_method": conn_method,
            "connect_latency_ms": conn_lat_ms,
            "verified_connected": bt_st_after_conn
        })

    # --------------------------------------------------------------------------
    # TEST SUITE 2: FOUR KEY STREAMING PROVIDERS
    # --------------------------------------------------------------------------
    print("\n[3/5] Testing 4 Key Streaming Providers (YouTube, Netflix, Prime Video, Apple TV)...")
    providers_to_test = [
        {"id": "youtube", "name": "YouTube", "content": "07d2dXHYb94", "expected_autoplay": True},
        {"id": "netflix", "name": "Netflix", "content": "81154455", "expected_autoplay": False},
        {"id": "prime_video", "name": "Prime Video", "content": "B08W53R987", "expected_autoplay": False},
        {"id": "apple_tv", "name": "Apple TV", "content": "ted-lasso", "expected_autoplay": False},
    ]

    for p in providers_to_test:
        pid = p["id"]
        print(f"\n  --- Testing Provider: {p['name']} ({pid}) ---")
        t0 = time.time()
        res = service.watch_content(query=p["content"], provider=pid, direct_play_first=True)
        dur = int((time.time() - t0) * 1000)

        # Telemetry verification
        st = service.get_live_state()
        print(f"    Result: success={res.success}, truthful_status='{res.truthful_status}', latency={dur}ms")
        print(f"    Physical State: fg_app='{st.foreground_app}', playback_state='{st.playback_state}', active_provider='{st.active_provider}'")

        results["provider_matrix"][pid] = {
            "display_name": p["name"],
            "success": res.success,
            "truthful_status": res.truthful_status,
            "action_taken": res.action_taken,
            "duration_ms": dur,
            "verified_foreground": st.foreground_app,
            "playback_state": st.playback_state,
            "expected_autoplay": p["expected_autoplay"]
        }
        time.sleep(2.0)
        # Return home between apps
        capabilities.execute_capability("navigation_home")
        time.sleep(1.0)

    # --------------------------------------------------------------------------
    # TEST SUITE 3: CINEMA START & STOP FULL ORCHESTRATION CYCLE
    # --------------------------------------------------------------------------
    print("\n[4/5] Testing Cinema Full Room Orchestration (Start & Stop)...")
    # Start Cinema
    t_start = time.time()
    res_start = service.start_cinema(content="07d2dXHYb94", provider="youtube")
    lat_start = int((time.time() - t_start) * 1000)
    print(f"  -> Cinema Start: success={res_start.success}, status='{res_start.truthful_status}', latency={lat_start}ms, steps={res_start.action_taken}")

    time.sleep(3.0)

    # Stop Cinema
    t_stop = time.time()
    res_stop = service.stop_cinema(turn_off_projector=False)
    lat_stop = int((time.time() - t_stop) * 1000)
    print(f"  -> Cinema Stop: success={res_stop.success}, status='{res_stop.truthful_status}', latency={lat_stop}ms, steps={res_stop.action_taken}")

    results["cinema_cycles"].append({
        "start": {"success": res_start.success, "status": res_start.truthful_status, "latency_ms": lat_start},
        "stop": {"success": res_stop.success, "status": res_stop.truthful_status, "latency_ms": lat_stop}
    })

    # --------------------------------------------------------------------------
    # TEST SUITE 4: NATURAL LANGUAGE SPOKEN COMMAND DISPATCH
    # --------------------------------------------------------------------------
    print("\n[5/5] Testing Spoken Natural Language Command Resolution...")
    nl_commands = [
        "Play Article 15 on YouTube",
        "Put on Stranger Things on Netflix",
        "Open Prime Video",
        "Switch to Apple TV",
        "Quick break",
        "Goodnight"
    ]

    for cmd in nl_commands:
        t_nl = time.time()
        res_nl = service.watch_content(query=cmd) if "break" not in cmd and "goodnight" not in cmd else service.execute_automation("quick_break" if "break" in cmd else "goodnight")
        dur_nl = int((time.time() - t_nl) * 1000)
        print(f"  -> Command: \"{cmd}\" -> success={res_nl.success}, status='{res_nl.truthful_status}', action={res_nl.action_taken} ({dur_nl}ms)")
        results["natural_language_tests"].append({
            "command": cmd,
            "success": res_nl.success,
            "status": res_nl.truthful_status,
            "action": res_nl.action_taken,
            "latency_ms": dur_nl
        })
        time.sleep(1.5)

    # Summary Report
    print("\n" + "=" * 80)
    print("PHASE E.2 ACCEPTANCE AUDIT COMPLETE")
    print("=" * 80)
    avg_bt_conn = sum(c["connect_latency_ms"] for c in results["bt_cycles"]) / len(results["bt_cycles"])
    avg_bt_disc = sum(c["disconnect_latency_ms"] for c in results["bt_cycles"]) / len(results["bt_cycles"])
    print(f"Direct Bluetooth Connect Average Latency:    {avg_bt_conn:.1f}ms")
    print(f"Direct Bluetooth Disconnect Average Latency: {avg_bt_disc:.1f}ms")
    print(f"Provider Success Rate:                       {sum(1 for p in results['provider_matrix'].values() if p['success'])}/{len(results['provider_matrix'])}")
    print(f"Cinema Cycle Success:                        {res_start.success and res_stop.success}")
    print("=" * 80)

    with open("phase_e2_physical_acceptance_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to phase_e2_physical_acceptance_results.json")


if __name__ == "__main__":
    run_phase_e2_acceptance()
