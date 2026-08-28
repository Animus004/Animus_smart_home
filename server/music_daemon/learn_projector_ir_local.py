"""
================================================================================
ANIMUS SMART ROOM — DIRECT LOCAL IR LEARNING & TESTING UTILITY (METHOD 3)
================================================================================
Authoritative Zero-Cloud script to capture and persist the physical Zebronics
Projector IR Power Key over the local Wi-Fi LAN (192.168.1.12:6668):

1. Activates Tuya 3.5 Hardware Study Mode on Smart IR Blaster
2. Prompts user visually and vocally (Sonia Neural via LG Soundbar)
3. Listens on DP 201 for the physical 38kHz photodiode capture
4. Decodes and persists the base64 waveform into local.properties
5. Executes an immediate local test dispatch to turn on the physical Projector!
================================================================================
"""

import os
import sys
import time
import json
import logging
from pathlib import Path

# Ensure music_daemon in path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server", "music_daemon"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ac_controller import _read_local_properties
from tts_service import RoomTtsService
import tinytuya

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("learn_ir_local")


def banner(title: str):
    width = 75
    print("\n" + "=" * width)
    print(f"   {title}".center(width))
    print("=" * width)


def save_power_key_to_properties(base64_code: str) -> bool:
    """Saves the captured IR code into local.properties."""
    candidates = [
        Path("d:/AnimusSmartRoom/local.properties"),
        Path("local.properties"),
        Path(__file__).parent.parent / "local.properties"
    ]
    key_name = "tuya.ir_blaster.power_key_base64"
    saved = False
    
    for c in candidates:
        if c.exists():
            try:
                lines = []
                found = False
                with open(c, "r", encoding="utf-8") as f:
                    for l in f:
                        if l.strip().startswith(f"{key_name}="):
                            lines.append(f"{key_name}={base64_code}\n")
                            found = True
                        else:
                            lines.append(l)
                if not found:
                    lines.append(f"{key_name}={base64_code}\n")
                with open(c, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                logger.info(f"Successfully saved {key_name} to {c.resolve()}")
                saved = True
                break
            except Exception as e:
                logger.error(f"Error saving to {c}: {e}")
                
    return saved


def main():
    banner("DIRECT LOCAL IR LEARNING UTILITY — ZEBRONICS PROJECTOR")
    
    props = _read_local_properties()
    ip = props.get("tuya.ir_blaster.ip", "192.168.1.12")
    dev_id = props.get("tuya.ir_blaster.device_id", "d7c9483cd505ac54eauidb")
    local_key = props.get("tuya.ir_blaster.local_key", "^$0WJKhafPb64-c}")

    tts = RoomTtsService(enabled=True, voice="en-GB-SoniaNeural", rate="+8%")

    print(f"Target Smart IR IP : {ip}:6668")
    print(f"Target Device ID   : {dev_id}")
    print(f"Protocol           : Tuya Protocol 3.5 (100% Zero-Cloud LAN)")
    print("-" * 75)

    # 1. Initialize Device
    d = tinytuya.Device(dev_id, ip, local_key, version=3.5)
    d.set_socketTimeout(3.0)

    # 2. Check Reachability
    t0 = time.perf_counter()
    hb = d.heartbeat()
    lat_ms = (time.perf_counter() - t0) * 1000.0
    if hb is not None and isinstance(hb, dict) and "Error" in hb:
        print(f"[ERROR] Smart IR Blaster unreachable on LAN: {hb}")
        tts.speak("Smart IR blaster is unreachable on the network, sir.", timeout=7.0)
        tts.shutdown()
        return

    print(f"[READY] Smart IR Blaster is online ({lat_ms:.1f}ms roundtrip).")

    # 3. Enter Study Mode
    banner("STEP 1: ACTIVATING LOCAL HARDWARE STUDY MODE")
    print(">>> Sending Study Mode activation packet to DP 201...")
    
    study_payload = json.dumps({"control": "study", "head": ""})
    try:
        d.set_value(201, study_payload, nowait=True)
        # Also trigger backup DP 202 study flag
        d.set_value(202, True, nowait=True)
        print(">>> [SUCCESS] Study mode dispatched to hardware!")
    except Exception as e:
        print(f"[ERROR] Failed activating study mode: {e}")
        tts.shutdown()
        return

    # 4. Spoken Instruction & User Countdown
    print("\n" + "*" * 75)
    print("   PLEASE POINT YOUR ZEBRONICS REMOTE AT THE SMART IR BLASTER (5-10 cm)")
    print("   AND PRESS THE 'POWER' BUTTON NOW!")
    print("*" * 75)
    
    tts.speak("Smart IR blaster is in learning mode. Please point the Zebronics remote at the blaster and press the power button, sir.", timeout=10.0)

    # 5. Polling Loop for Captured Signal
    banner("STEP 2: LISTENING FOR 38kHz INFRARED PULSE FROM REMOTE")
    timeout_window = 20.0
    start_time = time.time()
    captured_code = None

    while time.time() - start_time < timeout_window:
        remaining = int(timeout_window - (time.time() - start_time))
        print(f"   ... listening for remote pulse ({remaining}s remaining)...", end="\r", flush=True)
        
        try:
            st = d.status()
            if st and isinstance(st, dict):
                dps = st.get("dps", {})
                
                # Check DP 201
                raw_201 = dps.get("201")
                if raw_201 and isinstance(raw_201, str) and raw_201 not in ('{"control":"study"}', '{"control":"study","head":""}'):
                    try:
                        parsed = json.loads(raw_201)
                        if parsed.get("key1"):
                            captured_code = parsed.get("key1")
                            break
                    except Exception:
                        if len(raw_201) > 20:
                            captured_code = raw_201
                            break

                # Check DP 202
                raw_202 = dps.get("202")
                if raw_202 and isinstance(raw_202, str) and len(raw_202) > 20:
                    captured_code = raw_202
                    break
        except Exception:
            pass

        time.sleep(0.6)

    # 6. Exit Study Mode
    try:
        d.set_value(201, json.dumps({"control": "study_exit"}), nowait=True)
        d.set_value(202, False, nowait=True)
    except Exception:
        pass

    # 7. Process Captured Code
    print("\n")
    if captured_code:
        banner("STEP 3: IR CODE CAPTURED & PERSISTED SUCCESSFULLY!")
        print(f"Captured Raw Base64 : {captured_code}")
        print(f"Code Length         : {len(captured_code)} characters")
        
        saved = save_power_key_to_properties(captured_code)
        if saved:
            print("[PERSISTENCE] Successfully saved to local.properties as 'tuya.ir_blaster.power_key_base64'.")
            tts.speak("IR power code captured and saved successfully, sir.", timeout=7.0)

        # 8. Test Dispatch
        banner("STEP 4: LIVE TRANSMISSION TEST TO WAKE PROJECTOR")
        print(">>> Transmitting captured 38kHz infrared pulse to Projector...")
        
        test_payload = json.dumps({
            "control": "send_ir",
            "head": "",
            "key1": captured_code,
            "type": 0,
            "delay": 300
        }, separators=(',', ':'))
        
        try:
            d.set_value(201, test_payload, nowait=True)
            print(">>> [SUCCESS] IR Wake Pulse transmitted over local LAN!")
            tts.speak("Transmitted IR power pulse to the projector, sir. Projector should now illuminate and boot.", timeout=10.0)
        except Exception as e:
            print(f"[ERROR] Failed transmitting IR test pulse: {e}")
            
    else:
        banner("LEARNING TIMED OUT")
        print("[TIMEOUT] No IR signal received during the 20-second window.")
        print("Tip: Make sure the remote is aimed directly at the transparent top dome of the Smart IR Blaster.")
        tts.speak("Learning window timed out without receiving an IR signal, sir.", timeout=7.0)

    banner("LEARNING SESSION CONCLUDED")
    tts.shutdown()


if __name__ == "__main__":
    main()
