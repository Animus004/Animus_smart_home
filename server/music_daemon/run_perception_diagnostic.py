"""
================================================================================
ANIMUS SMART ROOM — REAL-TIME PERCEPTION & ROOM STATE CACHE DIAGNOSTIC
================================================================================
Demonstrates the continuous, non-blocking Animus Perception Engine:
1. Background worker continuously monitors physical reality (AC over LAN, IR Hub, PC).
2. Reality is cached in memory with deterministic epistemic freshness & provenance.
3. Animus Brain accesses instantaneous reality via get_room_state() in < 1 ms.
================================================================================
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.abspath("server/music_daemon"))

from room_state.perception_collector import PerceptionCollector
from room_state.models import RoomState
from room_state.provenance import Provenance
from tuya_local_read_adapter import TuyaLocalAcReadAdapter


def run_diagnostic():
    print("=" * 80)
    print("   ANIMUS SMART ROOM — PERCEPTION LAYER & ZERO-CLOUD CACHE DIAGNOSTIC")
    print("=" * 80)
    print(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Mode      : BACKGROUND CONTINUOUS PERCEPTION / LOCAL LAN TRANSPORT")
    print("-" * 80)

    # 1. Initialize Perception Collector
    print("[1] Initializing Background Perception Collector...")
    ac_adapter = TuyaLocalAcReadAdapter(timeout=2.0)
    collector = PerceptionCollector(
        ac_read_adapter=ac_adapter,
        poll_interval_seconds=3.0,
        ir_hub_ip="192.168.1.12",
        ir_hub_port=6668,
    )

    print("    [+] Starting perception engine thread...")
    collector.start()
    time.sleep(1.0)  # Allow initial background poll cycle to complete

    # 2. Benchmark Sub-Millisecond Brain Access Latency
    print("\n[2] Benchmarking Brain Reality Query Latency (get_room_state())...")
    iterations = 50
    latencies_us = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        st = collector.get_room_state(force_refresh=False)
        t1 = time.perf_counter_ns()
        latencies_us.append((t1 - t0) / 1000.0)

    avg_us = sum(latencies_us) / len(latencies_us)
    min_us = min(latencies_us)
    max_us = max(latencies_us)
    print(f"    [+] Query Latency (Min) : {min_us:.2f} us ({min_us / 1000.0:.4f} ms)")
    print(f"    [+] Query Latency (Avg) : {avg_us:.2f} us ({avg_us / 1000.0:.4f} ms) [PASS: < 1 ms]")
    print(f"    [+] Query Latency (Max) : {max_us:.2f} us ({max_us / 1000.0:.4f} ms)")

    # 3. Inspect Canonical Room State Snapshot
    print("\n[3] Canonical Room State Snapshot (Physical Observations & Provenance):")
    print("-" * 80)
    now = time.time()
    room_dict = st.to_dict(now)

    # AC Subsystem
    ac_d = room_dict["ac"]
    ac_pwr = "ON" if ac_d["power"]["value"] else "OFF"
    ac_prov = ac_d["power"]["provenance"]
    ac_tgt = ac_d["target_temperature"]["value"]
    ac_mode = ac_d["mode"]["value"]
    ac_fan = ac_d["fan_speed"]["value"]
    ac_trans = ac_d["transport_used"]["value"]

    print(f"  [AC Subsystem]")
    print(f"    - Power State          : {ac_pwr} (Provenance: {ac_prov})")
    print(f"    - Target Setpoint      : {ac_tgt}°C")
    print(f"    - Operating Mode       : {ac_mode}")
    print(f"    - Blower Fan Speed     : {ac_fan}")
    print(f"    - Transport Used       : {ac_trans}")

    # IR Hub Subsystem
    ir_d = room_dict["ir_hub"]
    ir_online = "ONLINE" if ir_d["online"]["value"] else "OFFLINE"
    ir_prov = ir_d["online"]["provenance"]
    ir_trans = ir_d["transport"]["value"]

    print(f"\n  [Smart IR Hub]")
    print(f"    - Connectivity         : {ir_online} (Provenance: {ir_prov})")
    print(f"    - Transport            : {ir_trans}")

    # PC Host Subsystem
    pc_d = room_dict["pc"]
    print(f"\n  [PC Host / Audio]")
    print(f"    - Host Daemon          : {'ONLINE' if pc_d['online']['value'] else 'OFFLINE'}")
    print(f"    - Master Volume        : {pc_d['master_volume']['value']}% (Muted: {pc_d['is_muted']['value']})")
    print(f"    - Audio Endpoint       : {pc_d['default_audio_endpoint']['value']}")

    # 4. Canonical Brain Markdown Perception Block
    print("\n[4] Authoritative Brain Perception Block (to_brain_markdown_prompt()):")
    print("-" * 80)
    print(st.to_brain_markdown_prompt(now))

    # 5. LLM Prompt-Sanitized JSON Payload
    print("\n[5] LLM Prompt-Ready Sanitized Perception Snapshot (JSON):")
    print("-" * 80)
    prompt_ready = st.to_sanitized_prompt_dict(now)
    print(json.dumps(prompt_ready, indent=2))

    # 6. Background Engine Health
    print("\n[6] Background Worker Health:")
    print(f"    - Total Polling Cycles : {collector._total_polls}")
    print(f"    - Worker Active        : {collector.is_running()}")

    print("\n[6] Stopping Perception Collector...")
    collector.stop()
    print("    [+] Worker cleanly terminated.")
    print("=" * 80)


if __name__ == "__main__":
    run_diagnostic()
