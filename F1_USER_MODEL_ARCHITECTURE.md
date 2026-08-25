# Phase F.1 User Model & Agent Memory Architecture

## Executive Summary

Phase F.1 establishes the foundational **User Model** and **Agent Memory Taxonomy** for the Animus Personal Agent. Building additively on top of the physically validated Phase E.8.2/E.8.3 smart-room orchestration pipeline, Phase F.1 equips Animus with deep user understanding, behavioral routine tracking, 9-tier memory taxonomy, AC semantic independence, and native task/reminder bookkeeping.

---

## 1. Architectural Principles & Safety Invariants

1. **Decoupled Agent vs. Hardware Pipeline**:
   - **Personal Agent Layer (Phase F.1)**: Determines *what the human actually wants*, maintains memory, tracks routines, asks follow-up questions when ambiguous, provides conversational feedback, and manages tasks.
   - **Orchestration Pipeline (Phase E.8.x)**: Translates resolved intent into structured plans, validates physical safety bounds, checks preconditions, executes minimal necessary hardware steps via idempotency, and performs physical readback verification.
2. **Zero Modification to Hardware Safety Contracts**:
   - The existing `RoomStateAggregator`, `AudioContextResolver`, `ContextEngine`, `GeminiPlannerClient`, `PlanValidator`, `PlanExecutor`, and physical device drivers remain authoritative and 100% backward compatible.
3. **Epistemological Integrity & Zero State Fabrication**:
   - Unpolled or unreachable telemetry remains strictly `UNKNOWN`.
   - Agent assumptions are never silently converted into permanent facts without explicit user confirmation.

---

## 2. Authoritative User Profile (`agent.models.UserProfile`)

### 2.1 Identity & Conversational Addressing
- **Name**: Sayan Halder
- **Preferred Address**: `"buddy"`
- **Rule**: The agent addresses the user naturally as *"buddy"* without repetitive robotic spamming on every sentence.
- **Location PIN**: `741235` (used strictly for legitimate environmental and weather queries).
- **Privacy Mode**: `STANDARD_SAFEGUARDS` (least-privilege, standard platform security preserved).

### 2.2 Daily Behavioral Routines (`agent.models.DailyRoutines`)
The agent maintains structured behavioral hints rather than rigid automations:

```
[ Wake Up ]
    │
    ▼
[ Morning Briefing ] ───► Priorities, Tasks, Reminders, Weather, Motivation Tune
    │
    ▼
[ Work / SQL Learning ] ───► Begins after 11:00 AM; quiet hours enforced
    │
    ▼
[ Lunch Transition ] ───► Conversational trigger ("I had lunch") -> Suggest guitar / SQL / rest
    │
    ▼
[ Guitar Practice ] ───► Preferred around 17:00 or after lunch; duplicate reminder prevention
    │
    ▼
[ Entertainment / Relax ] ───► Projector + Fire TV + LG Soundbar; streaming services
    │
    ▼
[ Good Night ] ───► Summary of completed/pending tasks; sleep-friendly environment
```

- **Lunch-Completion Trigger**: When the user says *"I had lunch"*, *"Just had lunch"*, *"I have lunch"*, or *"finished lunch"*, Animus recognizes this as a natural routine transition point. It contextually offers guitar practice or SQL continuation without forcing actions.
- **Night Routine**: *"Good night"* summarizes pending items and tomorrow's commitments. Devices are **never** automatically shut down unless explicitly configured.

---

## 3. Explicit Thermal & AC Semantics

To prevent erroneous commands (e.g. setting AC to 30°C upon entering work mode), Phase F.1 introduces an explicit semantic distinction across 5 dimensions:

| Semantic Dimension | Definition | Default Value |
|---|---|---|
| **Preferred AC Setpoint** | Stated configuration setpoint for AC hardware when active | `24°C` (bounded [16, 30]) |
| **Comfort Preference** | Subjective thermal feeling & operating mode | `COOL` (COOL, AUTO, DRY, FAN) |
| **Current Ambient Temperature** | Real-time physical sensor / cloud telemetry | Observed dynamically |
| **Work-Mode AC Policy** | Environmental automation behavior during work hours | `MAINTAIN_COMFORT` |
| **Explicit AC Command** | Natural language user instruction (e.g. *"Set AC to 22"*) | **Highest Precedence** |

### AC Subsystem Independence Contract
- **AC is an independent controllable subsystem**: AC adjustments are not inherently coupled to Movie Mode or Work Mode.
- If the user says *"Let's watch something"*, AC is left untouched unless an explicit temperature change was requested.
- If AC is currently `OFF` when entering work mode, the policy leaves it `OFF` rather than forcefully powering it on.

---

## 4. 9-Tier Agent Memory Taxonomy (`agent.models.MemoryCategory`)

Every discrete piece of knowledge in Animus is categorized into a strict 9-tier taxonomy:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         9-TIER MEMORY TAXONOMY                           │
├─────────────────────────┬────────────────────────────────────────────────┤
│ Category                │ Description & Examples                         │
├─────────────────────────┼────────────────────────────────────────────────┤
│ STABLE_USER_FACT        │ Immutable facts (Name: Sayan, PIN: 741235)     │
│ USER_PREFERENCE         │ Stated preferences (Preferred streaming apps)  │
│ ROUTINE                 │ Behavioral routine hints (Work after 11 AM)    │
│ TASK                    │ Discrete goals (Practice SQL queries)          │
│ REMINDER                │ Time-triggered alerts (Guitar at 17:00)        │
│ TEMPORARY_CONTEXT       │ Transient state with TTL (YouTube running)     │
│ OBSERVATION             │ Empirical event (User said "I had lunch")      │
│ AGENT_ASSUMPTION        │ Unconfirmed hypotheses (User wants music)      │
│ USER_CONFIRMED_DECISION │ Verified user decisions (Chose Netflix)        │
└─────────────────────────┴────────────────────────────────────────────────┘
```

### Critical Epistemological Invariant
`AGENT_ASSUMPTION` items have `user_confirmed = False`. They are **never** promoted to facts or executed as permanent preferences without explicit user confirmation (`confirm_decision`).

---

## 5. Task & Reminder Bookkeeping Model (`agent.models.Task`, `agent.models.Reminder`)

### Task Schema
- `id`: Unique identifier (e.g. UUID).
- `title`: Task title (e.g. *"Learn and practice SQL"*).
- `description`: Optional detailed description.
- `created_at` / `completed_at`: Unix epoch timestamps.
- `priority`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- `status`: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `MISSED`, `SNOOZED`.
- `category`: `WORK`, `LEARNING`, `PERSONAL`, `GENERAL`.
- `source`: `USER_REQUESTED`, `ROUTINE_SUGGESTED`, `SYSTEM_DEFAULT`.

### Reminder Deduplication
If a guitar reminder was already triggered, acknowledged, or completed today, subsequent reminders for the same day are suppressed to prevent spam.

---

## 6. Persistence & Storage (`agent.persistence.AgentPersistence`)

- **Storage Location**: `server/music_daemon/secrets/user_agent_state.json`
- **Data Encapsulated**: User profile, active memory items, tasks, and active reminders.
- **Safety**: Atomic write with automatic fallback to clean defaults if the file does not exist or is corrupted.
