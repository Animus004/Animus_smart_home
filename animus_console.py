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

API_BASE_URL = os.getenv("ANIMUS_API_URL", "http://127.0.0.1:8095")


def print_banner():
    print("=" * 65)
    print("   ★ ANIMUS PERSONAL ROOM INTELLIGENCE CONSOLE ★   ")
    print("   Deterministic Physical Room Agent | Phase 2 Production   ")
    print("=" * 65)
    print(f"Connecting to Animus Daemon at: {API_BASE_URL}")
    print("Type your request naturally (e.g. 'Movie time', 'Make it 24', 'What's happening?')")
    print("Commands: 'status' (room summary), 'clear' (reset context), 'exit' / 'quit'\n")


def check_daemon_health() -> bool:
    try:
        resp = requests.get(f"{API_BASE_URL}/api/agent/profile", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def get_room_summary():
    try:
        resp = requests.post(f"{API_BASE_URL}/api/agent/interact", json={"utterance": "What's happening?"}, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("agent_message", "No response from room.")
    except Exception as e:
        return f"Could not fetch room summary: {e}"
    return "Room status unavailable."


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

            if user_input.lower() == "status":
                user_input = "What's happening?"

            # Send turn
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

            print(f"\nAnimus > {agent_msg}")
            if action_taken:
                print(f"         [Verified Physical Action Executed | Intent: {intent}]")
            print()

        except KeyboardInterrupt:
            print("\nExiting Animus Console...")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}\n")


if __name__ == "__main__":
    main()
