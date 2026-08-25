# ANIMUS SMART ROOM — PHASE 2 STAGE 2 FROZEN BASELINE

**Freeze Date:** August 25, 2026  
**Status:** SEALED & FROZEN  
**Test Suite Verification:** 534 Passed, 17 Skipped, 0 Failed  

---

## 1. Core Architectural Axioms & Epistemic Invariants

1. **Epistemic Invariant (Truth Over Expectation):**  
   Animus **never** treats an intended/requested action as equivalent to a completed physical action.  
   - `StateDelta.verified_value` is populated strictly from authoritative post-action physical readback telemetry (`exec_res.steps[i].readback_result`).
   - If physical telemetry is mismatched, missing, or timed out, `execution_success` is forced to `False` and `physical_verification` is set to `FAILED`.
   - The feedback engine strictly reports factual failure rather than fabricating a "Done" response.

2. **Cache-Bypass Verification:**  
   - Normal room-state consumers query `RoomStateAggregator.get_room_state()` with normal 3.0s caching.
   - Post-command verification polling in `PlanExecutor._verify_physical_readback()` invokes `_get_fresh_room_state(time.time(), force_refresh=True)`, ensuring 100% live hardware polling across the network.

3. **Deterministic Safety Boundary (PlanValidator Gate):**  
   - The LLM/agent reasoning layer is strictly forbidden from directly mutating hardware.
   - Authoritative execution chain:
     $$\text{Natural Language} \longrightarrow \text{IntentResolver} \longrightarrow \text{PlanValidator} \longrightarrow \text{PlanExecutor} \longrightarrow \text{Transport} \longrightarrow \text{Physical Readback} \longrightarrow \text{AgentFeedback}$$

---

## 2. Sealed Physical Hardware & Transports

### A. Projector Subsystem (Zebronics PixaPlay 25)
- **Primary Power Wake:** Tuya Cloud IR Blaster (`POST /v1.0/infrareds/{infrared_id}/send-keys`)
  - IR Device ID: `d7c9483cd505ac54eauidb`
  - Remote ID: `d718f75c8f82c9145954hl`
  - Learned Key Code: `1787666042`
  - Transmission Status: Physically verified wake from cold standby.
- **ADB Command & Telemetry Transport:** `192.168.1.11:5555` (TCP)
  - Navigation, HDMI 1 switching, brightness, media keys, and live wakefulness readback.

### B. Air Conditioner Subsystem (Inverter Split AC)
- **Device ID:** `76776532a4e57c0a2ca4`
- **LAN IP & Port:** `192.168.1.4:6668`
- **Primary Transport:** Local Tuya Protocol 3.3 (AES-128-ECB).
- **Fallback Transport:** Tuya Cloud OpenAPI (`POST /v1.0/devices/76776532a4e57c0a2ca4/commands`).
- **Telemetry Readback:** Verified live readback via `temp_set` / `switch` / `temp_current`.
- **Precondition Rule:** `ac.power == True` is strictly enforced before setting temperature; rejected truthfully if off.

### C. Soundbar & Audio Subsystem (LG SNC4R)
- **Bluetooth A2DP Auto-Reconnect:** [`BluetoothAudioHelper.ensure_audio_endpoint()`](file:///d:/AnimusSmartRoom/server/music_daemon/bluetooth_helper.py)
- **WASAPI Device ID:** `wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}` (`Speakers (LG SNC4R(79))`)
- **Shared Audio Architecture:**
  - Music playback (`player.py`) and Room TTS (`tts_service.py`) both use `ensure_audio_endpoint()` to automatically wake/reconnect the soundbar before passing `--audio-device=wasapi/{...}` to `mpv.com`.
  - Automatic music ducking to 30% volume during speech and full restoration after speech.

### D. Fire TV Subsystem
- **ADB Target:** `192.168.1.5:5555`
- **Capabilities:** Power wake/sleep, navigation, YouTube/Netflix launching, Bluetooth soundbar ownership routing.

---

## 3. Sealed Conversational Intelligence & Agent State

- **Context Buffer & Multi-Turn Retention:** [`ConversationContextBuffer`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/context_buffer.py) tracks interaction history, recent state deltas, active multi-turn flows, and pending follow-ups.
- **Action Introspection:** Full support for *"What did you just change?"* and *"Why did you do that?"*.
- **Action Rollback & Replay:** Full support for *"Actually, never mind. Put it back."* (Undo) and *"Do that again"* (Replay).
- **First-Class Cancellation:** Safe intent cancellation (*"Never mind"*, *"Forget it"*).
- **Semantic Thermal Comfort Reasoning:** Resolves *"I'm freezing"*, *"It's too hot in here"*, *"It's comfortable now"*.

---

## 4. Authoritative Verification Metrics

| Test Suite | Tests Passed | Tests Skipped | Tests Failed |
| :--- | :---: | :---: | :---: |
| `test_phase2_stage1_intelligence.py` | **13** | 0 | 0 |
| `test_phase2_stage2_agent_feedback.py` | **20** | 0 | 0 |
| Full Repository (`server/music_daemon/tests/`) | **534** | **17** | **0** |

---

## 5. Frozen File Registry

- [`server/music_daemon/agent/core.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/core.py)
- [`server/music_daemon/agent/intent_resolver.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/intent_resolver.py)
- [`server/music_daemon/agent/context_buffer.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/context_buffer.py)
- [`server/music_daemon/agent/interaction_result.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/interaction_result.py)
- [`server/music_daemon/agent/feedback.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/feedback.py)
- [`server/music_daemon/planner/executor.py`](file:///d:/AnimusSmartRoom/server/music_daemon/planner/executor.py)
- [`server/music_daemon/planner/validator.py`](file:///d:/AnimusSmartRoom/server/music_daemon/planner/validator.py)
- [`server/music_daemon/room_state/aggregator.py`](file:///d:/AnimusSmartRoom/server/music_daemon/room_state/aggregator.py)
- [`server/music_daemon/tts_service.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tts_service.py)
- [`server/music_daemon/bluetooth_helper.py`](file:///d:/AnimusSmartRoom/server/music_daemon/bluetooth_helper.py)
- [`server/music_daemon/player.py`](file:///d:/AnimusSmartRoom/server/music_daemon/player.py)
- [`server/music_daemon/ac_controller.py`](file:///d:/AnimusSmartRoom/server/music_daemon/ac_controller.py)
- [`server/music_daemon/projector_controller.py`](file:///d:/AnimusSmartRoom/server/music_daemon/projector_controller.py)
- [`server/music_daemon/main.py`](file:///d:/AnimusSmartRoom/server/music_daemon/main.py)
