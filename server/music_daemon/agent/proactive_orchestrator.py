"""
================================================================================
ANIMUS SMART ROOM — PROACTIVE AMBIENT INITIATIVE ORCHESTRATOR
================================================================================
Autonomous background cognitive monitor. Continuously perceives room conditions,
thermal metrics, time-of-day habits, and user fatigue to generate polite,
non-intrusive proactive vocal suggestions with interactive human follow-up.
================================================================================
"""

from __future__ import annotations
import os
import time
import logging
import threading
import queue
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("music_daemon.agent.proactive_orchestrator")


class ProactiveTriggerCategory:
    THERMAL_CARE = "THERMAL_CARE"
    LATE_NIGHT_FATIGUE = "LATE_NIGHT_FATIGUE"
    WORK_SESSION_FATIGUE = "WORK_SESSION_FATIGUE"
    WORK_SESSION_WRAPUP = "WORK_SESSION_WRAPUP"
    MORNING_GREETING = "MORNING_GREETING"
    IDLE_OPTICAL_PROTECTION = "IDLE_OPTICAL_PROTECTION"
    ROUTINE_ANTICIPATION = "ROUTINE_ANTICIPATION"
    EVENING_DEBRIEF = "EVENING_DEBRIEF"
    ERGONOMIC_50MIN_BREAK = "ERGONOMIC_50MIN_BREAK"


class ProactiveOrchestrator:
    """
    Autonomous Proactive Room Intelligence.
    Monitors PerceptionCollector live telemetry and speaks up when helpful,
    registering interactive follow-up contexts for human conversational response.
    """

    def __init__(
        self,
        tts_service: Optional[Any] = None,
        followup_engine: Optional[Any] = None,
        check_interval: float = 2.0,
        cooldown_seconds: float = 1800.0,  # 30 minute minimum cooldown per category
        enable_speech: bool = True,
        memory_store: Optional[Any] = None,
        decision_engine: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        pc_controller: Optional[Any] = None,
        pc_lock_timeout: Optional[float] = None,      # 60s default absence threshold before locking PC
        dormancy_timeout: Optional[float] = None     # 30m default absence threshold before autonomous dormancy
    ):
        self.tts_service = tts_service
        self.followup_engine = followup_engine
        self.check_interval = check_interval
        self.cooldown_seconds = cooldown_seconds
        self.enable_speech = enable_speech
        self.memory_store = memory_store
        self.decision_engine = decision_engine
        self.event_bus = event_bus
        self.orchestrator = orchestrator
        self.pc_controller = pc_controller
        self.pc_lock_timeout = pc_lock_timeout if pc_lock_timeout is not None else float(os.getenv("ANIMUS_PC_LOCK_TIMEOUT", "60.0"))
        self.dormancy_timeout = dormancy_timeout if dormancy_timeout is not None else float(os.getenv("ANIMUS_DORMANCY_TIMEOUT", "1800.0"))

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_trigger_times: Dict[str, float] = {}
        self._last_global_trigger_time: float = 0.0
        self._pc_active_since: Optional[float] = None
        self._morning_greeted_today: Optional[str] = None
        self._evening_debriefed_today: Optional[str] = None
        self._idle_media_start: Optional[float] = None

        # Event Bus subscription queue for real-time reactivity
        self._event_queue: queue.Queue = queue.Queue(maxsize=100)
        if self.event_bus and hasattr(self.event_bus, "subscribe"):
            try:
                self.event_bus.subscribe(self._event_queue)
            except Exception as e:
                logger.debug(f"[PROACTIVE_EVENT_BUS_SUB_ERR] {e}")

        # Work Mode presence and departure state tracking
        self._music_paused_by_departure: bool = False
        self._music_played_while_present: bool = False
        self._work_session_started_at: Optional[float] = None
        self._time_left_desk: Optional[float] = None
        self._pc_locked_by_departure: bool = False
        self._breaks_taken: int = 0
        self._ergonomic_alerted: bool = False

    def notify_manual_playback_started(self) -> None:
        """Called when user explicitly initiates music playback (via voice, mobile app, or API)."""
        self._music_paused_by_departure = False
        self._music_played_while_present = False
        logger.info("[PROACTIVE_PLAYBACK_NOTIFY] Manual playback started. Departure pause suppressed unless user sits at desk and then leaves.")

    def start(self) -> None:
        """Starts the proactive cognitive background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="AnimusProactiveThread", daemon=True)
        self._thread.start()
        logger.info("[PROACTIVE_ORCHESTRATOR_STARTED] Proactive cognitive loop active.")

    def stop(self) -> None:
        """Stops the proactive cognitive background thread."""
        self._running = False
        if self.event_bus and hasattr(self.event_bus, "unsubscribe") and hasattr(self, "_event_queue"):
            try:
                self.event_bus.unsubscribe(self._event_queue)
            except Exception as e:
                logger.debug(f"[PROACTIVE_EVENT_BUS_UNSUB_ERR] {e}")
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("[PROACTIVE_ORCHESTRATOR_STOPPED] Proactive loop stopped.")

    def _run_loop(self) -> None:
        """Main background loop."""
        while self._running:
            try:
                self.evaluate_proactive_rules()
            except Exception as e:
                logger.error(f"[PROACTIVE_EVAL_ERROR] {e}")

            # Sleep or immediately wake up on presence event arrivals
            try:
                if hasattr(self, "_event_queue") and self._event_queue is not None:
                    evt = self._event_queue.get(timeout=self.check_interval)
                    e_type = str(getattr(evt, "event_type", ""))
                    if "DESK_USER" in e_type:
                        try:
                            self.evaluate_proactive_rules()
                        except Exception as e:
                            logger.error(f"[PROACTIVE_EVENT_EVAL_ERROR] {e}")
                else:
                    time.sleep(self.check_interval)
            except queue.Empty:
                pass
            except Exception:
                time.sleep(self.check_interval)


    # =========================================================================
    # Rule Evaluation Engine
    # =========================================================================

    def evaluate_proactive_rules(self, telemetry: Optional[Dict[str, Any]] = None) -> Optional[Tuple[str, str]]:
        """
        Evaluates all ambient rules against live room telemetry.
        Returns (category, message) if a rule fired, else None.
        """
        if telemetry is None:
            from room_state.perception_collector import get_perception_collector
            collector = get_perception_collector()
            telemetry = collector.get_live_telemetry()

        now = time.time()
        now_dt = datetime.now()
        hour = int(telemetry["hour"]) if "hour" in telemetry else now_dt.hour
        today_str = str(telemetry.get("today_str", now_dt.strftime("%Y-%m-%d")))
        suppress_morning = bool(telemetry.get("suppress_morning", False))

        # Read active mode, PC state, and desk presence from telemetry
        active_mode = str(telemetry.get("active_mode", "")).upper()
        if not active_mode or active_mode == "IDLE":
            if self.orchestrator and hasattr(self.orchestrator, "current_mode"):
                orch_m = str(self.orchestrator.current_mode).upper()
                if orch_m and orch_m != "IDLE":
                    active_mode = orch_m
        is_work_active = (active_mode == "WORK")
        pc_connected = bool(telemetry.get("pc_online", False))
        pc_locked = bool(telemetry.get("pc_locked", False))
        user_idle = float(telemetry.get("user_idle_seconds", 0.0))
        if "desk_present" in telemetry:
            desk_present = bool(telemetry["desk_present"])
        else:
            desk_present = bool(pc_connected and not pc_locked and user_idle < 300)

        # Active desk session is active when in Work Mode OR when PC is connected & unlocked (outside cinema/sleep)
        is_desk_session_active = is_work_active or (pc_connected and not pc_locked and active_mode not in ("MOVIE", "SLEEP"))

        # 1. Check Morning Awakening & Desk Arrival (7:00 AM - 12:00 PM)
        # Presence-gated: triggers when user is visually detected at desk OR active at unlocked PC
        if not suppress_morning and 7 <= hour < 12 and self._morning_greeted_today != today_str:
            is_present = desk_present or (pc_connected and not pc_locked and user_idle < 300)
            if is_present and self._can_trigger(ProactiveTriggerCategory.MORNING_GREETING, now):
                ac_temp = telemetry.get("ac_ambient_temp", 24)
                sg_title = None
                if self.memory_store and hasattr(self.memory_store, "get_current_work_subgoal"):
                    try:
                        curr_sg = self.memory_store.get_current_work_subgoal()
                        if curr_sg:
                            sg_title = curr_sg.get("title")
                    except Exception:
                        pass

                if sg_title:
                    msg = f"Good morning, Sir! The room is at {ac_temp} degrees. Your focus today is '{sg_title}'. Shall I start your morning focus playlist or print your daily plan on the HP Ink Tank 310?"
                else:
                    msg = f"Good morning, Sir! The room is at {ac_temp} degrees. Shall I start your morning playlist and brief you on the day?"

                self._morning_greeted_today = today_str
                self._dispatch_suggestion(
                    ProactiveTriggerCategory.MORNING_GREETING,
                    msg,
                    followup_context="PROACTIVE_MORNING_BRIEFING"
                )
                return ProactiveTriggerCategory.MORNING_GREETING, msg

        # 2. Check Desk Presence, Fatigue & Work Session Lifecycle
        if is_desk_session_active or self._music_paused_by_departure or self._pc_locked_by_departure:
            # Sub-case A: Sir is physically present at the desk
            if desk_present:
                # If newly arrived / resuming work session
                if self._work_session_started_at is None and is_work_active:
                    self._work_session_started_at = now
                self._time_left_desk = None
                self._pc_locked_by_departure = False

                # Auto-Resume Music if previously paused by departure
                if self._music_paused_by_departure:
                    if self.orchestrator:
                        try:
                            if hasattr(self.orchestrator, "safe_resume"):
                                self.orchestrator.safe_resume()
                            elif hasattr(self.orchestrator, "player") and self.orchestrator.player:
                                self.orchestrator.player.resume()
                            logger.info("[PROACTIVE_PRESENCE] Sir returned to desk: Music resumed.")
                        except Exception as e:
                            logger.debug(f"[PROACTIVE_RESUME_ERR] {e}")
                    self._music_paused_by_departure = False

                # Mark music as played while present at desk
                is_currently_playing = False
                if self.orchestrator:
                    if hasattr(self.orchestrator, "current_state") and str(self.orchestrator.current_state).endswith("PLAYING"):
                        is_currently_playing = True
                    elif hasattr(self.orchestrator, "player") and self.orchestrator.player:
                        p_st = self.orchestrator.player.get_status()
                        if p_st.get("status") == "PLAYING" or p_st.get("playback_status") == "PLAYING" or getattr(self.orchestrator.player, "_playback_status", "") == "PLAYING":
                            is_currently_playing = True
                if is_currently_playing:
                    self._music_played_while_present = True

                # 2A. Ergonomic 50-Minute Deep Work Break Nudge (strictly in Work Mode)
                if is_work_active:
                    desk_seated_sec = float(telemetry.get("desk_seated_seconds", 0.0))
                    session_focus_sec = (now - self._work_session_started_at) if self._work_session_started_at else 0.0
                    effective_seated = max(desk_seated_sec, session_focus_sec)

                    if effective_seated >= 3000.0 and not self._ergonomic_alerted:  # 50 minutes continuous focus
                        if self._can_trigger(ProactiveTriggerCategory.ERGONOMIC_50MIN_BREAK, now):
                            self._breaks_taken += 1
                            self._ergonomic_alerted = True
                            curr_sg = self.memory_store.get_current_work_subgoal() if self.memory_store and hasattr(self.memory_store, "get_current_work_subgoal") else None
                            sg_title = curr_sg.get("title") if curr_sg else None
                            focus_topic = "SQL"
                            if sg_title and "SQL" in sg_title.upper():
                                focus_topic = "SQL"
                            elif sg_title:
                                focus_topic = sg_title

                            msg = f"Sir, you have completed 50 minutes of continuous focus on {focus_topic}. Time to stand, stretch, and hydrate."
                            self._dispatch_suggestion(
                                ProactiveTriggerCategory.ERGONOMIC_50MIN_BREAK,
                                msg,
                                followup_context="PROACTIVE_ERGONOMIC_BREAK"
                            )
                            return ProactiveTriggerCategory.ERGONOMIC_50MIN_BREAK, msg

                    # 2B. 90-Minute Prolonged Work Fatigue Evaluation
                    if pc_connected and not pc_locked and user_idle < 600:
                        if self._pc_active_since is None:
                            self._pc_active_since = now
                        elif (now - self._pc_active_since) > 5400:  # 90 minutes
                            if (1 <= hour < 5):
                                if self._can_trigger(ProactiveTriggerCategory.LATE_NIGHT_FATIGUE, now):
                                    msg = "Sir, you've been working late tonight in Work Mode. Shall I dim the lights and play something soothing for you?"
                                    self._dispatch_suggestion(
                                        ProactiveTriggerCategory.LATE_NIGHT_FATIGUE,
                                        msg,
                                        followup_context="PROACTIVE_WORK_FATIGUE_TRANSITION"
                                    )
                                    return ProactiveTriggerCategory.LATE_NIGHT_FATIGUE, msg
                            else:
                                if self._can_trigger(ProactiveTriggerCategory.WORK_SESSION_FATIGUE, now):
                                    curr_sg = self.memory_store.get_current_work_subgoal() if self.memory_store and hasattr(self.memory_store, "get_current_work_subgoal") else None
                                    sg_title = curr_sg.get("title") if curr_sg else None
                                    if sg_title:
                                        msg = f"Sir, you've been focused in Work Mode on '{sg_title}' for a while. Shall I dim the lights and play something soothing for a quick break?"
                                    else:
                                        msg = "Sir, you've been focused in Work Mode for a while. Shall I dim the lights and play something soothing for a quick break?"
                                    self._dispatch_suggestion(
                                        ProactiveTriggerCategory.WORK_SESSION_FATIGUE,
                                        msg,
                                        followup_context="PROACTIVE_WORK_FATIGUE_TRANSITION"
                                    )
                                    return ProactiveTriggerCategory.WORK_SESSION_FATIGUE, msg
                    else:
                        self._pc_active_since = None
                else:
                    self._pc_active_since = None

            # Sub-case B: Sir is NOT present at the desk (stepped away / absent)
            else:
                # Work Session Wrap-Up detection on PC lock after prolonged work session
                if is_work_active and self._pc_active_since and (now - self._pc_active_since) > 3600 and pc_locked:
                    if self._can_trigger(ProactiveTriggerCategory.WORK_SESSION_WRAPUP, now):
                        self._pc_active_since = None
                        msg = "It looks like you're wrapping up work for now, Sir. Shall I switch the room to relax mode?"
                        self._dispatch_suggestion(
                            ProactiveTriggerCategory.WORK_SESSION_WRAPUP,
                            msg,
                            followup_context="PROACTIVE_WORK_WRAPUP"
                        )
                        return ProactiveTriggerCategory.WORK_SESSION_WRAPUP, msg

                # Sir physically stood up / left desk: reset ergonomic alert flag for next sprint
                self._ergonomic_alerted = False

                if self._time_left_desk is None:
                    # Anchor to vision last_seen_timestamp if fresh (< 120s ago), else now
                    v_last = float(telemetry.get("last_seen_timestamp", 0.0))
                    if v_last > 0.0 and (now - v_last) < 120.0:
                        self._time_left_desk = v_last
                    else:
                        self._time_left_desk = now

                away_duration = now - self._time_left_desk

                # 1. At 20s absence: Soft-pause active work/desk music (only if played while Sir was at desk)
                if away_duration >= 20.0 and not self._music_paused_by_departure and self._music_played_while_present:
                    is_playing = False
                    if self.orchestrator:
                        if hasattr(self.orchestrator, "current_state") and str(self.orchestrator.current_state).endswith("PLAYING"):
                            is_playing = True
                        if hasattr(self.orchestrator, "player") and self.orchestrator.player:
                            p_st = self.orchestrator.player.get_status()
                            if p_st.get("status") == "PLAYING" or p_st.get("playback_status") == "PLAYING" or getattr(self.orchestrator.player, "_playback_status", "") == "PLAYING":
                                is_playing = True

                    if is_playing:
                        try:
                            if hasattr(self.orchestrator, "safe_pause"):
                                self.orchestrator.safe_pause()
                            elif self.orchestrator.player:
                                self.orchestrator.player.pause()
                            self._music_paused_by_departure = True
                            self._music_played_while_present = False
                            logger.info(f"[PROACTIVE_DEPARTURE] Sir stepped away (>= 20s, away={away_duration:.1f}s): Music paused.")
                        except Exception as e:
                            logger.debug(f"[PROACTIVE_PAUSE_ERR] {e}")

                # 2. At absence threshold (60s default): Lock Windows workstation for privacy
                if away_duration >= self.pc_lock_timeout and not self._pc_locked_by_departure:
                    if self.pc_controller and hasattr(self.pc_controller, "lock_workstation"):
                        try:
                            self.pc_controller.lock_workstation()
                            self._pc_locked_by_departure = True
                            logger.info(f"[PROACTIVE_DEPARTURE] Sir away >= {self.pc_lock_timeout}s (away={away_duration:.1f}s): Windows workstation locked.")
                        except Exception as e:
                            logger.debug(f"[PROACTIVE_LOCK_ERR] {e}")

                # 3. At dormancy timeout: Autonomous Work Dormancy Timeout (strictly in Work Mode)
                if is_work_active and away_duration >= self.dormancy_timeout:
                    logger.info(f"[PROACTIVE_WORK_DORMANCY] Sir away >= {self.dormancy_timeout}s in Work Mode. Triggering Autonomous Work Dormancy.")

                    # a. Save open files (Ctrl+S)
                    if self.pc_controller and hasattr(self.pc_controller, "send_save_keystrokes"):
                        try:
                            self.pc_controller.send_save_keystrokes()
                        except Exception as e:
                            logger.error(f"[PROACTIVE_DORMANCY_SAVE_ERR] {e}")

                    # b. Record session in SQLite (strictly excluding the dormancy absence)
                    true_work_end = self._time_left_desk or now
                    started_at = self._work_session_started_at or true_work_end
                    duration_sec = max(0.0, true_work_end - started_at)

                    if self.memory_store and hasattr(self.memory_store, "record_work_session"):
                        try:
                            curr_sg = self.memory_store.get_current_work_subgoal() if hasattr(self.memory_store, "get_current_work_subgoal") else None
                            sg_title = curr_sg.get("title") if curr_sg else "Deep Work Focus"
                            self.memory_store.record_work_session(
                                session_duration_seconds=duration_sec,
                                subgoal_title=sg_title,
                                exit_reason="AUTONOMOUS_DORMANCY_TIMEOUT"
                            )
                            logger.info(f"[PROACTIVE_DORMANCY_RECORD] Recorded work session: {duration_sec:.1f}s (excluding absence).")
                        except Exception as e:
                            logger.error(f"[PROACTIVE_DORMANCY_DB_ERR] {e}")

                    # c. Auto-transition room mode to IDLE
                    if self.orchestrator and hasattr(self.orchestrator, "set_active_mode"):
                        self.orchestrator.set_active_mode("IDLE")

                    # d. Reset work state
                    self._work_session_started_at = None
                    self._time_left_desk = None
                    self._music_paused_by_departure = False
                    self._pc_locked_by_departure = False
                    self._pc_active_since = None
                    self._ergonomic_alerted = False

                    # e. Dispatch typed event WORK_SESSION_AUTO_DORMANT
                    if self.event_bus and hasattr(self.event_bus, "publish"):
                        try:
                            self.event_bus.publish("WORK_SESSION_AUTO_DORMANT", {
                                "duration_seconds": duration_sec,
                                "started_at": started_at,
                                "ended_at": true_work_end,
                                "timestamp": now
                            })
                        except Exception as e:
                            logger.debug(f"[PROACTIVE_EVENTBUS_ERR] {e}")

                    msg = f"Sir, work mode has timed out after {int(self.dormancy_timeout // 60)} minutes of absence. Your files have been saved and your session recorded."
                    return ProactiveTriggerCategory.WORK_SESSION_WRAPUP, msg

        else:
            # STRICT ISOLATION: Outside Work Mode, clear all work-tracking state
            # Walking away in Relax, Movie, Sleep, Casual, Gaming, or Idle mode does NOT pause music or lock PC.
            self._work_session_started_at = None
            self._time_left_desk = None
            self._music_paused_by_departure = False
            self._pc_locked_by_departure = False
            self._pc_active_since = None
            self._ergonomic_alerted = False

        # 3. Check Thermal Discomfort
        ambient_temp = telemetry.get("ac_ambient_temp")
        ac_power = telemetry.get("ac_power", False)
        if ambient_temp is not None:
            # Overheating rule (ambient >= 28°C while AC is off)
            if ambient_temp >= 28 and not ac_power:
                if self._can_trigger(ProactiveTriggerCategory.THERMAL_CARE, now):
                    msg = f"Sir, the room is getting quite warm at {ambient_temp} degrees. Shall I turn on the AC to 24?"
                    self._dispatch_suggestion(
                        ProactiveTriggerCategory.THERMAL_CARE,
                        msg,
                        followup_context="PROACTIVE_THERMAL_CARE"
                    )
                    return ProactiveTriggerCategory.THERMAL_CARE, msg

            # Overchilling rule (ambient <= 19°C while AC is running)
            if ambient_temp <= 19 and ac_power:
                if self._can_trigger(ProactiveTriggerCategory.THERMAL_CARE, now):
                    msg = f"Sir, it's getting chilly in here ({ambient_temp} degrees). Would you like me to raise the AC temperature?"
                    self._dispatch_suggestion(
                        ProactiveTriggerCategory.THERMAL_CARE,
                        msg,
                        followup_context="PROACTIVE_THERMAL_CARE"
                    )
                    return ProactiveTriggerCategory.THERMAL_CARE, msg

        # 4. Check Idle Optical Protection (Projector ON but idle > 20 min)
        proj_on = telemetry.get("projector_power", False)
        media_playing = telemetry.get("media_playing", False)
        if proj_on and not media_playing:
            if self._idle_media_start is None:
                self._idle_media_start = now
            elif (now - self._idle_media_start) > 1200:  # 20 minutes idle
                if self._can_trigger(ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION, now):
                    msg = "Sir, the projector has been idle for 20 minutes. Would you like me to put it into standby to protect the optical lamp?"
                    self._dispatch_suggestion(
                        ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION,
                        msg,
                        followup_context="PROACTIVE_IDLE_OPTICAL"
                    )
                    return ProactiveTriggerCategory.IDLE_OPTICAL_PROTECTION, msg
        else:
            self._idle_media_start = None

        # 5. Check Routine Anticipation (e.g. Guitar Practice around 5:30 PM)
        if self.memory_store and hasattr(self.memory_store, "get_all_structured_memories"):
            try:
                routines = self.memory_store.get_all_structured_memories(memory_type="routine")
                guitar_routine = next((r for r in routines if "guitar" in str(r.get("subject", "")).lower() or "guitar" in str(r.get("value", "")).lower()), None)
                if guitar_routine and hour == 17:
                    is_present = (pc_connected and not pc_locked and user_idle < 600)
                    if is_present and self._can_trigger(ProactiveTriggerCategory.ROUTINE_ANTICIPATION, now):
                        msg = "It's 5:30 PM, Sir. Time for your guitar practice routine, or are you continuing with your study?"
                        self._dispatch_suggestion(
                            ProactiveTriggerCategory.ROUTINE_ANTICIPATION,
                            msg,
                            followup_context="PROACTIVE_ROUTINE_GUITAR"
                        )
                        return ProactiveTriggerCategory.ROUTINE_ANTICIPATION, msg
            except Exception as e:
                logger.debug(f"[ROUTINE_ANTICIPATION_EVAL_ERR] {e}")

        # 6. Check Evening Debrief & Wrap-Up Routine (18:00 - 23:00)
        if 18 <= hour < 23 and self._evening_debriefed_today != today_str:
            is_present = desk_present or (pc_connected and not pc_locked and user_idle < 600)
            if is_present and self._can_trigger(ProactiveTriggerCategory.EVENING_DEBRIEF, now):
                msg = "Good evening, Sir. You've completed today's focus session. Shall I print tomorrow's checklist on the HP Ink Tank 310, and cue your 5:30 PM guitar practice session?"
                self._evening_debriefed_today = today_str
                self._dispatch_suggestion(
                    ProactiveTriggerCategory.EVENING_DEBRIEF,
                    msg,
                    followup_context="PROACTIVE_EVENING_DEBRIEF"
                )
                return ProactiveTriggerCategory.EVENING_DEBRIEF, msg

        return None

    def _can_trigger(self, category: str, now: float) -> bool:
        """Checks cooldown invariants."""
        # Global cooldown prevents immediate back-to-back suggestions across any category
        if (now - self._last_global_trigger_time) < min(self.cooldown_seconds, 60.0):
            return False
        last_t = self._last_trigger_times.get(category, 0.0)
        return (now - last_t) >= self.cooldown_seconds

    def _dispatch_suggestion(
        self,
        category: str,
        message: str,
        followup_context: Optional[str] = None
    ) -> None:
        """Records trigger timestamp, stages conversational follow-up, and speaks message politely."""
        now = time.time()
        self._last_trigger_times[category] = now
        self._last_global_trigger_time = now
        logger.info(f"[PROACTIVE_TRIGGER] {category} ➔ {message}")

        # 1. Stage in AgentDecisionEngine for direct PC Chat / Mobile Interact / Voice resolution
        if self.decision_engine and hasattr(self.decision_engine, "set_pending_proactive_followup"):
            try:
                self.decision_engine.set_pending_proactive_followup(
                    category=category,
                    followup_context=followup_context or category,
                    message=message,
                    metadata={"category": category, "prompt": message}
                )
            except Exception as e:
                logger.error(f"[PROACTIVE_DECISION_ENGINE_STAGING_ERROR] {e}")

        # 2. Publish to AgentEventBus for real-time mobile / websocket broadcast
        if self.event_bus and hasattr(self.event_bus, "publish"):
            try:
                from event_bus import AgentEvent, AgentEventType, AgentEventPriority
                self.event_bus.publish(AgentEvent(
                    event_type=AgentEventType.AGENT_PROACTIVE_MESSAGE,
                    priority=AgentEventPriority.NORMAL,
                    message=message,
                    payload={"category": category, "prompt": message, "followup_context": followup_context}
                ))
            except Exception as e:
                logger.debug(f"[PROACTIVE_EVENTBUS_BROADCAST_ERROR] {e}")

        # 3. Stage in legacy followup engine for backward compatibility
        if followup_context and self.followup_engine:
            try:
                self.followup_engine.set_pending_followup(
                    followup_context,
                    metadata={"category": category, "prompt": message}
                )
            except Exception as e:
                logger.error(f"[PROACTIVE_FOLLOWUP_ERROR] {e}")

        # 4. Speak aloud via TTS if speech is enabled
        if self.enable_speech and self.tts_service:
            try:
                self.tts_service.speak(message)
            except Exception as e:
                logger.error(f"[PROACTIVE_TTS_ERROR] {e}")


# Global singleton instance
_global_proactive: Optional[ProactiveOrchestrator] = None


def get_proactive_orchestrator(
    tts_service: Optional[Any] = None,
    followup_engine: Optional[Any] = None,
    memory_store: Optional[Any] = None,
    decision_engine: Optional[Any] = None,
    event_bus: Optional[Any] = None,
    orchestrator: Optional[Any] = None,
    pc_controller: Optional[Any] = None
) -> ProactiveOrchestrator:
    """Returns or initializes the global ProactiveOrchestrator singleton."""
    global _global_proactive
    if _global_proactive is None:
        _global_proactive = ProactiveOrchestrator(
            tts_service=tts_service,
            followup_engine=followup_engine,
            memory_store=memory_store,
            decision_engine=decision_engine,
            event_bus=event_bus,
            orchestrator=orchestrator,
            pc_controller=pc_controller
        )
    else:
        if tts_service and not _global_proactive.tts_service:
            _global_proactive.tts_service = tts_service
        if followup_engine and not _global_proactive.followup_engine:
            _global_proactive.followup_engine = followup_engine
        if memory_store and not _global_proactive.memory_store:
            _global_proactive.memory_store = memory_store
        if decision_engine and not _global_proactive.decision_engine:
            _global_proactive.decision_engine = decision_engine
        if event_bus and not _global_proactive.event_bus:
            _global_proactive.event_bus = event_bus
        if orchestrator and not _global_proactive.orchestrator:
            _global_proactive.orchestrator = orchestrator
        if pc_controller and not _global_proactive.pc_controller:
            _global_proactive.pc_controller = pc_controller
    return _global_proactive

