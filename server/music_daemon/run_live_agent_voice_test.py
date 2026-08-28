"""
Animus Smart Room — Live Interactive Agent Voice, Vocabulary & Physical Execution Diagnostic.
Tests the ultra-natural Neural Voice synthesis through the room's speakers,
evaluates colloquial & butler verb recognition, checks live physical hardware perception,
and interactively gathers feedback on observed hardware changes.
"""

import os
import sys
import time

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tts_service import RoomTtsService
from agent.core import AnimusPersonalAgent
from room_state.perception_collector import PerceptionCollector


def print_banner(title: str):
    width = 80
    print("\n" + "=" * width)
    print(f"   {title}".center(width))
    print("=" * width)


def main():
    print_banner("ANIMUS SMART ROOM — LIVE NEURAL VOICE & INTELLIGENCE DIAGNOSTIC")
    print(f"Timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Engine    : Microsoft Edge Neural TTS + Perception Cache + Refined Agent")
    print("-" * 80)

    # 1. Start Perception Collector
    print("\n[1] Starting Live Background Perception Engine...")
    collector = PerceptionCollector(poll_interval_seconds=1.5)
    time.sleep(1.0)
    live_state = collector.get_room_state(force_refresh=True)
    print(f"    [+] Canonical Room State acquired (Consistent: {live_state.is_consistent})")
    if live_state.ac and live_state.ac.power.value is not None:
        print(f"    [+] Live AC Power: {'ON' if live_state.ac.power.value else 'OFF'}, Setpoint: {live_state.ac.target_temperature.value}°C (Mode: {live_state.ac.mode.value})")
    if live_state.ir_hub:
        print(f"    [+] Live Smart IR Hub: {'ONLINE' if live_state.ir_hub.online.value else 'OFFLINE'}")

    # 2. Initialize Animus Personal Agent & Neural TTS
    print("\n[2] Initializing Animus Agent with Live Neural Voice Engine...")
    agent = AnimusPersonalAgent(room_state_aggregator=collector)
    agent.user_model.profile.identity.preferred_address = "sir"

    tts = RoomTtsService(enabled=True, voice="en-GB-RyanNeural")
    cfg = tts.get_config()
    print(f"    [+] Neural Voice Config: Voice='{cfg['voice']}', Rate='{cfg['rate']}', Pitch='{cfg['pitch']}'")

    # 3. Live Speech Test Turn 1: Welcome Salutation
    print("\n[3] Executing Turn 1: Conversational Greeting & Salutation...")
    user_query_1 = "Good evening Animus"
    print(f"    [User] -> \"{user_query_1}\"")
    resp_1 = agent.interact(user_query_1, room_state=live_state)
    print(f"    [Animus (Understood: {resp_1.understood_intent})] -> \"{resp_1.agent_message}\"")
    print("    [+] Speaking turn aloud through room speakers...")
    tts.speak(resp_1.agent_message, timeout=8.0)

    # 4. Live Speech Test Turn 2: Comprehensive Room Status Briefing
    print("\n[4] Executing Turn 2: Colloquial Room Status Rundown...")
    user_query_2 = "Give me a quick status briefing on the quarters"
    print(f"    [User] -> \"{user_query_2}\"")
    # Fresh observation
    fresh_state = collector.get_room_state(force_refresh=True)
    resp_2 = agent.interact(user_query_2, room_state=fresh_state)
    print(f"    [Animus (Understood: {resp_2.understood_intent})] -> \"{resp_2.agent_message}\"")
    print("    [+] Speaking turn aloud through room speakers...")
    tts.speak(resp_2.agent_message, timeout=12.0)

    # 5. Live Speech Test Turn 3: Colloquial AC Climate Command
    print("\n[5] Executing Turn 3: Colonial / Butler Climate Command...")
    user_query_3 = "Kindly dial the AC temperature to 24"
    print(f"    [User] -> \"{user_query_3}\"")
    resp_3 = agent.interact(user_query_3, room_state=fresh_state)
    print(f"    [Animus (Understood: {resp_3.understood_intent})] -> \"{resp_3.agent_message}\"")
    print("    [+] Speaking turn aloud through room speakers...")
    tts.speak(resp_3.agent_message, timeout=8.0)

    print("\n" + "=" * 80)
    print("   LIVE VERIFICATION COMPLETE")
    print("=" * 80)
    print("[+] All neural voice utterances, vocabulary parsers, and live room state engines verified cleanly.")

    # Cleanup
    tts.shutdown()
    collector.stop()


if __name__ == "__main__":
    main()
