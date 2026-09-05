#!/usr/bin/env python3
"""
================================================================================
ANIMUS OPTICAL VISION & PERCEPTION RADAR — LIVE CAMERA TEST
================================================================================
Real-time terminal visualizer and interactive telemetry monitor for Sir's
physical HD camera (DirectShow Index 2, USB VID_349C&PID_2317).

Demonstrates:
1. Instantaneous optical luminance / ambient lighting conditions (0-255 Lux).
2. Dynamic inter-frame motion energy flux with zero-cloud, in-RAM processing.
3. Debounced desk occupancy state machine (EMPTY -> ARRIVED -> PRESENT -> DEPARTED).
4. Continuous seated focus / ergonomic timer.
5. Autonomous Animus proactive reflexes triggered by Sir's physical arrival.
================================================================================
"""

import os
import sys
import time
import argparse
import urllib.request
import json

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DAEMON_URL = "http://127.0.0.1:8095/api/vision/presence"



def draw_bar(value: float, max_value: float = 100.0, length: int = 24, fill_char: str = "█", empty_char: str = "░") -> str:
    """Renders a smooth ASCII progress gauge."""
    clamped = max(0.0, min(float(value), float(max_value)))
    ratio = clamped / max_value if max_value > 0 else 0.0
    filled_len = int(round(ratio * length))
    filled = fill_char * filled_len
    empty = empty_char * (length - filled_len)
    return f"[{filled}{empty}]"


def format_duration(seconds: float) -> str:
    """Formats seconds into HH:MM:SS."""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_telemetry():
    """Polls live telemetry from Animus daemon vision endpoint."""
    req = urllib.request.Request(DAEMON_URL, headers={"User-Agent": "Animus-Radar/1.0"})
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def render_hud(data: dict, cycle: int):
    """Renders high-tech ASCII executive HUD."""
    online = data.get("camera_online", False)
    device = data.get("hardware_device", "Unknown Camera")
    res = data.get("resolution", "320x240")
    state = data.get("state", "EMPTY")
    is_present = data.get("is_present", False)
    confidence = data.get("confidence", 0.0) * 100.0
    motion = data.get("motion_score", 0.0)
    lux = data.get("ambient_luminance", 0.0)
    contrast = data.get("contrast_score", 0.0)
    lighting_cond = data.get("lighting_condition", "UNKNOWN")
    seated_sec = data.get("seated_duration_seconds", 0.0)

    # State Badge Styling
    if not online or state == "DISCONNECTED":
        state_badge = "[ ⚠️ DISCONNECTED - UNPLUGGED ]"
    elif state == "PRESENT":
        state_badge = "[ ● PRESENT - SIR AT DESK ]"
    elif state == "ARRIVED":
        state_badge = "[ ➔ ARRIVED - WELCOME SIR  ]"
    elif state == "DEPARTED":
        state_badge = "[ ◌ DEPARTED - DESK EMPTY ]"
    else:
        state_badge = "[ ○ EMPTY - DESK CLEAR    ]"

    # Lighting gauge (0-255)
    lux_bar = draw_bar(lux, max_value=255.0, length=24)
    # Motion gauge (0-100)
    motion_bar = draw_bar(motion, max_value=100.0, length=24)

    # Proactive Suggestion based on telemetry
    if not online or state == "DISCONNECTED":
        reflex = "HARDWARE ALERT: Physical USB camera is disconnected (Windows Code 45). Please reconnect USB cable."
    elif not is_present:
        reflex = "Desk is clear. Background monitoring active with sub-0.5% CPU."
    elif state == "ARRIVED":
        reflex = "Sir has arrived! Ready to print Morning Briefing on HP Ink Tank 310."
    elif seated_sec > 3600:
        reflex = "Sir has been focused for > 1 hour. Suggesting ergonomic stretch & hydration."
    elif lighting_cond == "DARK / CINEMA":
        reflex = "Cinema lighting detected. Screen glare minimized for focused reading."
    elif lighting_cond == "DIM / AMBIENT":
        reflex = "Ambient lighting detected. Optimal for relaxed evening data analysis."
    else:
        reflex = "Optimal illumination detected. Deep work focus session active."

    hud = []
    hud.append("╔══════════════════════════════════════════════════════════════════════════════════╗")
    hud.append("║                   ANIMUS OPTICAL VISION & PERCEPTION RADAR                       ║")
    hud.append("║            100% Offline | Ephemeral In-RAM Processing | Zero Cloud               ║")
    hud.append("╚══════════════════════════════════════════════════════════════════════════════════╝")
    hud.append(f"  Hardware Device : {device} ({res})")
    hud.append(f"  Sensor Status   : {'ONLINE (Streaming)' if online else 'OFFLINE (Unplugged)'}")
    hud.append(f"  Telemetry Cycle : #{cycle} | Timestamp: {time.strftime('%H:%M:%S')}")
    hud.append("─" * 82)
    hud.append(f"  Desk Occupancy  : {state_badge}  (Confidence: {confidence:.0f}%)")
    hud.append(f"  Seated Duration : {format_duration(seated_sec)} (Focus Timer)")
    hud.append("─" * 82)
    hud.append(f"  Ambient Light   : {lux_bar} {lux:5.1f} / 255 LUX  [{lighting_cond}]")
    hud.append(f"  Motion Energy   : {motion_bar} {motion:5.1f} %  Flux")
    hud.append(f"  Optical Contrast: {contrast:5.1f} StdDev Variance")
    hud.append("─" * 82)
    hud.append(f"  Animus Reflex   : ⚡ {reflex}")
    hud.append("═" * 82)
    return "\n".join(hud)


def main():
    parser = argparse.ArgumentParser(description="Animus Optical Vision Live Radar")
    parser.add_argument("--cycles", type=int, default=0, help="Number of telemetry cycles to run (0 = continuous)")
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")
    args = parser.parse_args()

    print("\nConnecting to Animus Vision Perception Engine...")
    cycle = 0
    try:
        while True:
            cycle += 1
            try:
                data = get_telemetry()
                hud_str = render_hud(data, cycle)
                # Clear terminal or print separator
                if os.name == "nt":
                    os.system("cls")
                else:
                    print("\033[H\033[J", end="")
                print(hud_str)
                print("\n[Interactive Tests Sir Can Try Right Now]")
                print(" 1. Wave your hand in front of the lens  -> Watch 'Motion Energy' pulse immediately.")
                print(" 2. Cover the camera lens with your hand -> Watch 'Ambient Light' drop to DARK / CINEMA.")
                print(" 3. Shine phone torch / desk light at lens -> Watch 'Ambient Light' surge to BRIGHT / DAYLIGHT.")
                print(" 4. Sit in your chair                    -> Watch Occupancy flip from EMPTY -> ARRIVED -> PRESENT.")
                print(" Press Ctrl+C to exit radar.")
            except Exception as e:
                print(f"[Radar Error] Failed to read optical telemetry: {e}")

            if args.cycles > 0 and cycle >= args.cycles:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[+] Optical Vision Radar gracefully closed. Background perception continues in daemon.")


if __name__ == "__main__":
    main()
