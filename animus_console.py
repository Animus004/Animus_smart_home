"""
Animus Interactive Smart Room Console.
Dedicated real-time terminal interface for natural language interaction,
room status introspection, and voice-style multi-turn dialogue with Animus.
"""

import sys
import os
import time
import requests

# Add server/music_daemon to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "server", "music_daemon")))

from datetime import datetime

API_BASE_URL = os.getenv("ANIMUS_API_URL", "http://127.0.0.1:8095")


def print_banner():
    now_str = datetime.now().astimezone().strftime("%A, %d %B %Y, %I:%M %p (%Z)")
    print("=" * 68)
    print("      ★ ANIMUS COGNITIVE SMART ROOM ORCHESTRATOR CONSOLE ★      ")
    print("   Agent-Centric Cognition | Local Qwen 4B + Gemini Hybrid Cloud   ")
    print("=" * 68)
    print(f"Current Local Time: {now_str}")
    print(f"Connecting to Animus Daemon at: {API_BASE_URL}")
    print("Type your request naturally (e.g. 'Movie time', 'What are my active goals?', 'Make it 22')")
    print("Special Commands: 'goals' (active tasks), 'memory' (facts), 'status', 'clear', 'exit'\n")


def check_daemon_health() -> bool:
    try:
        resp = requests.get(f"{API_BASE_URL}/api/agent/profile", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def main():
    print_banner()

    is_online = check_daemon_health()
    if not is_online:
        print("[WARNING] Animus daemon not detected on port 8095.")
        print("          Starting in standalone embedded mode...\n")
        try:
            from agent.core import AnimusPersonalAgent
            agent = AnimusPersonalAgent()
            print("[ONLINE] Standalone AnimusPersonalAgent initialized successfully!\n")
            use_embedded = True
        except Exception as e:
            print(f"[ERROR] Could not load embedded agent: {e}")
            print("Please run `python server/music_daemon/main.py` first.")
            return
    else:
        print("[ONLINE] Connected to live Animus Daemon!\n")
        use_embedded = False

    while True:
        try:
            user_input = input("You > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("\nGoodbye, buddy!")
                break

            if user_input.lower() == "clear":
                if use_embedded:
                    agent.context_buffer.clear_history()
                    agent.conversation_engine.clear_history()
                print("[CONTEXT] Conversation history cleared.\n")
                continue

            if user_input.lower() in ("time", "/time"):
                now_str = datetime.now().astimezone().strftime("%A, %d %B %Y, %I:%M:%S %p (%Z)")
                print(f"[TIME] {now_str}\n")
                continue

            if user_input.lower() in ("goals", "/goals", "goal", "/goal"):
                from agent.long_term_memory import get_long_term_memory
                lt_mem = get_long_term_memory()
                active = lt_mem.get_active_goal()
                if active:
                    print(f"\n[ACTIVE GOAL] {active['title']} (Status: {active['status']})")
                    for sg in active.get("subgoals", []):
                        mark = "[✓]" if sg.get("completed") else ("[→]" if sg.get("is_current") else "[ ]")
                        print(f"  {mark} {sg.get('title', '')}")
                    print()
                else:
                    print("\n[GOALS] No active continuous goal. Give Animus an objective!\n")
                continue

            if user_input.lower() in ("memory", "/memory"):
                from agent.long_term_memory import get_long_term_memory
                facts = get_long_term_memory().get_all_facts()
                print("\n[EPITEMIC MEMORY FACTS]")
                for k, v in list(facts.items())[:12]:
                    print(f"  • {k}: {v}")
                print()
                continue

            if user_input.lower() == "status":
                user_input = "What's happening in the room right now?"

            # Send turn
            t0 = time.time()
            if use_embedded:
                resp = agent.interact(user_input)
                agent_msg = resp.agent_message
                action_taken = resp.action_taken
                intent = resp.understood_intent
            else:
                r = requests.post(f"{API_BASE_URL}/api/agent/interact", json={"utterance": user_input}, timeout=120.0)
                if r.status_code == 200:
                    data = r.json()
                    agent_msg = data.get("agent_message", "")
                    action_taken = data.get("action_taken", False)
                    intent = data.get("understood_intent", "")
                else:
                    print(f"[ERROR] HTTP {r.status_code}: {r.text}")
                    continue

            dur = round(time.time() - t0, 2)
            print(f"\nAnimus > {agent_msg}")
            if action_taken:
                print(f"         [Physical Execution Verified | Intent: {intent} | Latency: {dur}s]")
            else:
                print(f"         [Response Latency: {dur}s]")
            print()

        except KeyboardInterrupt:
            print("\nExiting Animus Console...")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()

