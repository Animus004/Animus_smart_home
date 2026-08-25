# Phase F.1 Agent Intelligence & Intent Resolution Design

## Executive Summary

Phase F.1 designs and deploys the intelligent cognitive agent layer of Animus. By sitting cleanly above the existing Phase E.8.2/E.8.3 physical orchestration pipeline, the agent resolves human natural-language intent, manages follow-up clarification turns, generates readback-backed conversational feedback, synthesizes daily briefings, and introspects capabilities.

---

## 1. End-to-End Cognitive Architecture Pipeline

```
                    USER
                      │
                      ▼
              Natural Language
                      │
                      ▼
          ┌───────────────────────┐
          │   PERSONAL AGENT F.1  │
          │                       │
          │ User Model            │
          │ Memory (9 Categories) │
          │ Intent Resolution     │
          │ Mood / Vibe           │
          │ Follow-up Engine      │
          │ Task / Reminder       │
          │ Capability Awareness  │
          │ Feedback Generator    │
          └───────────┬───────────┘
                      │
              "What does Sayan
               actually want?"
                      │
          ┌───────────▼───────────┐
          │  FOLLOW-UP IF NEEDED  │
          └───────────┬───────────┘
                      │
                      ▼
               Resolved Intent
                      │
                      ▼
             Existing E.8.x
              Orchestration
                      │
          ┌───────────▼───────────┐
          │ ContextEngine         │
          │ Gemini Planner        │
          │ PlanValidator         │
          │ PlanExecutor          │
          └───────────┬───────────┘
                      │
                      ▼
               REAL HARDWARE
                      │
                      ▼
              PHYSICAL READBACK
                      │
                      ▼
              Agent Feedback
                      │
             ┌────────┴────────┐
             ▼                 ▼
          Response         Bookkeeping
                              │
                       Memory / Tasks /
                       Reminders / State
```

---

## 2. 6-Tier Intent Classification Engine (`agent.intent_resolver.IntentResolver`)

Every user turn is classified into one of 6 mutually exclusive intent categories:

```
┌─────────────────────────────────┬────────────────────────────────────────────────────────────┐
│ Intent Category                 │ Agent Action & Dispatch Behavior                           │
├─────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ 1. CLEAR_EXECUTABLE             │ Direct translation to plan -> validation -> hardware       │
│ 2. CLEAR_WITH_MISSING_NON_CRIT  │ Perform deterministic room prep + ask for missing param    │
│ 3. AMBIGUOUS_REQUIRES_FOLLOW_UP │ Ask single clarification question BEFORE executing         │
│ 4. UNSUPPORTED_CAPABILITY       │ Explain capability limitation honestly without hallucinating│
│ 5. UNSAFE_NOT_AUTHORIZED        │ Fail closed immediately with clear safety reasoning        │
│ 6. INFORMATIONAL_ONLY           │ Answer query (Daily brief, tasks, capabilities, weather)   │
└─────────────────────────────────┴────────────────────────────────────────────────────────────┘
```

### Controlled Mood / Vibe Intent Vocabulary (`agent.models.MoodVibe`)
Controlled vocabulary: `RELAX`, `FOCUS`, `ENTERTAINMENT`, `MOVIE`, `MUSIC`, `WORK`, `SLEEP`, `WAKE_UP`, `SOCIAL`, `QUIET`.

- **Probabilistic Synthesis**: Mood/vibe is treated as contextual and non-medical. The agent combines user utterance + room state + time of day + active tasks + user preferences.

---

## 3. Follow-Up Question Engine (`agent.followup_engine.FollowUpEngine`)

### Principles:
1. **Never ask for information determinable from RoomState**: If projector power, HDMI source, or soundbar route is known, do not ask the user about them.
2. **Single-Question Focus**: Ask only one question at a time to reduce uncertainty systematically.
3. **Conversational Multi-Turn Resolution**:
   - **Turn 1 (User)**: *"Put on something relaxing."*
   - **Turn 1 (Agent)**: *"Want some music, a movie, or just a quiet room, buddy?"*
   - **Turn 2 (User)**: *"Music."*
   - **Turn 2 (Agent)**: Resolves to `PLAY_RELAXING_MUSIC` on LG Soundbar $\to$ Dispatches plan $\to$ Verifies readback $\to$ *"Playing relaxing music on the soundbar, buddy."*

---

## 4. Truthful Agent Feedback Engine (`agent.feedback.AgentFeedbackGenerator`)

The feedback generator translates `ExecutionResult` and physical readbacks into human-like responses:

- **Full Success**: *"All set, buddy — I've prepared the projector, Fire TV, and the soundbar routed to Fire TV."*
- **Idempotent Skip**: *"Everything is already set up and ready, buddy."*
- **Partial Execution**: *"I got the projector and Fire TV ready, buddy, but the soundbar didn't respond as expected."*
- **Safety / Rejection**: *"I couldn't execute that, buddy: Requested temperature 45°C is outside safe physical hardware bounds [16, 30]."*

---

## 5. Daily Brief Engine (`agent.daily_brief.DailyBriefEngine`)

Synthesizes structured daily briefings:
1. **Greeting**: *"Good morning, buddy! Here's your briefing for today:"*
2. **Core Priorities**: Work session after 11:00 AM, SQL learning practice, Guitar practice session at ~17:00.
3. **Pending Tasks**: Top pending items from `TaskManager`.
4. **Scheduled Reminders**: Active time-scheduled reminders.
5. **Local Weather**: PIN 741235 weather summary.
6. **Motivation Tune**: Offer to start morning motivation music.

---

## 6. Capability Awareness Engine (`agent.capability_awareness.CapabilityAwarenessEngine`)

Dynamically reflects the `UnifiedCapabilityRegistry`:
- **Supported Capabilities Query** (*"What can you control?"*):
  - Hardware: Projector, Fire TV 4K Max, LG Soundbar, PC Audio, Tuya AC.
  - Streaming: YouTube, Netflix, Prime Video, Apple TV.
  - Automation: Movie Mode, Work Mode, Morning Motivation, Audio Ownership Routing.
  - Assistant: Task Management, Scheduled Reminders, Daily Briefings.
- **Unsupported Capabilities Query** (*"Turn on the bedroom fan"*):
  - *"I can't control the fan yet, buddy. I can control the Projector, Fire TV, LG Soundbar, PC Audio, and AC."*

---

## 7. REST API Integration (`main.py`)

| Method | Path | Description |
|:---|:---|:---|
| `POST` | `/api/agent/interact` | Primary natural-language conversational interaction endpoint |
| `GET` | `/api/agent/brief` | Generates a fresh morning or daily briefing |
| `GET` | `/api/agent/profile` | Returns the authoritative UserProfile |
| `POST` | `/api/agent/profile` | Updates user profile and preferences |
| `GET` | `/api/agent/tasks` | Lists active or completed tasks |
| `POST` | `/api/agent/tasks` | Creates a new task in the agent task store |
| `POST` | `/api/agent/tasks/{task_id}/complete` | Marks a task as completed |
| `GET` | `/api/agent/memory` | Returns 9-category structured memory summary |
