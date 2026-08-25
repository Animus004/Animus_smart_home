# PHASE 2 STAGE 6 FROZEN BASELINE
**Authoritative Architectural State & Regression Baseline**
*Timestamp: 2026-08-26 | Phase 2 Stages 1–6 Fully Verified*

---

## 1. System Status & Verification Baseline

- **Total Automated Tests**: **777 passed, 17 skipped (hardware-bound), 0 failed**.
- **Stage 6 Test Battery**: **91 passed, 0 failed** in [`server/music_daemon/tests/test_phase2_stage6_long_horizon_intelligence.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tests/test_phase2_stage6_long_horizon_intelligence.py).
- **Stage 5 Test Battery**: **83 passed, 0 failed** in [`server/music_daemon/tests/test_phase2_stage5_behavioral_intelligence.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tests/test_phase2_stage5_behavioral_intelligence.py).
- **Stage 4 Test Battery**: **80 passed, 0 failed** in [`server/music_daemon/tests/test_phase2_stage4_task_planning.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tests/test_phase2_stage4_task_planning.py).
- **Stage 3 Test Battery**: **72 passed, 0 failed** in [`server/music_daemon/tests/test_phase2_stage3_context_memory.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tests/test_phase2_stage3_context_memory.py).
- **Stage 2 Test Battery**: **82 passed, 0 failed** in [`server/music_daemon/tests/test_phase2_stage2_agent_feedback.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tests/test_phase2_stage2_agent_feedback.py).
- **Stage 1 Test Battery**: **73 passed, 0 failed** in [`server/music_daemon/tests/test_phase2_stage1_intelligence.py`](file:///d:/AnimusSmartRoom/server/music_daemon/tests/test_phase2_stage1_intelligence.py).
- **Audio Routing & Hardware Baseline**: **100% passed** across all unit and integration tests.

---

## 2. Invariant Rules (Permanent Ground Rules)

1. **Scheduler Execution Pipeline**:
   - The scheduler is **never a secondary execution engine**. It contains zero direct hardware execution logic.
   - All scheduled tasks route strictly:
     $$\text{Scheduler} \longrightarrow \text{GeminiStructuredPlan} \longrightarrow \text{PlanValidator} \longrightarrow \text{PlanExecutor} \longrightarrow \text{Physical Hardware} \longrightarrow \text{Readback}$$

2. **Event Bus Cascade Boundedness**:
   - `RoomEventBus` enforces sliding deduplication (`1.0s`) and cascade depth limiting (`max_cascade_depth = 4`) to prevent runaway recursive loops between room state monitors and recovery handlers.

3. **Deferred Intent Is Not Deferred Truth**:
   - Scheduled tasks and timers never modify physical room state prior to trigger time.
   - Upon trigger, tasks evaluate stale intent and live physical idempotency before execution.

4. **Epistemic Invariant on Persistence**:
   - Persistence never stores "physical truth". It stores intent, goals, schedules, preferences, and history.
   - On system restart:
     $$\text{Persisted State} \longrightarrow \text{Fresh Physical Telemetry Readback} \longrightarrow \text{Reconciliation} \longrightarrow \text{Current Truth}$$

5. **Authoritative Soundbar Ownership**:
   - When `soundbar.current_owner == FIRE_TV`, Fire TV owns Bluetooth audio.
   - TTS and recovery routines must **never** attempt to reclaim PC Bluetooth or modify Windows audio endpoints.

6. **Bounded Autonomous Recovery**:
   - Autonomous fault recovery is strictly bounded to `max_attempts = 1`. No infinite retry loops.

---

## 3. Core Component Manifest

| Component | Path | Responsibility |
| :--- | :--- | :--- |
| `RoomEvent` / `RoomEventType` | [`server/music_daemon/agent/room_events.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/room_events.py) | Immutable, strongly typed room event model (22 classifications). |
| `RoomEventBus` | [`server/music_daemon/agent/event_bus.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/event_bus.py) | In-process deterministic event broker with deduplication and cascade limit. |
| `RoomStateMonitor` | [`server/music_daemon/agent/room_monitor.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/room_monitor.py) | Continuous telemetry monitor; detects external changes & mode divergences. |
| `RoomScheduler` | [`server/music_daemon/agent/scheduler.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/scheduler.py) | Delayed task and reminder scheduling with stale-intent validation. |
| `LongHorizonGoalManager` | [`server/music_daemon/agent/long_horizon_goals.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/long_horizon_goals.py) | Multi-step goal lifecycle (pause/resume/supersede/lease expiration). |
| `BehavioralProfileManager` | [`server/music_daemon/agent/behavioral_profile.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/behavioral_profile.py) | Bounded preference storage (`max_preferences=20`) with provenance. |
| `SituationEngine` | [`server/music_daemon/agent/situation_engine.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/situation_engine.py) | High-level situation assessment across 13 operational states. |
| `AnimusPersonalAgent` | [`server/music_daemon/agent/core.py`](file:///d:/AnimusSmartRoom/server/music_daemon/agent/core.py) | Central orchestrator unifying all intelligence and hardware engines. |

---

*Baseline frozen and preserved. All 777 regression tests are green.*
